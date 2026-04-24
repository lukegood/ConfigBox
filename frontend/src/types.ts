export type Tool = {
  id: "claude" | "codex";
  name: string;
  format: "json" | "toml";
  profileExt: string;
  pathLabel: string;
};

export type ActiveConfig = {
  tool: string;
  content: string;
  format: "json" | "toml";
  mtime: number | null;
  pathLabel: string;
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
  format: "json" | "toml";
  mtime: number | null;
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
  format: "json" | "toml";
  mtime: number | null;
};

export type ViewMode = "active" | "profile" | "backup";
