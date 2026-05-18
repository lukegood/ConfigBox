<div align="center">
  <img src="logo_config.png" alt="ConfigBox" width="800">
  <h1>ConfigBox: Web端的Claude Code / Codex / OpenCode配置切换器</h1>
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/lukegood/ConfigBox">
  <img alt="GitHub forks" src="https://img.shields.io/github/forks/lukegood/ConfigBox">
  <img alt="GitHub License" src="https://img.shields.io/github/license/lukegood/ConfigBox">
  <p>
    <a href="README.md">简体中文</a> |
    <a href="README.en.md">English</a>
  </p>
</div>

## 为什么选择ConfigBox :raising_hand:

- Web端的工具，无需安装任何软件。浏览器提供一切服务的践行者。

- 基于Docker，更容易使用。无需考虑跨平台换工具的问题。

- 功能简洁实用，更高效。响应需求更迅速，**热忱欢迎提PR和贡献代码！**

## 能做什么 :muscle:

- ConfigBox是一个Docker化的Web管理工具，用于在浏览器中可视化管理和切换 Claude Code、Codex 与OpenCode的配置文件。

- 具备Codex转发功能，支持GLM、Deepseek、Kimi第三方模型接入Codex。已内置基于[Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer)的Codex转发能力并将持续追踪更新。

- 支持Linux、macOS 和 Windows平台。支持Claude Code, Codex和OpenCode。

**欢迎积极试用提PR，成为贡献者 :raising_hand:**

## 版本更新 :sunny:

v0.2.0: 5月6日更新，优化codex的配置方式。  
v0.3.3: 5月7日更新，加入codex转发功能，能够接入国模以及未实现response协议的模型。优化使用体验。  
v0.4.0: 5月9日更新，增加对MacOS和Windows平台的支持。  
v0.5.0: 5月10日更新，增加对OpenCode的支持。  
v0.5.2: 5月14日更新，同步上游codex转发网关的更改，修复gateway界面的前端。  
v0.5.3: 5月18日更新，优化配置切换逻辑，同步上游codex网关更新。   
v0.5.4: 5月18日更新，紧急修复codex网关失效的BUG。  

## 项目截图 :camera:

<img src="yanshi.png" alt="ConfigBox screenshot" width="800">

## 运行要求 :mag_right:

- 已安装 Docker

## 安装方式 :hammer:

### 方式一: 使用已发布镜像

<details open>
<summary><strong>Linux</strong></summary>

- git clone 本项目:
```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```bash
cd deploy/linux
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```
- 查找id
```bash
id -u
id -g
```
- 编辑环境变量

编辑 `.env`，把 `yourname` 改成你的用户名，并把 `CONFIGBOX_UID` / `CONFIGBOX_GID` 改成上面 `id -u` / `id -g` 的输出。这两个值在 Linux 下必填，否则会报错。

- 设置登录密码

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/work" cloudcollector/configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像
```bash
docker compose up -d
```

</details>

<details>
<summary><strong>macOS</strong></summary>

- git clone 本项目:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```bash
cd deploy/macos
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- 编辑环境变量

编辑 `.env`，把 `/Users/yourname` 改成你的用户目录。

- 设置登录密码

```bash
docker run --rm -it -v "$PWD:/work" cloudcollector/configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像

```bash
docker compose up -d
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

- git clone 本项目:

