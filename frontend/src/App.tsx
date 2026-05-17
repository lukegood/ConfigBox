import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  Check,
  DatabaseBackup,
  Eye,
  EyeOff,
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
  clearHistory,
  createProfile,
  deleteHistory,
  deleteGatewayProvider,
  deleteProfile,
  getGatewayConfig,
  getGatewayLogs,
  getGatewayStatus,
  getHistory,
  getProfile,
  getTools,
  hasAuth,
  listHistory,
  listProfiles,
  me,
  restoreHistory,
  restartGateway,
  saveProfile,
  setAuth,
  startGateway,
  stopGateway,
  updateGatewayProvider
} from "./api";
import type {
  ConfigFile,
  GatewayConfig,
  GatewayStatus,
  HistoryDoc,
  HistoryItem,
  ProfileDoc,
  ProfileItem,
  Tool,
  ToolId,
  ViewMode
} from "./types";

const profileNamePattern = /^[a-zA-Z0-9_-]{1,64}$/;
const secretDots = "●●●●●●●●●●";

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

type OpenCodeProviderForm = {
  providerId: string;
  name: string;
  npm: string;
  baseURL: string;
  apiKey: string;
  modelId: string;
  modelName: string;
};

type OpenCodeModelForm = {
  providerId: string;
  modelId: string;
  modelName: string;
};

