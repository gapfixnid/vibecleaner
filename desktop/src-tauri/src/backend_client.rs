use std::sync::Arc;
use std::time::Duration;

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use reqwest::{redirect::Policy, Method, Response};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::error::{BridgeError, CommandResult};

pub const TOKEN_HEADER: &str = "X-VibeCleaner-Token";
pub const REQUEST_ID_HEADER: &str = "X-VibeCleaner-Request-ID";

#[derive(Clone, Copy)]
pub enum RequestClass {
    Health,
    Metadata,
    JobPoll,
    Image,
    Export,
}

impl RequestClass {
    fn timeout(self) -> Duration {
        match self {
            Self::Health => Duration::from_millis(750),
            Self::Metadata => Duration::from_secs(30),
            Self::JobPoll => Duration::from_secs(10),
            Self::Image => Duration::from_secs(60),
            Self::Export => Duration::from_secs(120),
        }
    }
}

#[derive(Clone)]
pub struct BackendClient {
    client: reqwest::Client,
    base_url: Arc<str>,
    token: Option<Arc<str>>,
}

pub struct BytesResponse {
    pub status: reqwest::StatusCode,
    pub headers: reqwest::header::HeaderMap,
    pub body: Vec<u8>,
}

impl BackendClient {
    pub fn new(port: u16, token: Option<String>) -> CommandResult<Self> {
        let client = reqwest::Client::builder()
            .connect_timeout(Duration::from_millis(1500))
            .read_timeout(Duration::from_secs(30))
            .redirect(Policy::none())
            .no_proxy()
            .build()
            .map_err(|error| {
                BridgeError::new(
                    "BACKEND_UNAVAILABLE",
                    format!("Failed to create the backend HTTP client: {error}"),
                    true,
                )
            })?;
        Ok(Self {
            client,
            base_url: format!("http://127.0.0.1:{port}").into(),
            token: token.map(Into::into),
        })
    }

    fn request(
        &self,
        method: Method,
        path: &str,
        class: RequestClass,
        authenticated: bool,
    ) -> CommandResult<(reqwest::RequestBuilder, String)> {
        if !path.starts_with('/') || path.starts_with("//") || path.contains("://") {
            return Err(BridgeError::new(
                "BACKEND_INVALID_RESPONSE",
                "Rejected an invalid backend request path.",
                false,
            ));
        }
        let request_id = random_id()?;
        let mut request = self
            .client
            .request(method, format!("{}{}", self.base_url, path))
            .timeout(class.timeout())
            .header(REQUEST_ID_HEADER, &request_id);
        if authenticated {
            let token = self.token.as_deref().ok_or_else(|| {
                BridgeError::new(
                    "BACKEND_UNAUTHORIZED",
                    "The backend session is not authenticated.",
                    false,
                )
            })?;
            request = request.header(TOKEN_HEADER, token);
        }
        Ok((request, request_id))
    }

    pub async fn health(&self, challenge: &str) -> CommandResult<Response> {
        let (request, request_id) =
            self.request(Method::GET, "/health", RequestClass::Health, false)?;
        request
            .header("X-VibeCleaner-Challenge", challenge)
            .send()
            .await
            .map_err(|error| map_reqwest_error(error, request_id))
    }

    pub async fn get_json<T: DeserializeOwned>(&self, path: &str) -> CommandResult<T> {
        self.send_json(Method::GET, path, RequestClass::Metadata, None::<&()>)
            .await
    }

    pub async fn get_json_with_class<T: DeserializeOwned>(
        &self,
        path: &str,
        class: RequestClass,
    ) -> CommandResult<T> {
        self.send_json(Method::GET, path, class, None::<&()>).await
    }

    pub async fn post_json<T: DeserializeOwned, P: Serialize + ?Sized>(
        &self,
        path: &str,
        payload: &P,
    ) -> CommandResult<T> {
        self.send_json(Method::POST, path, RequestClass::Metadata, Some(payload))
            .await
    }

    pub async fn post_empty<T: DeserializeOwned>(&self, path: &str) -> CommandResult<T> {
        self.send_json(Method::POST, path, RequestClass::Metadata, None::<&()>)
            .await
    }

    pub async fn post_form<T: DeserializeOwned>(
        &self,
        path: &str,
        fields: &[(String, String)],
        class: RequestClass,
    ) -> CommandResult<T> {
        let (request, request_id) = self.request(Method::POST, path, class, true)?;
        let response = request
            .form(fields)
            .send()
            .await
            .map_err(|error| map_reqwest_error(error, request_id.clone()))?;
        response_json(response, request_id).await
    }

    pub async fn get_bytes(&self, path: &str) -> CommandResult<BytesResponse> {
        let (request, request_id) = self.request(Method::GET, path, RequestClass::Image, true)?;
        let response = request
            .send()
            .await
            .map_err(|error| map_reqwest_error(error, request_id.clone()))?;
        let status = response.status();
        let headers = response.headers().clone();
        if !status.is_success() {
            return Err(response_error(response, request_id).await);
        }
        let body = response
            .bytes()
            .await
            .map_err(|error| map_reqwest_error(error, request_id))?
            .to_vec();
        Ok(BytesResponse {
            status,
            headers,
            body,
        })
    }

    async fn send_json<T: DeserializeOwned, P: Serialize + ?Sized>(
        &self,
        method: Method,
        path: &str,
        class: RequestClass,
        payload: Option<&P>,
    ) -> CommandResult<T> {
        let (mut request, request_id) = self.request(method, path, class, true)?;
        if let Some(payload) = payload {
            request = request.json(payload);
        }
        let response = request
            .send()
            .await
            .map_err(|error| map_reqwest_error(error, request_id.clone()))?;
        response_json(response, request_id).await
    }
}

