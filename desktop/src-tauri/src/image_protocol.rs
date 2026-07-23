use std::collections::HashMap;

use http::{header, Request, Response, StatusCode};
use percent_encoding::{percent_decode_str, utf8_percent_encode, NON_ALPHANUMERIC};
use tauri::UriSchemeResponder;

use crate::backend_process::BackendManager;

const IMAGE_PREFIX: &str = "/api/pages/";
const IMAGE_SUFFIX: &str = "/image";
const TEXT_LAYER_PREFIX: &str = "/api/text-layers/";
const MAX_TEXT_LAYER_BYTES: usize = 32 * 1024 * 1024;

pub fn handle_image_request(
    manager: BackendManager,
    request: Request<Vec<u8>>,
    responder: UriSchemeResponder,
) {
    tauri::async_runtime::spawn(async move {
        let response = match validated_backend_path(&request) {
            Ok(path) => match manager.session_snapshot() {
                Ok(session) => match session.client.get_bytes(&path).await {
                    Ok(backend_response) => {
                        if session.ensure_current().is_err() {
                            error_response(StatusCode::SERVICE_UNAVAILABLE)
                        } else if path.starts_with(TEXT_LAYER_PREFIX)
                            && backend_response.status.is_success()
                            && !valid_text_layer_png(&backend_response)
                        {
                            error_response(StatusCode::BAD_GATEWAY)
                        } else {
                            let mut builder = Response::builder().status(backend_response.status);
                            for name in [
                                header::CONTENT_TYPE,
                                header::CONTENT_LENGTH,
                                header::CACHE_CONTROL,
                                header::ETAG,
                                header::LAST_MODIFIED,
                                header::HeaderName::from_static("x-vibecleaner-text-layer-key"),
                                header::X_CONTENT_TYPE_OPTIONS,
                            ] {
                                if let Some(value) = backend_response.headers.get(&name) {
                                    builder = builder.header(name, value);
                                }
                            }
                            builder
                                .body(backend_response.body)
                                .unwrap_or_else(|_| error_response(StatusCode::BAD_GATEWAY))
                        }
                    }
                    Err(_) => error_response(StatusCode::BAD_GATEWAY),
                },
                Err(_) => error_response(StatusCode::SERVICE_UNAVAILABLE),
            },
            Err(status) => error_response(status),
        };
        responder.respond(response);
    });
}

fn validated_backend_path(request: &Request<Vec<u8>>) -> Result<String, StatusCode> {
    if request.method() != http::Method::GET {
        return Err(StatusCode::METHOD_NOT_ALLOWED);
    }
    let (path, query) = decoded_request_target(request)?;
    if path.starts_with(TEXT_LAYER_PREFIX) {
        return validate_text_layer_path(&path, query.as_deref());
    }
    let encoded_page_id = path
        .strip_prefix(IMAGE_PREFIX)
        .and_then(|value| value.strip_suffix(IMAGE_SUFFIX))
        .ok_or(StatusCode::NOT_FOUND)?;
    if encoded_page_id.is_empty() || encoded_page_id.contains('/') {
        return Err(StatusCode::BAD_REQUEST);
    }
    let page_id = percent_decode_str(encoded_page_id)
        .decode_utf8()
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    if page_id.is_empty()
        || page_id.len() > 128
        || page_id.contains('/')
        || page_id.contains('\\')
        || page_id.contains("..")
        || page_id.contains('\0')
        || page_id.chars().any(char::is_control)
    {
        return Err(StatusCode::BAD_REQUEST);
    }

    let mut values = HashMap::<String, String>::new();
    if let Some(query) = query.as_deref() {
        for (name, value) in url::form_urlencoded::parse(query.as_bytes()) {
            if !matches!(name.as_ref(), "type" | "thumbnail" | "preview" | "v")
                || values
                    .insert(name.into_owned(), value.into_owned())
                    .is_some()
            {
                return Err(StatusCode::BAD_REQUEST);
            }
        }
    }
    if let Some(value) = values.get("type") {
        if !matches!(value.as_str(), "original" | "inpainted") {
            return Err(StatusCode::BAD_REQUEST);
        }
    }
    for name in ["thumbnail", "preview"] {
        if let Some(value) = values.get(name) {
            if !matches!(value.as_str(), "true" | "false") {
                return Err(StatusCode::BAD_REQUEST);
            }
        }
    }
    if let Some(value) = values.get("v") {
        value.parse::<u64>().map_err(|_| StatusCode::BAD_REQUEST)?;
    }

    let encoded_page_id = utf8_percent_encode(&page_id, NON_ALPHANUMERIC);
    let mut serializer = url::form_urlencoded::Serializer::new(String::new());
    for name in ["type", "thumbnail", "preview"] {
        if let Some(value) = values.get(name) {
            serializer.append_pair(name, value);
        }
    }
    let query = serializer.finish();
    let path = format!("{IMAGE_PREFIX}{encoded_page_id}{IMAGE_SUFFIX}");
    Ok(if query.is_empty() {
        path
    } else {
        format!("{path}?{query}")
    })
}

