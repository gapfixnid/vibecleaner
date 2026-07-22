use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::{Arc, Mutex, Weak};
use std::time::{Duration, Instant};

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use hmac::{Hmac, Mac};
use serde::Serialize;
use sha2::Sha256;
use tauri::{AppHandle, Emitter};

use crate::backend_client::{random_bytes, BackendClient};
use crate::error::{BridgeError, CommandResult};

const SESSION_TOKEN_ENV: &str = "VIBECLEANER_SESSION_TOKEN";
const HEALTH_PROOF_HEADER: &str = "X-VibeCleaner-Proof";
const HEALTH_PREFIX: &str = "vibecleaner-health-v1:";
const START_DEADLINE: Duration = Duration::from_secs(30);
const WATCH_INTERVAL: Duration = Duration::from_millis(250);

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BackendPhase {
    Starting,
    Running,
    Restarting,
    Failed,
    Stopping,
    Stopped,
}

#[derive(Clone, Debug, Serialize)]
pub struct BackendStatus {
    pub running: bool,
    pub phase: BackendPhase,
    pub error: Option<BridgeError>,
    pub pid: Option<u32>,
    pub generation: u64,
}

struct SessionToken([u8; 32]);

impl SessionToken {
    fn generate() -> CommandResult<Self> {
        Ok(Self(random_bytes::<32>()?))
    }

    fn encoded(&self) -> String {
        URL_SAFE_NO_PAD.encode(self.0)
    }

    fn verify_health_proof(&self, challenge: &str, proof: &str) -> bool {
        let Ok(proof_bytes) = URL_SAFE_NO_PAD.decode(proof) else {
            return false;
        };
        let Ok(mut mac) = HmacSha256::new_from_slice(&self.0) else {
            return false;
        };
        mac.update(format!("{HEALTH_PREFIX}{challenge}").as_bytes());
        mac.verify_slice(&proof_bytes).is_ok()
    }
}

impl Drop for SessionToken {
    fn drop(&mut self) {
        self.0.fill(0);
    }
}

pub struct BackendRuntime {
    generation: u64,
    phase: BackendPhase,
    port: Option<u16>,
    pid: Option<u32>,
    client: Option<Arc<BackendClient>>,
    child: Option<Child>,
    error: Option<BridgeError>,
}

#[derive(Clone)]
pub struct BackendManager {
    runtime: Arc<Mutex<BackendRuntime>>,
    restart_lock: Arc<tokio::sync::Mutex<()>>,
}

#[derive(Clone)]
pub struct BackendSession {
    pub generation: u64,
    pub client: Arc<BackendClient>,
    runtime: Weak<Mutex<BackendRuntime>>,
}

impl BackendSession {
    pub fn ensure_current(&self) -> CommandResult<()> {
        let runtime = self.runtime.upgrade().ok_or_else(BridgeError::restarted)?;
        let runtime = lock_runtime(&runtime);
        let is_current = runtime.generation == self.generation
            && runtime.phase == BackendPhase::Running
            && runtime
                .client
                .as_ref()
                .is_some_and(|client| Arc::ptr_eq(client, &self.client));
        if !is_current {
            Err(BridgeError::restarted())
        } else {
            Ok(())
        }
    }
}

impl BackendManager {
    pub fn new() -> Self {
        Self {
            runtime: Arc::new(Mutex::new(BackendRuntime {
                generation: 0,
                phase: BackendPhase::Stopped,
                port: None,
                pid: None,
                client: None,
                child: None,
                error: None,
            })),
            restart_lock: Arc::new(tokio::sync::Mutex::new(())),
        }
    }

    pub fn status(&self) -> BackendStatus {
        let runtime = lock_runtime(&self.runtime);
        status_from_runtime(&runtime)
    }

    pub fn session_snapshot(&self) -> CommandResult<BackendSession> {
        let runtime = lock_runtime(&self.runtime);
        if runtime.phase != BackendPhase::Running {
            return Err(runtime.error.clone().unwrap_or_else(|| {
                BridgeError::new("BACKEND_UNAVAILABLE", "The backend is not running.", true)
            }));
        }
        let client = runtime.client.clone().ok_or_else(|| {
            BridgeError::new(
                "BACKEND_UNAVAILABLE",
                "The backend client is unavailable.",
                true,
            )
        })?;
        Ok(BackendSession {
            generation: runtime.generation,
            client,
            runtime: Arc::downgrade(&self.runtime),
        })
    }

    pub async fn start(&self, app: AppHandle) -> BackendStatus {
        let _restart_guard = self.restart_lock.lock().await;
        self.start_attempt(app, false).await
    }

    pub async fn restart(&self, app: AppHandle) -> BackendStatus {
        let _restart_guard = self.restart_lock.lock().await;
        self.start_attempt(app, true).await
    }

