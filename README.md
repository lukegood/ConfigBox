# ConfigBox

ConfigBox 是一个 Docker 化 Web 管理工具，用于可视化管理 Linux 用户空间里的两个 AI 工具配置文件：

- Claude Code：`${HOME}/.claude/settings.json`
- Codex：`${HOME}/.codex/auth.json`

项目只管理以上两个文件，不提供任意文件浏览器，不允许用户输入任意路径。

## 功能特性

- 后端：FastAPI
- 前端：React + Vite + Monaco Editor
- Docker / docker-compose 部署
- 登录保护，支持 PBKDF2-SHA256 密码哈希
- 登录后使用 HttpOnly Session Cookie，前端不保存明文密码
- 查看、编辑、保存 Claude / Codex 当前生效配置
- 保存前校验 JSON
- 保存前自动备份
- 写入使用临时文件、`fsync`、`os.replace` 原子替换
- 保存、启用 Profile、恢复备份时使用文件锁
- 支持 Profile：创建、编辑、删除、启用
- 支持 Backups：查看、恢复历史备份
- 支持外部修改冲突检测
- 支持深色 / 浅色模式
- 容器内使用非 root 用户运行，UID/GID 与宿主机用户一致
- 默认监听 `0.0.0.0:8787`，适合服务器部署后远程访问

## 项目结构

```text
.
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── app/
├── frontend/
└── tests/
```

## 安装方式

ConfigBox 支持两种安装方式：

- 使用已经发布的 Docker 镜像
- 从源码在本机服务器上构建镜像

下面任选一种即可。

## 方式一：使用已发布的 Docker 镜像

这种方式适合普通用户，服务器上只需要 Docker 和 Docker Compose。

创建一个部署目录：

```bash
mkdir -p ~/configbox
cd ~/configbox
```

准备宿主机配置目录：

```bash
mkdir -p ~/.claude ~/.codex ~/.ai-config-manager
[ -f ~/.claude/settings.json ] || printf '{}\n' > ~/.claude/settings.json
[ -f ~/.codex/auth.json ] || printf '{}\n' > ~/.codex/auth.json
```

创建 `.env` 文件：

```bash
cat > .env <<EOF
UID=$(id -u)
GID=$(id -g)
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=
SESSION_SECRET=
APP_COOKIE_SECURE=false
BACKUP_RETENTION=50
TZ=Asia/Shanghai
EOF
```

生成登录密码哈希和 Session Secret：

```bash
docker run --rm -it <ConfigBox镜像名> python -m app.password_hash
```

例如，如果维护者发布的镜像名是 `ghcr.io/example/configbox:latest`，则运行：

```bash
docker run --rm -it ghcr.io/example/configbox:latest python -m app.password_hash
```

命令会提示输入两次登录密码，然后输出：

```env
APP_PASSWORD_HASH=...
SESSION_SECRET=...
```

把输出的两行填入 `.env`，并保持：

```env
APP_PASSWORD=
```

创建 `docker-compose.yml`：

```yaml
services:
  configbox:
    image: <ConfigBox镜像名>
    container_name: configbox
    restart: unless-stopped
    ports:
      - "8787:8787"
    environment:
      TZ: ${TZ:-Asia/Shanghai}
      APP_HOST: 0.0.0.0
      APP_PORT: 8787
      APP_USERNAME: ${APP_USERNAME:-admin}
      APP_PASSWORD: ${APP_PASSWORD:-}
      APP_PASSWORD_HASH: ${APP_PASSWORD_HASH:-}
      SESSION_SECRET: ${SESSION_SECRET:-}
      APP_COOKIE_SECURE: ${APP_COOKIE_SECURE:-false}
      CLAUDE_CONFIG_PATH: /config/claude/settings.json
      CODEX_CONFIG_PATH: /config/codex/auth.json
      DATA_DIR: /data
      BACKUP_RETENTION: ${BACKUP_RETENTION:-50}
    volumes:
      - ${HOME}/.claude:/config/claude
      - ${HOME}/.codex:/config/codex
      - ${HOME}/.ai-config-manager:/data
```

请把其中的 `<ConfigBox镜像名>` 替换为实际镜像名。

启动：

```bash
docker compose up -d
```

如果你的服务器使用旧版 Compose 命令：

```bash
docker-compose up -d
```

## 方式二：从源码构建镜像

这种方式适合需要自行修改代码、二次开发或本地构建镜像的用户。

进入源码目录：

```bash
cd ai-config-manager
```

准备宿主机配置目录：

```bash
mkdir -p ~/.claude ~/.codex ~/.ai-config-manager
[ -f ~/.claude/settings.json ] || printf '{}\n' > ~/.claude/settings.json
[ -f ~/.codex/auth.json ] || printf '{}\n' > ~/.codex/auth.json
```

创建 `.env`：

```bash
cp .env.example .env
sed -i "s/^UID=.*/UID=$(id -u)/" .env
sed -i "s/^GID=.*/GID=$(id -g)/" .env
```

先构建镜像：

```bash
docker compose build
```

如果你的服务器使用旧版 Compose 命令：

```bash
docker-compose build
```

生成登录密码哈希和 Session Secret：

