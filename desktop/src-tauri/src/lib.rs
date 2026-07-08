// src-tauri/src/lib.rs
use std::net::TcpListener;
use std::sync::Mutex;
use std::process::{Child, Command};
use std::path::{Path, PathBuf};
use tauri::Manager;

struct PortState(u16);

/// Serializable backend status surfaced to the frontend so it can render a
/// recoverable error screen (in-app, matching the UI design) instead of the
/// process crashing on startup.
#[derive(Clone, serde::Serialize)]
struct BackendStatus {
    running: bool,
    error: Option<String>,
    port: u16,
}

struct BackendState {
    child: Mutex<Option<Child>>,
    status: Mutex<BackendStatus>,
}

fn get_free_port() -> Option<u16> {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .ok()
}

/// Locate the bundled backend sidecar binary in production builds.
fn locate_sidecar() -> Result<PathBuf, String> {
    let current_exe =
        std::env::current_exe().map_err(|e| format!("실행 파일 경로를 확인하지 못했습니다: {e}"))?;
    let exe_dir = current_exe
        .parent()
        .ok_or_else(|| "실행 파일 디렉터리를 확인하지 못했습니다.".to_string())?;

    let sidecar_name = "server-x86_64-pc-windows-msvc.exe";
    let candidates = vec![
        exe_dir.join(sidecar_name),
        exe_dir.join("resources").join(sidecar_name),
        exe_dir.join("resources").join("binaries").join(sidecar_name),
        exe_dir.join("binaries").join(sidecar_name),
    ];

    candidates
        .iter()
        .find(|p| p.exists())
        .cloned()
        .ok_or_else(|| {
            let searched = candidates
                .iter()
                .map(|c| format!("  - {}", c.display()))
                .collect::<Vec<_>>()
                .join("\n");
            format!("백엔드 서버 실행 파일을 찾을 수 없습니다.\n검색한 경로:\n{searched}")
        })
}

/// Build the command used to launch the backend (dev: python, prod: sidecar).
fn build_backend_command(port: u16) -> Result<Command, String> {
    let mut cmd = if cfg!(debug_assertions) {
        let python_path = if Path::new("../../venv/Scripts/python.exe").exists() {
            "../../venv/Scripts/python.exe"
        } else if Path::new("../venv/Scripts/python.exe").exists() {
            "../venv/Scripts/python.exe"
        } else if Path::new("venv/Scripts/python.exe").exists() {
            "venv/Scripts/python.exe"
        } else {
            "python"
        };

        let mut c = Command::new(python_path);
        c.arg("../../backend/main.py").arg("--port").arg(port.to_string());
        c
    } else {
        let sidecar_path = locate_sidecar()?;
        println!("Found backend sidecar at: {}", sidecar_path.display());
        let mut c = Command::new(sidecar_path);
        c.arg("--port").arg(port.to_string());
        c
    };

    // Hide console window on Windows
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    Ok(cmd)
}

/// Attempt to spawn the backend process. Never panics; returns an error string
/// that the frontend can display and retry.
fn spawn_backend(port: u16) -> Result<Child, String> {
    let mut cmd = build_backend_command(port)?;
    cmd.spawn()
        .map_err(|e| format!("백엔드 서버 프로세스를 시작하지 못했습니다: {e}"))
}

fn terminate_child(child: &mut Child) {
    let pid = child.id();
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string()])
            .status();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = Command::new("kill").arg("-9").arg(pid.to_string()).status();
    }
}

fn backend_error_message(status: reqwest::StatusCode, body: &str) -> String {
    let detail = serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|v| v.get("detail").cloned())
        .map(|v| {
            if let Some(s) = v.as_str() {
                s.to_string()
            } else {
                v.to_string()
            }
        })
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| body.to_string());

    if detail.is_empty() {
        format!("서버 오류: {status}")
    } else {
        format!("서버 오류 {status}: {detail}")
    }
}