    async fn start_attempt(&self, app: AppHandle, restarting: bool) -> BackendStatus {
        let (generation, previous_child) = {
            let mut runtime = lock_runtime(&self.runtime);
            runtime.generation = runtime.generation.saturating_add(1);
            runtime.phase = if restarting {
                BackendPhase::Restarting
            } else {
                BackendPhase::Starting
            };
            runtime.client = None;
            runtime.error = None;
            runtime.port = None;
            runtime.pid = None;
            let child = runtime.child.take();
            (runtime.generation, child)
        };
        emit_status(&app, &self.status());

        if let Some(mut child) = previous_child {
            let _ = tauri::async_runtime::spawn_blocking(move || terminate_child(&mut child)).await;
        }

        if restarting {
            let mut runtime = lock_runtime(&self.runtime);
            if runtime.generation != generation {
                return status_from_runtime(&runtime);
            }
            runtime.phase = BackendPhase::Starting;
            drop(runtime);
            emit_status(&app, &self.status());
        }

        let listener = match TcpListener::bind("127.0.0.1:0") {
            Ok(listener) => listener,
            Err(error) => {
                return self.fail(
                    &app,
                    generation,
                    BridgeError::new(
                        "BACKEND_SPAWN_FAILED",
                        format!("Failed to reserve a backend port: {error}"),
                        true,
                    ),
                );
            }
        };
        let port = match listener.local_addr() {
            Ok(address) => address.port(),
            Err(error) => {
                return self.fail(
                    &app,
                    generation,
                    BridgeError::new(
                        "BACKEND_SPAWN_FAILED",
                        format!("Failed to inspect the reserved backend port: {error}"),
                        true,
                    ),
                );
            }
        };
        let token = match SessionToken::generate() {
            Ok(token) => token,
            Err(error) => return self.fail(&app, generation, error),
        };
        let encoded_token = token.encoded();
        let client = match BackendClient::new(port, Some(encoded_token.clone())) {
            Ok(client) => Arc::new(client),
            Err(error) => return self.fail(&app, generation, error),
        };

        let command = build_backend_command(port, &encoded_token);
        drop(listener);
        let child = match command.and_then(|mut command| {
            command.spawn().map_err(|error| {
                BridgeError::new(
                    "BACKEND_SPAWN_FAILED",
                    format!("Failed to start the backend process: {error}"),
                    true,
                )
            })
        }) {
            Ok(child) => child,
            Err(error) => return self.fail(&app, generation, error),
        };
        let pid = child.id();
        {
            let mut runtime = lock_runtime(&self.runtime);
            if runtime.generation != generation {
                drop(runtime);
                let mut child = child;
                terminate_child(&mut child);
                return self.status();
            }
            runtime.port = Some(port);
            runtime.pid = Some(pid);
            runtime.child = Some(child);
        }
        emit_status(&app, &self.status());

        let deadline = Instant::now() + START_DEADLINE;
        loop {
            if self.child_exited(generation, pid) {
                return self.fail(
                    &app,
                    generation,
                    BridgeError::new(
                        "BACKEND_EXITED",
                        "The backend exited before it became ready.",
                        true,
                    ),
                );
            }
            if Instant::now() >= deadline {
                self.terminate_generation(generation).await;
                return self.fail(
                    &app,
                    generation,
                    BridgeError::new(
                        "BACKEND_START_TIMEOUT",
                        "The backend did not become ready within 30 seconds.",
                        true,
                    ),
                );
            }

            let challenge = match random_bytes::<32>() {
                Ok(bytes) => URL_SAFE_NO_PAD.encode(bytes),
                Err(error) => {
                    self.terminate_generation(generation).await;
                    return self.fail(&app, generation, error);
                }
            };
            match client.health(&challenge).await {
                Ok(response) if response.status().is_success() => {
                    let proof = response
                        .headers()
                        .get(HEALTH_PROOF_HEADER)
                        .and_then(|value| value.to_str().ok())
                        .map(str::to_owned);
                    let body = response.json::<serde_json::Value>().await;
                    let protocol = body
                        .as_ref()
                        .ok()
                        .and_then(|value| value.get("protocol_version"))
                        .and_then(|value| value.as_u64());
                    if protocol != Some(1) {
                        self.terminate_generation(generation).await;
                        return self.fail(
                            &app,
                            generation,
                            BridgeError::new(
                                "BACKEND_PROTOCOL_MISMATCH",
                                "The backend health protocol is incompatible.",
                                false,
                            ),
                        );
                    }
                    if !proof
                        .as_deref()
                        .is_some_and(|proof| token.verify_health_proof(&challenge, proof))
                    {
                        self.terminate_generation(generation).await;
                        return self.fail(
                            &app,
                            generation,
                            BridgeError::new(
                                "BACKEND_IDENTITY_MISMATCH",
                                "The process on the backend port failed identity verification.",
                                false,
                            ),
                        );
                    }
                    {
                        let mut runtime = lock_runtime(&self.runtime);
                        if runtime.generation != generation {
                            return status_from_runtime(&runtime);
                        }
                        runtime.phase = BackendPhase::Running;
                        runtime.client = Some(client.clone());
                        runtime.error = None;
                    }
                    let status = self.status();
                    emit_status(&app, &status);
                    spawn_watcher(Arc::downgrade(&self.runtime), app, generation, pid);
                    return status;
                }
                Ok(_) => {
                    self.terminate_generation(generation).await;
                    return self.fail(
                        &app,
                        generation,
                        BridgeError::new(
                            "BACKEND_IDENTITY_MISMATCH",
                            "The process on the backend port returned an unexpected health response.",
                            false,
                        ),
                    );
                }
                Err(error)
                    if error.code == "BACKEND_UNAVAILABLE" || error.code == "BACKEND_TIMEOUT" =>
                {
                    tokio::time::sleep(WATCH_INTERVAL).await;
                }
                Err(error) => {
                    self.terminate_generation(generation).await;
                    return self.fail(&app, generation, error);
                }
            }
        }
    }