```powershell
git clone https://github.com/lukegood/ConfigBox
Set-Location ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```powershell
Set-Location deploy\windows
Copy-Item .env.example .env
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude", "$env:USERPROFILE\.codex", "$env:USERPROFILE\.config\opencode", "$env:USERPROFILE\.configbox" | Out-Null
if (!(Test-Path "$env:USERPROFILE\.claude\settings.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.claude\settings.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\auth.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.codex\auth.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\config.toml")) { New-Item -ItemType File -Force "$env:USERPROFILE\.codex\config.toml" | Out-Null }
if (!(Test-Path "$env:USERPROFILE\.config\opencode\config.json")) { '{"$schema":"https://opencode.ai/config.json","provider":{}}' | Set-Content -Encoding ascii "$env:USERPROFILE\.config\opencode\config.json" }
```

- 编辑环境变量

编辑 `.env`，把 `C:/Users/yourname` 改成你的用户目录。Windows 路径必须使用正斜杠，例如 `C:/Users/Alice/.codex`。

- 设置登录密码

```powershell
docker run --rm -it -v "$($PWD.Path):/work" cloudcollector/configbox:latest `
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像

```powershell
docker compose up -d
```

</details>

启动后访问：

```text
http://127.0.0.1:8787
```

如果部署在远程主机上，请访问：

```text
http://主机IP:8787
```

### 方式二: 从源码本地 Docker 构建

<details>
<summary><strong>Linux</strong></summary>

- git clone 本项目:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```bash
cd deploy/linux
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- 查找 id

```bash
id -u
id -g
```

- 编辑环境变量

编辑 `.env`，把 `yourname` 改成你的用户名，并把 `CONFIGBOX_UID` / `CONFIGBOX_GID` 改成上面 `id -u` / `id -g` 的输出。这两个值在 Linux 下必填；不填写时会报错。

- 构建镜像

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- 设置登录密码

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/work" configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

<details>
<summary><strong>macOS</strong></summary>

- git clone 本项目:

```bash
git clone https://github.com/lukegood/ConfigBox
cd ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```bash
cd deploy/macos
cp .env.example .env
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.configbox"
[ -f "$HOME/.claude/settings.json" ] || printf '{}\n' > "$HOME/.claude/settings.json"
[ -f "$HOME/.codex/auth.json" ] || printf '{}\n' > "$HOME/.codex/auth.json"
[ -f "$HOME/.codex/config.toml" ] || touch "$HOME/.codex/config.toml"
[ -f "$HOME/.config/opencode/config.json" ] || printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "provider": {}\n}\n' > "$HOME/.config/opencode/config.json"
```

- 编辑环境变量

编辑 `.env`，把 `/Users/yourname` 改成你的用户目录。

- 构建镜像

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- 设置登录密码

```bash
docker run --rm -it -v "$PWD:/work" configbox:latest \
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

- git clone 本项目:

```powershell
git clone https://github.com/lukegood/ConfigBox
Set-Location ConfigBox
```

- 准备目录和文件。以下命令不会覆盖你的本地文件，可放心执行:

```powershell
Set-Location deploy\windows
Copy-Item .env.example .env
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude", "$env:USERPROFILE\.codex", "$env:USERPROFILE\.config\opencode", "$env:USERPROFILE\.configbox" | Out-Null
if (!(Test-Path "$env:USERPROFILE\.claude\settings.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.claude\settings.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\auth.json")) { "{}" | Set-Content -Encoding ascii "$env:USERPROFILE\.codex\auth.json" }
if (!(Test-Path "$env:USERPROFILE\.codex\config.toml")) { New-Item -ItemType File -Force "$env:USERPROFILE\.codex\config.toml" | Out-Null }
if (!(Test-Path "$env:USERPROFILE\.config\opencode\config.json")) { '{"$schema":"https://opencode.ai/config.json","provider":{}}' | Set-Content -Encoding ascii "$env:USERPROFILE\.config\opencode\config.json" }
```

- 编辑环境变量

编辑 `.env`，把 `C:/Users/yourname` 改成你的用户目录。Windows 路径使用正斜杠，例如 `C:/Users/Alice/.codex`。

- 构建镜像

```powershell
docker compose -f docker-compose.yml -f docker-compose.build.yml build
```

- 设置登录密码

```powershell
docker run --rm -it -v "$($PWD.Path):/work" configbox:latest `
  python -m app.password_hash --env-file /work/.env
```

- 启动镜像

```powershell
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