```bash
docker run --rm -it configbox:latest python -m app.password_hash
```

把输出的 `APP_PASSWORD_HASH=...` 和 `SESSION_SECRET=...` 填入 `.env`，并保持：

```env
APP_PASSWORD=
```

启动：

```bash
docker compose up -d
```

旧版 Compose：

```bash
docker-compose up -d
```

访问：

```text
http://服务器IP:8787
```

## 环境变量

`.env.example` 示例：

```env
UID=1000
GID=1000
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=
SESSION_SECRET=
APP_COOKIE_SECURE=false
BACKUP_RETENTION=50
TZ=Asia/Shanghai
NPM_REGISTRY=https://registry.npmmirror.com
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

推荐认证配置：

```env
APP_USERNAME=admin
APP_PASSWORD=
APP_PASSWORD_HASH=pbkdf2_sha256$...
SESSION_SECRET=一串长随机字符串
```

临时测试也可以使用明文密码：

```env
APP_USERNAME=admin
APP_PASSWORD=your_password
APP_PASSWORD_HASH=
SESSION_SECRET=一串长随机字符串
```

长期使用推荐 `APP_PASSWORD_HASH`，不要使用明文 `APP_PASSWORD`。

## 远程访问

`docker-compose.yml` 默认暴露：

```yaml
ports:
  - "8787:8787"
```

因此可以通过服务器 IP 访问：

```text
http://服务器IP:8787
```

如果部署在公网服务器，建议配合以下方式使用：

- 服务器防火墙 / 云安全组限制来源 IP
- VPN
- Nginx Proxy Manager / Caddy / Traefik / Nginx 反向代理
- HTTPS

如果使用 HTTPS 反向代理，请设置：

```env
APP_COOKIE_SECURE=true
```

如果使用普通 HTTP、SSH 隧道、VS Code Ports 转发，请保持：

```env
APP_COOKIE_SECURE=false
```

## 使用教程

### 当前配置

左侧选择 `Claude` 或 `Codex`，点击 `当前配置`。

这里编辑的是真实生效配置：

```text
Claude -> ~/.claude/settings.json
Codex  -> ~/.codex/auth.json
```

点击 `保存` 时，系统会：

```text
校验 JSON -> 备份旧版本 -> 原子写入新版本
```

如果文件在页面打开后被外部终端修改，保存时会提示冲突，避免覆盖外部修改。

### Profiles

Profile 是你主动保存的配置方案，适合保存多套可切换配置。

例如：

```text
default
proxy
company
local
```

Profile 存放在：

```text
~/.ai-config-manager/profiles/claude/
~/.ai-config-manager/profiles/codex/
```

点击某个 Profile 后可以编辑它。点击 `启用` 时，系统会把该 Profile 覆盖到真实配置文件中。

### Backups

Backups 是系统自动保存的历史版本。

每次执行以下操作前都会自动备份：

```text
保存当前配置
启用 Profile
恢复备份
```

备份目录：

```text
~/.ai-config-manager/backups/claude/
~/.ai-config-manager/backups/codex/
```

如果配置改坏了，可以在 `Backups` 中选择历史版本并点击 `恢复`。

## 数据挂载

容器内路径：

```text
/config/claude/settings.json
/config/codex/auth.json
/data
```

宿主机映射：

```text
${HOME}/.claude             -> /config/claude
${HOME}/.codex              -> /config/codex
${HOME}/.ai-config-manager  -> /data
```

## API 验证

API 仍支持 Basic Auth，便于命令行检查：

```bash
curl -u admin:你的密码 http://127.0.0.1:8787/api/tools
curl -u admin:你的密码 http://127.0.0.1:8787/api/configs/codex/active
```

浏览器 UI 使用 `/api/login` 和 HttpOnly Cookie。

## 本地测试

后端测试：

```bash
uv venv --python /usr/bin/python3 --seed .venv
uv pip install -r requirements.txt --python .venv/bin/python
.venv/bin/python -m pytest
```

前端构建测试：

```bash
cd frontend
npm install
npm run build
```

## 常见问题

查看容器日志：

```bash
docker logs --tail 100 configbox
```

查看容器状态：

```bash
docker ps --filter name=configbox
```

如果容器反复重启并提示 `/data` 权限错误，检查 `.env` 中的 UID/GID 是否与当前用户一致：

```bash
id -u
id -g
```

然后修改：

```env
UID=你的UID
GID=你的GID
```

如果登录成功后又变回未登录，检查：

```env
APP_COOKIE_SECURE=false
```

普通 HTTP 下不能设置为 `true`。只有 HTTPS 下才应设置为 `true`。

如果 Docker 构建时依赖下载慢，可以修改：

```env
NPM_REGISTRY=
PIP_INDEX_URL=
```

## 安全说明

ConfigBox 能查看和编辑敏感配置文件，请把它当作管理员工具使用。

建议：

- 不要提交 `.env`
- 使用 `APP_PASSWORD_HASH`，不要长期使用明文 `APP_PASSWORD`
- 使用强随机 `SESSION_SECRET`
- 公网部署时使用 HTTPS
- 尽量通过防火墙、VPN、安全组限制访问来源