    fn child_exited(&self, generation: u64, pid: u32) -> bool {
        let mut runtime = lock_runtime(&self.runtime);
        if runtime.generation != generation || runtime.pid != Some(pid) {
            return false;
        }
        let exited = runtime
            .child
            .as_mut()
            .and_then(|child| child.try_wait().ok().flatten())
            .is_some();
        if exited {
            runtime.child.take();
            runtime.client = None;
            runtime.pid = None;
        }
        exited
    }

    async fn terminate_generation(&self, generation: u64) {
        let child = {
            let mut runtime = lock_runtime(&self.runtime);
            if runtime.generation != generation {
                None
            } else {
                runtime.pid = None;
                runtime.client = None;
                runtime.child.take()
            }
        };
        if let Some(mut child) = child {
            let _ = tauri::async_runtime::spawn_blocking(move || terminate_child(&mut child)).await;
        }
    }

    fn fail(&self, app: &AppHandle, generation: u64, error: BridgeError) -> BackendStatus {
        {
            let mut runtime = lock_runtime(&self.runtime);
            if runtime.generation == generation {
                runtime.phase = BackendPhase::Failed;
                runtime.client = None;
                runtime.error = Some(error);
            }
        }
        let status = self.status();
        emit_status(app, &status);
        status
    }

    pub fn shutdown(&self, app: &AppHandle) {
        let (generation, child) = {
            let mut runtime = lock_runtime(&self.runtime);
            runtime.phase = BackendPhase::Stopping;
            runtime.client = None;
            runtime.pid = None;
            (runtime.generation, runtime.child.take())
        };
        emit_status(app, &self.status());
        if let Some(mut child) = child {
            terminate_child(&mut child);
        }
        {
            let mut runtime = lock_runtime(&self.runtime);
            if runtime.generation == generation {
                runtime.phase = BackendPhase::Stopped;
            }
        }
        let _ = app.emit("backend-status-changed", self.status());
    }
}

fn spawn_watcher(
    runtime: Weak<Mutex<BackendRuntime>>,
    app: AppHandle,
    generation: u64,
    watched_pid: u32,
) {
    std::thread::spawn(move || loop {
        std::thread::sleep(WATCH_INTERVAL);
        let Some(runtime) = runtime.upgrade() else {
            return;
        };
        let status = {
            let mut state = lock_runtime(&runtime);
            if state.generation != generation || state.pid != Some(watched_pid) {
                return;
            }
            if !matches!(state.phase, BackendPhase::Starting | BackendPhase::Running) {
                return;
            }
            let exited = state
                .child
                .as_mut()
                .and_then(|child| child.try_wait().ok().flatten());
            let Some(exit_status) = exited else {
                continue;
            };
            state.child.take();
            state.client = None;
            state.pid = None;
            state.phase = BackendPhase::Failed;
            state.error = Some(BridgeError::new(
                "BACKEND_EXITED",
                format!("The backend exited unexpectedly with status {exit_status}."),
                true,
            ));
            status_from_runtime(&state)
        };
        emit_status(&app, &status);
        return;
    });
}

fn emit_status(app: &AppHandle, status: &BackendStatus) {
    let _ = app.emit("backend-status-changed", status.clone());
}

fn status_from_runtime(runtime: &BackendRuntime) -> BackendStatus {
    BackendStatus {
        running: runtime.phase == BackendPhase::Running,
        phase: runtime.phase,
        error: runtime.error.clone(),
        pid: runtime.pid,
        generation: runtime.generation,
    }
}