async fn response_json<T: serde::de::DeserializeOwned>(res: reqwest::Response) -> Result<T, String> {
    let status = res.status();
    let body = res.text().await.map_err(|e| format!("HTTP 응답 읽기 실패: {e}"))?;
    if !status.is_success() {
        return Err(backend_error_message(status, &body));
    }
    serde_json::from_str::<T>(&body).map_err(|e| format!("JSON 파싱 실패: {e}"))
}

// Helper functions for Python API forwarding (Fully Asynchronous)
async fn forward_get<T: serde::de::DeserializeOwned>(port: u16, path: &str) -> Result<T, String> {
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let res = reqwest::get(&url)
        .await
        .map_err(|e| format!("HTTP GET 실패: {e}"))?;
    response_json(res).await
}

async fn forward_post<T: serde::de::DeserializeOwned, P: serde::Serialize>(
    port: u16,
    path: &str,
    payload: &P,
) -> Result<T, String> {
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .json(payload)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;
    response_json(res).await
}

async fn forward_empty_post<T: serde::de::DeserializeOwned>(port: u16, path: &str) -> Result<T, String> {
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;
    response_json(res).await
}

async fn forward_form<T: serde::de::DeserializeOwned>(
    port: u16,
    path: &str,
    fields: Vec<(String, String)>,
) -> Result<T, String> {
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .form(&fields)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;
    response_json(res).await
}

#[tauri::command]
fn get_api_port(port_state: tauri::State<'_, PortState>) -> u16 {
    port_state.0
}

#[tauri::command]
fn get_backend_status(state: tauri::State<'_, BackendState>) -> BackendStatus {
    state.status.lock().unwrap().clone()
}

/// Re-attempt to start the backend (invoked by the in-app error screen).
#[tauri::command]
fn retry_backend(
    port_state: tauri::State<'_, PortState>,
    state: tauri::State<'_, BackendState>,
) -> BackendStatus {
    let port = port_state.0;

    // Tear down any previous (possibly dead) child first.
    {
        let mut guard = state.child.lock().unwrap();
        if let Some(mut child) = guard.take() {
            terminate_child(&mut child);
        }
    }

    let status = match spawn_backend(port) {
        Ok(child) => {
            println!("Backend respawned with PID: {}", child.id());
            *state.child.lock().unwrap() = Some(child);
            BackendStatus { running: true, error: None, port }
        }
        Err(e) => {
            eprintln!("Backend retry failed: {e}");
            BackendStatus { running: false, error: Some(e), port }
        }
    };

    *state.status.lock().unwrap() = status.clone();
    status
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
fn select_multiple_files(title: String, filters: Vec<(String, Vec<String>)>) -> Option<Vec<String>> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    for (name, exts) in filters {
        let exts_str: Vec<&str> = exts.iter().map(|s| s.as_str()).collect();
        dialog = dialog.add_filter(&name, &exts_str);
    }
    dialog.pick_files().map(|paths| {
        paths.iter().map(|p| p.to_string_lossy().into_owned()).collect()
    })
}

#[tauri::command]
fn save_file(title: String, _default_ext: String, filters: Vec<(String, Vec<String>)>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    for (name, exts) in filters {
        let exts_str: Vec<&str> = exts.iter().map(|s| s.as_str()).collect();
        dialog = dialog.add_filter(&name, &exts_str);
    }
    dialog.save_file().map(|p| p.to_string_lossy().into_owned())
}

// --- DTO Commands Implementation (All Async) ---

