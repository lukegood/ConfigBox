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
  PlugZap,
  Power,
  RefreshCcw,
  Save,
  Sun,
  Trash2
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  activateProfile,
  activateGatewayProvider,
  addGatewayProvider,
  clearGatewayLogs,
  clearAuth,
  createProfile,
  deleteGatewayProvider,
  deleteProfile,
  getGatewayConfig,
  getGatewayLogs,
  getGatewayStatus,
  getActiveConfig,
  getBackup,
  getProfile,
  getTools,
  hasAuth,
  listBackups,
  listProfiles,
  me,
  restoreBackup,
  restartGateway,
  saveActiveConfig,
  saveProfile,
  setAuth,
  startGateway,
  stopGateway,
  updateGatewayProvider
} from "./api";
import type {
  ActiveConfig,
  BackupDoc,
  BackupItem,
  ConfigFile,
  GatewayConfig,
  GatewayStatus,
  ProfileDoc,
  ProfileItem,
  Tool,
  ToolId,
  ViewMode
} from "./types";

const profileNamePattern = /^[a-zA-Z0-9_-]{1,64}$/;

type GatewayProviderForm = {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  authScheme: string;
  apiFormat: string;
  defaultModel: string;
  gpt53Model: string;
};

const emptyGatewayProviderForm: GatewayProviderForm = {
  id: "",
  name: "",
  baseUrl: "",
  apiKey: "",
  authScheme: "bearer",
  apiFormat: "openai_chat",
  defaultModel: "",
  gpt53Model: ""
};