fn lock_runtime(runtime: &Arc<Mutex<BackendRuntime>>) -> std::sync::MutexGuard<'_, BackendRuntime> {
    runtime
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn locate_sidecar() -> CommandResult<PathBuf> {
    let current_exe = std::env::current_exe().map_err(|error| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            format!("Failed to locate the application executable: {error}"),
            false,
        )
    })?;
    let exe_dir = current_exe.parent().ok_or_else(|| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            "Failed to locate the application directory.",
            false,
        )
    })?;
    let sidecar_name = "server-x86_64-pc-windows-msvc.exe";
    let candidates = [
        exe_dir.join(sidecar_name),
        exe_dir.join("resources").join(sidecar_name),
        exe_dir
            .join("resources")
            .join("binaries")
            .join(sidecar_name),
        exe_dir.join("binaries").join(sidecar_name),
    ];
    candidates
        .into_iter()
        .find(|candidate| candidate.exists())
        .ok_or_else(|| {
            BridgeError::new(
                "BACKEND_SPAWN_FAILED",
                "The bundled backend executable could not be found.",
                false,
            )
        })
}

fn build_backend_command(port: u16, token: &str) -> CommandResult<Command> {
    let mut command = if cfg!(debug_assertions) {
        let python_path = if Path::new("../../venv/Scripts/python.exe").exists() {
            "../../venv/Scripts/python.exe"
        } else if Path::new("../venv/Scripts/python.exe").exists() {
            "../venv/Scripts/python.exe"
        } else if Path::new("venv/Scripts/python.exe").exists() {
            "venv/Scripts/python.exe"
        } else {
            "python"
        };
        let mut command = Command::new(python_path);
        command
            .arg("../../backend/main.py")
            .arg("--port")
            .arg(port.to_string());
        command
    } else {
        let mut command = Command::new(locate_sidecar()?);
        command.arg("--port").arg(port.to_string());
        command
    };
    command.env(SESSION_TOKEN_ENV, token);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    Ok(command)
}

fn windows_taskkill_args(pid: u32) -> Vec<String> {
    vec![
        "/PID".to_string(),
        pid.to_string(),
        "/T".to_string(),
        "/F".to_string(),
    ]
}

pub fn terminate_child(child: &mut Child) {
    let pid = child.id();
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let status = Command::new("taskkill")
            .args(windows_taskkill_args(pid))
            .creation_flags(CREATE_NO_WINDOW)
            .status();
        if !status.as_ref().is_ok_and(|status| status.success()) {
            let _ = child.kill();
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = child.kill();
    }
    let _ = child.wait();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn taskkill_terminates_the_entire_backend_process_tree() {
        assert_eq!(windows_taskkill_args(4242), ["/PID", "4242", "/T", "/F"]);
    }

    #[test]
    fn health_proof_verification_uses_the_canonical_message() {
        let token = SessionToken([7_u8; 32]);
        let challenge = URL_SAFE_NO_PAD.encode([9_u8; 32]);
        let mut mac = HmacSha256::new_from_slice(&[7_u8; 32]).unwrap();
        mac.update(format!("{HEALTH_PREFIX}{challenge}").as_bytes());
        let proof = URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes());
        assert!(token.verify_health_proof(&challenge, &proof));
        assert!(!token.verify_health_proof("wrong", &proof));
    }

    #[test]
    fn backend_session_is_invalidated_when_generation_changes() {
        let manager = BackendManager::new();
        let client = Arc::new(BackendClient::new(49152, Some("token".to_string())).unwrap());
        {
            let mut runtime = lock_runtime(&manager.runtime);
            runtime.generation = 7;
            runtime.phase = BackendPhase::Running;
            runtime.client = Some(client);
        }
        let session = manager.session_snapshot().unwrap();
        assert!(session.ensure_current().is_ok());
        lock_runtime(&manager.runtime).generation = 8;
        let error = session.ensure_current().unwrap_err();
        assert_eq!(error.code, "BACKEND_RESTARTED");
    }

    #[test]
    fn backend_session_is_invalidated_when_phase_stops() {
        let manager = BackendManager::new();
        let client = Arc::new(BackendClient::new(49153, Some("token".to_string())).unwrap());
        {
            let mut runtime = lock_runtime(&manager.runtime);
            runtime.generation = 9;
            runtime.phase = BackendPhase::Running;
            runtime.client = Some(client);
        }
        let session = manager.session_snapshot().unwrap();
        lock_runtime(&manager.runtime).phase = BackendPhase::Stopping;
        assert_eq!(
            session.ensure_current().unwrap_err().code,
            "BACKEND_RESTARTED"
        );
    }
}
