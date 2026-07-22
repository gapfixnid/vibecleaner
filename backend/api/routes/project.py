import os
import zipfile
import json
import logging
import tempfile
from copy import deepcopy
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Form
from PIL import Image
from ..dependencies import get_container
from ...core.models import MangaPage
from ...core.version import APP_NAME
from ...core.container import AppContainer
from ...infrastructure.image.encoding import encode_preview_jpeg_bytes
from ...infrastructure.image.loading import load_cv_image
from ...infrastructure.storage.project_schema import (
    ProjectSchemaError,
    create_project_metadata,
    normalize_project_metadata,
)
from ..use_cases.page_crud import get_pages_response

router = APIRouter()
logger = logging.getLogger(APP_NAME)

PROJECT_CACHE_WARM_RADIUS = 2


def _warm_inpainted_response_caches(state, page_indices: list[int]) -> None:
    for page_idx in page_indices:
        with state.lock:
            if page_idx < 0 or page_idx >= len(state.pages):
                continue
            page = state.pages[page_idx]
            if page.inpainted_image is None:
                continue
            inpainted_image = page.inpainted_image.copy()

        try:
            preview_bytes = encode_preview_jpeg_bytes(inpainted_image)
        except Exception as exc:
            logger.warning("Failed to warm inpainted preview cache for page %s: %s", page_idx, exc)
            continue

        with state.lock:
            if page_idx < 0 or page_idx >= len(state.pages):
                continue
            page = state.pages[page_idx]
            if page.inpainted_image is None:
                continue
            page._preview_inpainted_bytes = preview_bytes


def _start_project_cache_warmup(cache_tasks, state, page_count: int, current_index: int) -> None:
    if page_count <= 0:
        return

    warm_indices = []
    for distance in range(PROJECT_CACHE_WARM_RADIUS + 1):
        for idx in (current_index - distance, current_index + distance):
            if 0 <= idx < page_count and idx not in warm_indices:
                warm_indices.append(idx)

    cache_tasks.submit(lambda: _warm_inpainted_response_caches(state, warm_indices))

@router.post("/api/project/new")
def new_project(container: AppContainer = Depends(get_container)):
    """Reset the in-memory project: clear all pages and selection.

    Used by the "New Project" action. The frontend is responsible for warning
    about unsaved changes before calling this; the backend simply clears state.
    """
    state = container.project_state
    with state.lock:
        state.pages = []
        state.current_page_idx = -1
        state.project_extensions = {}
        state.touch()
    return {"page_count": 0, "current_index": -1}


def _append_imported_pages(state, loaded_pages: list[MangaPage]) -> dict:
    """Append unique pages and select a single new import atomically."""
    with state.lock:
        before_count = len(state.pages)
        existing_paths = {page.file_path for page in state.pages}
        added = [page for page in loaded_pages if page.file_path not in existing_paths]
        state.pages.extend(added)

        if before_count == 0 and added:
            state.current_page_idx = 0
        elif len(added) == 1:
            state.current_page_idx = before_count
        elif state.current_page_idx < 0 and state.pages:
            state.current_page_idx = 0

        if added:
            state.touch()
        return {
            "page_count": len(state.pages),
            "current_index": state.current_page_idx,
            "added": len(added),
        }


def _import_result(state, loaded_pages: list[MangaPage]) -> dict:
    """Return the committed page snapshot with the import mutation.

    Keeping the mutation and its UI snapshot in one HTTP response avoids a
    startup/restart race where the import succeeds but a follow-up /api/pages
    request is rejected by the desktop backend manager.
    """
    with state.lock:
        result = _append_imported_pages(state, loaded_pages)
        result.update(get_pages_response(state))
        return result

@router.post("/api/project/open-directory")
def open_directory(directory: str = Form(...), container: AppContainer = Depends(get_container)):
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="Invalid directory path")
    
    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = []
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts:
            files.append(os.path.join(directory, f))
    
    files.sort()
    
    if not files:
        raise HTTPException(status_code=400, detail="No valid images found in the specified directory")
    
    loaded_pages = []
    for f in files:
        try:
            with Image.open(f) as img:
                w, h = img.size
            page = MangaPage(file_path=f, cv_image=None)
            page._width = w
            page._height = h
            page._loaded = False
            loaded_pages.append(page)
        except Exception:
            continue

    return _import_result(container.project_state, loaded_pages)