#[tauri::command]
async fn get_project(port_state: tauri::State<'_, PortState>) -> Result<serde_json::Value, String> {
    let pages_res: serde_json::Value = forward_get(port_state.0, "/api/pages").await?;
    let settings_res: serde_json::Value = forward_get(port_state.0, "/api/settings").await?;
    
    let pages = pages_res.get("pages").cloned().unwrap_or(serde_json::json!([]));
    let current_index = pages_res.get("current_index").and_then(|v| v.as_i64()).unwrap_or(0) as usize;
    
    let pages_dto: Vec<serde_json::Value> = if let Some(arr) = pages.as_array() {
        arr.iter().enumerate().map(|(idx, p)| {
            let page_id = p.get("page_id").cloned().unwrap_or(serde_json::json!(""));
            let filename = p.get("filename").cloned().unwrap_or(serde_json::json!(""));
            let width = p.get("width").cloned().unwrap_or(serde_json::json!(0));
            let height = p.get("height").cloned().unwrap_or(serde_json::json!(0));
            let has_inpaint = p.get("has_inpaint").and_then(|v| v.as_bool()).unwrap_or(false);
            let bubble_count = p.get("bubble_count").and_then(|v| v.as_i64()).unwrap_or(0);
            let translated_count = p.get("translated_count").and_then(|v| v.as_i64()).unwrap_or(0);
            let status = p.get("status").cloned().unwrap_or_else(|| {
                serde_json::json!(if has_inpaint { "ready_for_review" } else { "idle" })
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
        }).collect()
    } else {
        vec![]
    };

    let current_page_id = pages_dto.get(current_index)
        .and_then(|p| p.get("id").and_then(|id| id.as_str()))
        .map(|s| s.to_string());

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
    port_state: tauri::State<'_, PortState>,
    page_id: String,
) -> Result<serde_json::Value, String> {
    let pages_res: serde_json::Value = forward_get(port_state.0, "/api/pages").await?;
    let pages = pages_res.get("pages").cloned().unwrap_or(serde_json::json!([]));
    
    let page_info = pages.as_array()
        .and_then(|arr| arr.iter().find(|p| p.get("page_id").and_then(|id| id.as_str()) == Some(&page_id)))
        .cloned()
        .ok_or_else(|| "Page not found".to_string())?;

    let bubbles_res: serde_json::Value = forward_get(port_state.0, &format!("/api/pages/{}/bubbles", page_id)).await?;
    let bubbles = bubbles_res.get("bubbles").cloned().unwrap_or(serde_json::json!([]));

    let bubbles_dto: Vec<serde_json::Value> = if let Some(arr) = bubbles.as_array() {
        arr.iter().map(|b| {
            let id = b.get("id").and_then(|v| v.as_i64()).unwrap_or(0);
            let x = b.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let y = b.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let w = b.get("width").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let h = b.get("height").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let bubble_box = serde_json::json!({ "x": x, "y": y, "width": w, "height": h });
            let text_box = b.get("text_box")
                .filter(|v| v.is_object())
                .cloned()
                .unwrap_or_else(|| bubble_box.clone());
            let layout_box = b.get("layout_box")
                .filter(|v| v.is_object())
                .cloned()
                .unwrap_or_else(|| text_box.clone());
            let text = b.get("text").and_then(|v| v.as_str()).unwrap_or("");
            let translated = b.get("translated").and_then(|v| v.as_str()).unwrap_or("");
            let font_family = b.get("font_family").and_then(|v| v.as_str()).unwrap_or("");
            let computed_font_family = b.get("computed_font_family").and_then(|v| v.as_str()).unwrap_or("");
            let font_size = b.get("font_size").and_then(|v| v.as_i64()).unwrap_or(0);
            let computed_font_size = b.get("computed_font_size").and_then(|v| v.as_i64()).unwrap_or(12);
            let bold = b.get("bold").and_then(|v| v.as_bool()).unwrap_or(false);
            let italic = b.get("italic").and_then(|v| v.as_bool()).unwrap_or(false);
            let color = b.get("color").and_then(|v| v.as_str()).unwrap_or("#000000");
            let alignment = b.get("alignment").and_then(|v| v.as_str()).unwrap_or("center");
            let text_class = b.get("text_class").and_then(|v| v.as_str()).unwrap_or("");
            let lines = b.get("lines").cloned().unwrap_or(serde_json::json!([]));
            let writing_mode = b.get("writing_mode").and_then(|v| v.as_str()).unwrap_or("horizontal");
            let text_direction = b.get("text_direction").and_then(|v| v.as_str()).unwrap_or("ltr");
            let justification = b.get("justification").and_then(|v| v.as_str()).unwrap_or("none");
            let layout_padding = b.get("layout_padding").cloned().unwrap_or(serde_json::json!({}));
            let layout_margin = b.get("layout_margin").cloned().unwrap_or(serde_json::json!({}));
            let layout_confidence = b.get("layout_confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let layout_reasoning = b.get("layout_reasoning").and_then(|v| v.as_str()).unwrap_or("");
            let layout_overflow = b.get("layout_overflow").and_then(|v| v.as_bool()).unwrap_or(false);
            let status = b.get("status").cloned().unwrap_or_else(|| {
                serde_json::json!(if translated.is_empty() { "needs_review" } else { "ok" })
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
        }).collect()
    } else {
        vec![]
    };

    let width = page_info.get("width").cloned().unwrap_or(serde_json::json!(100));
    let height = page_info.get("height").cloned().unwrap_or(serde_json::json!(100));
    let filename = page_info.get("filename").cloned().unwrap_or(serde_json::json!(""));
    let has_inpaint = page_info.get("has_inpaint").and_then(|v| v.as_bool()).unwrap_or(false);
    let status = page_info.get("status").cloned().unwrap_or_else(|| {
        serde_json::json!(if has_inpaint { "ready_for_review" } else { "idle" })
    });
    let problems = page_info.get("problems").cloned().unwrap_or(serde_json::json!([]));

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
    port_state: tauri::State<'_, PortState>,
    paths: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/api/project/open-files", port_state.0);
    
    let paths_vec = paths.unwrap_or_default();
    let files_json = serde_json::to_string(&paths_vec).unwrap();

    let res = client.post(&url)
        .form(&[("files_json", &files_json)])
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;

    let _: serde_json::Value = response_json(res).await?;

    get_project(port_state).await
}

#[tauri::command]
async fn import_directory(
    port_state: tauri::State<'_, PortState>,
    directory: String,
) -> Result<serde_json::Value, String> {
    let _: serde_json::Value = forward_form(
        port_state.0,
        "/api/project/open-directory",
        vec![("directory".to_string(), directory)],
    ).await?;
    get_project(port_state).await
}

#[tauri::command]
async fn new_project(port_state: tauri::State<'_, PortState>) -> Result<serde_json::Value, String> {
    forward_empty_post(port_state.0, "/api/project/new").await
}

#[tauri::command]
async fn load_project(
    port_state: tauri::State<'_, PortState>,
    file_path: String,
) -> Result<serde_json::Value, String> {
    forward_form(
        port_state.0,
        "/api/project/load",
        vec![("file_path".to_string(), file_path)],
    ).await
}

#[tauri::command]
async fn save_project(
    port_state: tauri::State<'_, PortState>,
    file_path: String,
    selected_indices: Option<Vec<i64>>,
) -> Result<serde_json::Value, String> {
    let selected_json = serde_json::to_string(&selected_indices.unwrap_or_default())
        .map_err(|e| format!("선택 페이지 직렬화 실패: {e}"))?;
    forward_form(
        port_state.0,
        "/api/project/save",
        vec![
            ("file_path".to_string(), file_path),
            ("selected_indices".to_string(), selected_json),
        ],
    ).await
}

fn page_ref_fields(index: Option<i64>, page_id: Option<String>) -> Result<Vec<(String, String)>, String> {
    if let Some(pid) = page_id.filter(|s| !s.is_empty()) {
        return Ok(vec![("page_id".to_string(), pid)]);
    }
    if let Some(idx) = index {
        return Ok(vec![("index".to_string(), idx.to_string())]);
    }
    Err("index 또는 page_id가 필요합니다.".to_string())
}

#[tauri::command]
async fn select_page(
    port_state: tauri::State<'_, PortState>,
    index: Option<i64>,
    page_id: Option<String>,
) -> Result<serde_json::Value, String> {
    forward_form(port_state.0, "/api/pages/select", page_ref_fields(index, page_id)?).await
}

#[tauri::command]
async fn duplicate_page(
    port_state: tauri::State<'_, PortState>,
    index: Option<i64>,
    page_id: Option<String>,
) -> Result<serde_json::Value, String> {
    forward_form(port_state.0, "/api/pages/duplicate", page_ref_fields(index, page_id)?).await
}

#[tauri::command]
async fn duplicate_pages_batch(
    port_state: tauri::State<'_, PortState>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids.unwrap_or_default(),
    });
    forward_post(port_state.0, "/api/pages/duplicate-batch", &payload).await
}

#[tauri::command]
async fn delete_page(
    port_state: tauri::State<'_, PortState>,
    index: Option<i64>,
    page_id: Option<String>,
) -> Result<serde_json::Value, String> {
    forward_form(port_state.0, "/api/pages/delete", page_ref_fields(index, page_id)?).await
}

#[tauri::command]
async fn delete_pages_batch(
    port_state: tauri::State<'_, PortState>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids.unwrap_or_default(),
    });
    forward_post(port_state.0, "/api/pages/delete-batch", &payload).await
}

#[tauri::command]
async fn reorder_pages(
    port_state: tauri::State<'_, PortState>,
    from_index: i64,
    to_index: i64,
) -> Result<serde_json::Value, String> {
    forward_form(
        port_state.0,
        "/api/pages/reorder",
        vec![
            ("from_index".to_string(), from_index.to_string()),
            ("to_index".to_string(), to_index.to_string()),
        ],
    ).await
}

#[tauri::command]
async fn rename_page(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    name: String,
) -> Result<serde_json::Value, String> {
    forward_form(
        port_state.0,
        &format!("/api/pages/{}/rename", page_id),
        vec![("name".to_string(), name)],
    ).await
}

async fn start_page_job(port: u16, page_id: String, action: &str) -> Result<serde_json::Value, String> {
    forward_empty_post(port, &format!("/api/pages/{}/{}", page_id, action)).await
}

#[tauri::command]
async fn inpaint_page(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
) -> Result<serde_json::Value, String> {
    start_page_job(port_state.0, page_id, "inpaint").await
}

#[tauri::command]
async fn translate_all_page(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
) -> Result<serde_json::Value, String> {
    start_page_job(port_state.0, page_id, "translate-all").await
}

#[tauri::command]
async fn translate_batch(
    port_state: tauri::State<'_, PortState>,
    page_indices: Option<Vec<i64>>,
    page_ids: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "page_indices": page_indices.unwrap_or_default(),
        "page_ids": page_ids.unwrap_or_default(),
    });
    forward_post(port_state.0, "/api/pages/translate-batch", &payload).await
}

