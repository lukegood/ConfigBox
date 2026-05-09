<div align="center">
  <img src="logo_config.png" alt="ConfigBox" width="800">
  <h1>ConfigBox: Web-Based Configuration Switcher for Claude Code / Codex / OpenCode</h1>
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/lukegood/ConfigBox">
  <img alt="GitHub forks" src="https://img.shields.io/github/forks/lukegood/ConfigBox">
  <img alt="GitHub License" src="https://img.shields.io/github/license/lukegood/ConfigBox">
  <p>
    <a href="README.md">简体中文</a> |
    <a href="README.en.md">English</a>
  </p>
</div>

ConfigBox is a Dockerized web management tool for viewing, editing, and switching Claude Code, Codex, and OpenCode configuration files from your browser. ConfigBox includes Codex forwarding capabilities, allowing third-party models to connect to Codex. ConfigBox supports Linux, macOS, and Windows.

## Recent Updates

:loudspeaker: 2026.05.06 v0.2.0, improved Codex configuration support

:loudspeaker: 2026.05.07 v0.3.3, added built-in Codex forwarding based on [Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer), allowing Chinese and other third-party models to connect to Codex; fixed MiniMax forwarding errors and frontend issues

:loudspeaker: 2026.05.09 v0.4.0, added platform-specific Docker deployment directories for Linux, macOS, and Windows, plus bilingual README and cross-platform build instructions

## Screenshot

<img src="yanshi.png" alt="ConfigBox screenshot" width="800">

## Requirements

- Docker installed
- Host `.claude`, `.codex`, and `.configbox` directories available for Docker bind mounts

## Installation

### Option 1: Use the Published Image

<details open>
<summary><strong>Linux</strong></summary>

- Clone this repository:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```bash
cd deploy/linux
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- Find your user id:

```bash
id -u
id -g
```

- Edit environment variables

Edit `.env`, replace `yourname` with your username, and set `CONFIGBOX_UID` / `CONFIGBOX_GID` to the output of `id -u` / `id -g` above. These values are required on Linux; if they are missing, Docker Compose fails early instead of letting the container fail later with directory permission errors.

- Set the login password

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/work" cloudcollector/configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```bash
docker compose up -d
```

</details>

<details>
<summary><strong>macOS</strong></summary>

- Clone this repository:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```bash
cd deploy/macos
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- Edit environment variables

Edit `.env` and replace `/Users/yourname` with your user directory.

- Set the login password

```bash
docker run --rm -it -v "$PWD:/work" cloudcollector/configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```bash
docker compose up -d
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

- Clone this repository:

```powershell
git clone https://github.com/lukegood/ConfigBox
Set-Location ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```powershell
Set-Location deploy\windows
Copy-Item .env.example .env
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude", "$env:USERPROFILE\.codex", "$env:USERPROFILE\.config\opencode", "$env:USERPROFILE\.configbox" | Out-Null
if (!(Test-Path "$env:USERPROFILE\.claude\settings.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.claude\settings.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\auth.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.codex\auth.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\config.toml")) { New-Item -ItemType File -Force "$env:USERPROFILE\.codex\config.toml" | Out-Null }
if (!(Test-Path "$env:USERPROFILE\.config\opencode\config.json")) { '{"$schema":"https://opencode.ai/config.json","provider":{}}' | Set-Content -Encoding ascii "$env:USERPROFILE\.config\opencode\config.json" }
```

- Edit environment variables

Edit `.env` and replace `C:/Users/yourname` with your user directory. Use forward slashes in Windows paths, for example `C:/Users/Alice/.codex`.

- Set the login password

```powershell
docker run --rm -it -v "$($PWD.Path):/work" cloudcollector/configbox:latest `
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```powershell
docker compose up -d
```

</details>

Open after startup:

```text
http://127.0.0.1:8787
```

For a remote host, use:

```text
http://HOST_IP:8787
```

### Option 2: Build From Source With Docker

Local builds compile the frontend, backend image, and bundled `codex-gateway` inside Docker. Enter the matching platform directory, prepare `.env`, then layer `docker-compose.build.yml`.

<details>
<summary><strong>Linux</strong></summary>

- Clone this repository:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```bash
cd deploy/linux
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- Find your user id:

