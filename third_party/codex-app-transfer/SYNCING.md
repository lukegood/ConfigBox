# Syncing `codex-app-transfer` into ConfigBox

This vendored tree intentionally keeps only the headless forwarding stack used by ConfigBox.

## Keep

- `crates/adapters`
- `crates/proxy`
- `crates/registry`
- `crates/gemini_oauth`
- ConfigBox's local `crates/gateway`

These crates form the forwarding runtime. When upstream changes touch request conversion, provider routing, auth rewriting, protocol adapters, presets, or proxy tests, review and sync them here.

## Do not re-import

- Frontend / Tauri UI
- Desktop-only management code
- Upstream `crates/codex_integration`

ConfigBox owns Codex CLI takeover in `app/gateway.py`. Keep that integration local instead of reviving the upstream desktop implementation.
ConfigBox also keeps a small headless OAuth admin surface in local `crates/gateway`
for `gemini_cli_oauth` and `antigravity_oauth`; preserve that local bridge when
syncing gateway-related code.

## ConfigBox-local integration responsibilities

When upstream changes affect Codex CLI behavior, port only the useful semantics into `app/gateway.py`:

- `model_catalog_json`
- `model_context_window`
- restore/snapshot rules for keys ConfigBox itself manages

Do not blindly copy upstream restore machinery. ConfigBox uses a single gateway lifecycle snapshot, not the desktop app's multi-session recovery UX.

## Sync checklist

1. Compare upstream changes under:
   - `crates/adapters`
   - `crates/proxy`
   - `crates/registry`
   - `crates/gemini_oauth`
2. Ignore pure UI / docs / desktop-only changes unless they describe runtime behavior that must be reimplemented locally.
3. Preserve ConfigBox-local files:
   - `crates/gateway`
   - root workspace membership without `crates/codex_integration`
4. After syncing forwarding crates, check whether ConfigBox config normalization also needs updates:
   - new `apiFormat` values
   - new model-mapping behavior
   - new preset fields used by the forwarding runtime
   - OAuth / provider credential semantics that the local gateway admin routes must still expose
5. Run:
   - `cargo test` in this vendored workspace
   - Python gateway tests

## Current divergence by design

- ConfigBox writes `[model_providers.configbox_gateway]` and keeps `model_provider = "configbox_gateway"`.
- Upstream desktop integration often writes `model_provider = "openai"`; do not import that behavior here.
- ConfigBox snapshot state lives in `codex-snapshot.json`; upstream desktop recovery directories are intentionally omitted.
- ConfigBox exposes only the headless OAuth status/login/logout routes needed by its own UI; upstream desktop admin handlers remain intentionally omitted.
