// Helpers for pi coding agent profiles: models.json (JSONC) + settings.json (strict JSON).

export const piApis = [
  { value: "openai-completions", label: "OpenAI Chat Completions" },
  { value: "openai-responses", label: "OpenAI Responses" },
  { value: "anthropic-messages", label: "Anthropic Messages" },
  { value: "google-generative-ai", label: "Google Generative AI" }
] as const;

export type PiPreset = {
  id: string;
  name: string;
  description: string;
  api: string;
  baseUrl: string;
  apiKey?: string;
  models: Array<{ id: string; name: string; reasoning?: boolean; contextWindow?: number }>;
};

export type PiModelRow = {
  rowId: string;
  id: string;
  name: string;
  contextWindow: string;
  reasoning: boolean;
};

export type PiProviderForm = {
  originalProviderId: string;
  presetId: string;
  providerId: string;
  name: string;
  api: string;
  baseUrl: string;
  apiKey: string;
  hasExistingApiKey: boolean;
  models: PiModelRow[];
  setDefault: boolean;
};

export type PiProviderSummary = {
  id: string;
  name: string;
  api: string;
  baseUrl: string;
  modelIds: string[];
};

export type PiModelsSummary = {
  valid: boolean;
  hasComments: boolean;
  providers: PiProviderSummary[];
  modelCount: number;
};

export type PiDefaults = {
  valid: boolean;
  provider: string;
  model: string;
};

export const piPresets: PiPreset[] = [
  {
    id: "openai-compatible",
    name: "OpenAI Compatible",
    description: "通用 OpenAI 兼容接口",
    api: "openai-completions",
    baseUrl: "",
    models: [{ id: "", name: "" }]
  },
  {
    id: "ollama",
    name: "Ollama",
    description: "本机 Ollama，Key 为占位值",
    api: "openai-completions",
    baseUrl: "http://localhost:11434/v1",
    apiKey: "ollama",
    models: [{ id: "qwen2.5-coder:7b", name: "Qwen2.5 Coder 7B" }]
  },
  {
    id: "zhipu",
    name: "智谱 GLM",
    description: "GLM Coding / OpenAI 兼容接口",
    api: "openai-completions",
    baseUrl: "https://open.bigmodel.cn/api/coding/paas/v4",
    models: [{ id: "GLM-5.1", name: "GLM-5.1", reasoning: true }]
  },
  {
    id: "moonshot",
    name: "Moonshot Kimi",
    description: "Moonshot OpenAI 兼容接口",
    api: "openai-completions",
    baseUrl: "https://api.moonshot.cn/v1",
    models: [{ id: "kimi-k2-0711-preview", name: "Kimi K2" }]
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek OpenAI 兼容接口",
    api: "openai-completions",
    baseUrl: "https://api.deepseek.com/v1",
    models: [{ id: "deepseek-chat", name: "DeepSeek Chat" }]
  }
];

let piModelRowCounter = 0;

export function nextPiModelRow(model: Partial<Omit<PiModelRow, "rowId">> = {}): PiModelRow {
  piModelRowCounter += 1;
  return {
    rowId: `pi-model-${piModelRowCounter}`,
    id: model.id ?? "",
    name: model.name ?? "",
    contextWindow: model.contextWindow ?? "",
    reasoning: model.reasoning ?? false
  };
}

// Same rules as pi's stripJsonComments: `//` line comments and trailing commas only.
export function stripPiJsonc(content: string) {
  return content
    .replace(/"(?:\\.|[^"\\])*"|\/\/[^\n]*/g, (match) => (match[0] === '"' ? match : ""))
    .replace(/"(?:\\.|[^"\\])*"|,(\s*[}\]])/g, (match, tail?: string) => tail ?? (match[0] === '"' ? match : ""));
}

export function hasPiJsoncSyntax(content: string) {
  return stripPiJsonc(content) !== content;
}

export function parsePiModels(content: string): Record<string, unknown> {
  const parsed = JSON.parse(stripPiJsonc(content || "{}"));
  if (!isPlainObject(parsed)) {
    throw new Error("models.json 根节点必须是 JSON 对象");
  }
  if (parsed.providers !== undefined && !isPlainObject(parsed.providers)) {
    throw new Error("models.json 的 providers 必须是对象");
  }
  return parsed;
}

export function parsePiSettings(content: string): Record<string, unknown> {
  const parsed = JSON.parse(content || "{}");
  if (!isPlainObject(parsed)) {
    throw new Error("settings.json 根节点必须是 JSON 对象");
  }
  return parsed;
}