</details>

如果 Docker 构建依赖下载慢，可以在对应平台目录的 `.env` 中调整：

```env
NPM_REGISTRY=https://registry.npmmirror.com
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

## 环境变量 :battery:

主要变量如下：

| 变量 | 说明 |
| --- | --- |
| `CLAUDE_DIR` | 宿主机 Claude Code 配置目录，挂载到容器 `/config/claude` |
| `CODEX_DIR` | 宿主机 Codex 配置目录，挂载到容器 `/config/codex` |
| `OPENCODE_DIR` | 宿主机 OpenCode 配置目录，挂载到容器 `/config/opencode` |
| `CONFIGBOX_DATA_DIR` | ConfigBox 的 profiles、history、gateway 配置和日志目录 |
| `CONFIGBOX_UID` / `CONFIGBOX_GID` | Linux 专用，容器运行用户，必填，建议设置为 `id -u` / `id -g` |
| `APP_USERNAME` | Web 登录用户名 |
| `APP_PASSWORD_HASH` | Web 登录密码哈希，推荐使用 |
| `SESSION_SECRET` | Cookie 签名密钥 |
| `APP_COOKIE_SECURE` | HTTPS 反向代理下设为 `true` |
| `CODEX_GATEWAY_PORT` | Codex Gateway 宿主机端口 |
| `CODEX_GATEWAY_PUBLIC_HOST` | 写入 Codex 配置的 Gateway 主机名，默认 `127.0.0.1` |
| `CODEX_MODEL_CATALOG_CLIENT_PATH` | 写入 Codex 配置、供宿主机 Codex / VS Code 插件读取的模型目录路径；Docker 部署会自动设为宿主机 `CONFIGBOX_DATA_DIR/codex-gateway/codex-model-catalog.json` |

推荐认证配置：

```env
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=pbkdf2_sha256$$...
SESSION_SECRET=一串长随机字符串
```

长期使用推荐 `APP_PASSWORD_HASH`，不要使用明文 `APP_PASSWORD`。

## 远程访问 :key:

默认端口：

```yaml
ports:
  - "8787:8787"
  - "127.0.0.1:18080:18080"