@router.post("/api/project/open-files")
def open_files(files_json: str = Form(...), container: AppContainer = Depends(get_container)):
    try:
        files = json.loads(files_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid files list format")
        
    if not files:
        raise HTTPException(status_code=400, detail="No files selected")
        
    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    valid_files = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts and os.path.isfile(f):
            valid_files.append(f)
            
    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid images selected")
        
    loaded_pages = []
    for f in valid_files:
        try:
            with Image.open(f) as img:
                w, h = img.size
            page = MangaPage(file_path=f, cv_image=None)
            page._width = w
            page._height = h
            page._loaded = False
            loaded_pages.append(page)
        except Exception:
            continue

    return _import_result(container.project_state, loaded_pages)

@router.post("/api/project/save")
def save_project(
    file_path: str = Form(...),
    selected_indices: str = Form(""),
    container: AppContainer = Depends(get_container),
):
    state = container.project_state
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")

    parent = os.path.dirname(os.path.abspath(file_path))
    if not os.path.isdir(parent):
        raise HTTPException(status_code=400, detail=f"Target directory does not exist: {parent}")

    # Parse the sidebar multi-selection (frontend-only state) passed by the client.
    try:
        parsed_selected = json.loads(selected_indices) if selected_indices else []
        if not isinstance(parsed_selected, list):
            parsed_selected = []
    except Exception:
        parsed_selected = []

    temporary_project_path = None
    try:
        # Capture a lightweight, consistent snapshot under the lock: image
        # references (not copies) + serialized bubble metadata. Image bytes are
        # encoded later, outside the lock and one page at a time, so peak memory
        # stays bounded instead of loading/copying every page simultaneously.
        with state.lock:
            if not state.pages:
                raise HTTPException(status_code=400, detail="No project pages loaded")

            page_total = len(state.pages)
            current_index = state.current_page_idx
            project_extensions = deepcopy(state.project_extensions)

            snapshot = []
            for source in state.pages:
                snapshot.append({
                    "page_id": source.page_id,
                    "file_path": source.file_path,
                    "cv_image": source.cv_image,  # may be None if lazily unloaded
                    "inpainted_image": source.inpainted_image,
                    "bubble_counter": source.bubble_counter,
                    "display_name": source.display_name,
                    "status": source.status,
                    "problems": list(source.problems),
                    "bubbles": [bubble.to_project_dict() for bubble in source.bubbles],
                    "project_extensions": deepcopy(source.project_extensions),
                })

        # Normalize selection against the captured page count.
        selected_clean = sorted({
            int(i)
            for i in parsed_selected
            if isinstance(i, (int, float)) and 0 <= int(i) < page_total
        })
        if not (0 <= current_index < page_total):
            current_index = 0


        temporary_fd, temporary_project_path = tempfile.mkstemp(
            prefix=".vibecleaner-project-",
            suffix=".tmp",
            dir=parent,
        )
        os.close(temporary_fd)
        with zipfile.ZipFile(temporary_project_path, "w", zipfile.ZIP_DEFLATED) as zf:
            pages_meta = []
            for idx, snap in enumerate(snapshot):
                # Resolve the original image without retaining it: prefer the
                # already-loaded array, otherwise read from disk only for the
                # duration of this iteration (kept lazy pages stay unloaded).
                cv_image = snap["cv_image"]
                read_from_disk = cv_image is None or getattr(cv_image, "size", 0) == 0
                if read_from_disk:
                    cv_image = load_cv_image(snap["file_path"])
                    if cv_image is None:
                        logger.error("Failed to load image while saving project: %s", snap["file_path"])
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to load a project image",
                        )

                orig_name = f"page_{idx}_orig.png"
                success, orig_buf = cv2.imencode(".png", cv_image)
                if not success:
                    raise ValueError(f"Failed to encode original image for page {idx}")
                zf.writestr(f"images/{orig_name}", orig_buf.tobytes())
                # Free per-page buffers eagerly to keep peak memory bounded.
                del orig_buf
                if read_from_disk:
                    del cv_image

                inpaint_name = None
                inpainted = snap["inpainted_image"]
                if inpainted is not None:
                    inpaint_name = f"page_{idx}_inpaint.png"
                    success, inp_buf = cv2.imencode(".png", inpainted)
                    if success:
                        zf.writestr(f"images/{inpaint_name}", inp_buf.tobytes())
                    del inp_buf

                pages_meta.append({
                    **snap["project_extensions"],
                    "page_id": snap["page_id"],
                    "original_file_path": os.path.basename(snap["file_path"]),
                    "file_name": orig_name,
                    "inpaint_file_name": inpaint_name,
                    "bubble_counter": snap["bubble_counter"],
                    "display_name": snap["display_name"],
                    "status": snap["status"],
                    "problems": snap["problems"],
                    "bubbles": snap["bubbles"],
                })

            project_meta = create_project_metadata(
                pages=pages_meta,
                current_index=current_index,
                selected_indices=selected_clean,
                extensions=project_extensions,
            )
            zf.writestr("project.json", json.dumps(project_meta, ensure_ascii=False, indent=4))

        if not zipfile.is_zipfile(temporary_project_path):
            raise ValueError("Project archive verification failed")
        with zipfile.ZipFile(temporary_project_path, "r") as verification_archive:
            corrupt_member = verification_archive.testzip()
            if corrupt_member is not None:
                raise ValueError(f"Project archive member is corrupt: {corrupt_member}")
            normalize_project_metadata(
                json.loads(verification_archive.read("project.json").decode("utf-8"))
            )
        os.replace(temporary_project_path, file_path)
        temporary_project_path = None
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Save project failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temporary_project_path and os.path.exists(temporary_project_path):
            try:
                os.unlink(temporary_project_path)
            except OSError:
                logger.warning("Failed to remove temporary project file: %s", temporary_project_path)