#[tauri::command]
async fn get_job(
    port_state: tauri::State<'_, PortState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    forward_get(port_state.0, &format!("/api/jobs/{}", job_id)).await
}

#[tauri::command]
async fn cancel_job(
    port_state: tauri::State<'_, PortState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    forward_empty_post(port_state.0, &format!("/api/jobs/{}/cancel", job_id)).await
}

#[tauri::command]
async fn update_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
    patch: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    
    let bubbles_res: serde_json::Value = forward_get(port_state.0, &format!("/api/pages/{}/bubbles", page_id)).await?;
    let bubbles = bubbles_res.get("bubbles").cloned().unwrap_or(serde_json::json!([]));
    
    let mut bubbles_arr = bubbles.as_array().ok_or("Invalid bubbles array")?.clone();
    let bubble_index = bubbles_arr.iter()
        .position(|b| b.get("id").and_then(|v| v.as_i64()) == Some(id_num))
        .ok_or_else(|| "Bubble not found".to_string())?;

    let mut current_bubble = bubbles_arr.get(bubble_index)
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

    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/api/pages/{}/bubbles", port_state.0, page_id);
    
    let res = client.post(&url)
        .json(&bubbles_arr)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;

    let _: serde_json::Value = response_json(res).await?;

    let page_dto = get_page(port_state, page_id).await?;
    let bubbles_arr = page_dto.get("bubbles").and_then(|v| v.as_array()).ok_or("Invalid bubbles array")?;
    let updated_bubble = bubbles_arr.iter()
        .find(|b| b.get("id").and_then(|id| id.as_str()) == Some(&bubble_id))
        .cloned()
        .ok_or_else(|| "Updated bubble not found".to_string())?;

    Ok(updated_bubble)
}

