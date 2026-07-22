mod backend_client;
mod backend_process;
mod error;
mod image_protocol;

use backend_client::RequestClass;
use backend_process::{BackendManager, BackendSession, BackendStatus};
use error::{BridgeError, CommandResult};
use percent_encoding::{utf8_percent_encode, NON_ALPHANUMERIC};
use std::path::{Path, PathBuf};
use tauri::Manager;

fn encode_path_segment(value: &str, kind: &str) -> CommandResult<String> {
    let forbidden = value.is_empty()
        || value.len() > 128
        || matches!(value, "." | "..")
        || value
            .chars()
            .any(|character| matches!(character, '/' | '\\' | '#' | '?'))
        || value.chars().any(char::is_control);
    if forbidden {
        return Err(BridgeError::new(
            "INVALID_PATH_IDENTIFIER",
            format!("Invalid {kind}."),
            false,
        ));
    }
    Ok(utf8_percent_encode(value, NON_ALPHANUMERIC).to_string())
}

fn page_api_path(page_id: &str, suffix: &str) -> CommandResult<String> {
    Ok(format!(
        "/api/pages/{}{suffix}",
        encode_path_segment(page_id, "page_id")?
    ))
}

fn job_api_path(job_id: &str, suffix: &str) -> CommandResult<String> {
    Ok(format!(
        "/api/jobs/{}{suffix}",
        encode_path_segment(job_id, "job_id")?
    ))
}

fn batch_export_path(output_dir: &Path, ordinal: usize) -> CommandResult<PathBuf> {
    let canonical_dir = std::fs::canonicalize(output_dir).map_err(|error| {
        BridgeError::new(
            "INVALID_EXPORT_DIRECTORY",
            format!("Cannot resolve export directory: {error}"),
            false,
        )
    })?;
    if !canonical_dir.is_dir() {
        return Err(BridgeError::new(
            "INVALID_EXPORT_DIRECTORY",
            "The export destination is not a directory.",
            false,
        ));
    }

    let candidate = canonical_dir.join(format!("page_{:04}.png", ordinal + 1));
    let checked_path = match std::fs::symlink_metadata(&candidate) {
        Ok(_) => std::fs::canonicalize(&candidate).map_err(|error| {
            BridgeError::new(
                "INVALID_EXPORT_PATH",
                format!("Cannot resolve export path: {error}"),
                false,
            )
        })?,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => candidate.clone(),
        Err(error) => {
            return Err(BridgeError::new(
                "INVALID_EXPORT_PATH",
                format!("Cannot inspect export path: {error}"),
                false,
            ))
        }
    };
    if !checked_path.starts_with(&canonical_dir) {
        return Err(BridgeError::new(
            "INVALID_EXPORT_PATH",
            "The export path escapes the selected directory.",
            false,
        ));
    }
    Ok(candidate)
}

async fn forward_get<T: serde::de::DeserializeOwned>(
    session: &BackendSession,
    path: &str,
) -> CommandResult<T> {
    session.ensure_current()?;
    let result = session.client.get_json(path).await;
    session.ensure_current()?;
    result
}

async fn forward_get_class<T: serde::de::DeserializeOwned>(
    session: &BackendSession,
    path: &str,
    class: RequestClass,
) -> CommandResult<T> {
    session.ensure_current()?;
    let result = session.client.get_json_with_class(path, class).await;
    session.ensure_current()?;
    result
}

async fn forward_post<T: serde::de::DeserializeOwned, P: serde::Serialize + ?Sized>(
    session: &BackendSession,
    path: &str,
    payload: &P,
) -> CommandResult<T> {
    session.ensure_current()?;
    let result = session.client.post_json(path, payload).await;
    session.ensure_current()?;
    result
}

async fn forward_empty_post<T: serde::de::DeserializeOwned>(
    session: &BackendSession,
    path: &str,
) -> CommandResult<T> {
    session.ensure_current()?;
    let result = session.client.post_empty(path).await;
    session.ensure_current()?;
    result
}

async fn forward_form<T: serde::de::DeserializeOwned>(
    session: &BackendSession,
    path: &str,
    fields: Vec<(String, String)>,
) -> CommandResult<T> {
    forward_form_class(session, path, fields, RequestClass::Metadata).await
}