fn validate_text_layer_path(path: &str, query: Option<&str>) -> Result<String, StatusCode> {
    if query.is_some() {
        return Err(StatusCode::BAD_REQUEST);
    }
    let segments: Vec<&str> = path
        .strip_prefix(TEXT_LAYER_PREFIX)
        .ok_or(StatusCode::NOT_FOUND)?
        .split('/')
        .collect();
    if segments.len() != 4 {
        return Err(StatusCode::NOT_FOUND);
    }
    let namespace = segments[0];
    let encoded_page_id = segments[1];
    let bubble_id = segments[2];
    let cache_file = segments[3];
    if namespace.len() != 32
        || !namespace
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    if bubble_id.starts_with('0') || bubble_id.len() > 10 {
        return Err(StatusCode::BAD_REQUEST);
    }
    let parsed_bubble = bubble_id
        .parse::<u32>()
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    if parsed_bubble == 0 || parsed_bubble > i32::MAX as u32 {
        return Err(StatusCode::BAD_REQUEST);
    }
    let cache_key = cache_file
        .strip_suffix(".png")
        .ok_or(StatusCode::BAD_REQUEST)?;
    if cache_key.len() != 24
        || !cache_key
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    let page_id = percent_decode_str(encoded_page_id)
        .decode_utf8()
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    if page_id.is_empty()
        || page_id.len() > 128
        || page_id.contains('/')
        || page_id.contains('\\')
        || page_id.contains("..")
        || page_id.contains('\0')
        || page_id.chars().any(char::is_control)
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    Ok(format!(
        "{TEXT_LAYER_PREFIX}{namespace}/{}/{bubble_id}/{cache_key}.png",
        utf8_percent_encode(&page_id, NON_ALPHANUMERIC)
    ))
}

fn valid_text_layer_png(response: &crate::backend_client::BytesResponse) -> bool {
    let content_type_ok = response
        .headers
        .get(header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| {
            value
                .split(';')
                .next()
                .is_some_and(|mime| mime.trim() == "image/png")
        });
    let body = &response.body;
    if !content_type_ok || body.len() > MAX_TEXT_LAYER_BYTES || body.len() < 24 {
        return false;
    }
    if &body[..8] != b"\x89PNG\r\n\x1a\n" || &body[12..16] != b"IHDR" {
        return false;
    }
    let width = u32::from_be_bytes(body[16..20].try_into().unwrap());
    let height = u32::from_be_bytes(body[20..24].try_into().unwrap());
    width > 0 && height > 0 && u64::from(width) * u64::from(height) <= 64_000_000
}