@router.post("/api/project/load")
def load_project(file_path: str = Form(...), container: AppContainer = Depends(get_container)):
    state = container.project_state
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")
            
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Project file not found")
        
    try:
        loaded_pages = []
        restored_current = 0
        restored_selected: list[int] = []
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, "r") as zf:
                project_json_data = zf.read("project.json").decode("utf-8")
                project_meta = normalize_project_metadata(json.loads(project_json_data))
                restored_current = project_meta.get("current_index", 0)
                restored_selected = project_meta.get("selected_indices", []) or []
                
                for page_meta in project_meta.get("pages", []):
                    # Load original image
                    orig_bytes = zf.read(f"images/{page_meta['file_name']}")
                    nparr = np.frombuffer(orig_bytes, np.uint8)
                    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    inpainted_image = None
                    if page_meta.get("inpaint_file_name"):
                        try:
                            inp_bytes = zf.read(f"images/{page_meta['inpaint_file_name']}")
                            inp_nparr = np.frombuffer(inp_bytes, np.uint8)
                            inpainted_image = cv2.imdecode(inp_nparr, cv2.IMREAD_COLOR)
                        except Exception:
                            pass
                            
                    page = MangaPage.from_project_dict(page_meta, cv_img)
                    page.inpainted_image = inpainted_image
                    
                    # Set dimensions
                    page._width = cv_img.shape[1]
                    page._height = cv_img.shape[0]
                    page._loaded = True
                    
                    loaded_pages.append(page)
        else:
            # Legacy JSON load
            with open(file_path, "r", encoding="utf-8") as f:
                project_meta = normalize_project_metadata(json.load(f))
            restored_current = project_meta.get("current_index", 0)
            restored_selected = project_meta.get("selected_indices", []) or []
            base_dir = os.path.dirname(file_path)
            for page_meta in project_meta.get("pages", []):
                p_path = page_meta.get("original_file_path") or page_meta.get("file_path")
                if p_path and not os.path.isabs(p_path):
                    p_path = os.path.join(base_dir, p_path)
                if not p_path or not os.path.exists(p_path):
                    continue
                # We lazy load legacy json pages as well!
                try:
                    with Image.open(p_path) as img:
                        w, h = img.size
                    # Lazy page: image is loaded from disk on demand, so don't
                    # allocate a full-size placeholder array.
                    page = MangaPage.from_project_dict(page_meta, None)
                    page._width = w
                    page._height = h
                    page._loaded = False
                    loaded_pages.append(page)
                except Exception:
                    continue
                
        if not loaded_pages:
            raise ValueError("No valid pages loaded from project")

        # Clamp restored selection against the actual loaded page count.
        n = len(loaded_pages)
        try:
            restored_current = int(restored_current)
        except (TypeError, ValueError):
            restored_current = 0
        if not (0 <= restored_current < n):
            restored_current = 0
        selected_clean = sorted({
            int(i)
            for i in restored_selected
            if isinstance(i, (int, float)) and 0 <= int(i) < n
        })
        if not selected_clean:
            selected_clean = [restored_current]

        project_known_keys = {
            "format", "schema_version", "app_version", "version",
            "current_index", "selected_indices", "pages",
        }
        project_extensions = {
            key: deepcopy(value)
            for key, value in project_meta.items()
            if key not in project_known_keys
        }

        with state.lock:
            state.pages = loaded_pages
            state.current_page_idx = restored_current
            state.project_extensions = project_extensions
            state.touch()
            page_count = len(state.pages)
            current_index = state.current_page_idx
        _start_project_cache_warmup(container.cache_tasks, state, page_count, current_index)
        return {
            "page_count": page_count,
            "current_index": current_index,
            "selected_indices": selected_clean,
        }

    except ProjectSchemaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Load project failed")
        raise HTTPException(status_code=500, detail=str(e))