```

Web UI 通过 `8787` 访问。Codex Gateway默认只把宿主机 `127.0.0.1:18080` 映射到容器，供同一台机器上的 Codex CLI / VS Code Codex 插件访问。

如果使用 HTTPS 反向代理，请设置：

```env
APP_COOKIE_SECURE=true
```

如果使用普通 HTTP、SSH 隧道、VS Code Ports 转发，请保持：

```env
APP_COOKIE_SECURE=false
```

## 使用教程 :floppy_disk:

### Profiles 与 History

<img src="yanshi.png" alt="ConfigBox screenshot" width="800">

ConfigBox 现在以 `Profile` 作为唯一配置真源。左侧选择 `Claude`、`Codex` 或 `OpenCode` 后，直接编辑对应 Profile；点击 `启用` 时，系统会把该 Profile 投影到真实生效文件中：

```text
Claude -> .claude/settings.json
Codex  -> .codex/auth.json + .codex/config.toml
OpenCode -> .config/opencode/config.json
```

Profile 默认存放在宿主机 `CONFIGBOX_DATA_DIR` 下：

```text
profiles/claude/
profiles/codex/
history/claude/
history/codex/
```

保存 Profile 时，系统会先把旧版本写入 `History`，再校验 JSON/TOML 并原子写入新版本；如果这个 Profile 当前已启用，真实配置文件会同步更新。每个 Profile 都可以拥有多条历史记录，左侧 `History` 会按时间线展示，并在标签中标明归属的 Profile。Codex 的一个 Profile 会同时保存 `auth.json` 和 `config.toml`。

### OpenCode Provider / Model 编辑

左侧选择 `OpenCode` 后，可以直接编辑 Profile 中的完整 `config.json`。Profile 处于可编辑状态时，编辑器上方会显示 OpenCode 配置助手，可通过按钮添加 Provider 或 Model。添加动作会先写入编辑器内容，确认无误后点击 `保存` 才会写入 Profile；若该 Profile 已启用，真实文件也会同步更新。

### Codex Gateway 接入第三方模型

左侧选择 `Codex`，点击 `Gateway`。Gateway 用于把 Codex 的 Responses API 请求转发到 OpenAI Chat 兼容上游。

```text
添加 Provider -> 启动 Gateway -> 在 Codex / VS Code Codex 插件中使用
```

点击 `启动` 时，ConfigBox 会清空上次 Gateway 日志、启动本地 `codex-gateway`，并自动写入 `.codex/auth.json` 与 `config.toml`。点击 `停止` 时会停止本地 `codex-gateway`，并恢复启动前的 Codex 配置。

Gateway 日志存放在宿主机：

```text
CONFIGBOX_DATA_DIR/codex-gateway/logs/
```

## 数据挂载 :cd:

容器内路径：

```text
/config/claude/settings.json
/config/codex/auth.json
/config/codex/config.toml
/config/opencode/config.json
/data
/data/codex-gateway/config.json
/data/codex-gateway/logs/
```

宿主机映射：

```text
CLAUDE_DIR         -> /config/claude
CODEX_DIR          -> /config/codex
OPENCODE_DIR       -> /config/opencode
CONFIGBOX_DATA_DIR -> /data
```

## API 验证 :pencil2:

API 仍支持 Basic Auth，便于命令行检查：

```bash
curl -u admin:你的密码 http://127.0.0.1:8787/api/tools
curl -u admin:你的密码 http://127.0.0.1:8787/api/profiles/codex
```

浏览器 UI 使用 `/api/login` 和 HttpOnly Cookie。

## 常见问题 :green_book:

### Windows 下的路径应该怎么写？

`.env` 中建议使用正斜杠：

```env
CLAUDE_DIR=C:/Users/yourname/.claude
CODEX_DIR=C:/Users/yourname/.codex
OPENCODE_DIR=C:/Users/yourname/.config/opencode
CONFIGBOX_DATA_DIR=C:/Users/yourname/.configbox
```

如果你在 WSL2 里运行 Docker Engine，并希望管理 Windows 用户目录，可以使用 `/mnt/c/Users/yourname/.codex` 这类 WSL 路径。

### Windows/macOS 挂载目录不可写怎么办？

确认 Docker 运行时允许共享你的用户目录。Docker Desktop等工具都可能有目录共享或文件访问权限设置。

### Linux 容器反复重启并提示 /data 权限错误怎么办？

检查 `.env` 中的 `CONFIGBOX_UID` / `CONFIGBOX_GID` 是否与当前用户一致：

```bash
id -u
id -g
```

### Docker 构建时依赖下载慢怎么办？

可以修改对应平台目录 `.env` 中的：

```env
NPM_REGISTRY=
PIP_INDEX_URL=
```

## 安全说明 :microscope:

ConfigBox 能查看和编辑敏感配置文件，请把它当作管理员工具使用。

建议：

- 使用 `APP_PASSWORD_HASH`，不要长期使用明文 `APP_PASSWORD`
- 使用强随机 `SESSION_SECRET`
- 公网部署时使用 HTTPS
- 尽量通过防火墙、安全组限制访问来源
- 不要把 `.env`、`.claude`、`.codex`、`.config/opencode`、`.configbox` 提交到公开仓库

## 致谢与社区支持 :golf:

- ConfigBox 的 Codex Gateway 转发能力基于 [Cmochance/codex-app-transfer](https://github.com/Cmochance/codex-app-transfer)。感谢作者对开源的贡献。

<a href="https://linux.do">
  <img src="https://ldimg.ldcstore.com/integer/20260425_linuxdo_vtx01n.png" alt="linuxdo">
</a>