async fn forward_form_class<T: serde::de::DeserializeOwned>(
    session: &BackendSession,
    path: &str,
    fields: Vec<(String, String)>,
    class: RequestClass,
) -> CommandResult<T> {
    session.ensure_current()?;
    let result = session.client.post_form(path, &fields, class).await;
    session.ensure_current()?;
    result
}

#[tauri::command]
fn get_backend_status(manager: tauri::State<'_, BackendManager>) -> BackendStatus {
    manager.status()
}

/// Re-attempt to start the backend (invoked by the in-app error screen).
#[tauri::command]
async fn retry_backend(
    app: tauri::AppHandle,
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<BackendStatus> {
    Ok(manager.restart(app).await)
}

#[tauri::command]
fn select_directory() -> Option<String> {
    rfd::FileDialog::new()
        .set_title("Select Manga Directory")
        .pick_folder()
        .map(|p| p.to_string_lossy().into_owned())
}

#[tauri::command]
fn select_file(title: String, filters: Vec<(String, Vec<String>)>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    for (name, exts) in filters {
        let exts_str: Vec<&str> = exts.iter().map(|s| s.as_str()).collect();
        dialog = dialog.add_filter(&name, &exts_str);
    }
    dialog.pick_file().map(|p| p.to_string_lossy().into_owned())
}

#[tauri::command]
fn select_multiple_files(
    title: String,
    filters: Vec<(String, Vec<String>)>,
) -> Option<Vec<String>> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    for (name, exts) in filters {
        let exts_str: Vec<&str> = exts.iter().map(|s| s.as_str()).collect();
        dialog = dialog.add_filter(&name, &exts_str);
    }
    dialog.pick_files().map(|paths| {
        paths
            .iter()
            .map(|p| p.to_string_lossy().into_owned())
            .collect()
    })
}

#[tauri::command]
fn save_file(
    title: String,
    _default_ext: String,
    filters: Vec<(String, Vec<String>)>,
) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    for (name, exts) in filters {
        let exts_str: Vec<&str> = exts.iter().map(|s| s.as_str()).collect();
        dialog = dialog.add_filter(&name, &exts_str);
    }
    dialog.save_file().map(|p| p.to_string_lossy().into_owned())
}

// --- DTO Commands Implementation (All Async) ---

#[tauri::command]
async fn get_project(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let pages_res: serde_json::Value = forward_get(&session, "/api/pages").await?;
    let settings_res: serde_json::Value = forward_get(&session, "/api/settings").await?;

    let pages = pages_res
        .get("pages")
        .cloned()
        .unwrap_or(serde_json::json!([]));
    let current_index = pages_res
        .get("current_index")
        .and_then(|v| v.as_i64())
        .unwrap_or(0) as usize;

    let pages_dto: Vec<serde_json::Value> = if let Some(arr) = pages.as_array() {
        arr.iter()
            .enumerate()
            .map(|(idx, p)| {
                let page_id = p.get("page_id").cloned().unwrap_or(serde_json::json!(""));
                let filename = p.get("filename").cloned().unwrap_or(serde_json::json!(""));
                let width = p.get("width").cloned().unwrap_or(serde_json::json!(0));
                let height = p.get("height").cloned().unwrap_or(serde_json::json!(0));
                let has_inpaint = p
                    .get("has_inpaint")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let bubble_count = p.get("bubble_count").and_then(|v| v.as_i64()).unwrap_or(0);
                let translated_count = p
                    .get("translated_count")
                    .and_then(|v| v.as_i64())
                    .unwrap_or(0);
                let status = p.get("status").cloned().unwrap_or_else(|| {
                    serde_json::json!(if has_inpaint {
                        "ready_for_review"
                    } else {
                        "idle"
                    })
                });
                let problems = p.get("problems").cloned().unwrap_or(serde_json::json!([]));

                serde_json::json!({
                    "id": page_id,
                    "index": idx,
                    "filename": filename,
                    "file_path": "",
                    "width": width,
                    "height": height,
                    "status": status,
                    "has_inpaint": has_inpaint,
                    "bubble_count": bubble_count,
                    "translated_count": translated_count,
                    "bubbles": [],
                    "problems": problems
                })
            })
            .collect()
    } else {
        vec![]
    };

    let current_page_id = pages_dto
        .get(current_index)
        .and_then(|p| p.get("id").and_then(|id| id.as_str()))
        .map(|s| s.to_string());

    session.ensure_current()?;
    Ok(serde_json::json!({
        "id": "current_project",
        "name": "My Project",
        "pages": pages_dto,
        "current_page_id": current_page_id,
        "settings": settings_res
    }))
}