type OpenCodeSummary = {
  valid: boolean;
  providerCount: number;
  modelCount: number;
  providerIds: string[];
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

const emptyOpenCodeProviderForm: OpenCodeProviderForm = {
  providerId: "",
  name: "",
  npm: "@ai-sdk/openai-compatible",
  baseURL: "",
  apiKey: "",
  modelId: "",
  modelName: ""
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
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [mode, setMode] = useState<ViewMode>("profile");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [selectedHistory, setSelectedHistory] = useState<{ profileName: string; name: string } | null>(null);
  const [files, setFiles] = useState<ConfigFile[]>([]);
  const [savedFiles, setSavedFiles] = useState<ConfigFile[]>([]);
  const [activeFileId, setActiveFileId] = useState("");
  const [mtime, setMtime] = useState<number | null>(null);
  const [title, setTitle] = useState("Profile");
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
  const [openCodeProviderForm, setOpenCodeProviderForm] = useState<OpenCodeProviderForm | null>(null);
  const [openCodeModelForm, setOpenCodeModelForm] = useState<OpenCodeModelForm | null>(null);
  const [showGatewayProviderApiKey, setShowGatewayProviderApiKey] = useState(false);
  const [showOpenCodeProviderApiKey, setShowOpenCodeProviderApiKey] = useState(false);

  const tool = useMemo(() => tools.find((item) => item.id === toolId), [tools, toolId]);
  const activeFile = useMemo(() => files.find((file) => file.id === activeFileId) ?? files[0], [files, activeFileId]);
  const activeContent = activeFile?.content ?? "";
  const openCodeStats = useMemo(() => summarizeOpenCodeConfig(activeContent), [activeContent]);
  const dirty = filesChanged(files, savedFiles);
  const readonly = mode === "history" || mode === "gateway";
  const showOpenCodeAssistant = toolId === "opencode" && mode === "profile" && activeFile?.format === "json";
  const sensitive = files.some((file) => /api[_-]?key|token|secret|password/i.test(file.content));
  const contentLength = files.reduce((sum, file) => sum + file.content.length, 0);

  function applyDocument(
    doc: ProfileDoc | HistoryDoc,
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
    const [profileItems, historyItems] = await Promise.all([listProfiles(nextTool), listHistory(nextTool)]);
    setProfiles(profileItems);
    setHistory(historyItems);
    return profileItems;
  }

  async function loadTool(nextTool: ToolId) {
    setLoading(true);
    setError("");
    try {
      setToolId(nextTool);
      const profileItems = await loadLists(nextTool);
      const activeProfile = profileItems.find((item) => item.active) ?? profileItems[0];
      if (!activeProfile) {
        throw new Error("未找到可用 Profile");
      }
      const doc = await getProfile(nextTool, activeProfile.name);
      setMode("profile");
      setSelectedProfile(activeProfile.name);
      setSelectedHistory(null);
      applyDocument(doc, `Profile: ${activeProfile.name}`, "已加载已启用 Profile", "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function reloadSelectedProfile() {
    const fallback = profiles.find((item) => item.active) ?? profiles[0];
    const name = selectedProfile || fallback?.name;
    if (!name) return;
    const doc = await getProfile(toolId, name);
    setMode("profile");
    setSelectedProfile(name);
    setSelectedHistory(null);
    applyDocument(doc, `Profile: ${name}`, "已重新加载");
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
      setSelectedHistory(null);
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
      setSelectedHistory(null);
      applyDocument(doc, `Profile: ${name}`, "已加载 Profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Profile 失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistoryEntry(profileName: string, name: string) {
    setLoading(true);
    setError("");
    try {
      const doc = await getHistory(toolId, profileName, name);
      setMode("history");
      setSelectedHistory({ profileName, name });
      setSelectedProfile("");
      applyDocument(doc, `History: ${profileName}`, "已加载历史版本");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载历史版本失败");
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
    if (mode !== "profile" || !selectedProfile) return;
    setLoading(true);
    setError("");
    try {
      const preferredFileId = activeFileId;
      const saved = await saveProfile(toolId, selectedProfile, files);
      applyDocument(saved, `Profile: ${selectedProfile}`, "Profile 已保存，旧版本已写入 History", preferredFileId);
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
      const profileItems = await loadLists();
      const nextProfile = profileItems.find((item) => item.active) ?? profileItems[0];
      if (nextProfile) {
        await loadProfile(nextProfile.name);
      }
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
      setMode("profile");
      setSelectedHistory(null);
      applyDocument(active, `Profile: ${selectedProfile}`, `已启用 Profile: ${selectedProfile}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启用失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRestoreHistory() {
    if (!selectedHistory) return;
    const { profileName, name } = selectedHistory;
    if (!window.confirm(`恢复 ${profileName} 的历史版本 "${name}"？`)) return;
    setLoading(true);
    setError("");
    try {
      const restored = await restoreHistory(toolId, profileName, name);
      await loadLists();
      setMode("profile");
      setSelectedProfile(profileName);
      setSelectedHistory(null);
      applyDocument(restored, `Profile: ${profileName}`, "历史版本已恢复，恢复前版本也已写入 History");
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteHistory() {
    if (!selectedHistory) return;
    const { profileName, name } = selectedHistory;
    if (!window.confirm(`删除 ${profileName} 的历史版本 "${name}"？`)) return;
    setLoading(true);
    setError("");
    try {
      await deleteHistory(toolId, profileName, name);
      await loadLists();
      await reloadSelectedProfile();
      setStatus("历史版本已删除");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除历史版本失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleClearHistory() {
    if (!history.length) return;
    if (!window.confirm(`删除 ${tool?.name || toolId} 的全部 ${history.length} 条历史版本？`)) return;
    setLoading(true);
    setError("");
    try {
      await clearHistory(toolId);
      await loadLists();
      if (mode === "history") {
        await reloadSelectedProfile();
      }
      setSelectedHistory(null);
      setStatus("全部历史版本已删除");
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空历史版本失败");
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


  async function handleRefreshGatewayLogs() {
    if (loading) return;
    setLoading(true);
    try {
      const logs = await getGatewayLogs();
      setGatewayLogs(logs.lines);
      setGatewayLogBytes({ current: logs.currentBytes, max: logs.maxBytes });
    } catch { /* ignore */ }
    setLoading(false);
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
    setShowGatewayProviderApiKey(false);
    if (!provider) {
      setGatewayProviderForm(emptyGatewayProviderForm);
      return;
    }
    setGatewayProviderForm({
      id: provider.id,
      name: provider.name,
      baseUrl: provider.baseUrl,
      apiKey: provider.apiKey || "",
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

  function openOpenCodeProviderForm() {
    setShowOpenCodeProviderApiKey(false);
    setOpenCodeProviderForm(emptyOpenCodeProviderForm);
  }

  function openOpenCodeModelFormDialog() {
    const stats = summarizeOpenCodeConfig(activeContent);
    if (!stats.valid) {
      setError("OpenCode 配置不是合法 JSON，请先修复后再添加。");
      return;
    }
    if (!stats.providerIds.length) {
      setError("请先添加 Provider。");
      return;
    }
    setOpenCodeModelForm({ providerId: stats.providerIds[0], modelId: "", modelName: "" });
  }

  function updateOpenCodeProviderForm(field: keyof OpenCodeProviderForm, value: string) {
    setOpenCodeProviderForm((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateOpenCodeModelForm(field: keyof OpenCodeModelForm, value: string) {
    setOpenCodeModelForm((current) => (current ? { ...current, [field]: value } : current));
  }

  function handleOpenCodeProviderSubmit(event: FormEvent) {
    event.preventDefault();
    if (!openCodeProviderForm) return;
    const form = trimOpenCodeProviderForm(openCodeProviderForm);
    if (!form.providerId || !form.name || !form.npm || !form.baseURL || !form.apiKey || !form.modelId) {
      setError("Provider ID、名称、npm、Base URL、API Key 和初始模型必填");
      return;
    }
    try {
      const doc = parseOpenCodeObject(activeContent);
      const providers = ensurePlainObject(doc.provider);
      if (providers[form.providerId] !== undefined) {
        setError(`Provider "${form.providerId}" 已存在`);
        return;
      }
      doc.$schema = typeof doc.$schema === "string" ? doc.$schema : "https://opencode.ai/config.json";
      providers[form.providerId] = {
        npm: form.npm,
        name: form.name,
        options: {
          baseURL: form.baseURL,
          apiKey: form.apiKey
        },
        models: {
          [form.modelId]: {
            name: form.modelName || form.modelId
          }
        }
      };
      doc.provider = providers;
      updateActiveContent(formatOpenCodeConfig(doc));
      setOpenCodeProviderForm(null);
      setError("");
      setStatus(`已添加 OpenCode Provider: ${form.providerId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加 Provider 失败");
    }
  }

  function handleOpenCodeModelSubmit(event: FormEvent) {
    event.preventDefault();
    if (!openCodeModelForm) return;
    const providerId = openCodeModelForm.providerId.trim();
    const modelId = openCodeModelForm.modelId.trim();
    const modelName = openCodeModelForm.modelName.trim() || modelId;
    if (!providerId || !modelId) {
      setError("Provider 和模型 ID 必填");
      return;
    }
    try {
      const doc = parseOpenCodeObject(activeContent);
      const providers = ensurePlainObject(doc.provider);
      if (providers[providerId] === undefined) {
        setError(`Provider "${providerId}" 不存在`);
        return;
      }
      const provider = ensurePlainObject(providers[providerId]);
      const models = ensurePlainObject(provider.models);
      if (models[modelId] !== undefined) {
        setError(`Model "${modelId}" 已存在`);
        return;
      }
      models[modelId] = { name: modelName };
      provider.models = models;
      providers[providerId] = provider;
      doc.provider = providers;
      updateActiveContent(formatOpenCodeConfig(doc));
      setOpenCodeModelForm(null);
      setError("");
      setStatus(`已添加 OpenCode Model: ${modelId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加 Model 失败");
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

        {toolId === "codex" ? (
          <section className="nav-section">
            <button className={mode === "gateway" ? "nav-item selected" : "nav-item"} onClick={loadGateway}>
              <span>Gateway</span>
              <PlugZap size={15} />
            </button>
          </section>
        ) : null}

        <section className="nav-section">
          <div className="section-title">
            <span>Profiles</span>
            <div className="mini-actions">
              <button title="从已启用 Profile 创建" onClick={() => handleCreateProfile("active")}>
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

        <section className="nav-section history">
          <div className="section-title">
            <span>History</span>
            <div className="mini-actions">
              <span className="section-icon">
                <DatabaseBackup size={15} />
              </span>
              <button
                className="danger"
                title="删除全部历史"
                onClick={handleClearHistory}
                disabled={loading || history.length === 0}
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>
          <div className="scroll-list">
            {history.map((item) => (
              <button
                key={`${item.profileName}-${item.name}`}
                className={
                  mode === "history" &&
                  selectedHistory?.profileName === item.profileName &&
                  selectedHistory.name === item.name
                    ? "nav-item selected"
                    : "nav-item"
                }
                onClick={() => loadHistoryEntry(item.profileName, item.name)}
                title={`${item.profileName} · ${formatTime(item.mtime)}`}
              >
                <span>{item.profileName}</span>
                <span>{formatTime(item.mtime)}</span>
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
                ? "管理 Providers 与运行日志"
                : mode === "history"
                  ? `历史版本属于 Profile: ${selectedHistory?.profileName ?? "-"}`
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
                <button onClick={reloadSelectedProfile} disabled={loading} title="重新加载">
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
            {mode === "history" ? (
              <>
                <button onClick={handleRestoreHistory} disabled={loading} title="恢复历史版本">
                  <Play size={16} />
                  恢复
                </button>
                <button className="danger" onClick={handleDeleteHistory} disabled={loading} title="删除历史版本">
                  <Trash2 size={16} />
                </button>
              </>
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
              <span>{mode === "history" ? "只读历史" : dirty ? "未保存" : "已同步"}</span>
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
                <div className="section-title gateway-log-heading">
                  <div className="log-title-block">
                    <span>Logs</span>
                    <span className="log-meta">
                      {formatBytes(gatewayLogBytes.current)} / {formatBytes(gatewayLogBytes.max)}
                    </span>
                  </div>
                  <div className="mini-actions">
                    <button onClick={handleRefreshGatewayLogs} disabled={loading} title="刷新日志">
                      <RefreshCcw size={15} />
                      刷新
                    </button>
                    <button className="danger" onClick={handleGatewayClearLogs} disabled={loading} title="清除日志">
                      <Trash2 size={15} />
                      清除日志
                    </button>
                  </div>
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

            <div className={showOpenCodeAssistant ? "editor-panel with-helper" : "editor-panel"}>
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
              {showOpenCodeAssistant ? (
                <div className="opencode-helper">
                  <div className="opencode-helper-title">
                    <span>OpenCode 配置助手</span>
                    <span className={openCodeStats.valid ? "pill" : "pill muted-pill"}>
                      {openCodeStats.valid ? "JSON" : "JSON 错误"}
                    </span>
                  </div>
                  <div className="opencode-helper-stats">
                    <span>{openCodeStats.providerCount} providers</span>
                    <span>{openCodeStats.modelCount} models</span>
                  </div>
                  <div className="opencode-helper-actions">
                    <button type="button" onClick={openOpenCodeProviderForm} disabled={loading}>
                      <FolderPlus size={15} />
                      Provider
                    </button>
                    <button type="button" onClick={openOpenCodeModelFormDialog} disabled={loading}>
                      +
                      Model
                    </button>
                  </div>
                </div>
              ) : null}
              <div className="editor-wrap">
                <Editor
                  key={`${toolId}-${mode}-${selectedProfile}-${selectedHistory?.profileName ?? ""}-${selectedHistory?.name ?? ""}-${activeFile?.id ?? "file"}`}
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
                <div className="secret-input-wrap">
                  <input
                    value={gatewayProviderForm.apiKey}
                    onChange={(event) => updateGatewayProviderForm("apiKey", event.target.value)}
                    placeholder={gatewayProviderForm.id ? "留空则保持原 API Key" : "sk-..."}
                    type={showGatewayProviderApiKey ? "text" : "password"}
                  />
                  <button
                    type="button"
                    className="secret-toggle input"
                    onClick={() => setShowGatewayProviderApiKey((current) => !current)}
                    title={showGatewayProviderApiKey ? "隐藏 Key" : "显示 Key"}
                  >
                    {showGatewayProviderApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
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
                将Codex请求的模型映射为
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
      {openCodeProviderForm ? (
        <div className="modal-backdrop" role="presentation">
          <form className="provider-modal" onSubmit={handleOpenCodeProviderSubmit}>
            <div className="modal-head">
              <div>
                <h3>添加 OpenCode Provider</h3>
                <p>config.json</p>
              </div>
              <button type="button" onClick={() => setOpenCodeProviderForm(null)}>
                关闭
              </button>
            </div>
            <div className="provider-form-grid">
              <label>
                Provider ID
                <input
                  value={openCodeProviderForm.providerId}
                  onChange={(event) => updateOpenCodeProviderForm("providerId", event.target.value)}
                  placeholder="tianyiyun"
                  autoFocus
                />
              </label>
              <label>
                名称
                <input
                  value={openCodeProviderForm.name}
                  onChange={(event) => updateOpenCodeProviderForm("name", event.target.value)}
                  placeholder="tianyiyun"
                />
              </label>
              <label>
                npm
                <input
                  value={openCodeProviderForm.npm}
                  onChange={(event) => updateOpenCodeProviderForm("npm", event.target.value)}
                  placeholder="@ai-sdk/openai-compatible"
                />
              </label>
              <label>
                Base URL
                <input
                  value={openCodeProviderForm.baseURL}
                  onChange={(event) => updateOpenCodeProviderForm("baseURL", event.target.value)}
                  placeholder="https://open.bigmodel.cn/api/coding/paas/v4"
                />
              </label>
              <label>
                API Key
                <div className="secret-input-wrap">
                  <input
                    value={openCodeProviderForm.apiKey}
                    onChange={(event) => updateOpenCodeProviderForm("apiKey", event.target.value)}
                    placeholder="sk-..."
                    type={showOpenCodeProviderApiKey ? "text" : "password"}
                  />
                  <button
                    type="button"
                    className="secret-toggle input"
                    onClick={() => setShowOpenCodeProviderApiKey((current) => !current)}
                    title={showOpenCodeProviderApiKey ? "隐藏 Key" : "显示 Key"}
                  >
                    {showOpenCodeProviderApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </label>
              <label>
                初始模型 ID
                <input
                  value={openCodeProviderForm.modelId}
                  onChange={(event) => updateOpenCodeProviderForm("modelId", event.target.value)}
                  placeholder="GLM-5.1"
                />
              </label>
              <label>
                初始模型名称
                <input
                  value={openCodeProviderForm.modelName}
                  onChange={(event) => updateOpenCodeProviderForm("modelName", event.target.value)}
                  placeholder="GLM-5.1"
                />
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" onClick={() => setOpenCodeProviderForm(null)}>
                取消
              </button>
              <button className="primary" type="submit">
                <Save size={16} />
                添加
              </button>
            </div>
          </form>
        </div>
      ) : null}
      {openCodeModelForm ? (
        <div className="modal-backdrop" role="presentation">
          <form className="provider-modal compact-modal" onSubmit={handleOpenCodeModelSubmit}>
            <div className="modal-head">
              <div>
                <h3>添加 OpenCode Model</h3>
                <p>config.json</p>
              </div>
              <button type="button" onClick={() => setOpenCodeModelForm(null)}>
                关闭
              </button>
            </div>
            <div className="provider-form-grid">
              <label>
                Provider
                <select
                  value={openCodeModelForm.providerId}
                  onChange={(event) => updateOpenCodeModelForm("providerId", event.target.value)}
                  autoFocus
                >
                  {openCodeStats.providerIds.map((providerId) => (
                    <option key={providerId} value={providerId}>
                      {providerId}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                模型 ID
                <input
                  value={openCodeModelForm.modelId}
                  onChange={(event) => updateOpenCodeModelForm("modelId", event.target.value)}
                  placeholder="GLM-5.1"
                />
              </label>
              <label>
                模型名称
                <input
                  value={openCodeModelForm.modelName}
                  onChange={(event) => updateOpenCodeModelForm("modelName", event.target.value)}
                  placeholder="GLM-5.1"
                />
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" onClick={() => setOpenCodeModelForm(null)}>
                取消
              </button>
              <button className="primary" type="submit">
                <Save size={16} />
                添加
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </main>
  );
}

function normalizeDocFiles(doc: ProfileDoc | HistoryDoc): ConfigFile[] {
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
      pathLabel: ""
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

function parseOpenCodeObject(content: string): Record<string, unknown> {
  const parsed = JSON.parse(content || "{}");
  if (!isPlainObject(parsed)) {
    throw new Error("OpenCode 配置根节点必须是 JSON 对象");
  }
  return parsed;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function ensurePlainObject(value: unknown): Record<string, unknown> {
  return isPlainObject(value) ? value : {};
}

function summarizeOpenCodeConfig(content: string): OpenCodeSummary {
  try {
    const doc = parseOpenCodeObject(content);
    const providers = ensurePlainObject(doc.provider);
    const providerIds = Object.keys(providers);
    const modelCount = Object.values(providers).reduce<number>((sum, provider) => {
      const providerDoc = ensurePlainObject(provider);
      return sum + Object.keys(ensurePlainObject(providerDoc.models)).length;
    }, 0);
    return {
      valid: true,
      providerCount: providerIds.length,
      modelCount,
      providerIds
    };
  } catch {
    return {
      valid: false,
      providerCount: 0,
      modelCount: 0,
      providerIds: []
    };
  }
}

function trimOpenCodeProviderForm(form: OpenCodeProviderForm): OpenCodeProviderForm {
  return {
    providerId: form.providerId.trim(),
    name: form.name.trim(),
    npm: form.npm.trim(),
    baseURL: form.baseURL.trim(),
    apiKey: form.apiKey.trim(),
    modelId: form.modelId.trim(),
    modelName: form.modelName.trim()
  };
}

function formatOpenCodeConfig(doc: Record<string, unknown>) {
  return JSON.stringify(doc, null, 2) + "\n";
}

export default App;
