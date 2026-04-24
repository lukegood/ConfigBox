import type { ActiveConfig, BackupDoc, BackupItem, ProfileDoc, ProfileItem, Tool } from "./types";

const AUTH_KEY = "configbox.loggedIn";

export async function setAuth(username: string, password: string) {
  const user = await request<{ username: string; defaultPassword: boolean }>("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  sessionStorage.setItem(AUTH_KEY, "1");
  return user;
}

export async function clearAuth() {
  sessionStorage.removeItem(AUTH_KEY);
  try {
    await request<{ ok: boolean }>("/api/logout", { method: "POST" });
  } catch {
    // The cookie may already be gone.
  }
}

export function hasAuth() {
  return Boolean(sessionStorage.getItem(AUTH_KEY));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = data?.error?.message || response.statusText || "Request failed";
    const error = new Error(message) as Error & { code?: string; status?: number };
    error.code = data?.error?.code;
    error.status = response.status;
    throw error;
  }
  return data as T;
}

export async function me() {
  return request<{ username: string; defaultPassword: boolean }>("/api/me");
}

export async function getTools() {
  return request<Tool[]>("/api/tools");
}

export async function getActiveConfig(tool: string) {
  return request<ActiveConfig>(`/api/configs/${tool}/active`);
}

export async function saveActiveConfig(tool: string, content: string, mtime?: number | null) {
  return request<ActiveConfig>(`/api/configs/${tool}/active`, {
    method: "PUT",
    body: JSON.stringify({ content, lastKnownMtime: mtime ?? null })
  });
}

export async function listProfiles(tool: string) {
  return request<ProfileItem[]>(`/api/profiles/${tool}`);
}

export async function createProfile(tool: string, name: string, source: "active" | "empty" = "active") {
  return request<ProfileDoc>(`/api/profiles/${tool}`, {
    method: "POST",
    body: JSON.stringify({ name, source })
  });
}

export async function getProfile(tool: string, name: string) {
  return request<ProfileDoc>(`/api/profiles/${tool}/${name}`);
}

export async function saveProfile(tool: string, name: string, content: string) {
  return request<ProfileDoc>(`/api/profiles/${tool}/${name}`, {
    method: "PUT",
    body: JSON.stringify({ content })
  });
}

export async function deleteProfile(tool: string, name: string) {
  return request<{ ok: boolean }>(`/api/profiles/${tool}/${name}`, { method: "DELETE" });
}

export async function activateProfile(tool: string, name: string) {
  return request<ActiveConfig>(`/api/profiles/${tool}/${name}/activate`, { method: "POST" });
}

export async function listBackups(tool: string) {
  return request<BackupItem[]>(`/api/backups/${tool}`);
}

export async function getBackup(tool: string, backupName: string) {
  return request<BackupDoc>(`/api/backups/${tool}/${backupName}`);
}

export async function restoreBackup(tool: string, backupName: string) {
  return request<ActiveConfig>(`/api/backups/${tool}/${backupName}/restore`, { method: "POST" });
}
