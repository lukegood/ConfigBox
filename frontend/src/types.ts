export type ConfigFormat = "json" | "toml";

export type ToolFile = {
  id: string;
  label: string;
  filename: string;
  format: ConfigFormat;
  pathLabel: string;
};

export type ConfigFile = ToolFile & {
  content: string;
  mtime: number | null;
};

export type Tool = {
  id: ToolId;
  name: string;
  format: ConfigFormat;
  profileExt: string;
  pathLabel: string;
  files: ToolFile[];
};

export type ProfileItem = {
  name: string;
  mtime: number | null;
  active: boolean;
};

export type ProfileDoc = {
  tool: string;
  name: string;
  content: string;
  format: ConfigFormat;
  mtime: number | null;
  files?: ConfigFile[];
  active?: boolean;
  runtimeChanged?: boolean;
};

export type HistoryItem = {
  profileName: string;
  name: string;
  mtime: number | null;
  size: number;
  reason: string;
};

export type HistoryDoc = {
  tool: string;
  profileName: string;
  name: string;
  content: string;
  format: ConfigFormat;
  mtime: number | null;
  files?: ConfigFile[];
};

export type ToolId = "claude" | "codex" | "opencode";

export type ViewMode = "profile" | "history" | "gateway";

export type GatewayProvider = {
  id: string;
  name: string;
  baseUrl: string;
  apiFormat: string;
  authScheme: string;
  models: Record<string, string>;
  extraHeaders?: Record<string, string>;
  modelCapabilities?: Record<string, unknown>;
  requestOptions?: Record<string, unknown>;
  apiKey?: string;
  hasApiKey?: boolean;
  hasGrokWeb?: boolean;
  isBuiltin?: boolean;
};

export type GatewayPresetMessage = {
  level?: "info" | "warning" | string;
  text: string;
};

export type GatewayPresetBaseUrl = {
  url: string;
  label?: string;
};

export type GatewayPreset = {
  id: string;
  name: string;
  description?: string;
  experimental?: boolean;
  baseUrls?: GatewayPresetBaseUrl[];
  messages?: GatewayPresetMessage[];
  provider: Pick<GatewayProvider, "name" | "baseUrl" | "apiFormat" | "authScheme" | "models"> & {
    extraHeaders?: Record<string, string>;
    modelCapabilities?: Record<string, unknown>;
    requestOptions?: Record<string, unknown>;
  };
};

export type GatewayModelEntry = {
  id?: string;
  model?: string;
  name?: string;
  display_name?: string;
  recommended?: boolean;
  tag_title?: string;
};

export type GatewayConfig = {
  activeProvider: string | null;
  gatewayApiKey: string;
  gatewayApiKeyPresent: boolean;
  providers: GatewayProvider[];
  path: string;
  logDir: string;
  settings: {
    proxyPort: number;
  };
};

export type GatewayStatus = {
  running: boolean;
  managedProcess: boolean;
  healthy: boolean;
  pid: number | null;
  host: string;
  publicBaseUrl: string;
  port: number;
  configPath: string;
  logDir: string;
  activeProvider: string | null;
  providerCount: number;
  codexRestored?: boolean;
  codexApplied?: boolean;
};

export type OAuthStatus = {
  loggedIn: boolean;
  email?: string | null;
  projectId?: string | null;
  expiresAt?: number | null;
  shouldRefresh?: boolean;
  cancelled?: boolean;
};