#[tauri::command]
async fn update_bubbles(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubbles: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let url = format!("http://127.0.0.1:{}/api/pages/{}/bubbles", port_state.0, page_id);
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .json(&bubbles)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;
    response_json(res).await
}

#[tauri::command]
async fn layout_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
) -> Result<serde_json::Value, String> {
    let page_dto = get_page(port_state, page_id).await?;
    let bubbles_arr = page_dto.get("bubbles").and_then(|v| v.as_array()).ok_or("Invalid bubbles array")?;
    let bubble = bubbles_arr.iter()
        .find(|b| b.get("id").and_then(|id| id.as_str()) == Some(&bubble_id))
        .cloned()
        .ok_or_else(|| "Bubble not found".to_string())?;
    Ok(bubble)
}

#[tauri::command]
async fn reocr_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
) -> Result<serde_json::Value, String> {
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = format!("/api/pages/{}/bubbles/{}/ocr", page_id, id_num);
    let _: serde_json::Value = forward_post(port_state.0, &url, &serde_json::json!({})).await?;
    
    layout_bubble(port_state, page_id, bubble_id).await
}

#[tauri::command]
async fn retranslate_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
) -> Result<serde_json::Value, String> {
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = format!("http://127.0.0.1:{}/api/pages/{}/bubbles/{}/translate", port_state.0, page_id, id_num);
    
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;

    let job_status: serde_json::Value = response_json(res).await?;

    let job_id = job_status.get("job_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Job ID missing".to_string())?.to_string();

    loop {
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        let poll_url = format!("http://127.0.0.1:{}/api/jobs/{}", port_state.0, job_id);
        let poll_res = client.get(&poll_url).send().await;
        
        if let Ok(resp) = poll_res {
            if let Ok(status) = resp.json::<serde_json::Value>().await {
                let state = status.get("status").and_then(|v| v.as_str()).unwrap_or("queued");
                if state == "succeeded" {
                    break;
                } else if state == "failed" || state == "cancelled" {
                    return Err("Translation failed".to_string());
                }
            }
        }
    }

    layout_bubble(port_state, page_id, bubble_id).await
}

