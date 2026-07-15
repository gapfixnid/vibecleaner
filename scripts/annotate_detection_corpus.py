#!/usr/bin/env python3
"""Temporary local tool for drawing detection ground-truth boxes.

This is a benchmark helper, not a product feature. Left-drag a rectangle over
each text region, then use Next/Previous or the keyboard shortcuts to navigate.
Coordinates are stored in the original image pixel space.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageTk

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError as exc:  # pragma: no cover - depends on the local Python build
    raise SystemExit("Tkinter is required for the temporary annotation tool") from exc


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def normalize_box(start: tuple[float, float], end: tuple[float, float]) -> list[int] | None:
    x1, y1 = (round(value) for value in start)
    x2, y2 = (round(value) for value in end)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    if right - left < 2 or bottom - top < 2:
        return None
    return [left, top, right, bottom]


def image_files(image_dir: Path) -> list[Path]:
    return sorted(
        path for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


class AnnotationApp:
    def __init__(self, image_dir: Path, output_path: Path) -> None:
        self.image_dir = image_dir.resolve()
        self.output_path = output_path.resolve()
        self.paths = image_files(self.image_dir)
        if not self.paths:
            raise ValueError(f"No supported images found in {self.image_dir}")

        self.cases: dict[str, dict[str, Any]] = self._load_existing()
        self.index = 0
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.scale = 1.0
        self.offset = (0.0, 0.0)
        self.boxes: list[list[int]] = []
        self.drag_start: tuple[float, float] | None = None
        self.drag_preview: int | None = None

        self.root = tk.Tk()
        self.root.title("Detection Corpus Annotator (temporary)")
        self.root.geometry("1280x900")
        self.root.minsize(800, 600)
        self.category = tk.StringVar(value="uncategorized")
        self.status = tk.StringVar()
        self._build_ui()
        self.root.bind("<Right>", lambda _event: self.next_image())
        self.root.bind("<Left>", lambda _event: self.previous_image())
        self.root.bind("u", lambda _event: self.undo())
        self.root.bind("c", lambda _event: self.clear_boxes())
        self.root.bind("s", lambda _event: self.save())
        self.root.bind("<Control-s>", lambda _event: self.save())
        self.root.bind("<Return>", lambda _event: self.next_image())
        self._load_image()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Previous", command=self.previous_image).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Next", command=self.next_image).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Undo (U)", command=self.undo).pack(side=tk.LEFT, padx=(18, 0))
        ttk.Button(toolbar, text="Clear (C)", command=self.clear_boxes).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save (S)", command=self.save).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(toolbar, text="Category:").pack(side=tk.LEFT, padx=(20, 4))
        ttk.Entry(toolbar, textvariable=self.category, width=24).pack(side=tk.LEFT)
        ttk.Label(toolbar, textvariable=self.status).pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self.root, background="#202124", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<ButtonPress-1>", self._start_box)
        self.canvas.bind("<B1-Motion>", self._drag_box)
        self.canvas.bind("<ButtonRelease-1>", self._finish_box)

        ttk.Label(
            self.root,
            text="Left-drag each text region | U undo | C clear | Enter/Right next | Left previous | S save",
            padding=(8, 0, 8, 8),
        ).pack(fill=tk.X)

    def _load_existing(self) -> dict[str, dict[str, Any]]:
        if not self.output_path.exists():
            return {}
        try:
            payload = json.loads(self.output_path.read_text(encoding="utf-8"))
            cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
            return {
                str(case.get("image_path")): dict(case)
                for case in cases
                if isinstance(case, dict) and case.get("image_path")
            }
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def _relative_path(self, path: Path) -> str:
        return path.relative_to(self.image_dir).as_posix()

    def _load_image(self) -> None:
        path = self.paths[self.index]
        self.image = Image.open(path).convert("RGB")
        key = self._relative_path(path)
        existing = self.cases.get(key, {})
        self.boxes = [list(map(int, box[:4])) for box in existing.get("expected_boxes", [])]
        self.category.set(str(existing.get("category") or "uncategorized"))
        self._render()

    def _render(self) -> None:
        if self.image is None:
            return
        self.root.update_idletasks()
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        width, height = self.image.size
        self.scale = min(canvas_width / width, canvas_height / height)
        display_size = (max(1, round(width * self.scale)), max(1, round(height * self.scale)))
        self.offset = ((canvas_width - display_size[0]) / 2, (canvas_height - display_size[1]) / 2)
        display = self.image.resize(display_size)
        self.photo = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(*self.offset, image=self.photo, anchor=tk.NW, tags="image")
        for box in self.boxes:
            self._draw_box(box)
        self.status.set(
            f"{self.index + 1}/{len(self.paths)}  {self._relative_path(self.paths[self.index])}  boxes={len(self.boxes)}"
        )

    def _draw_box(self, box: list[int], *, preview: bool = False) -> None:
        x1, y1, x2, y2 = box
        ox, oy = self.offset
        self.canvas.create_rectangle(
            ox + x1 * self.scale,
            oy + y1 * self.scale,
            ox + x2 * self.scale,
            oy + y2 * self.scale,
            outline="#39ff88" if not preview else "#ffcc00",
            width=2,
            dash=(5, 3) if preview else None,
        )

    def _canvas_to_image(self, event: tk.Event) -> tuple[float, float]:
        ox, oy = self.offset
        width, height = self.image.size if self.image else (0, 0)
        return (
            max(0.0, min(width, (event.x - ox) / self.scale)),
            max(0.0, min(height, (event.y - oy) / self.scale)),
        )

    def _start_box(self, event: tk.Event) -> None:
        self.drag_start = self._canvas_to_image(event)
        self.drag_preview = None

    def _drag_box(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        if self.drag_preview is not None:
            self.canvas.delete(self.drag_preview)
        current = self._canvas_to_image(event)
        box = normalize_box(self.drag_start, current)
        if box is None:
            return
        x1, y1, x2, y2 = box
        ox, oy = self.offset
        self.drag_preview = self.canvas.create_rectangle(
            ox + x1 * self.scale, oy + y1 * self.scale,
            ox + x2 * self.scale, oy + y2 * self.scale,
            outline="#ffcc00", width=2, dash=(5, 3),
        )

    def _finish_box(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        box = normalize_box(self.drag_start, self._canvas_to_image(event))
        self.drag_start = None
        if self.drag_preview is not None:
            self.canvas.delete(self.drag_preview)
            self.drag_preview = None
        if box is not None:
            self.boxes.append(box)
            self._render()

    def undo(self) -> None:
        if self.boxes:
            self.boxes.pop()
            self._render()

    def clear_boxes(self) -> None:
        self.boxes.clear()
        self._render()

    def _save_current(self) -> None:
        key = self._relative_path(self.paths[self.index])
        self.cases[key] = {
            "case_id": Path(key).stem,
            "category": self.category.get().strip() or "uncategorized",
            "image_path": key,
            "expected_boxes": self.boxes,
        }

    def save(self) -> None:
        self._save_current()
        payload = {
            "schema_version": 1,
            "annotation_metadata": {"tool": "temporary_detection_annotator"},
            "cases": [self.cases.get(self._relative_path(path), {
                "case_id": path.stem,
                "category": "uncategorized",
                "image_path": self._relative_path(path),
                "expected_boxes": [],
            }) for path in self.paths],
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.status.set(f"Saved {self.output_path}")

    def next_image(self) -> None:
        self._save_current()
        if self.index < len(self.paths) - 1:
            self.index += 1
            self._load_image()
        else:
            self.save()
            messagebox.showinfo("Annotation complete", f"Saved corpus to:\n{self.output_path}")

    def previous_image(self) -> None:
        self._save_current()
        if self.index > 0:
            self.index -= 1
            self._load_image()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", type=Path, help="Folder containing local images")
    parser.add_argument("--output", type=Path, required=True, help="Output annotation corpus JSON")
    args = parser.parse_args()
    try:
        AnnotationApp(args.image_dir, args.output).run()
    except (OSError, ValueError) as exc:
        print(f"Annotation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