#[tauri::command]
async fn get_page(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    get_page_for_session(&session, page_id).await
}

async fn get_page_for_session(
    session: &BackendSession,
    page_id: String,
) -> CommandResult<serde_json::Value> {
    let pages_res: serde_json::Value = forward_get(session, "/api/pages").await?;
    let pages = pages_res
        .get("pages")
        .cloned()
        .unwrap_or(serde_json::json!([]));

    let page_info = pages
        .as_array()
        .and_then(|arr| {
            arr.iter()
                .find(|p| p.get("page_id").and_then(|id| id.as_str()) == Some(&page_id))
        })
        .cloned()
        .ok_or_else(|| "Page not found".to_string())?;

    let bubbles_path = page_api_path(&page_id, "/bubbles")?;
    let bubbles_res: serde_json::Value = forward_get(session, &bubbles_path).await?;
    let bubbles = bubbles_res
        .get("bubbles")
        .cloned()
        .unwrap_or(serde_json::json!([]));

    let bubbles_dto: Vec<serde_json::Value> = if let Some(arr) = bubbles.as_array() {
        arr.iter()
            .map(|b| {
                let id = b.get("id").and_then(|v| v.as_i64()).unwrap_or(0);
                let x = b.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let y = b.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let w = b.get("width").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let h = b.get("height").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let bubble_box = serde_json::json!({ "x": x, "y": y, "width": w, "height": h });
                let text_box = b
                    .get("text_box")
                    .filter(|v| v.is_object())
                    .cloned()
                    .unwrap_or_else(|| bubble_box.clone());
                let layout_box = b
                    .get("layout_box")
                    .filter(|v| v.is_object())
                    .cloned()
                    .unwrap_or_else(|| text_box.clone());
                let text = b.get("text").and_then(|v| v.as_str()).unwrap_or("");
                let translated = b.get("translated").and_then(|v| v.as_str()).unwrap_or("");
                let font_family = b.get("font_family").and_then(|v| v.as_str()).unwrap_or("");
                let computed_font_family = b
                    .get("computed_font_family")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let font_size = b.get("font_size").and_then(|v| v.as_i64()).unwrap_or(0);
                let font_mode = b
                    .get("font_mode")
                    .and_then(|v| v.as_str())
                    .unwrap_or(if font_size > 0 { "fixed" } else { "auto" });
                let requested_font_size =
                    b.get("requested_font_size").cloned().unwrap_or_else(|| {
                        if font_size > 0 {
                            serde_json::json!(font_size)
                        } else {
                            serde_json::Value::Null
                        }
                    });
                let computed_font_size = b
                    .get("computed_font_size")
                    .and_then(|v| v.as_i64())
                    .unwrap_or(12);
                let bold = b.get("bold").and_then(|v| v.as_bool()).unwrap_or(false);
                let italic = b.get("italic").and_then(|v| v.as_bool()).unwrap_or(false);
                let color = b.get("color").and_then(|v| v.as_str()).unwrap_or("#000000");
                let alignment = b
                    .get("alignment")
                    .and_then(|v| v.as_str())
                    .unwrap_or("center");
                let text_class = b.get("text_class").and_then(|v| v.as_str()).unwrap_or("");
                let lines = b.get("lines").cloned().unwrap_or(serde_json::json!([]));
                let writing_mode = b
                    .get("writing_mode")
                    .and_then(|v| v.as_str())
                    .unwrap_or("horizontal");
                let text_direction = b
                    .get("text_direction")
                    .and_then(|v| v.as_str())
                    .unwrap_or("ltr");
                let justification = b
                    .get("justification")
                    .and_then(|v| v.as_str())
                    .unwrap_or("none");
                let layout_padding = b
                    .get("layout_padding")
                    .cloned()
                    .unwrap_or(serde_json::json!({}));
                let layout_margin = b
                    .get("layout_margin")
                    .cloned()
                    .unwrap_or(serde_json::json!({}));
                let layout_confidence = b
                    .get("layout_confidence")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let layout_reasoning = b
                    .get("layout_reasoning")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let layout_overflow = b
                    .get("layout_overflow")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let status = b.get("status").cloned().unwrap_or_else(|| {
                    serde_json::json!(if translated.is_empty() {
                        "needs_review"
                    } else {
                        "ok"
                    })
                });
                let problems = b.get("problems").cloned().unwrap_or(serde_json::json!([]));
                let edited = b.get("edited").and_then(|v| v.as_bool()).unwrap_or(false);

                serde_json::json!({
                    "id": format!("bubble_{}", id),
                    "bubbleBox": bubble_box,
                    "textBox": text_box,
                    "layoutBox": layout_box,
                    "text": text,
                    "translated": translated,
                    "status": status,
                    "style": {
                        "font_family": font_family,
                        "computed_font_family": computed_font_family,
                        "font_size": font_size,
                        "font_mode": font_mode,
                        "requested_font_size": requested_font_size,
                        "computed_font_size": computed_font_size,
                        "bold": bold,
                        "italic": italic,
                        "color": color,
                        "alignment": alignment
                    },
                    "layout": {
                        "lines": lines,
                        "overflow": layout_overflow,
                        "writing_mode": writing_mode,
                        "text_direction": text_direction,
                        "justification": justification,
                        "padding": layout_padding,
                        "margin": layout_margin,
                        "confidence": layout_confidence,
                        "reasoning": layout_reasoning
                    },
                    "text_class": text_class,
                    "problems": problems,
                    "edited": edited
                })
            })
            .collect()
    } else {
        vec![]
    };

    let width = page_info
        .get("width")
        .cloned()
        .unwrap_or(serde_json::json!(100));
    let height = page_info
        .get("height")
        .cloned()
        .unwrap_or(serde_json::json!(100));
    let filename = page_info
        .get("filename")
        .cloned()
        .unwrap_or(serde_json::json!(""));
    let has_inpaint = page_info
        .get("has_inpaint")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let status = page_info.get("status").cloned().unwrap_or_else(|| {
        serde_json::json!(if has_inpaint {
            "ready_for_review"
        } else {
            "idle"
        })
    });
    let problems = page_info
        .get("problems")
        .cloned()
        .unwrap_or(serde_json::json!([]));

    session.ensure_current()?;
    Ok(serde_json::json!({
        "id": page_id,
        "index": page_info.get("index").cloned().unwrap_or(serde_json::json!(0)),
        "filename": filename,
        "file_path": "",
        "width": width,
        "height": height,
        "status": status,
        "has_inpaint": has_inpaint,
        "bubbles": bubbles_dto,
        "problems": problems
    }))
}