```bash
id -u
id -g
```

- Edit environment variables

Edit `.env`, replace `yourname` with your username, and set `CONFIGBOX_UID` / `CONFIGBOX_GID` to the output of `id -u` / `id -g` above. These values are required on Linux; if they are missing, Docker Compose fails early instead of letting the container fail later with directory permission errors.

- Build the image

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- Set the login password

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/work" configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

<details>
<summary><strong>macOS</strong></summary>

- Clone this repository:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```bash
cd deploy/macos
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- Edit environment variables

Edit `.env` and replace `/Users/yourname` with your user directory.

- Build the image

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- Set the login password

```bash
docker run --rm -it -v "$PWD:/work" configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

- Clone this repository:

```powershell
git clone https://github.com/lukegood/ConfigBox
Set-Location ConfigBox
```

- Prepare directories and files. These commands will not overwrite your local files:

```powershell
Set-Location deploy\windows
Copy-Item .env.example .env
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude", "$env:USERPROFILE\.codex", "$env:USERPROFILE\.config\opencode", "$env:USERPROFILE\.configbox" | Out-Null
if (!(Test-Path "$env:USERPROFILE\.claude\settings.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.claude\settings.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\auth.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.codex\auth.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\config.toml")) { New-Item -ItemType File -Force "$env:USERPROFILE\.codex\config.toml" | Out-Null }
if (!(Test-Path "$env:USERPROFILE\.config\opencode\config.json")) { '{"$schema":"https://opencode.ai/config.json","provider":{}}' | Set-Content -Encoding ascii "$env:USERPROFILE\.config\opencode\config.json" }
```

- Edit environment variables

Edit `.env` and replace `C:/Users/yourname` with your user directory. Use forward slashes in Windows paths, for example `C:/Users/Alice/.codex`.

- Build the image

```powershell
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- Set the login password

```powershell
docker run --rm -it -v "$($PWD.Path):/work" configbox:latest `
  python -m app.password_hash --env-file /work/.env
```

- Start the image

```powershell
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

If dependency downloads are slow during Docker builds, adjust these values in the platform `.env` file:

```env
NPM_REGISTRY=https://registry.npmmirror.com
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

## Environment Variables

Each platform directory has its own `.env.example`. Main variables:

| Variable | Description |
| --- | --- |
| `CLAUDE_DIR` | Host Claude Code config directory, mounted to `/config/claude` |
| `CODEX_DIR` | Host Codex config directory, mounted to `/config/codex` |
| `OPENCODE_DIR` | Host OpenCode config directory, mounted to `/config/opencode` |
| `CONFIGBOX_DATA_DIR` | Profiles, backups, gateway config, and logs |
| `CONFIGBOX_UID` / `CONFIGBOX_GID` | Linux only. Required container user, usually `id -u` / `id -g` |
| `APP_USERNAME` | Web login username |
| `APP_PASSWORD_HASH` | Recommended web login password hash |
| `SESSION_SECRET` | Cookie signing secret |
| `APP_COOKIE_SECURE` | Set to `true` behind HTTPS reverse proxies |
| `CODEX_GATEWAY_PORT` | Host port for Codex Gateway |
| `CODEX_GATEWAY_PUBLIC_HOST` | Gateway hostname written to Codex config, default `127.0.0.1` |

Recommended authentication settings:

```env
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=pbkdf2_sha256$$...
SESSION_SECRET=a-long-random-secret
```

For long-term use, prefer `APP_PASSWORD_HASH` instead of plaintext `APP_PASSWORD`.

## Remote Access

Default ports:

```yaml
ports:
  - "8787:8787"
  - "127.0.0.1:18080:18080"
```

The Web UI is available on `8787`. Codex Gateway is mapped to host `127.0.0.1:18080` by default, intended for Codex CLI or VS Code Codex running on the same machine.

For HTTPS reverse proxies:

```env
APP_COOKIE_SECURE=true
```

For plain HTTP, SSH tunnels, or VS Code Ports forwarding:

```env
APP_COOKIE_SECURE=false
```

## Usage

### Active Config

<img src="yanshi.png" alt="ConfigBox screenshot" width="800">