/// `convertFileSrc` percent-encodes the complete path and query as one path
/// segment (for example `/%2Fapi%2F...%3Fthumbnail%3Dtrue`). Unwrap that
/// transport encoding exactly once before applying the route allowlist. Direct
/// custom-protocol URLs are retained for tests and non-Windows runtimes.
fn decoded_request_target(
    request: &Request<Vec<u8>>,
) -> Result<(String, Option<String>), StatusCode> {
    let path = request.uri().path();
    let encoded = path.strip_prefix('/').unwrap_or(path);
    let wrapped = encoded
        .get(..3)
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case("%2f"));
    if !wrapped {
        return Ok((path.to_owned(), request.uri().query().map(str::to_owned)));
    }
    if request.uri().query().is_some() {
        return Err(StatusCode::BAD_REQUEST);
    }
    let decoded = percent_decode_str(encoded)
        .decode_utf8()
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    let (decoded_path, decoded_query) = decoded
        .split_once('?')
        .map_or((decoded.as_ref(), None), |(path, query)| {
            (path, Some(query))
        });
    Ok((decoded_path.to_owned(), decoded_query.map(str::to_owned)))
}

fn error_response(status: StatusCode) -> Response<Vec<u8>> {
    Response::builder()
        .status(status)
        .header(header::CACHE_CONTROL, "no-store")
        .body(Vec::new())
        .expect("static image protocol error response")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(uri: &str) -> Request<Vec<u8>> {
        Request::builder().uri(uri).body(Vec::new()).unwrap()
    }

    #[test]
    fn accepts_only_the_page_image_route_and_allowed_query() {
        assert_eq!(
            validated_backend_path(&request(
                "http://vibecleaner-image.localhost/api/pages/page_1/image?type=original&preview=true&v=3"
            ))
            .unwrap(),
            "/api/pages/page%5F1/image?type=original&preview=true"
        );
        assert!(validated_backend_path(&request(
            "http://vibecleaner-image.localhost/api/settings"
        ))
        .is_err());
        assert_eq!(
            validated_backend_path(&request(
                "http://vibecleaner-image.localhost/%2Fapi%2Fpages%2Fpage%255F1%2Fimage%3Ftype%3Doriginal%26thumbnail%3Dtrue%26v%3D4"
            ))
            .unwrap(),
            "/api/pages/page%5F1/image?type=original&thumbnail=true"
        );
    }

    #[test]
    fn rejects_traversal_duplicates_and_invalid_values() {
        for uri in [
            "http://vibecleaner-image.localhost/api/pages/../image",
            "http://vibecleaner-image.localhost/api/pages/a%2Fb/image",
            "http://vibecleaner-image.localhost/api/pages/a/image?preview=true&preview=false",
            "http://vibecleaner-image.localhost/api/pages/a/image?type=auto",
            "http://vibecleaner-image.localhost/api/pages/a/image?unknown=1",
            "http://vibecleaner-image.localhost/%2Fapi%2Fsettings",
            "http://vibecleaner-image.localhost/%2Fapi%2Fpages%2Fa%252Fb%2Fimage",
            "http://vibecleaner-image.localhost/%2Fapi%2Fpages%2Fa%2Fimage%3Fpreview%3Dtrue?preview=false",
        ] {
            assert!(validated_backend_path(&request(uri)).is_err(), "{uri}");
        }
    }

    #[test]
    fn accepts_only_canonical_text_layer_paths() {
        let namespace = "0123456789abcdef0123456789abcdef";
        let key = "0123456789abcdef01234567";
        assert_eq!(
            validated_backend_path(&request(&format!(
                "http://vibecleaner-image.localhost/api/text-layers/{namespace}/page_1/1/{key}.png"
            )))
            .unwrap(),
            format!("/api/text-layers/{namespace}/page%5F1/1/{key}.png")
        );
        for uri in [
            format!(
                "http://vibecleaner-image.localhost/api/text-layers/{namespace}/p/01/{key}.png"
            ),
            format!("http://vibecleaner-image.localhost/api/text-layers/{namespace}/p/0/{key}.png"),
            format!(
                "http://vibecleaner-image.localhost/api/text-layers/{namespace}/p/1/{key}.png?v=1"
            ),
        ] {
            assert!(validated_backend_path(&request(&uri)).is_err(), "{uri}");
        }
    }
}