#[tauri::command]
async fn import_images(
    manager: tauri::State<'_, BackendManager>,
    paths: Option<Vec<String>>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let paths_vec = paths.unwrap_or_default();
    let files_json = serde_json::to_string(&paths_vec)
        .map_err(|error| BridgeError::new("BACKEND_INVALID_RESPONSE", error.to_string(), false))?;
    forward_form(
        &session,
        "/api/project/open-files",
        vec![("files_json".to_string(), files_json)],
    )
    .await
}

#[tauri::command]
async fn import_directory(
    manager: tauri::State<'_, BackendManager>,
    directory: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/project/open-directory",
        vec![("directory".to_string(), directory)],
    )
    .await
}

#[tauri::command]
async fn get_pages(manager: tauri::State<'_, BackendManager>) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_get(&session, "/api/pages").await
}

#[tauri::command]
async fn new_project(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_empty_post(&session, "/api/project/new").await
}

#[tauri::command]
async fn load_project(
    manager: tauri::State<'_, BackendManager>,
    file_path: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/project/load",
        vec![("file_path".to_string(), file_path)],
    )
    .await
}

#[tauri::command]
async fn save_project(
    manager: tauri::State<'_, BackendManager>,
    file_path: String,
    selected_indices: Option<Vec<i64>>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let selected_json = serde_json::to_string(&selected_indices.unwrap_or_default())
        .map_err(|e| format!("선택 페이지 직렬화 실패: {e}"))?;
    forward_form(
        &session,
        "/api/project/save",
        vec![
            ("file_path".to_string(), file_path),
            ("selected_indices".to_string(), selected_json),
        ],
    )
    .await
}

