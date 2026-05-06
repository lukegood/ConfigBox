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
  id: "claude" | "codex";
  name: string;
  format: ConfigFormat;
  profileExt: string;
  pathLabel: string;
  files: ToolFile[];
};

export type ActiveConfig = {
  tool: string;
  content: string;
  format: ConfigFormat;
  mtime: number | null;
  pathLabel: string;
  files?: ConfigFile[];
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
};

export type BackupItem = {
  name: string;
  mtime: number | null;
  size: number;
};

export type BackupDoc = {
  tool: string;
  name: string;
  content: string;
  format: ConfigFormat;
  mtime: number | null;
  files?: ConfigFile[];
};

export type ViewMode = "active" | "profile" | "backup";