Choose `Claude`, `Codex`, or `OpenCode` on the left, then open `Current Config`. These are the real active config files:

```text
Claude -> .claude/settings.json
Codex  -> .codex/auth.json + .codex/config.toml
OpenCode -> .config/opencode/config.json
```

When you save, ConfigBox validates JSON/TOML, backs up the old version, then writes atomically. If a file changed outside the web UI after the page was opened, ConfigBox reports a conflict instead of overwriting it.

### Profiles

A Profile is a saved configuration set that can be edited and activated later. Profiles are stored under `CONFIGBOX_DATA_DIR`:

```text
profiles/claude/
profiles/codex/
```

Activating a Profile overwrites the real config files. A Codex Profile stores and activates both `auth.json` and `config.toml` together.

### OpenCode Provider / Model Editing

Choose `OpenCode` on the left to edit the full `config.json` directly. When the active config or a Profile is editable, the editor shows an OpenCode helper above the file editor for adding Providers or Models. These actions first update the editor content; click `Save` to write the real file.

### Codex Gateway for Third-Party Models

Choose `Codex`, then open `Gateway`. The gateway forwards Codex Responses API requests to OpenAI Chat-compatible upstream providers.

```text
Add Provider -> Start Gateway -> Use it in Codex / VS Code Codex extension
```

When started, ConfigBox clears previous gateway logs, starts local `codex-gateway`, and writes `.codex/auth.json` plus `config.toml`. When stopped, it stops `codex-gateway` and restores the previous Codex config.

Gateway logs are stored on the host:

```text
CONFIGBOX_DATA_DIR/codex-gateway/logs/
```

## Mounts

Container paths:

```text
/config/claude/settings.json
/config/codex/auth.json
/config/codex/config.toml
/config/opencode/config.json
/data
/data/codex-gateway/config.json
/data/codex-gateway/logs/
```

Host mappings:

```text
CLAUDE_DIR         -> /config/claude
CODEX_DIR          -> /config/codex
OPENCODE_DIR       -> /config/opencode
CONFIGBOX_DATA_DIR -> /data
```

## API Check

The API still supports Basic Auth for command-line checks:

```bash
curl -u admin:your-password http://127.0.0.1:8787/api/tools
curl -u admin:your-password http://127.0.0.1:8787/api/configs/codex/active
```

The browser UI uses `/api/login` and an HttpOnly cookie.

## FAQ

### How should Windows paths be written?

Use forward slashes in `.env`:

```env
CLAUDE_DIR=C:/Users/yourname/.claude
CODEX_DIR=C:/Users/yourname/.codex
OPENCODE_DIR=C:/Users/yourname/.config/opencode
CONFIGBOX_DATA_DIR=C:/Users/yourname/.configbox
```

If you run Docker Engine inside WSL2 and want to manage Windows user directories, use WSL paths such as `/mnt/c/Users/yourname/.codex`.

### What if Windows/macOS mounted directories are not writable?

Check that your Docker runtime is allowed to share your user directory. Docker Desktop, OrbStack, Colima, and similar tools may have separate file-sharing settings.

### What if Linux containers keep restarting with /data permission errors?

Check that `CONFIGBOX_UID` / `CONFIGBOX_GID` in `.env` match the current user:

```bash
id -u
id -g
```

### What if Docker builds download dependencies slowly?

Adjust these values in the platform `.env` file:

```env
NPM_REGISTRY=
PIP_INDEX_URL=
```

## Security

ConfigBox can view and edit sensitive config files. Treat it as an administrator tool.

Recommendations:

- Use `APP_PASSWORD_HASH`; avoid long-term plaintext `APP_PASSWORD`
- Use a strong random `SESSION_SECRET`
- Use HTTPS for public deployments
- Restrict access with firewall or security-group rules whenever possible
- Do not commit `.env`, `.claude`, `.codex`, `.config/opencode`, or `.configbox` to public repositories

## Credits

- ConfigBox's Codex Gateway forwarding is based on [Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer). Thanks to the author for the open-source work.

<a href="https://linux.do">
  <img src="https://ldimg.ldcstore.com/integer/20260425_linuxdo_vtx01n.png" alt="linuxdo">
</a>
