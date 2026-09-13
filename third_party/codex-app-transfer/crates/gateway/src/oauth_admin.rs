use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use axum::{
    extract::Query,
    http::StatusCode,
    response::{IntoResponse, Json},
    routing::{delete, get, post},
    Router,
};
use codex_app_transfer_gemini_oauth::{
    claim_pending_for_provider, complete_grok_build_login, grok_build_logout,
    prepare_grok_build_authorization, run_trae_login, run_zai_login, GrokBuildCredentialStore,
    GrokBuildError, OauthFlowConfig, TraeCredentialStore, TraeEdition, TraeError,
    TraePendingStore, ZaiCredentialStore, ZaiError, ZaiProvider, LOOPBACK_PORT, REDIRECT_URI,
};
use codex_app_transfer_gemini_oauth::qoder::{run_qoder_login, QoderError};
use codex_app_transfer_gemini_oauth::workbuddy::{run_workbuddy_login, WorkbuddyError};
use serde::Deserialize;
use serde_json::json;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tokio::sync::oneshot;

const LOGIN_TIMEOUT: Duration = Duration::from_secs(300);
const CONN_HANDLE_TIMEOUT: Duration = Duration::from_secs(5);

pub fn routes() -> Router {
    Router::new()
        .route("/__admin/zai-oauth/status", get(zai_status))
        .route("/__admin/zai-oauth/login", post(zai_login))
        .route("/__admin/zai-oauth/logout", delete(zai_logout))
        .route("/__admin/trae-oauth/status", get(trae_status))
        .route("/__admin/trae-oauth/login", post(trae_login))
        .route("/__admin/trae-oauth/logout", delete(trae_logout))
        .route("/__admin/trae-oauth/claim", post(trae_claim))
        .route("/__admin/workbuddy-oauth/status", get(workbuddy_status))
        .route("/__admin/workbuddy-oauth/login", post(workbuddy_login))
        .route("/__admin/workbuddy-oauth/account", delete(workbuddy_remove_account))
        .route("/__admin/workbuddy-oauth/switch", post(workbuddy_switch_account))
        .route("/__admin/qoder-oauth/status", get(qoder_status))
        .route("/__admin/qoder-oauth/login", post(qoder_login))
        .route("/__admin/qoder-oauth/account", delete(qoder_remove_account))
        .route("/__admin/qoder-oauth/switch", post(qoder_switch_account))
        .route("/__admin/grok-build-oauth/status", get(grok_build_status))
        .route("/__admin/grok-build-oauth/login", post(grok_build_login))
        .route(
            "/__admin/grok-build-oauth/submit-code",
            post(grok_build_submit_code),
        )
        .route("/__admin/grok-build-oauth/logout", delete(grok_build_logout_handler))
}

fn oauth_http_client() -> Result<reqwest::Client, reqwest::Error> {
    reqwest::Client::builder()
        .pool_idle_timeout(Duration::from_secs(30))
        .connect_timeout(Duration::from_secs(10))
        .timeout(Duration::from_secs(60))
        .build()
}

fn json_error(status: StatusCode, message: impl Into<String>) -> axum::response::Response {
    (
        status,
        Json(json!({
            "loggedIn": false,
            "error": message.into(),
        })),
    )
        .into_response()
}

fn open_auth_url(kind: &str, url: &str) {
    eprintln!("{kind} OAuth URL: {url}");
    if let Err(error) = webbrowser::open(url) {
        eprintln!("{kind} OAuth browser open failed: {error}; copy the URL above manually");
    }
}

fn oauth_flow_config(kind: &'static str) -> OauthFlowConfig {
    let mut config = OauthFlowConfig::default();
    config.on_auth_url = Some(std::sync::Arc::new(move |url| open_auth_url(kind, url)));
    config
}

#[derive(Debug, Deserialize)]
struct ZaiQuery {
    #[serde(default)]
    provider: String,
}

fn parse_zai_provider(query: &ZaiQuery) -> Option<ZaiProvider> {
    match query.provider.trim().to_ascii_lowercase().as_str() {
        "zai" => Some(ZaiProvider::Zai),
        "bigmodel" => Some(ZaiProvider::BigModel),
        _ => None,
    }
}