fn page_ref_fields(
    index: Option<i64>,
    page_id: Option<String>,
) -> CommandResult<Vec<(String, String)>> {
    if let Some(pid) = page_id.filter(|s| !s.is_empty()) {
        encode_path_segment(&pid, "page_id")?;
        return Ok(vec![("page_id".to_string(), pid)]);
    }
    if let Some(idx) = index {
        return Ok(vec![("index".to_string(), idx.to_string())]);
    }
    Err(BridgeError::new(
        "INVALID_PAGE_REFERENCE",
        "index 또는 page_id가 필요합니다.",
        false,
    ))
}

#[tauri::command]
async fn select_page(
    manager: tauri::State<'_, BackendManager>,
    index: Option<i64>,
    page_id: Option<String>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/pages/select",
        page_ref_fields(index, page_id)?,
    )
    .await
}

#[tauri::command]
async fn duplicate_page(
    manager: tauri::State<'_, BackendManager>,
    index: Option<i64>,
    page_id: Option<String>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/pages/duplicate",
        page_ref_fields(index, page_id)?,
    )
    .await
}

#[tauri::command]
async fn duplicate_pages_batch(
    manager: tauri::State<'_, BackendManager>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let page_ids = page_ids.unwrap_or_default();
    for page_id in &page_ids {
        encode_path_segment(page_id, "page_id")?;
    }
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids,
    });
    forward_post(&session, "/api/pages/duplicate-batch", &payload).await
}

#[tauri::command]
async fn delete_page(
    manager: tauri::State<'_, BackendManager>,
    index: Option<i64>,
    page_id: Option<String>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/pages/delete",
        page_ref_fields(index, page_id)?,
    )
    .await
}

#[tauri::command]
async fn delete_pages_batch(
    manager: tauri::State<'_, BackendManager>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let page_ids = page_ids.unwrap_or_default();
    for page_id in &page_ids {
        encode_path_segment(page_id, "page_id")?;
    }
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids,
    });
    forward_post(&session, "/api/pages/delete-batch", &payload).await
}

#[tauri::command]
async fn reorder_pages(
    manager: tauri::State<'_, BackendManager>,
    from_index: i64,
    to_index: i64,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_form(
        &session,
        "/api/pages/reorder",
        vec![
            ("from_index".to_string(), from_index.to_string()),
            ("to_index".to_string(), to_index.to_string()),
        ],
    )
    .await
}

#[tauri::command]
async fn rename_page(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    name: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let path = page_api_path(&page_id, "/rename")?;
    forward_form(&session, &path, vec![("name".to_string(), name)]).await
}

async fn start_page_job(
    session: &BackendSession,
    page_id: String,
    action: &str,
) -> CommandResult<serde_json::Value> {
    let path = page_api_path(&page_id, &format!("/{action}"))?;
    forward_empty_post(session, &path).await
}

#[tauri::command]
async fn inpaint_page(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    start_page_job(&session, page_id, "inpaint").await
}

#[tauri::command]
async fn translate_all_page(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    start_page_job(&session, page_id, "translate-all").await
}

#[tauri::command]
async fn translate_batch(
    manager: tauri::State<'_, BackendManager>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let page_ids = page_ids.unwrap_or_default();
    for page_id in &page_ids {
        encode_path_segment(page_id, "page_id")?;
    }
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids,
    });
    forward_post(&session, "/api/pages/translate-batch", &payload).await
}

#[tauri::command]
async fn get_job(
    manager: tauri::State<'_, BackendManager>,
    job_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let path = job_api_path(&job_id, "")?;
    forward_get_class(&session, &path, RequestClass::JobPoll).await
}

#[tauri::command]
async fn cancel_job(
    manager: tauri::State<'_, BackendManager>,
    job_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let path = job_api_path(&job_id, "/cancel")?;
    forward_empty_post(&session, &path).await
}

