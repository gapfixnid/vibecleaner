use std::fmt;

use serde::Serialize;

pub type CommandResult<T> = Result<T, BridgeError>;

#[derive(Clone, Debug, Serialize)]
pub struct BridgeError {
    pub code: String,
    pub message: String,
    pub retryable: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub http_status: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
}

impl BridgeError {
    pub fn new(code: impl Into<String>, message: impl Into<String>, retryable: bool) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            retryable,
            http_status: None,
            request_id: None,
        }
    }

    pub fn http(
        code: impl Into<String>,
        message: impl Into<String>,
        status: u16,
        retryable: bool,
        request_id: Option<String>,
    ) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
            retryable,
            http_status: Some(status),
            request_id,
        }
    }

    pub fn restarted() -> Self {
        Self::new(
            "BACKEND_RESTARTED",
            "The backend restarted while the request was in progress.",
            true,
        )
    }
}

impl fmt::Display for BridgeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for BridgeError {}

impl From<String> for BridgeError {
    fn from(message: String) -> Self {
        Self::new("BACKEND_INVALID_RESPONSE", message, false)
    }
}

impl From<&str> for BridgeError {
    fn from(message: &str) -> Self {
        Self::from(message.to_string())
    }
}