#[tauri::command]
async fn autofit_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
) -> Result<serde_json::Value, String> {
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    let url = format!("http://127.0.0.1:{}/api/pages/{}/bubbles/{}/inpaint", port_state.0, page_id, id_num);
    
    let client = reqwest::Client::new();
    let res = client.post(&url)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;

    let job_status: serde_json::Value = response_json(res).await?;

    let job_id = job_status.get("job_id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Job ID missing".to_string())?.to_string();

    loop {
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        let poll_url = format!("http://127.0.0.1:{}/api/jobs/{}", port_state.0, job_id);
        let poll_res = client.get(&poll_url).send().await;
        
        if let Ok(resp) = poll_res {
            if let Ok(status) = resp.json::<serde_json::Value>().await {
                let state = status.get("status").and_then(|v| v.as_str()).unwrap_or("queued");
                if state == "succeeded" {
                    break;
                } else if state == "failed" || state == "cancelled" {
                    return Err("Inpainting failed".to_string());
                }
            }
        }
    }

    layout_bubble(port_state, page_id, bubble_id).await
}

#[tauri::command]
async fn delete_bubble(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    bubble_id: String,
) -> Result<serde_json::Value, String> {
    let id_num: i64 = bubble_id.replace("bubble_", "").parse().unwrap_or(0);
    
    let bubbles_res: serde_json::Value = forward_get(port_state.0, &format!("/api/pages/{}/bubbles", page_id)).await?;
    let bubbles = bubbles_res.get("bubbles").cloned().unwrap_or(serde_json::json!([]));
    
    let mut bubbles_arr = bubbles.as_array().ok_or("Invalid bubbles array")?.clone();
    bubbles_arr.retain(|b| b.get("id").and_then(|v| v.as_i64()) != Some(id_num));

    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/api/pages/{}/bubbles", port_state.0, page_id);
    
    let res = client.post(&url)
        .json(&bubbles_arr)
        .send()
        .await
        .map_err(|e| format!("HTTP POST 실패: {e}"))?;

    let _: serde_json::Value = response_json(res).await?;

    get_page(port_state, page_id).await
}