function App() {
  const [authenticated, setAuthenticated] = useState(hasAuth());
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState("");
  const [defaultPassword, setDefaultPassword] = useState(false);
  const [tools, setTools] = useState<Tool[]>([]);
  const [toolId, setToolId] = useState<ToolId>("claude");
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [mode, setMode] = useState<ViewMode>("active");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [selectedBackup, setSelectedBackup] = useState("");
  const [files, setFiles] = useState<ConfigFile[]>([]);
  const [savedFiles, setSavedFiles] = useState<ConfigFile[]>([]);
  const [activeFileId, setActiveFileId] = useState("");
  const [mtime, setMtime] = useState<number | null>(null);
  const [title, setTitle] = useState("当前配置");
  const [status, setStatus] = useState("准备就绪");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return localStorage.getItem("configbox.theme") === "light" ? "light" : "dark";
  });
  const [gatewayConfig, setGatewayConfig] = useState<GatewayConfig | null>(null);
  const [gatewayStatus, setGatewayStatus] = useState<GatewayStatus | null>(null);
  const [gatewayLogs, setGatewayLogs] = useState<string[]>([]);
  const [gatewayLogBytes, setGatewayLogBytes] = useState({ current: 0, max: 0 });
  const [gatewayProviderForm, setGatewayProviderForm] = useState<GatewayProviderForm | null>(null);
  const [gatewayRestartRequired, setGatewayRestartRequired] = useState(false);

  const tool = useMemo(() => tools.find((item) => item.id === toolId), [tools, toolId]);
  const activeFile = useMemo(() => files.find((file) => file.id === activeFileId) ?? files[0], [files, activeFileId]);
  const activeContent = activeFile?.content ?? "";
  const dirty = filesChanged(files, savedFiles);
  const readonly = mode === "backup" || mode === "gateway";
  const sensitive = files.some((file) => /api[_-]?key|token|secret|password/i.test(file.content));
  const contentLength = files.reduce((sum, file) => sum + file.content.length, 0);

  function applyDocument(
    doc: ActiveConfig | ProfileDoc | BackupDoc,
    nextTitle: string,
    nextStatus: string,
    preferredFileId = activeFileId
  ) {
    const nextFiles = normalizeDocFiles(doc);
    setFiles(nextFiles);
    setSavedFiles(nextFiles);
    setActiveFileId(nextFiles.some((file) => file.id === preferredFileId) ? preferredFileId : nextFiles[0]?.id ?? "");
    setMtime(doc.mtime);
    setTitle(nextTitle);
    setStatus(nextStatus);
  }

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

  async function loadTool(nextTool: ToolId) {
    setLoading(true);
    setError("");
    try {
      setToolId(nextTool);
      await loadLists(nextTool);
      const active = await getActiveConfig(nextTool);
      setMode("active");
      setSelectedProfile("");
      setSelectedBackup("");
      applyDocument(active, "当前配置", "已加载当前配置", "");
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
    applyDocument(active, "当前配置", "已重新加载");
  }

  async function loadGateway() {
    setLoading(true);
    setError("");
    try {
      const [config, statusData, logs] = await Promise.all([getGatewayConfig(), getGatewayStatus(), getGatewayLogs()]);
      setGatewayConfig(config);
      setGatewayStatus(statusData);
      if (!statusData.running) {
        setGatewayRestartRequired(false);
      }
      setGatewayLogs(logs.lines);
      setGatewayLogBytes({ current: logs.currentBytes, max: logs.maxBytes });
      setMode("gateway");
      setSelectedProfile("");
      setSelectedBackup("");
      setTitle("Gateway");
      setStatus(statusData.running ? "Gateway 运行中" : "Gateway 未启动");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Gateway 失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadProfile(name: string) {
    setLoading(true);
    setError("");
    try {
      const doc = await getProfile(toolId, name);
      setMode("profile");
      setSelectedProfile(name);
      setSelectedBackup("");
      applyDocument(doc, `Profile: ${name}`, "已加载 Profile");
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
      applyDocument(doc, `Backup: ${name}`, "已加载备份");
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
      const preferredFileId = activeFileId;
      if (mode === "active") {
        const saved = await saveActiveConfig(toolId, files, mtime);
        applyDocument(saved, "当前配置", "已保存，旧版本已备份", preferredFileId);
      } else if (mode === "profile" && selectedProfile) {
        const saved = await saveProfile(toolId, selectedProfile, files);
        applyDocument(saved, `Profile: ${selectedProfile}`, "Profile 已保存", preferredFileId);
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
      applyDocument(active, "当前配置", `已启用 Profile: ${selectedProfile}`);
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
      applyDocument(active, "当前配置", "备份已恢复，恢复前版本也已备份");
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayStart() {
    setLoading(true);
    setError("");
    try {
      const next = await startGateway();
      setGatewayStatus(next);
      setGatewayRestartRequired(false);
      setStatus(next.codexApplied ? "Gateway 已启动，Codex 配置已写入" : "Gateway 已启动");
      const logs = await getGatewayLogs();
      setGatewayLogs(logs.lines);
      setGatewayLogBytes({ current: logs.currentBytes, max: logs.maxBytes });
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动 Gateway 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayStop() {
    setLoading(true);
    setError("");
    try {
      const next = await stopGateway();
      setGatewayStatus(next);
      setGatewayRestartRequired(false);
      setStatus(next.codexRestored ? "Gateway 已停止，Codex 配置已自动还原" : "Gateway 已停止");
    } catch (err) {
      setError(err instanceof Error ? err.message : "停止 Gateway 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayRestart() {
    setLoading(true);
    setError("");
    try {
      const next = await restartGateway();
      setGatewayStatus(next);
      setGatewayRestartRequired(false);
      setStatus(next.codexApplied ? "Gateway 已重启，Provider 变更已生效" : "Gateway 已重启");
      const logs = await getGatewayLogs();
      setGatewayLogs(logs.lines);
      setGatewayLogBytes({ current: logs.currentBytes, max: logs.maxBytes });
    } catch (err) {
      setError(err instanceof Error ? err.message : "重启 Gateway 失败");
    } finally {
      setLoading(false);
    }
  }

  function openGatewayProviderForm(provider?: GatewayConfig["providers"][number]) {
    if (!provider) {
      setGatewayProviderForm(emptyGatewayProviderForm);
      return;
    }
    setGatewayProviderForm({
      id: provider.id,
      name: provider.name,
      baseUrl: provider.baseUrl,
      apiKey: "",
      authScheme: provider.authScheme || "bearer",
      apiFormat: provider.apiFormat || "openai_chat",
      defaultModel: provider.models?.default || "",
      gpt53Model: provider.models?.gpt_5_3_codex || provider.models?.default || ""
    });
  }

  function updateGatewayProviderForm(field: keyof GatewayProviderForm, value: string) {
    setGatewayProviderForm((current) => (current ? { ...current, [field]: value } : current));
  }

  async function handleGatewayProviderSubmit(event: FormEvent) {
    event.preventDefault();
    if (!gatewayProviderForm) return;
    const form = gatewayProviderForm;
    if (!form.name.trim() || !form.baseUrl.trim()) {
      setError("Provider 名称和 Base URL 必填");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const wasRunning = Boolean(gatewayStatus?.running);
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        baseUrl: form.baseUrl.trim(),
        apiFormat: form.apiFormat,
        authScheme: form.authScheme,
        models: {
          default: form.defaultModel.trim(),
          gpt_5_3_codex: form.gpt53Model.trim() || form.defaultModel.trim()
        }
      };
      if (form.apiKey.trim()) {
        payload.apiKey = form.apiKey.trim();
      }
      const provider = form.id
        ? await updateGatewayProvider(form.id, payload)
        : await addGatewayProvider(payload);
      if (!form.id) {
        await activateGatewayProvider(provider.id);
      }
      setGatewayProviderForm(null);
      await loadGateway();
      setGatewayRestartRequired(wasRunning);
      setStatus(
        wasRunning
          ? `${form.id ? "已更新" : "已添加"} Provider: ${provider.name}，请重启 Gateway 后生效`
          : `${form.id ? "已更新" : "已添加"} Provider: ${provider.name}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存 Provider 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayDeleteProvider(providerId: string, name: string) {
    if (!window.confirm(`删除 Provider "${name}"？`)) return;
    setLoading(true);
    setError("");
    try {
      const wasRunning = Boolean(gatewayStatus?.running);
      await deleteGatewayProvider(providerId);
      await loadGateway();
      setGatewayRestartRequired(wasRunning);
      setStatus(wasRunning ? `已删除 Provider: ${name}，请重启 Gateway 后生效` : `已删除 Provider: ${name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除 Provider 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayActivateProvider(providerId: string, name: string) {
    setLoading(true);
    setError("");
    try {
      const wasRunning = Boolean(gatewayStatus?.running);
      await activateGatewayProvider(providerId);
      await loadGateway();
      setGatewayRestartRequired(wasRunning);
      setStatus(wasRunning ? `已启用 Provider: ${name}，请重启 Gateway 后生效` : `已启用 Provider: ${name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启用 Provider 失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleGatewayClearLogs() {
    if (!window.confirm("清除 Gateway 日志？")) return;
    setLoading(true);
    setError("");
    try {
      await clearGatewayLogs();
      const logs = await getGatewayLogs();
      setGatewayLogs(logs.lines);
      setGatewayLogBytes({ current: logs.currentBytes, max: logs.maxBytes });
      setStatus("Gateway 日志已清除");
    } catch (err) {
      setError(err instanceof Error ? err.message : "清除日志失败");
    } finally {
      setLoading(false);
    }
  }

  function handleFormat() {
    if (!activeFile || activeFile.format !== "json") {
      setStatus("TOML 保留原格式");
      return;
    }
    try {
      updateActiveContent(JSON.stringify(JSON.parse(activeFile.content || "{}"), null, 2) + "\n");
      setStatus("JSON 已格式化");
    } catch (err) {
      setError(err instanceof Error ? err.message : "JSON 格式错误");
    }
  }

  function updateActiveContent(content: string) {
    setFiles((current) => current.map((file) => (file.id === activeFile?.id ? { ...file, content } : file)));
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
            <p className="eyebrow">ConfigBox</p>
            <h1>ConfigBox</h1>
            <p className="login-copy">Claude settings 与 Codex auth/config 的安全配置台</p>
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
          {toolId === "codex" ? (
            <button className={mode === "gateway" ? "nav-item selected" : "nav-item"} onClick={loadGateway}>
              <span>Gateway</span>
              <PlugZap size={15} />
            </button>
          ) : null}
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
            <h2>
              {tool?.name || toolId} / {title}
            </h2>
            <p>
              {mode === "gateway"
                ? `${gatewayStatus?.publicBaseUrl ?? "Gateway"} · ${gatewayConfig?.path ?? ""}`
                : `${tool?.pathLabel} · ${files.map((file) => file.format.toUpperCase()).join(" + ")}`}
            </p>
          </div>
          <div className="actions">
            {mode === "gateway" ? (
              <>
                <button onClick={() => openGatewayProviderForm()} disabled={loading} title="添加 Provider">
                  <FolderPlus size={16} />
                  Provider
                </button>
                {gatewayStatus?.running ? (
                  <>
                    <button onClick={handleGatewayRestart} disabled={loading} title="重启 Gateway">
                      <RefreshCcw size={16} />
                      重启
                    </button>
                    <button onClick={handleGatewayStop} disabled={loading} title="停止 Gateway">
                      <Power size={16} />
                      停止
                    </button>
                  </>
                ) : (
                  <button onClick={handleGatewayStart} disabled={loading} title="启动 Gateway">
                    <Play size={16} />
                    启动
                  </button>
                )}
                <button onClick={loadGateway} disabled={loading} title="刷新 Gateway">
                  <RefreshCcw size={16} />
                  刷新
                </button>
              </>
            ) : (
              <>
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
              </>
            )}
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

        <div className="statusline">
          {mode === "gateway" ? (
            <>
              <span className={gatewayStatus?.running ? "clean-dot" : "dirty-dot"} />
              <span>{gatewayStatus?.running ? "运行中" : "未启动"}</span>
              <span>端口 {gatewayStatus?.port ?? "-"}</span>
              <span>{gatewayStatus?.providerCount ?? 0} providers</span>
              <span>{status}</span>
            </>
          ) : (
            <>
              <span className={dirty ? "dirty-dot" : "clean-dot"} />
              <span>{dirty ? "未保存" : "已同步"}</span>
              <span>{contentLength} 字符</span>
              <span>{status}</span>
              <span>{mtime ? formatTime(mtime) : "无 mtime"}</span>
            </>
          )}
        </div>

        {mode === "gateway" ? (
          <>
            {error ? <div className="banner error">{error}</div> : null}
            {gatewayRestartRequired && gatewayStatus?.running ? (
              <div className="banner caution gateway-restart-banner">
                <AlertTriangle size={16} />
                <span>Provider 配置已变更，重启 Gateway 后生效。</span>
                <button onClick={handleGatewayRestart} disabled={loading} title="重启 Gateway">
                  <RefreshCcw size={15} />
                  重启
                </button>
              </div>
            ) : null}
            <div className="gateway-panel">
              <section className="gateway-section">
                <div className="gateway-summary">
                  <div>
                    <span>监听地址</span>
                    <strong>{gatewayStatus?.publicBaseUrl ?? "-"}</strong>
                  </div>
                  <div>
                    <span>配置文件</span>
                    <strong>{gatewayConfig?.path ?? "-"}</strong>
                  </div>
                  <div>
                    <span>Gateway Key</span>
                    <strong>{gatewayConfig?.gatewayApiKey ?? "-"}</strong>
                  </div>
                </div>
              </section>
              <section className="gateway-section">
                <div className="section-title">Providers</div>
                <div className="provider-table">
                  {(gatewayConfig?.providers ?? []).map((provider) => (
                    <div
                      key={provider.id}
                      className={provider.id === gatewayConfig?.activeProvider ? "provider-row selected" : "provider-row"}
                    >
                      <span>{provider.name}</span>
                      <span>{provider.models?.default || provider.models?.gpt_5_3_codex || "-"}</span>
                      <span>{provider.baseUrl}</span>
                      <span className="provider-actions">
                        {provider.id === gatewayConfig?.activeProvider ? (
                          <span className="pill">active</span>
                        ) : (
                          <button
                            onClick={() => handleGatewayActivateProvider(provider.id, provider.name)}
                            disabled={loading}
                          >
                            启用
                          </button>
                        )}
                        <button onClick={() => openGatewayProviderForm(provider)}>编辑</button>
                        <button
                          className="danger"
                          onClick={() => handleGatewayDeleteProvider(provider.id, provider.name)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </span>
                    </div>
                  ))}
                  {gatewayConfig?.providers.length ? null : <div className="empty-state">暂无 Provider</div>}
                </div>
              </section>
              <section className="gateway-section">
                <div className="section-title">
                  <span>Logs</span>
                  <button onClick={handleGatewayClearLogs} disabled={loading} title="清除日志">
                    <Trash2 size={15} />
                  </button>
                </div>
                <div className="log-meta">
                  {formatBytes(gatewayLogBytes.current)} / {formatBytes(gatewayLogBytes.max)}
                </div>
                <pre className="gateway-logs">{gatewayLogs.join("\n") || "暂无日志"}</pre>
              </section>
            </div>
          </>
        ) : (
          <>
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

            <div className="editor-panel">
              <div className="file-tabs" role="tablist">
                {files.map((file) => (
                  <button
                    key={file.id}
                    className={file.id === activeFile?.id ? "selected" : ""}
                    onClick={() => setActiveFileId(file.id)}
                    role="tab"
                    title={file.pathLabel}
                  >
                    {file.label}
                  </button>
                ))}
              </div>
              <div className="editor-wrap">
                <Editor
                  key={`${toolId}-${mode}-${selectedProfile}-${selectedBackup}-${activeFile?.id ?? "file"}`}
                  height="100%"
                  value={activeContent}
                  onChange={(value) => updateActiveContent(value ?? "")}
                  loading={<div className="editor-loading">加载编辑器...</div>}
                  language={activeFile?.format === "json" ? "json" : "plaintext"}
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
            </div>
          </>
        )}
      </section>
      {gatewayProviderForm ? (
        <div className="modal-backdrop" role="presentation">
          <form className="provider-modal" onSubmit={handleGatewayProviderSubmit}>
            <div className="modal-head">
              <div>
                <h3>{gatewayProviderForm.id ? "编辑 Provider" : "添加 Provider"}</h3>
                <p>OpenAI Chat 兼容上游</p>
              </div>
              <button type="button" onClick={() => setGatewayProviderForm(null)}>
                关闭
              </button>
            </div>
            <div className="provider-form-grid">
              <label>
                名称
                <input
                  value={gatewayProviderForm.name}
                  onChange={(event) => updateGatewayProviderForm("name", event.target.value)}
                  placeholder="DeepSeek"
                  autoFocus
                />
              </label>
              <label>
                Base URL
                <input
                  value={gatewayProviderForm.baseUrl}
                  onChange={(event) => updateGatewayProviderForm("baseUrl", event.target.value)}
                  placeholder="https://api.deepseek.com/v1"
                />
              </label>
              <label>
                API Key
                <input
                  value={gatewayProviderForm.apiKey}
                  onChange={(event) => updateGatewayProviderForm("apiKey", event.target.value)}
                  placeholder={gatewayProviderForm.id ? "留空则保持原 API Key" : "sk-..."}
                  type="password"
                />
              </label>
              <label>
                默认模型
                <input
                  value={gatewayProviderForm.defaultModel}
                  onChange={(event) => updateGatewayProviderForm("defaultModel", event.target.value)}
                  placeholder="deepseek-chat"
                />
              </label>
              <label>
                Codex 模型映射
                <input
                  value={gatewayProviderForm.gpt53Model}
                  onChange={(event) => updateGatewayProviderForm("gpt53Model", event.target.value)}
                  placeholder="deepseek-chat"
                />
              </label>
              <label>
                鉴权方式
                <select
                  value={gatewayProviderForm.authScheme}
                  onChange={(event) => updateGatewayProviderForm("authScheme", event.target.value)}
                >
                  <option value="bearer">Bearer</option>
                  <option value="x-api-key">X-Api-Key</option>
                  <option value="none">None</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" onClick={() => setGatewayProviderForm(null)}>
                取消
              </button>
              <button className="primary" type="submit" disabled={loading}>
                <Save size={16} />
                保存
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </main>
  );
}

function normalizeDocFiles(doc: ActiveConfig | ProfileDoc | BackupDoc): ConfigFile[] {
  if (doc.files?.length) {
    return doc.files;
  }
  return [
    {
      id: "primary",
      label: doc.format === "json" ? "config.json" : "config.toml",
      filename: doc.format === "json" ? "config.json" : "config.toml",
      content: doc.content,
      format: doc.format,
      mtime: doc.mtime,
      pathLabel: "pathLabel" in doc ? doc.pathLabel : ""
    }
  ];
}

function filesChanged(current: ConfigFile[], saved: ConfigFile[]) {
  if (current.length !== saved.length) return true;
  return current.some((file) => saved.find((item) => item.id === file.id)?.content !== file.content);
}

function formatTime(mtime: number | null) {
  if (!mtime) return "";
  return new Date(mtime * 1000).toLocaleString();
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export default App;