#[tauri::command]
async fn update_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
    patch: serde_json::Value,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);

    let bubbles_path = page_api_path(&page_id, "/bubbles")?;
    let bubbles_res: serde_json::Value = forward_get(&session, &bubbles_path).await?;
    let bubbles = bubbles_res
        .get("bubbles")
        .cloned()
        .unwrap_or(serde_json::json!([]));

    let mut bubbles_arr = bubbles.as_array().ok_or("Invalid bubbles array")?.clone();
    let bubble_index = bubbles_arr
        .iter()
        .position(|b| b.get("id").and_then(|v| v.as_i64()) == Some(id_num))
        .ok_or_else(|| "Bubble not found".to_string())?;

    let mut current_bubble = bubbles_arr
        .get(bubble_index)
        .cloned()
        .ok_or_else(|| "Bubble not found".to_string())?;

    if let Some(bubble_box) = patch.get("bubbleBox") {
        if let Some(x) = bubble_box.get("x") {
            current_bubble["x"] = x.clone();
        }
        if let Some(y) = bubble_box.get("y") {
            current_bubble["y"] = y.clone();
        }
        if let Some(width) = bubble_box.get("width") {
            current_bubble["width"] = width.clone();
        }
        if let Some(height) = bubble_box.get("height") {
            current_bubble["height"] = height.clone();
        }
    }

    if let Some(layout_box) = patch.get("layoutBox").or_else(|| patch.get("textBox")) {
        if patch.get("bubbleBox").is_none() {
            if let Some(x) = layout_box.get("x") {
                current_bubble["x"] = x.clone();
            }
            if let Some(y) = layout_box.get("y") {
                current_bubble["y"] = y.clone();
            }
            if let Some(width) = layout_box.get("width") {
                current_bubble["width"] = width.clone();
            }
            if let Some(height) = layout_box.get("height") {
                current_bubble["height"] = height.clone();
            }
        }
    }

    if let Some(style) = patch.get("style") {
        if let Some(font_family) = style.get("font_family") {
            current_bubble["font_family"] = font_family.clone();
        }
        if let Some(font_size) = style.get("font_size") {
            current_bubble["font_size"] = font_size.clone();
        }
        if let Some(bold) = style.get("bold") {
            current_bubble["bold"] = bold.clone();
        }
        if let Some(italic) = style.get("italic") {
            current_bubble["italic"] = italic.clone();
        }
        if let Some(color) = style.get("color") {
            current_bubble["color"] = color.clone();
        }
        if let Some(alignment) = style.get("alignment") {
            current_bubble["alignment"] = alignment.clone();
        }
    }

    if let Some(translated) = patch.get("translated") {
        current_bubble["translated"] = translated.clone();
    }

    if let Some(text) = patch.get("text") {
        current_bubble["text"] = text.clone();
    }

    bubbles_arr[bubble_index] = current_bubble;

    let _: serde_json::Value = forward_post(&session, &bubbles_path, &bubbles_arr).await?;

    let page_dto = get_page_for_session(&session, page_id).await?;
    let bubbles_arr = page_dto
        .get("bubbles")
        .and_then(|v| v.as_array())
        .ok_or("Invalid bubbles array")?;
    let updated_bubble = bubbles_arr
        .iter()
        .find(|b| b.get("id").and_then(|id| id.as_str()) == Some(&bubble_id))
        .cloned()
        .ok_or_else(|| "Updated bubble not found".to_string())?;

    session.ensure_current()?;
    Ok(updated_bubble)
}

#[tauri::command]
async fn update_bubbles(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubbles: serde_json::Value,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let path = page_api_path(&page_id, "/bubbles")?;
    forward_post(&session, &path, &bubbles).await
}

#[tauri::command]
async fn layout_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    layout_bubble_for_session(&session, page_id, bubble_id).await
}

async fn layout_bubble_for_session(
    session: &BackendSession,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let page_dto = get_page_for_session(session, page_id).await?;
    let bubbles_arr = page_dto
        .get("bubbles")
        .and_then(|v| v.as_array())
        .ok_or("Invalid bubbles array")?;
    let bubble = bubbles_arr
        .iter()
        .find(|b| b.get("id").and_then(|id| id.as_str()) == Some(&bubble_id))
        .cloned()
        .ok_or_else(|| "Bubble not found".to_string())?;
    session.ensure_current()?;
    Ok(bubble)
}

#[tauri::command]
async fn reocr_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = page_api_path(&page_id, &format!("/bubbles/{id_num}/ocr"))?;
    let _: serde_json::Value = forward_post(&session, &url, &serde_json::json!({})).await?;

    layout_bubble_for_session(&session, page_id, bubble_id).await
}

