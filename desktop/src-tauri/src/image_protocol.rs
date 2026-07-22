use std::collections::HashMap;

use http::{header, Request, Response, StatusCode};
use percent_encoding::{percent_decode_str, utf8_percent_encode, NON_ALPHANUMERIC};
use tauri::UriSchemeResponder;

use crate::backend_process::BackendManager;

const IMAGE_PREFIX: &str = "/api/pages/";
const IMAGE_SUFFIX: &str = "/image";

pub fn handle_image_request(
    manager: BackendManager,
    request: Request<Vec<u8>>,
    responder: UriSchemeResponder,
) {
    tauri::async_runtime::spawn(async move {
        let response = match validated_backend_path(&request) {
            Ok(path) => match manager.client_snapshot() {
                Ok((generation, client)) => match client.get_bytes(&path).await {
                    Ok(backend_response) => {
                        if manager.ensure_generation(generation).is_err() {
                            error_response(StatusCode::SERVICE_UNAVAILABLE)
                        } else {
                            let mut builder = Response::builder().status(backend_response.status);
                            for name in [
                                header::CONTENT_TYPE,
                                header::CONTENT_LENGTH,
                                header::CACHE_CONTROL,
                                header::ETAG,
                                header::LAST_MODIFIED,
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
}
