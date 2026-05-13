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

## Why ConfigBox :raising_hand:

- A web-based tool that requires no software installation. Browser is all you need.

- Built on Docker, easy to use. No need to worry about cross-platform compatibility.

- Simple, practical, and efficient features. Rapid response to user needs. **PRs and code contributions are warmly welcome!**

## What It Does :muscle:

- ConfigBox is a Dockerized web management tool for visually managing and switching Claude Code, Codex, and OpenCode configuration files from your browser.

- Includes Codex forwarding capabilities, supporting third-party models such as GLM, Deepseek, and Kimi connecting to Codex. Built-in Codex forwarding based on [Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer) with ongoing updates tracking upstream.

- Supports Linux, macOS, and Windows. Supports Claude Code, Codex, and OpenCode.

**Contributions and PRs are welcome — become a contributor! :raising_hand:**

## Version Updates :sunny:

:loudspeaker: 2026.05.14 Released v0.5.2, synced upstream codex-app-transfer, fixed some Gateway frontend issues.

## Screenshot :camera:

<img src="yanshi.png" alt="ConfigBox screenshot" width="800">

## Requirements :mag_right:

- Docker installed

## Installation :hammer:

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

Edit `.env`, replace `yourname` with your username, and set `CONFIGBOX_UID` / `CONFIGBOX_GID` to the output of `id -u` / `id -g` above. These values are required on Linux; omitting them will cause errors.

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

Edit `.env` and replace `C:/Users/yourname` with your user directory. Windows paths must use forward slashes, e.g. `C:/Users/Alice/.codex`.

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

After starting, visit:

```text
http://127.0.0.1:8787
```

If deployed on a remote host, visit:

```text
http://HOST_IP:8787
```

### Option 2: Build from Source with Docker

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

Edit `.env`, replace `yourname` with your username, and set `CONFIGBOX_UID` / `CONFIGBOX_GID` to the output of `id -u` / `id -g` above. These values are required on Linux; omitting them will cause errors.

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

Edit `.env` and replace `C:/Users/yourname` with your user directory. Windows paths must use forward slashes, e.g. `C:/Users/Alice/.codex`.

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

## Environment Variables :battery:

| Variable | Description |
|---|---|
| `CLAUDE_DIR` | Host Claude config directory, mounted to `/config/claude` |
| `CODEX_DIR` | Host Codex config directory, mounted to `/config/codex` |
| `OPENCODE_DIR` | Host OpenCode config directory, mounted to `/config/opencode` |
| `CONFIGBOX_DATA_DIR` | ConfigBox profiles, backups, gateway config and logs directory |
| `CONFIGBOX_UID` / `CONFIGBOX_GID` | Linux only, container runtime user, required, recommended to set to `id -u` / `id -g` |
| `APP_USERNAME` | Web login username |
| `APP_PASSWORD_HASH` | Web login password hash, recommended |
| `SESSION_SECRET` | Cookie signing secret |
| `APP_COOKIE_SECURE` | Set to `true` behind HTTPS reverse proxies |
| `CODEX_GATEWAY_PORT` | Codex Gateway host port |
| `CODEX_GATEWAY_PUBLIC_HOST` | Gateway hostname written to Codex config, default `127.0.0.1` |

Recommended authentication settings:

```env
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=pbkdf2_sha256$$...
SESSION_SECRET=a-long-random-secret
```

For long-term use, prefer `APP_PASSWORD_HASH` instead of plaintext `APP_PASSWORD`.

## Remote Access :key:

Default ports:

```yaml
ports:
  - "8787:8787"
  - "127.0.0.1:18080:18080"
```

The Web UI is available on `8787`. Codex Gateway is mapped to host `127.0.0.1:18080` by default, intended for Codex CLI or VS Code Codex plugin running on the same machine.

For HTTPS reverse proxies:

```env
APP_COOKIE_SECURE=true
```

For plain HTTP, SSH tunnels, or VS Code Ports forwarding:

```env
APP_COOKIE_SECURE=false
```

## Usage :floppy_disk:

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

Click a `Profile` to edit it. Click `Activate` to overwrite the real config files with that Profile, completing the config switch. A Codex Profile stores and activates both `auth.json` and `config.toml` together.

### OpenCode Provider / Model Editing

Choose `OpenCode` on the left to edit the full `config.json` directly. When the active config or a Profile is editable, the editor shows an OpenCode helper above the file editor for adding Providers or Models. These actions first update the editor content; click `Save` to write the real file.

### Codex Gateway for Third-Party Models

Choose `Codex`, then open `Gateway`. The Gateway forwards Codex's Responses API requests to OpenAI Chat compatible upstreams.

```text
Add Provider -> Start Gateway -> Use in Codex / VS Code Codex plugin
```

When you click `Start`, ConfigBox clears previous Gateway logs, starts the local `codex-gateway`, and automatically writes `.codex/auth.json` and `config.toml`. When you click `Stop`, it stops the local `codex-gateway` and restores the Codex config to its pre-start state.

Gateway logs are stored on the host:

```text
CONFIGBOX_DATA_DIR/codex-gateway/logs/
```

## Data Mounts :cd:

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

## API Authentication :pencil2:

The API still supports Basic Auth for command-line checks:

```bash
curl -u admin:your_password http://127.0.0.1:8787/api/tools
curl -u admin:your_password http://127.0.0.1:8787/api/configs/codex/active
```

The browser UI uses `/api/login` and HttpOnly Cookies.

## FAQ :green_book:

### How should Windows paths be written?

Use forward slashes in `.env`:

```env
CLAUDE_DIR=C:/Users/yourname/.claude
CODEX_DIR=C:/Users/yourname/.codex
OPENCODE_DIR=C:/Users/yourname/.config/opencode
CONFIGBOX_DATA_DIR=C:/Users/yourname/.configbox
```

If you run Docker Engine inside WSL2 and want to manage Windows user directories, you can use WSL paths like `/mnt/c/Users/yourname/.codex`.

### What if Windows/macOS mounted directories are not writable?

Make sure Docker runtime allows sharing your user directory. Docker Desktop and similar tools may have directory sharing or file access permission settings.

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

## Security :microscope:

ConfigBox can view and edit sensitive config files. Treat it as an administrator tool.

Recommendations:

- Use `APP_PASSWORD_HASH`; avoid long-term plaintext `APP_PASSWORD`
- Use a strong random `SESSION_SECRET`
- Use HTTPS for public deployments
- Restrict access with firewall or security-group rules whenever possible
- Do not commit `.env`, `.claude`, `.codex`, `.config/opencode`, or `.configbox` to public repositories

## Credits & Community :golf:

- ConfigBox's Codex Gateway forwarding is based on [Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer). Thanks to the author for the open-source contribution.

<a href="https://linux.do">
  <img src="https://ldimg.ldcstore.com/integer/20260425_linuxdo_vtx01n.png" alt="linuxdo">
</a>
