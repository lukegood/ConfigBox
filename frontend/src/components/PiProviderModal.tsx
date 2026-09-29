import { Eye, EyeOff, Save, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { applyPiPreset, nextPiModelRow, piApis, piPresets } from "../pi";
import type { PiModelRow, PiProviderForm } from "../pi";

type Props = {
  initial: PiProviderForm;
  onCancel: () => void;
  onSubmit: (form: PiProviderForm) => void;
};

export function PiProviderModal({ initial, onCancel, onSubmit }: Props) {
  const [form, setForm] = useState(initial);
  const [showApiKey, setShowApiKey] = useState(false);
  const isEditing = Boolean(form.originalProviderId);
  const knownApi = piApis.some((api) => api.value === form.api);

  function update<K extends keyof PiProviderForm>(field: K, value: PiProviderForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateModel<K extends keyof PiModelRow>(rowId: string, field: K, value: PiModelRow[K]) {
    setForm((current) => ({
      ...current,
      models: current.models.map((model) => (model.rowId === rowId ? { ...model, [field]: value } : model))
    }));
  }

  function removeModel(rowId: string) {
    setForm((current) => ({
      ...current,
      models: current.models.length > 1 ? current.models.filter((model) => model.rowId !== rowId) : [nextPiModelRow()]
    }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="provider-modal" onSubmit={handleSubmit}>
        <div className="modal-head">
          <div>
            <h3>{isEditing ? "编辑 Pi Provider" : "添加 Pi Provider"}</h3>
            <p>models.json · providers</p>
          </div>
          <button type="button" onClick={onCancel}>
            关闭
          </button>
        </div>
        <section className="gateway-preset-section">
          <div className="gateway-mapping-head">
            <div>
              <h4>快捷预设</h4>
              <p>按 pi models.json 写法填充 API 协议、Base URL 和常用模型。</p>
            </div>
          </div>
          <div className="gateway-preset-grid">
            {piPresets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={form.presetId === preset.id ? "gateway-preset-card selected" : "gateway-preset-card"}
                onClick={() => {
                  setForm((current) => applyPiPreset(current, preset));
                  setShowApiKey(false);
                }}
              >
                <span>
                  <strong>{preset.name}</strong>
                  <small>{preset.description}</small>
                </span>
                <span className="provider-meta">{preset.api}</span>
              </button>
            ))}
          </div>
        </section>
        <div className="provider-form-grid">
          <label>
            Provider ID
            <input
              value={form.providerId}
              onChange={(event) => update("providerId", event.target.value)}
              placeholder="deepseek"
              autoFocus
            />
          </label>
          <label>
            名称
            <input value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="可选" />
          </label>
          <label>
            API 协议
            <select value={form.api} onChange={(event) => update("api", event.target.value)}>
              <option value="">不设置（沿用内置 Provider）</option>
              {piApis.map((api) => (
                <option key={api.value} value={api.value}>
                  {api.label}
                </option>
              ))}
              {!knownApi && form.api ? <option value={form.api}>{form.api}</option> : null}
            </select>
          </label>
          <label>
            Base URL
            <input
              value={form.baseUrl}
              onChange={(event) => update("baseUrl", event.target.value)}
              placeholder="https://api.deepseek.com/v1"
            />
          </label>
          <label>
            API Key
            <div className="secret-input-wrap">
              <input
                value={form.apiKey}
                onChange={(event) => update("apiKey", event.target.value)}
                placeholder={
                  form.hasExistingApiKey ? "留空则保持原 API Key" : "sk-... 或 $ENV_NAME；留空则用 /login 或环境变量"
                }
                type={showApiKey ? "text" : "password"}
              />
              <button
                type="button"
                className="secret-toggle input"
                onClick={() => setShowApiKey((current) => !current)}
                title={showApiKey ? "隐藏 Key" : "显示 Key"}
              >
                {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </label>
          <label className="gateway-inline-toggle pi-default-toggle">
            <input
              type="checkbox"
              checked={form.setDefault}
              onChange={(event) => update("setDefault", event.target.checked)}
            />
            保存后设为 pi 默认模型（settings.json）
          </label>
        </div>
        <section className="gateway-mapping-section">
          <div className="gateway-mapping-head">
            <div>
              <h4>模型</h4>
              <p>写入 providers.*.models；未填写 contextWindow 时 pi 默认 128000。</p>
            </div>
            <button type="button" onClick={() => update("models", [...form.models, nextPiModelRow()])}>
              + 模型
            </button>
          </div>
          <div className="gateway-custom-mappings">
            {form.models.map((model) => (
              <div className="gateway-custom-mapping-row pi-model-row" key={model.rowId}>
                <label>
                  模型 ID
                  <input
                    value={model.id}
                    onChange={(event) => updateModel(model.rowId, "id", event.target.value)}
                    placeholder="deepseek-chat"
                  />
                </label>
                <label>
                  模型名称
                  <input
                    value={model.name}
                    onChange={(event) => updateModel(model.rowId, "name", event.target.value)}
                    placeholder={model.id || "可选"}
                  />
                </label>
                <label>
                  contextWindow
                  <input
                    value={model.contextWindow}
                    onChange={(event) => updateModel(model.rowId, "contextWindow", event.target.value)}
                    placeholder="128000"
                    inputMode="numeric"
                  />
                </label>
                <label className="gateway-inline-toggle">
                  <input
                    type="checkbox"
                    checked={model.reasoning}
                    onChange={(event) => updateModel(model.rowId, "reasoning", event.target.checked)}
                  />
                  reasoning
                </label>
                <button type="button" className="danger" onClick={() => removeModel(model.rowId)} title="删除模型">
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </section>
        <div className="modal-actions">
          <button type="button" onClick={onCancel}>
            取消
          </button>
          <button className="primary" type="submit">
            <Save size={16} />
            保存
          </button>
        </div>
      </form>
    </div>
  );
}