export function formatPiJson(doc: Record<string, unknown>) {
  return JSON.stringify(doc, null, 2) + "\n";
}

export function summarizePiModels(content: string): PiModelsSummary {
  try {
    const doc = parsePiModels(content);
    const providers = Object.entries(ensurePlainObject(doc.providers)).map(([id, value]) => {
      const provider = ensurePlainObject(value);
      return {
        id,
        name: stringValue(provider.name),
        api: stringValue(provider.api),
        baseUrl: stringValue(provider.baseUrl),
        modelIds: piModelList(provider)
          .map((model) => stringValue(model.id))
          .filter(Boolean)
      };
    });
    return {
      valid: true,
      hasComments: hasPiJsoncSyntax(content),
      providers,
      modelCount: providers.reduce((sum, provider) => sum + provider.modelIds.length, 0)
    };
  } catch {
    return { valid: false, hasComments: false, providers: [], modelCount: 0 };
  }
}

export function readPiDefaults(content: string): PiDefaults {
  try {
    const doc = parsePiSettings(content);
    return { valid: true, provider: stringValue(doc.defaultProvider), model: stringValue(doc.defaultModel) };
  } catch {
    return { valid: false, provider: "", model: "" };
  }
}

export function emptyPiProviderForm(): PiProviderForm {
  return {
    originalProviderId: "",
    presetId: "",
    providerId: "",
    name: "",
    api: "openai-completions",
    baseUrl: "",
    apiKey: "",
    hasExistingApiKey: false,
    models: [nextPiModelRow()],
    setDefault: false
  };
}

export function piProviderFormFromContent(modelsContent: string, providerId: string): PiProviderForm {
  const doc = parsePiModels(modelsContent);
  const provider = ensurePlainObject(ensurePlainObject(doc.providers)[providerId]);
  const models = piModelList(provider).map((model) =>
    nextPiModelRow({
      id: stringValue(model.id),
      name: stringValue(model.name),
      contextWindow: typeof model.contextWindow === "number" ? String(model.contextWindow) : "",
      reasoning: model.reasoning === true
    })
  );
  return {
    originalProviderId: providerId,
    presetId: findPiPresetId(stringValue(provider.baseUrl)),
    providerId,
    name: stringValue(provider.name),
    api: stringValue(provider.api),
    baseUrl: stringValue(provider.baseUrl),
    apiKey: "",
    hasExistingApiKey: Boolean(stringValue(provider.apiKey)),
    models: models.length ? models : [nextPiModelRow()],
    setDefault: false
  };
}

export function applyPiPreset(form: PiProviderForm, preset: PiPreset): PiProviderForm {
  return {
    ...form,
    presetId: preset.id,
    providerId: form.originalProviderId ? form.providerId : preset.id,
    name: preset.name,
    api: preset.api,
    baseUrl: preset.baseUrl,
    apiKey: preset.apiKey ?? form.apiKey,
    models: preset.models.map((model) =>
      nextPiModelRow({
        id: model.id,
        name: model.name,
        contextWindow: model.contextWindow ? String(model.contextWindow) : "",
        reasoning: model.reasoning === true
      })
    )
  };
}

/**
 * Applies the provider form to models.json and, when needed, settings.json.
 * Unknown provider/model fields (headers, compat, cost, modelOverrides, ...) are preserved.
 * Returns the new file contents; settingsContent is null when settings.json is unchanged.
 */