#[tauri::command]
async fn retranslate_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = page_api_path(&page_id, &format!("/bubbles/{id_num}/translate"))?;
    let job_status: serde_json::Value = forward_empty_post(&session, &url).await?;

    let job_id = job_status
        .get("job_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Job ID missing".to_string())?
        .to_string();

    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(600);
    loop {
        if std::time::Instant::now() >= deadline {
            return Err(BridgeError::new(
                "BACKEND_JOB_TIMEOUT",
                "The translation job did not finish within 10 minutes.",
                true,
            ));
        }
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        let job_path = job_api_path(&job_id, "")?;
        let status: serde_json::Value =
            forward_get_class(&session, &job_path, RequestClass::JobPoll).await?;
        let state = status
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("queued");
        if state == "succeeded" {
            break;
        } else if state == "failed" || state == "cancelled" {
            return Err(BridgeError::new(
                "BACKEND_HTTP_ERROR",
                "Translation failed.",
                false,
            ));
        }
    }

    layout_bubble_for_session(&session, page_id, bubble_id).await
}

#[tauri::command]
async fn autofit_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = page_api_path(&page_id, &format!("/bubbles/{id_num}/inpaint"))?;
    let job_status: serde_json::Value = forward_empty_post(&session, &url).await?;

    let job_id = job_status
        .get("job_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Job ID missing".to_string())?
        .to_string();

    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(600);
    loop {
        if std::time::Instant::now() >= deadline {
            return Err(BridgeError::new(
                "BACKEND_JOB_TIMEOUT",
                "The inpainting job did not finish within 10 minutes.",
                true,
            ));
        }
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        let job_path = job_api_path(&job_id, "")?;
        let status: serde_json::Value =
            forward_get_class(&session, &job_path, RequestClass::JobPoll).await?;
        let state = status
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("queued");
        if state == "succeeded" {
            break;
        } else if state == "failed" || state == "cancelled" {
            return Err(BridgeError::new(
                "BACKEND_HTTP_ERROR",
                "Inpainting failed.",
                false,
            ));
        }
    }

    layout_bubble_for_session(&session, page_id, bubble_id).await
}

#[tauri::command]
async fn delete_bubble(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    bubble_id: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);

    let bubbles_path = page_api_path(&page_id, "/bubbles")?;
    let bubbles_res: serde_json::Value = forward_get(&session, &bubbles_path).await?;
    let bubbles = bubbles_res
        .get("bubbles")
        .cloned()
        .unwrap_or(serde_json::json!([]));

    let mut bubbles_arr = bubbles.as_array().ok_or("Invalid bubbles array")?.clone();
    bubbles_arr.retain(|b| b.get("id").and_then(|v| v.as_i64()) != Some(id_num));

    let _: serde_json::Value = forward_post(&session, &bubbles_path, &bubbles_arr).await?;

    get_page_for_session(&session, page_id).await
}

#[tauri::command]
async fn export_page_to_path(
    manager: tauri::State<'_, BackendManager>,
    page_id: String,
    save_path: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let path = page_api_path(&page_id, "/export")?;
    forward_form(&session, &path, vec![("save_path".to_string(), save_path)]).await
}

#[tauri::command]
async fn export_pages(
    manager: tauri::State<'_, BackendManager>,
    options: serde_json::Value,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let page_ids = options
        .get("page_ids")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "Invalid page_ids".to_string())?;

    let output_dir = options
        .get("output_dir")
        .and_then(|v| v.as_str())
        .unwrap_or("./export");
    let output_dir = Path::new(output_dir);

    let mut exported_paths = vec![];

    for (ordinal, page_id) in page_ids.iter().enumerate() {
        let page_id_str = page_id
            .as_str()
            .ok_or_else(|| "Invalid page_id".to_string())?;
        let path = page_api_path(page_id_str, "/export")?;
        let save_path = batch_export_path(output_dir, ordinal)?;
        let save_path = save_path.to_string_lossy().into_owned();
        let _: serde_json::Value = forward_form_class(
            &session,
            &path,
            vec![("save_path".to_string(), save_path.clone())],
            RequestClass::Export,
        )
        .await?;
        exported_paths.push(save_path);
    }

    session.ensure_current()?;
    Ok(serde_json::json!({
        "success": !exported_paths.is_empty(),
        "exported_paths": exported_paths,
        "problems": []
    }))
}