async fn response_json<T: DeserializeOwned>(
    response: Response,
    request_id: String,
) -> CommandResult<T> {
    if !response.status().is_success() {
        return Err(response_error(response, request_id).await);
    }
    response.json::<T>().await.map_err(|error| {
        BridgeError::http(
            "BACKEND_INVALID_RESPONSE",
            format!("The backend returned invalid JSON: {error}"),
            200,
            false,
            Some(request_id),
        )
    })
}

async fn response_error(response: Response, request_id: String) -> BridgeError {
    let status = response.status();
    let response_request_id = response
        .headers()
        .get(REQUEST_ID_HEADER)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned)
        .unwrap_or(request_id);
    let body = response.text().await.unwrap_or_default();
    let parsed = serde_json::from_str::<serde_json::Value>(&body).ok();
    let detail = parsed
        .as_ref()
        .and_then(|value| value.get("detail"))
        .or(parsed.as_ref());
    let structured_code = detail
        .and_then(|value| value.get("code"))
        .and_then(|value| value.as_str());
    let structured_message = detail
        .and_then(|value| value.get("message"))
        .and_then(|value| value.as_str());
    let structured_retryable = detail
        .and_then(|value| value.get("retryable"))
        .and_then(|value| value.as_bool());
    let detail_text = detail.map(|value| {
        value
            .as_str()
            .map(str::to_owned)
            .unwrap_or_else(|| value.to_string())
    });
    let mut message: String = structured_message
        .map(str::to_owned)
        .or(detail_text)
        .unwrap_or(body)
        .chars()
        .take(2048)
        .collect();
    if message.is_empty() {
        message = format!("Backend HTTP error {status}");
    }
    let code = structured_code.unwrap_or(if status == reqwest::StatusCode::UNAUTHORIZED {
        "BACKEND_UNAUTHORIZED"
    } else {
        "BACKEND_HTTP_ERROR"
    });
    BridgeError::http(
        code,
        message,
        status.as_u16(),
        structured_retryable.unwrap_or_else(|| status.is_server_error()),
        Some(response_request_id),
    )
}

fn map_reqwest_error(error: reqwest::Error, request_id: String) -> BridgeError {
    let code = if error.is_timeout() {
        "BACKEND_TIMEOUT"
    } else if error.is_connect() {
        "BACKEND_UNAVAILABLE"
    } else {
        "BACKEND_HTTP_ERROR"
    };
    BridgeError {
        code: code.to_string(),
        message: format!("Backend request failed: {error}"),
        retryable: true,
        http_status: error.status().map(|status| status.as_u16()),
        request_id: Some(request_id),
    }
}

pub fn random_bytes<const N: usize>() -> CommandResult<[u8; N]> {
    let mut bytes = [0_u8; N];
    getrandom::fill(&mut bytes).map_err(|error| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            format!("Failed to obtain secure random bytes: {error}"),
            false,
        )
    })?;
    Ok(bytes)
}

pub fn random_id() -> CommandResult<String> {
    Ok(URL_SAFE_NO_PAD.encode(random_bytes::<16>()?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;
    use std::thread;

    fn fake_backend(
        response: &'static str,
        response_delay: Duration,
    ) -> (u16, mpsc::Receiver<String>, thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let (request_tx, request_rx) = mpsc::channel();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut bytes = [0_u8; 8192];
            let read = stream.read(&mut bytes).unwrap();
            request_tx
                .send(String::from_utf8_lossy(&bytes[..read]).into_owned())
                .unwrap();
            thread::sleep(response_delay);
            let _ = stream.write_all(response.as_bytes());
        });
        (port, request_rx, handle)
    }

    #[test]
    fn random_ids_are_url_safe_and_unpadded() {
        let id = random_id().unwrap();
        assert!(!id.contains('='));
        assert_eq!(URL_SAFE_NO_PAD.decode(&id).unwrap().len(), 16);
    }

    #[tokio::test]
    async fn authenticated_requests_send_token_and_request_id_headers() {
        let (port, request_rx, handle) = fake_backend(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}",
            Duration::ZERO,
        );
        let client = BackendClient::new(port, Some("session-secret".to_string())).unwrap();
        let _: serde_json::Value = client.get_json("/api/settings").await.unwrap();
        let request = request_rx.recv_timeout(Duration::from_secs(1)).unwrap();
        let request = request.to_ascii_lowercase();
        assert!(request.starts_with("get /api/settings http/1.1"));
        assert!(request.contains("x-vibecleaner-token: session-secret"));
        assert!(request.contains("x-vibecleaner-request-id:"));
        handle.join().unwrap();
    }

    #[tokio::test]
    async fn redirects_are_returned_as_errors_instead_of_followed() {
        let (port, _request_rx, handle) = fake_backend(
            "HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:1/rogue\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            Duration::ZERO,
        );
        let client = BackendClient::new(port, Some("session-secret".to_string())).unwrap();
        let error = client
            .get_json::<serde_json::Value>("/api/settings")
            .await
            .unwrap_err();
        assert_eq!(error.http_status, Some(302));
        assert_eq!(error.code, "BACKEND_HTTP_ERROR");
        handle.join().unwrap();
    }

    #[tokio::test]
    async fn health_requests_use_the_short_timeout() {
        let (port, _request_rx, handle) = fake_backend(
            "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            Duration::from_millis(900),
        );
        let client = BackendClient::new(port, None).unwrap();
        let error = client.health("challenge").await.unwrap_err();
        assert_eq!(error.code, "BACKEND_TIMEOUT");
        handle.join().unwrap();
    }
}
