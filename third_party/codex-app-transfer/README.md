# Vendored Codex Gateway Core

This directory contains the minimal Rust crates needed to build ConfigBox's
headless `codex-gateway` sidecar.

Source: https://github.com/Cmochance/codex-app-transfer

License: MIT. See `LICENSE.txt`.

Only the proxy, protocol adapters, registry, Codex integration helpers, and
ConfigBox's headless gateway binary are kept here. Desktop/Tauri UI, docs,
release tooling, screenshots, feedback worker, and other non-runtime assets are
intentionally excluded from this vendored copy.