#[tauri::command]
async fn get_settings(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_get(&session, "/api/settings").await
}

#[tauri::command]
async fn get_provider_catalog(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_get(&session, "/api/providers/catalog").await
}

#[tauri::command]
async fn update_settings(
    manager: tauri::State<'_, BackendManager>,
    settings: serde_json::Value,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let _: serde_json::Value = forward_post(&session, "/api/settings", &settings).await?;
    forward_get(&session, "/api/settings").await
}

#[tauri::command]
async fn get_model_status(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_get(&session, "/api/models/status").await
}

#[tauri::command]
async fn download_required_models(
    manager: tauri::State<'_, BackendManager>,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    forward_post(&session, "/api/models/download", &serde_json::json!({})).await
}

#[tauri::command]
async fn get_translation_models(
    manager: tauri::State<'_, BackendManager>,
    provider: String,
    api_key: String,
    base_url: String,
) -> CommandResult<serde_json::Value> {
    let session = manager.session_snapshot()?;
    let payload = serde_json::json!({
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url
    });
    forward_post(&session, "/api/translation/models", &payload).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_manager = BackendManager::new();
    let image_manager = backend_manager.clone();

    let build_result = tauri::Builder::default()
        .register_asynchronous_uri_scheme_protocol(
            "vibecleaner-image",
            move |_context, request, responder| {
                image_protocol::handle_image_request(image_manager.clone(), request, responder);
            },
        )
        .manage(backend_manager)
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            let manager = app.state::<BackendManager>().inner().clone();
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                manager.start(app_handle).await;
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            retry_backend,
            select_directory,
            select_file,
            select_multiple_files,
            save_file,
            import_images,
            import_directory,
            get_project,
            get_pages,
            get_page,
            new_project,
            load_project,
            save_project,
            select_page,
            duplicate_page,
            duplicate_pages_batch,
            delete_page,
            delete_pages_batch,
            reorder_pages,
            rename_page,
            inpaint_page,
            translate_all_page,
            translate_batch,
            get_job,
            cancel_job,
            update_bubbles,
            update_bubble,
            layout_bubble,
            reocr_bubble,
            retranslate_bubble,
            autofit_bubble,
            delete_bubble,
            export_page_to_path,
            export_pages,
            get_settings,
            get_provider_catalog,
            update_settings,
            get_model_status,
            download_required_models,
            get_translation_models
        ])
        .build(tauri::generate_context!());

    let app = match build_result {
        Ok(app) => app,
        Err(e) => {
            eprintln!("error while building tauri application: {e}");
            rfd::MessageDialog::new()
                .set_level(rfd::MessageLevel::Error)
                .set_title(concat!(env!("CARGO_PKG_NAME"), " 실행 오류"))
                .set_description(format!(
                    "앱을 초기화하지 못했습니다.\n{e}\n\nWebView2 런타임이 설치되어 있는지 확인해 주세요."
                ))
                .show();
            std::process::exit(1);
        }
    };

    app.run(move |app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            app_handle.state::<BackendManager>().shutdown(app_handle);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_segments_are_encoded_and_dangerous_inputs_are_rejected() {
        assert_eq!(
            page_api_path("page name", "/bubbles").unwrap(),
            "/api/pages/page%20name/bubbles"
        );
        for value in [
            "",
            ".",
            "..",
            "../escape",
            r"..\escape",
            "page?x",
            "page#x",
            "line\nfeed",
        ] {
            assert_eq!(
                encode_path_segment(value, "page_id").unwrap_err().code,
                "INVALID_PATH_IDENTIFIER"
            );
        }
    }

    #[test]
    fn batch_export_uses_fixed_filenames_inside_the_canonical_directory() {
        let unique = format!(
            "vibecleaner-export-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let directory = std::env::temp_dir().join(unique);
        std::fs::create_dir(&directory).unwrap();

        let export_path = batch_export_path(&directory, 0).unwrap();
        let canonical_directory = std::fs::canonicalize(&directory).unwrap();
        assert_eq!(export_path, canonical_directory.join("page_0001.png"));
        assert!(export_path.starts_with(&canonical_directory));

        std::fs::remove_dir(&directory).unwrap();
    }
}