#[tauri::command]
async fn export_page_to_path(
    port_state: tauri::State<'_, PortState>,
    page_id: String,
    save_path: String,
) -> Result<serde_json::Value, String> {
    forward_form(
        port_state.0,
        &format!("/api/pages/{}/export", page_id),
        vec![("save_path".to_string(), save_path)],
    ).await
}

#[tauri::command]
async fn export_pages(
    port_state: tauri::State<'_, PortState>,
    options: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let page_ids = options.get("page_ids")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "Invalid page_ids".to_string())?;

    let output_dir = options.get("output_dir")
        .and_then(|v| v.as_str())
        .unwrap_or("./export");

    let mut exported_paths = vec![];

    let client = reqwest::Client::new();
    for page_id in page_ids {
        let page_id_str = page_id.as_str().ok_or_else(|| "Invalid page_id".to_string())?;
        let save_path = format!("{}/{}.png", output_dir, page_id_str);
        let url = format!("http://127.0.0.1:{}/api/pages/{}/export", port_state.0, page_id_str);

        let res = client.post(&url)
            .form(&[("save_path", &save_path)])
            .send()
            .await
            .map_err(|e| format!("Export 실패: {e}"))?;

        let _: serde_json::Value = response_json(res).await?;
        exported_paths.push(save_path);
    }

    Ok(serde_json::json!({
        "success": !exported_paths.is_empty(),
        "exported_paths": exported_paths,
        "problems": []
    }))
}

#[tauri::command]
async fn get_settings(port_state: tauri::State<'_, PortState>) -> Result<serde_json::Value, String> {
    forward_get(port_state.0, "/api/settings").await
}

#[tauri::command]
async fn update_settings(
    port_state: tauri::State<'_, PortState>,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let _: serde_json::Value = forward_post(port_state.0, "/api/settings", &settings).await?;
    get_settings(port_state).await
}

#[tauri::command]
async fn get_model_status(port_state: tauri::State<'_, PortState>) -> Result<serde_json::Value, String> {
    forward_get(port_state.0, "/api/models/status").await
}

#[tauri::command]
async fn download_required_models(port_state: tauri::State<'_, PortState>) -> Result<serde_json::Value, String> {
    forward_post(port_state.0, "/api/models/download", &serde_json::json!({})).await
}

#[tauri::command]
async fn get_translation_models(
    port_state: tauri::State<'_, PortState>,
    provider: String,
    api_key: String,
    base_url: String,
) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url
    });
    forward_post(port_state.0, "/api/translation/models", &payload).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = get_free_port().unwrap_or(8000);
    println!("Selected free port for backend: {}", port);

    let (child, status) = match spawn_backend(port) {
        Ok(child) => {
            println!("Spawned backend process with PID: {}", child.id());
            (Some(child), BackendStatus { running: true, error: None, port })
        }
        Err(e) => {
            eprintln!("Backend failed to start: {e}");
            (None, BackendStatus { running: false, error: Some(e), port })
        }
    };

    let backend_state = BackendState {
        child: Mutex::new(child),
        status: Mutex::new(status),
    };

    let build_result = tauri::Builder::default()
        .manage(PortState(port))
        .manage(backend_state)
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_api_port,
            get_backend_status,
            retry_backend,
            select_directory,
            select_file,
            select_multiple_files,
            save_file,
            import_images,
            import_directory,
            get_project,
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
            let state = app_handle.state::<BackendState>();
            let mut guard = state.child.lock().unwrap();
            if let Some(mut child) = guard.take() {
                println!("Application exiting. Terminating backend process (PID: {})...", child.id());
                terminate_child(&mut child);
            }
        }
    });
}