export function applyPiProviderForm(
  modelsContent: string,
  settingsContent: string,
  rawForm: PiProviderForm
): { modelsContent: string; settingsContent: string | null } {
  const form = trimPiProviderForm(rawForm);
  const rows = form.models.filter((model) => model.id);
  if (!form.providerId) {
    throw new Error("Provider ID 必填");
  }
  if (!form.baseUrl && !rows.length) {
    throw new Error("Base URL 和模型至少填写一项");
  }
  const duplicated = findDuplicate(rows.map((model) => model.id));
  if (duplicated) {
    throw new Error(`Model "${duplicated}" 重复`);
  }
  for (const row of rows) {
    if (row.contextWindow && !/^[1-9]\d*$/.test(row.contextWindow)) {
      throw new Error(`Model "${row.id}" 的 contextWindow 必须是正整数`);
    }
  }
  if (form.setDefault && !rows.length) {
    throw new Error("设为默认需要至少一个模型");
  }

  const doc = parsePiModels(modelsContent);
  const providers = ensurePlainObject(doc.providers);
  const isEditing = Boolean(form.originalProviderId);
  const renamed = isEditing && form.originalProviderId !== form.providerId;
  if ((!isEditing || renamed) && providers[form.providerId] !== undefined) {
    throw new Error(`Provider "${form.providerId}" 已存在`);
  }

  const existingProvider = ensurePlainObject(providers[form.originalProviderId || form.providerId]);
  const existingModels = new Map(piModelList(existingProvider).map((model) => [stringValue(model.id), model]));
  const nextModels = rows.map((row) => {
    const model: Record<string, unknown> = { ...(existingModels.get(row.id) ?? {}), id: row.id };
    assignOrDelete(model, "name", row.name);
    assignOrDelete(model, "contextWindow", row.contextWindow ? Number(row.contextWindow) : "");
    assignOrDelete(model, "reasoning", row.reasoning ? true : "");
    return model;
  });

  const provider: Record<string, unknown> = { ...existingProvider };
  assignOrDelete(provider, "name", form.name);
  assignOrDelete(provider, "api", form.api);
  assignOrDelete(provider, "baseUrl", form.baseUrl);
  if (form.apiKey) {
    provider.apiKey = form.apiKey;
  }
  assignOrDelete(provider, "models", nextModels.length ? nextModels : "");

  if (renamed) {
    delete providers[form.originalProviderId];
  }
  providers[form.providerId] = provider;
  doc.providers = providers;

  let nextSettings: string | null = null;
  const defaults = readPiDefaults(settingsContent);
  const pointsToOriginal = isEditing && defaults.provider === form.originalProviderId;
  if (form.setDefault || (renamed && pointsToOriginal)) {
    if (!defaults.valid) {
      throw new Error("settings.json 不是合法 JSON，无法更新默认模型");
    }
    const settings = parsePiSettings(settingsContent);
    settings.defaultProvider = form.providerId;
    // Keep the current default model when it still exists on this provider.
    const keepModel = pointsToOriginal && rows.some((row) => row.id === defaults.model);
    if (form.setDefault && !keepModel) {
      settings.defaultModel = rows[0].id;
    }
    nextSettings = formatPiJson(settings);
  }

  return { modelsContent: formatPiJson(doc), settingsContent: nextSettings };
}

export function deletePiProvider(modelsContent: string, providerId: string) {
  const doc = parsePiModels(modelsContent);
  const providers = ensurePlainObject(doc.providers);
  delete providers[providerId];
  doc.providers = providers;
  return formatPiJson(doc);
}

export function setPiDefaultModel(settingsContent: string, provider: string, model: string) {
  const doc = parsePiSettings(settingsContent);
  if (provider && model) {
    doc.defaultProvider = provider;
    doc.defaultModel = model;
  } else {
    delete doc.defaultProvider;
    delete doc.defaultModel;
  }
  return formatPiJson(doc);
}

function trimPiProviderForm(form: PiProviderForm): PiProviderForm {
  return {
    ...form,
    originalProviderId: form.originalProviderId.trim(),
    providerId: form.providerId.trim(),
    name: form.name.trim(),
    api: form.api.trim(),
    baseUrl: form.baseUrl.trim(),
    apiKey: form.apiKey.trim(),
    models: form.models.map((model) => ({
      ...model,
      id: model.id.trim(),
      name: model.name.trim(),
      contextWindow: model.contextWindow.trim()
    }))
  };
}

function piModelList(provider: Record<string, unknown>) {
  return Array.isArray(provider.models) ? provider.models.map(ensurePlainObject) : [];
}

function findPiPresetId(baseUrl: string) {
  const normalized = normalizeUrl(baseUrl);
  if (!normalized) return "";
  return piPresets.find((preset) => preset.baseUrl && normalizeUrl(preset.baseUrl) === normalized)?.id || "";
}

function assignOrDelete(target: Record<string, unknown>, key: string, value: unknown) {
  if (value === "" || value === undefined) {
    delete target[key];
  } else {
    target[key] = value;
  }
}

function normalizeUrl(value: string) {
  return value.trim().replace(/\/+$/, "").toLowerCase();
}

function findDuplicate(values: string[]) {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) return value;
    seen.add(value);
  }
  return "";
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function ensurePlainObject(value: unknown): Record<string, unknown> {
  return isPlainObject(value) ? value : {};
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}