async fn zai_status(Query(query): Query<ZaiQuery>) -> impl IntoResponse {
    let Some(provider) = parse_zai_provider(&query) else {
        return json_error(StatusCode::BAD_REQUEST, "provider must be zai or bigmodel");
    };
    let store = match ZaiCredentialStore::for_provider(provider) {
        Ok(store) => store,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    match store.load() {
        Ok(None) => Json(json!({ "loggedIn": false, "provider": provider.wire_id() })).into_response(),
        Ok(Some(cred)) => Json(json!({
            "loggedIn": true,
            "provider": provider.wire_id(),
            "email": cred.email,
            "obtainedAt": cred.obtained_at_ms,
        }))
        .into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn zai_login(Query(query): Query<ZaiQuery>) -> impl IntoResponse {
    let Some(provider) = parse_zai_provider(&query) else {
        return json_error(StatusCode::BAD_REQUEST, "provider must be zai or bigmodel");
    };
    let http = match oauth_http_client() {
        Ok(http) => http,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    let config = oauth_flow_config(provider.wire_id());
    match run_zai_login(&http, provider, &config, None).await {
        Ok(cred) => Json(json!({
            "loggedIn": true,
            "provider": provider.wire_id(),
            "email": cred.email,
            "obtainedAt": cred.obtained_at_ms,
        }))
        .into_response(),
        Err(ZaiError::Flow(codex_app_transfer_gemini_oauth::FlowError::Cancelled)) => {
            Json(json!({ "loggedIn": false, "cancelled": true, "provider": provider.wire_id() })).into_response()
        }
        Err(error) => Json(json!({
            "loggedIn": false,
            "provider": provider.wire_id(),
            "error": error.to_string(),
        }))
        .into_response(),
    }
}

async fn zai_logout(Query(query): Query<ZaiQuery>) -> impl IntoResponse {
    let Some(provider) = parse_zai_provider(&query) else {
        return json_error(StatusCode::BAD_REQUEST, "provider must be zai or bigmodel");
    };
    let store = match ZaiCredentialStore::for_provider(provider) {
        Ok(store) => store,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    match store.delete() {
        Ok(()) => Json(json!({ "loggedIn": false, "provider": provider.wire_id() })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

#[derive(Debug, Deserialize)]
struct ProviderIdQuery {
    #[serde(default, rename = "providerId")]
    provider_id: String,
}

#[derive(Debug, Deserialize)]
struct AccountQuery {
    #[serde(default, rename = "providerId")]
    provider_id: String,
    #[serde(default)]
    uid: String,
}

fn nonempty(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

async fn trae_status(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let provider_id = nonempty(&query.provider_id).map(str::to_string);
    let loaded = match provider_id.as_deref() {
        Some(id) => TraeCredentialStore::for_provider_id(id).and_then(|store| store.load()),
        None => TraePendingStore::for_pending().and_then(|store| store.load()),
    };
    match loaded {
        Ok(None) => Json(json!({
            "loggedIn": false,
            "providerId": provider_id,
            "pending": provider_id.is_none(),
        }))
        .into_response(),
        Ok(Some(cred)) => Json(json!({
            "loggedIn": true,
            "providerId": provider_id,
            "pending": provider_id.is_none(),
            "email": cred.email,
            "userId": cred.user_id,
            "aiRegion": cred.ai_region,
            "obtainedAt": cred.obtained_at_ms,
        }))
        .into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn trae_login(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let provider_id = nonempty(&query.provider_id).map(str::to_string);
    let http = match oauth_http_client() {
        Ok(http) => http,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    let config = oauth_flow_config("trae");
    match run_trae_login(
        &http,
        TraeEdition::Cn,
        provider_id.as_deref(),
        &config,
        None,
    )
    .await
    {
        Ok(cred) => Json(json!({
            "loggedIn": true,
            "providerId": provider_id,
            "pending": provider_id.is_none(),
            "email": cred.email,
            "userId": cred.user_id,
            "aiRegion": cred.ai_region,
            "obtainedAt": cred.obtained_at_ms,
        }))
        .into_response(),
        Err(TraeError::Flow(codex_app_transfer_gemini_oauth::FlowError::Cancelled)) => {
            Json(json!({ "loggedIn": false, "cancelled": true, "providerId": provider_id })).into_response()
        }
        Err(error) => Json(json!({
            "loggedIn": false,
            "providerId": provider_id,
            "error": error.to_string(),
        }))
        .into_response(),
    }
}

async fn trae_logout(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let provider_id = nonempty(&query.provider_id).map(str::to_string);
    let deleted = match provider_id.as_deref() {
        Some(id) => TraeCredentialStore::for_provider_id(id).and_then(|store| store.delete()),
        None => TraePendingStore::for_pending().and_then(|store| store.delete()),
    };
    match deleted {
        Ok(()) => Json(json!({ "loggedIn": false, "providerId": provider_id })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn trae_claim(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let Some(provider_id) = nonempty(&query.provider_id) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId is required");
    };
    match claim_pending_for_provider(provider_id) {
        Ok(claimed) => Json(json!({ "claimed": claimed, "providerId": provider_id })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn workbuddy_status(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let Some(provider_id) = nonempty(&query.provider_id) else {
        return Json(json!({ "loggedIn": false, "accounts": [] })).into_response();
    };
    match codex_app_transfer_gemini_oauth::workbuddy::pool::list_pool(provider_id) {
        Ok(accounts) => {
            let now = codex_app_transfer_gemini_oauth::workbuddy::token::unix_now_ms();
            let list: Vec<_> = accounts
                .iter()
                .map(|account| {
                    json!({
                        "uid": account.uid,
                        "display": account.display,
                        "nickname": account.nickname,
                        "isActive": account.is_active,
                        "exhausted": account.exhausted_until > now,
                        "exhaustedUntil": account.exhausted_until,
                    })
                })
                .collect();
            Json(json!({ "loggedIn": !list.is_empty(), "accounts": list })).into_response()
        }
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn workbuddy_login(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let Some(provider_id) = nonempty(&query.provider_id).map(str::to_string) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId is required");
    };
    let http = match oauth_http_client() {
        Ok(http) => http,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    match run_workbuddy_login(&http, |url| open_auth_url("workbuddy", url), None).await {
        Ok(cred) => {
            let nickname = cred.nickname.clone();
            let obtained_at = cred.obtained_at_ms;
            match codex_app_transfer_gemini_oauth::workbuddy::pool::add_account(
                &provider_id,
                cred,
            ) {
                Ok(uid) => Json(json!({
                    "loggedIn": true,
                    "nickname": nickname,
                    "userId": uid,
                    "obtainedAt": obtained_at,
                }))
                .into_response(),
                Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
            }
        }
        Err(WorkbuddyError::Cancelled) => {
            Json(json!({ "loggedIn": false, "cancelled": true })).into_response()
        }
        Err(error) => Json(json!({ "loggedIn": false, "error": error.to_string() })).into_response(),
    }
}

async fn workbuddy_remove_account(Query(query): Query<AccountQuery>) -> impl IntoResponse {
    let (Some(provider_id), Some(uid)) = (nonempty(&query.provider_id), nonempty(&query.uid)) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId and uid are required");
    };
    match codex_app_transfer_gemini_oauth::workbuddy::pool::remove_account(provider_id, uid) {
        Ok(()) => Json(json!({ "removed": true })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn workbuddy_switch_account(Query(query): Query<AccountQuery>) -> impl IntoResponse {
    let (Some(provider_id), Some(uid)) = (nonempty(&query.provider_id), nonempty(&query.uid)) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId and uid are required");
    };
    match codex_app_transfer_gemini_oauth::workbuddy::pool::set_active(provider_id, uid) {
        Ok(()) => Json(json!({ "active": uid })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn qoder_status(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let Some(provider_id) = nonempty(&query.provider_id) else {
        return Json(json!({ "loggedIn": false, "accounts": [] })).into_response();
    };
    match codex_app_transfer_gemini_oauth::qoder::pool::list_pool(provider_id) {
        Ok(accounts) => {
            let now = codex_app_transfer_gemini_oauth::qoder::token::unix_now_ms();
            let list: Vec<_> = accounts
                .iter()
                .map(|account| {
                    json!({
                        "uid": account.uid,
                        "display": account.display,
                        "nickname": account.nickname,
                        "isActive": account.is_active,
                        "exhausted": account.exhausted_until > now,
                        "exhaustedUntil": account.exhausted_until,
                    })
                })
                .collect();
            Json(json!({ "loggedIn": !list.is_empty(), "accounts": list })).into_response()
        }
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn qoder_login(Query(query): Query<ProviderIdQuery>) -> impl IntoResponse {
    let Some(provider_id) = nonempty(&query.provider_id).map(str::to_string) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId is required");
    };
    let http = match oauth_http_client() {
        Ok(http) => http,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    match run_qoder_login(&http, |url| open_auth_url("qoder", url), None).await {
        Ok(cred) => {
            let nickname = cred.nickname.clone();
            let obtained_at = cred.obtained_at_ms;
            match codex_app_transfer_gemini_oauth::qoder::pool::add_account(&provider_id, cred) {
                Ok(uid) => Json(json!({
                    "loggedIn": true,
                    "nickname": nickname,
                    "userId": uid,
                    "obtainedAt": obtained_at,
                }))
                .into_response(),
                Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
            }
        }
        Err(QoderError::Cancelled) => {
            Json(json!({ "loggedIn": false, "cancelled": true })).into_response()
        }
        Err(error) => Json(json!({ "loggedIn": false, "error": error.to_string() })).into_response(),
    }
}

async fn qoder_remove_account(Query(query): Query<AccountQuery>) -> impl IntoResponse {
    let (Some(provider_id), Some(uid)) = (nonempty(&query.provider_id), nonempty(&query.uid)) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId and uid are required");
    };
    match codex_app_transfer_gemini_oauth::qoder::pool::remove_account(provider_id, uid) {
        Ok(()) => Json(json!({ "removed": true })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn qoder_switch_account(Query(query): Query<AccountQuery>) -> impl IntoResponse {
    let (Some(provider_id), Some(uid)) = (nonempty(&query.provider_id), nonempty(&query.uid)) else {
        return json_error(StatusCode::BAD_REQUEST, "providerId and uid are required");
    };
    match codex_app_transfer_gemini_oauth::qoder::pool::set_active(provider_id, uid) {
        Ok(()) => Json(json!({ "active": uid })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

async fn grok_build_status() -> impl IntoResponse {
    let store = match GrokBuildCredentialStore::single() {
        Ok(store) => store,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    match store.load() {
        Ok(Some(cred)) => Json(json!({
            "loggedIn": true,
            "email": cred.email,
            "userId": cred.user_id,
            "expiryDate": cred.expiry_date,
        }))
        .into_response(),
        Ok(None) => Json(json!({ "loggedIn": false })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

fn manual_code_slot() -> &'static Mutex<Option<oneshot::Sender<String>>> {
    static SLOT: OnceLock<Mutex<Option<oneshot::Sender<String>>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(None))
}

#[derive(Deserialize)]
struct SubmitCodeBody {
    code: String,
}

async fn grok_build_submit_code(Json(body): Json<SubmitCodeBody>) -> impl IntoResponse {
    match manual_code_slot()
        .lock()
        .unwrap_or_else(|poison| poison.into_inner())
        .take()
    {
        Some(sender) => Json(json!({ "accepted": sender.send(body.code).is_ok() })).into_response(),
        None => Json(json!({ "accepted": false, "error": "no login in progress" })).into_response(),
    }
}

async fn grok_build_logout_handler() -> impl IntoResponse {
    match grok_build_logout() {
        Ok(()) => Json(json!({ "loggedIn": false })).into_response(),
        Err(error) => json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    }
}

fn extract_manual_code(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.contains("code=") {
        let parsed = reqwest::Url::parse(trimmed)
            .or_else(|_| reqwest::Url::parse(&format!("http://127.0.0.1/?{trimmed}")))
            .ok();
        if let Some(url) = parsed {
            if let Some((_, value)) = url.query_pairs().find(|(key, _)| key == "code") {
                if !value.is_empty() {
                    return value.into_owned();
                }
            }
        }
    }
    trimmed.to_string()
}

struct CallbackParams {
    code: String,
    state: String,
}

enum CaptureError {
    Timeout,
    Denied(String),
}

async fn read_request_target(stream: &mut tokio::net::TcpStream) -> Option<String> {
    let mut buffer = [0u8; 8192];
    let size = stream.read(&mut buffer).await.ok()?;
    if size == 0 {
        return None;
    }
    let head = String::from_utf8_lossy(&buffer[..size]);
    head.lines()
        .next()?
        .split_whitespace()
        .nth(1)
        .map(str::to_string)
}

async fn write_html_response(stream: &mut tokio::net::TcpStream, status: &str, body_html: &str) {
    let body = format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Grok Login</title></head>\
         <body style=\"font-family:system-ui;text-align:center;padding-top:15vh;color:#222\">{body_html}</body></html>"
    );
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.as_bytes().len()
    );
    let _ = stream.write_all(response.as_bytes()).await;
    let _ = stream.flush().await;
}

enum ConnOutcome {
    Success(CallbackParams),
    Denied(String),
    Ignore,
}

async fn handle_conn(stream: &mut tokio::net::TcpStream, expected_state: &str) -> ConnOutcome {
    let Some(target) = read_request_target(stream).await else {
        write_html_response(stream, "400 Bad Request", "<h2>Bad Request</h2>").await;
        return ConnOutcome::Ignore;
    };
    if !target.starts_with("/callback") {
        write_html_response(stream, "404 Not Found", "").await;
        return ConnOutcome::Ignore;
    }
    let pairs: HashMap<String, String> =
        reqwest::Url::parse(&format!("http://127.0.0.1{target}"))
            .map(|url| url.query_pairs().into_owned().collect())
            .unwrap_or_default();
    if let Some(err) = pairs.get("error") {
        if pairs.get("state").map(String::as_str) != Some(expected_state) {
            write_html_response(stream, "400 Bad Request", "<h2>State mismatch</h2>").await;
            return ConnOutcome::Ignore;
        }
        let desc = pairs
            .get("error_description")
            .cloned()
            .unwrap_or_else(|| err.clone());
        write_html_response(stream, "200 OK", "<h2>Authorization did not complete</h2>").await;
        return ConnOutcome::Denied(desc);
    }
    match (pairs.get("code"), pairs.get("state")) {
        (Some(code), Some(state)) if !code.is_empty() && state == expected_state => {
            write_html_response(stream, "200 OK", "<h2>Login completed</h2>").await;
            ConnOutcome::Success(CallbackParams {
                code: code.clone(),
                state: state.clone(),
            })
        }
        (Some(_), Some(_)) => {
            write_html_response(stream, "400 Bad Request", "<h2>State mismatch</h2>").await;
            ConnOutcome::Ignore
        }
        _ => {
            write_html_response(stream, "400 Bad Request", "<h2>Missing code</h2>").await;
            ConnOutcome::Ignore
        }
    }
}

async fn capture_callback(
    listener: TcpListener,
    expected_state: &str,
    timeout: Duration,
) -> Result<CallbackParams, CaptureError> {
    let deadline = tokio::time::sleep(timeout);
    tokio::pin!(deadline);
    loop {
        tokio::select! {
            _ = &mut deadline => return Err(CaptureError::Timeout),
            accept = listener.accept() => {
                let mut stream = match accept {
                    Ok((stream, _)) => stream,
                    Err(_) => continue,
                };
                match tokio::time::timeout(CONN_HANDLE_TIMEOUT, handle_conn(&mut stream, expected_state)).await {
                    Ok(ConnOutcome::Success(params)) => return Ok(params),
                    Ok(ConnOutcome::Denied(desc)) => return Err(CaptureError::Denied(desc)),
                    Ok(ConnOutcome::Ignore) | Err(_) => continue,
                }
            }
        }
    }
}

async fn grok_build_login() -> impl IntoResponse {
    let http = match oauth_http_client() {
        Ok(http) => http,
        Err(error) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()),
    };
    let auth_req = match prepare_grok_build_authorization(&http, REDIRECT_URI).await {
        Ok(auth_req) => auth_req,
        Err(error) => {
            return Json(json!({ "loggedIn": false, "error": error.to_string() })).into_response()
        }
    };
    let listener = match TcpListener::bind(("127.0.0.1", LOOPBACK_PORT)).await {
        Ok(listener) => listener,
        Err(error) => {
            return Json(json!({
                "loggedIn": false,
                "error": format!("local callback port {LOOPBACK_PORT} is busy: {error}"),
            }))
            .into_response()
        }
    };
    open_auth_url("grok-build", &auth_req.authorize_url);

    let (code_tx, code_rx) = oneshot::channel::<String>();
    *manual_code_slot()
        .lock()
        .unwrap_or_else(|poison| poison.into_inner()) = Some(code_tx);
    let capture = tokio::select! {
        callback = capture_callback(listener, &auth_req.state, LOGIN_TIMEOUT) => callback,
        manual = code_rx => match manual {
            Ok(raw) => {
                let code = extract_manual_code(&raw);
                if code.is_empty() {
                    Err(CaptureError::Denied("pasted content does not contain an authorization code".into()))
                } else {
                    Ok(CallbackParams { code, state: auth_req.state.clone() })
                }
            }
            Err(_) => Err(CaptureError::Denied("manual code submission was cancelled".into())),
        },
    };
    manual_code_slot()
        .lock()
        .unwrap_or_else(|poison| poison.into_inner())
        .take();

    let result = match capture {
        Ok(callback) => complete_grok_build_login(&http, &auth_req, &callback.code, &callback.state).await,
        Err(CaptureError::Timeout) => Err(GrokBuildError::DeviceCodeExpired),
        Err(CaptureError::Denied(desc)) => Err(GrokBuildError::OAuth {
            error: "access_denied".into(),
            description: desc,
        }),
    };
    match result {
        Ok(cred) => Json(json!({
            "loggedIn": true,
            "email": cred.email,
            "userId": cred.user_id,
            "obtainedAt": cred.obtained_at_ms,
        }))
        .into_response(),
        Err(error) => Json(json!({ "loggedIn": false, "error": error.to_string() })).into_response(),
    }
}
