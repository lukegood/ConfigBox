import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  Check,
  DatabaseBackup,
  FileCode2,
  FolderPlus,
  LogOut,
  Moon,
  Play,
  RefreshCcw,
  Save,
  Sun,
  Trash2
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  activateProfile,
  clearAuth,
  createProfile,
  deleteProfile,
  getActiveConfig,
  getBackup,
  getProfile,
  getTools,
  hasAuth,
  listBackups,
  listProfiles,
  me,
  restoreBackup,
  saveActiveConfig,
  saveProfile,
  setAuth
} from "./api";
import type { BackupItem, ProfileItem, Tool, ViewMode } from "./types";

const profileNamePattern = /^[a-zA-Z0-9_-]{1,64}$/;

function App() {
  const [authenticated, setAuthenticated] = useState(hasAuth());
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState("");
  const [defaultPassword, setDefaultPassword] = useState(false);
  const [tools, setTools] = useState<Tool[]>([]);
  const [toolId, setToolId] = useState<"claude" | "codex">("claude");
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [mode, setMode] = useState<ViewMode>("active");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [selectedBackup, setSelectedBackup] = useState("");
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [mtime, setMtime] = useState<number | null>(null);
  const [title, setTitle] = useState("当前配置");
  const [status, setStatus] = useState("准备就绪");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return localStorage.getItem("configbox.theme") === "light" ? "light" : "dark";
  });

  const tool = useMemo(() => tools.find((item) => item.id === toolId), [tools, toolId]);
  const dirty = content !== savedContent;
  const readonly = mode === "backup";
  const sensitive = /api[_-]?key|token|secret|password/i.test(content);

  async function bootstrap() {
    setLoading(true);
    setError("");
    try {
      const user = await me();
      const toolList = await getTools();
      setCurrentUser(user.username);
      setDefaultPassword(user.defaultPassword);
      setTools(toolList);
      setAuthenticated(true);
      await loadTool(toolId);
    } catch (err) {
      await clearAuth();
      setAuthenticated(false);
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadLists(nextTool = toolId) {
    const [profileItems, backupItems] = await Promise.all([listProfiles(nextTool), listBackups(nextTool)]);
    setProfiles(profileItems);
    setBackups(backupItems);
  }

  async function loadTool(nextTool: "claude" | "codex") {
    setLoading(true);
    setError("");
    try {
      setToolId(nextTool);
      await loadLists(nextTool);
      const active = await getActiveConfig(nextTool);
      setMode("active");
      setSelectedProfile("");
      setSelectedBackup("");
      setContent(active.content);
      setSavedContent(active.content);
      setMtime(active.mtime);
      setTitle("当前配置");
      setStatus("已加载当前配置");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadActive() {
    const active = await getActiveConfig(toolId);
    setMode("active");
    setSelectedProfile("");
    setSelectedBackup("");
    setContent(active.content);
    setSavedContent(active.content);
    setMtime(active.mtime);
    setTitle("当前配置");
    setStatus("已重新加载");
  }

  async function loadProfile(name: string) {
    setLoading(true);
    setError("");
    try {
      const doc = await getProfile(toolId, name);
      setMode("profile");
      setSelectedProfile(name);
      setSelectedBackup("");
      setContent(doc.content);
      setSavedContent(doc.content);
      setMtime(doc.mtime);
      setTitle(`Profile: ${name}`);
      setStatus("已加载 Profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Profile 失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadBackup(name: string) {
    setLoading(true);
    setError("");
    try {
      const doc = await getBackup(toolId, name);
      setMode("backup");
      setSelectedBackup(name);
      setSelectedProfile("");
      setContent(doc.content);
      setSavedContent(doc.content);
      setMtime(doc.mtime);
      setTitle(`Backup: ${name}`);
      setStatus("已加载备份");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载备份失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const user = await setAuth(username, password);
      const toolList = await getTools();
      setCurrentUser(user.username);
      setDefaultPassword(user.defaultPassword);
      setTools(toolList);
      setAuthenticated(true);
      await loadTool(toolId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setLoading(true);
    setError("");
    try {
      if (mode === "active") {
        const saved = await saveActiveConfig(toolId, content, mtime);
        setContent(saved.content);
        setSavedContent(saved.content);
        setMtime(saved.mtime);
        setStatus("已保存，旧版本已备份");
      } else if (mode === "profile" && selectedProfile) {
        const saved = await saveProfile(toolId, selectedProfile, content);
        setContent(saved.content);
        setSavedContent(saved.content);
        setMtime(saved.mtime);
        setStatus("Profile 已保存");
      }
      await loadLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateProfile(source: "active" | "empty") {
    const name = window.prompt("Profile 名称");
    if (!name) return;
    if (!profileNamePattern.test(name)) {
      setError("Profile 名称只能使用字母、数字、下划线和短横线，最长 64 个字符");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await createProfile(toolId, name, source);
      await loadLists();
      await loadProfile(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建 Profile 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteProfile() {
    if (!selectedProfile || !window.confirm(`删除 Profile "${selectedProfile}"？`)) return;
    setLoading(true);
    setError("");
    try {
      await deleteProfile(toolId, selectedProfile);
      await loadLists();
      await loadActive();
      setStatus("Profile 已删除");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleActivateProfile() {
    if (!selectedProfile) return;
    setLoading(true);
    setError("");
    try {
      const active = await activateProfile(toolId, selectedProfile);
      await loadLists();
      setMode("active");
      setSelectedProfile("");
      setContent(active.content);
      setSavedContent(active.content);
      setMtime(active.mtime);
      setTitle("当前配置");
      setStatus(`已启用 Profile: ${selectedProfile}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启用失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRestoreBackup() {
    if (!selectedBackup || !window.confirm(`恢复备份 "${selectedBackup}"？`)) return;
    setLoading(true);
    setError("");
    try {
      const active = await restoreBackup(toolId, selectedBackup);
      await loadLists();
      setMode("active");
      setSelectedBackup("");
      setContent(active.content);
      setSavedContent(active.content);
      setMtime(active.mtime);
      setTitle("当前配置");
      setStatus("备份已恢复，恢复前版本也已备份");
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    } finally {
      setLoading(false);
    }
  }

  function handleFormat() {
    if (tool?.format !== "json") {
      setStatus("TOML 保留原格式");
      return;
    }
    try {
      setContent(JSON.stringify(JSON.parse(content || "{}"), null, 2) + "\n");
      setStatus("JSON 已格式化");
    } catch (err) {
      setError(err instanceof Error ? err.message : "JSON 格式错误");
    }
  }

  async function logout() {
    await clearAuth();
    setAuthenticated(false);
    setCurrentUser("");
    setPassword("");
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("configbox.theme", nextTheme);
  }

  useEffect(() => {
    if (hasAuth()) {
      bootstrap();
    }
  }, []);

  if (!authenticated) {
    return (
      <main className={`login-shell theme-${theme}`}>
        <form className="login-panel" onSubmit={handleLogin}>
          <div>
            <p className="eyebrow">AI Config Manager</p>
            <h1>ConfigBox</h1>
            <p className="login-copy">Claude settings 与 Codex auth 的安全配置台</p>
          </div>
          <label>
            用户名
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label>
            密码
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
            />
          </label>
          {error ? <p className="message error">{error}</p> : null}
          <button className="primary" type="submit" disabled={loading}>
            <Check size={16} />
            登录
          </button>
          <button className="secondary" type="button" onClick={toggleTheme}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "浅色模式" : "深色模式"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className={`app-shell theme-${theme}`}>
      <aside className="sidebar">
        <div className="brand">
          <FileCode2 size={22} />
          <div>
            <h1>ConfigBox</h1>
            <p>{currentUser}</p>
          </div>
        </div>

        <div className="tool-switcher">
          {tools.map((item) => (
            <button
              key={item.id}
              className={item.id === toolId ? "selected" : ""}
              onClick={() => loadTool(item.id)}
              title={item.pathLabel}
            >
              {item.name}
            </button>
          ))}
        </div>

        <section className="nav-section">
          <button className={mode === "active" ? "nav-item selected" : "nav-item"} onClick={loadActive}>
            当前配置
          </button>
        </section>

        <section className="nav-section">
          <div className="section-title">
            <span>Profiles</span>
            <div className="mini-actions">
              <button title="从当前配置创建 Profile" onClick={() => handleCreateProfile("active")}>
                <FolderPlus size={15} />
              </button>
              <button title="创建空 Profile" onClick={() => handleCreateProfile("empty")}>
                +
              </button>
            </div>
          </div>
          <div className="scroll-list">
            {profiles.map((item) => (
              <button
                key={item.name}
                className={mode === "profile" && selectedProfile === item.name ? "nav-item selected" : "nav-item"}
                onClick={() => loadProfile(item.name)}
              >
                <span>{item.name}</span>
                {item.active ? <span className="pill">active</span> : null}
              </button>
            ))}
          </div>
        </section>

        <section className="nav-section backups">
          <div className="section-title">
            <span>Backups</span>
            <DatabaseBackup size={15} />
          </div>
          <div className="scroll-list">
            {backups.map((item) => (
              <button
                key={item.name}
                className={mode === "backup" && selectedBackup === item.name ? "nav-item selected" : "nav-item"}
                onClick={() => loadBackup(item.name)}
                title={formatTime(item.mtime)}
              >
                {item.name}
              </button>
            ))}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>{tool?.name || toolId} / {title}</h2>
            <p>{tool?.pathLabel} · {tool?.format.toUpperCase()}</p>
          </div>
          <div className="actions">
            <button onClick={handleSave} disabled={loading || readonly || !dirty} title="保存">
              <Save size={16} />
              保存
            </button>
            <button onClick={handleFormat} disabled={loading || readonly} title="格式化 JSON">
              <Check size={16} />
              格式化
            </button>
            <button onClick={loadActive} disabled={loading} title="重新加载">
              <RefreshCcw size={16} />
              重载
            </button>
            <button onClick={toggleTheme} title="切换主题">
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
              {theme === "dark" ? "浅色" : "深色"}
            </button>
            {mode === "profile" ? (
              <>
                <button onClick={handleActivateProfile} disabled={loading} title="启用 Profile">
                  <Play size={16} />
                  启用
                </button>
                <button className="danger" onClick={handleDeleteProfile} disabled={loading} title="删除 Profile">
                  <Trash2 size={16} />
                </button>
              </>
            ) : null}
            {mode === "backup" ? (
              <button onClick={handleRestoreBackup} disabled={loading} title="恢复备份">
                <Play size={16} />
                恢复
              </button>
            ) : null}
            <button onClick={logout} title="退出">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        {defaultPassword ? (
          <div className="banner warning">
            <AlertTriangle size={16} />
            默认密码仍在使用，请修改 APP_PASSWORD。
          </div>
        ) : null}
        {sensitive ? (
          <div className="banner caution">
            <AlertTriangle size={16} />
            内容里可能包含敏感字段。
          </div>
        ) : null}
        {error ? <div className="banner error">{error}</div> : null}

        <div className="editor-wrap">
          <Editor
            key={`${toolId}-${mode}-${selectedProfile}-${selectedBackup}`}
            height="100%"
            value={content}
            onChange={(value) => setContent(value ?? "")}
            loading={<div className="editor-loading">加载编辑器...</div>}
            language={tool?.format === "json" ? "json" : "plaintext"}
            theme={theme === "dark" ? "vs-dark" : "vs"}
            options={{
              automaticLayout: true,
              minimap: { enabled: false },
              readOnly: readonly,
              scrollBeyondLastLine: false,
              fontSize: 14,
              wordWrap: "on"
            }}
          />
        </div>

        <footer className="statusbar">
          <span className={dirty ? "dirty-dot" : "clean-dot"} />
          <span>{dirty ? "未保存" : "已同步"}</span>
          <span>{content.length} 字符</span>
          <span>{status}</span>
          <span>{mtime ? formatTime(mtime) : "无 mtime"}</span>
        </footer>
      </section>
    </main>
  );
}

function formatTime(mtime: number | null) {
  if (!mtime) return "";
  return new Date(mtime * 1000).toLocaleString();
}

export default App;
