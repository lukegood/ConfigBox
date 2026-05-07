use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use axum::{routing::get, Json, Router};
use codex_app_transfer_proxy::{build_router, proxy_telemetry, StaticResolver};
use codex_app_transfer_registry::{load_raw_config, Config};
use serde_json::json;
use tokio::net::TcpListener;

#[derive(Debug, Clone)]
struct Args {
    config: PathBuf,
    host: String,
    port: u16,
    log_dir: Option<PathBuf>,
}

impl Args {
    fn parse() -> Result<Self, String> {
        let mut config: Option<PathBuf> = std::env::var_os("CODEX_GATEWAY_CONFIG")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("CODEX_APP_TRANSFER_CONFIG_FILE").map(PathBuf::from)
            });
        let mut host = std::env::var("CODEX_GATEWAY_HOST").unwrap_or_else(|_| "127.0.0.1".to_owned());
        let mut port = std::env::var("CODEX_GATEWAY_PORT")
            .ok()
            .and_then(|raw| raw.parse::<u16>().ok())
            .unwrap_or(18080);
        let mut log_dir = std::env::var_os("CODEX_GATEWAY_LOG_DIR").map(PathBuf::from);

        let mut args = std::env::args().skip(1);
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--config" => {
                    config = Some(PathBuf::from(
                        args.next().ok_or_else(|| "--config requires a path".to_owned())?,
                    ));
                }
                "--host" => {
                    host = args.next().ok_or_else(|| "--host requires a value".to_owned())?;
                }
                "--port" => {
                    let raw = args.next().ok_or_else(|| "--port requires a value".to_owned())?;
                    port = raw
                        .parse::<u16>()
                        .map_err(|_| format!("invalid --port value: {raw}"))?;
                }
                "--log-dir" => {
                    log_dir = Some(PathBuf::from(
                        args.next().ok_or_else(|| "--log-dir requires a path".to_owned())?,
                    ));
                }
                "--help" | "-h" => {
                    print_help();
                    std::process::exit(0);
                }
                other => {
                    return Err(format!("unknown argument: {other}"));
                }
            }
        }

        let config = config.unwrap_or_else(default_config_path);
        Ok(Self {
            config,
            host,
            port,
            log_dir,
        })
    }
}

fn default_config_path() -> PathBuf {
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    home.join(".configbox").join("codex-gateway").join("config.json")
}

fn print_help() {
    println!(
        "codex-gateway\n\n\
         Usage: codex-gateway [--config PATH] [--host HOST] [--port PORT] [--log-dir PATH]\n\n\
         Environment overrides:\n\
           CODEX_GATEWAY_CONFIG\n\
           CODEX_GATEWAY_HOST\n\
           CODEX_GATEWAY_PORT\n\
           CODEX_GATEWAY_LOG_DIR"
    );
}

#[tokio::main]
async fn main() {
    if let Err(error) = run().await {
        eprintln!("codex-gateway: {error}");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), String> {
    let args = Args::parse()?;
    configure_env(&args);
    let cfg = load_config(&args.config)?;
    if cfg.providers.is_empty() {
        return Err(format!(
            "no providers configured in {}",
            args.config.display()
        ));
    }

    let gateway_key = cfg.gateway_api_key.clone().filter(|key| !key.is_empty());
    let resolver = StaticResolver::new(gateway_key, cfg.providers, cfg.active_provider);
    let proxy = build_router(Arc::new(resolver));
    let app = Router::new()
        .route("/__health", get(health))
        .merge(proxy);
    let addr: SocketAddr = format!("{}:{}", args.host, args.port)
        .parse()
        .map_err(|e| format!("invalid listen address: {e}"))?;
    let listener = TcpListener::bind(addr)
        .await
        .map_err(|e| format!("bind {addr} failed: {e}"))?;
    let actual_addr = listener
        .local_addr()
        .map_err(|e| format!("read listener address failed: {e}"))?;

    proxy_telemetry()
        .logs
        .add("INFO", format!("codex-gateway listening on {actual_addr}"));
    eprintln!("codex-gateway listening on {actual_addr}");

    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .map_err(|e| format!("server error: {e}"))?;
    Ok(())
}

fn configure_env(args: &Args) {
    std::env::set_var("CODEX_APP_TRANSFER_CONFIG_FILE", &args.config);
    if let Some(parent) = args.config.parent() {
        std::env::set_var("CODEX_APP_TRANSFER_CONFIG_DIR", parent);
    }
    if let Some(log_dir) = &args.log_dir {
        std::env::set_var("CODEX_APP_TRANSFER_LOG_DIR", log_dir);
    }
}

fn load_config(path: &PathBuf) -> Result<Config, String> {
    let raw = load_raw_config(path).map_err(|e| format!("read config failed: {e}"))?;
    serde_json::from_value(raw).map_err(|e| format!("parse config failed: {e}"))
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({"ok": true, "service": "codex-gateway"}))
}
