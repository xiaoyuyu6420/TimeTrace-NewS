import { useEffect, useState } from 'react';
import api from '../../api/client';
import {
  Settings as SettingsIcon, Key, Sliders, Save, CheckCircle, AlertTriangle,
  Eye, EyeOff, RefreshCw, Plus, Trash2, Edit3, X, ChevronDown, ChevronRight,
  Zap, Cpu, ShieldCheck, FileSearch, Bot, Server,
} from 'lucide-react';

// ─── 常量 ──────────────────────────────────────────────────────────

const PRESET_BASES = [
  { label: '智谱 AI', url: 'https://open.bigmodel.cn/api/paas/v4' },
  { label: 'DeepSeek', url: 'https://api.deepseek.com/v1' },
  { label: 'Moonshot', url: 'https://api.moonshot.cn/v1' },
  { label: '通义千问', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { label: '零一万物', url: 'https://api.lingyiwanwu.com/v1' },
  { label: 'Ollama', url: 'http://localhost:11434/v1' },
  { label: 'OpenAI', url: 'https://api.openai.com/v1' },
];

const ROLES = [
  { key: 'distill', label: '拆解（Distill）', desc: '小模型，快速提取原子事实', icon: FileSearch, color: 'text-blue-500', bg: 'bg-blue-50' },
  { key: 'reason', label: '推演（Reason）', desc: '大模型，深度分析与判断', icon: Cpu, color: 'text-purple-500', bg: 'bg-purple-50' },
  { key: 'audit', label: '审计（Audit）', desc: '验证事实、检测冲突', icon: ShieldCheck, color: 'text-amber-500', bg: 'bg-amber-50' },
  { key: 'embed', label: '向量化（Embed）', desc: '生成文本 Embedding', icon: Zap, color: 'text-emerald-500', bg: 'bg-emerald-50' },
] as const;

// ─── 类型 ──────────────────────────────────────────────────────────

interface LlmModelItem {
  id: number;
  provider_id: number;
  name: string;
  model: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  is_active: boolean;
  created_at: string | null;
}

interface Provider {
  id: number;
  name: string;
  api_base: string;
  api_key_set: boolean;
  is_active: boolean;
  created_at: string | null;
  models: LlmModelItem[];
}

interface EmbedModelItem {
  id: number;
  provider_id: number;
  name: string;
  model: string;
  is_active: boolean;
  created_at: string | null;
}

interface EmbedProvider {
  id: number;
  name: string;
  api_base: string;
  api_key_set: boolean;
  is_active: boolean;
  created_at: string | null;
  models: EmbedModelItem[];
}

interface DiscoveredModel {
  id: string;
  owned_by: string;
}

interface RoutingConfig {
  distill_model_id: number | null;
  distill_model_name: string | null;
  distill_provider_name: string | null;
  reason_model_id: number | null;
  reason_model_name: string | null;
  reason_provider_name: string | null;
  audit_model_id: number | null;
  audit_model_name: string | null;
  audit_provider_name: string | null;
  embed_model_id: number | null;
  embed_model_name: string | null;
  embed_provider_name: string | null;
}

interface SettingsData {
  crawl_interval_minutes: number;
  similarity_threshold: number;
  embedding_threshold: number;
  event_time_window_days: number;
  event_auto_close_days: number;
}

interface FlatLlmModel {
  id: number;
  name: string;
  model: string;
  is_active: boolean;
  provider_name: string;
}

interface FlatEmbedModel {
  id: number;
  name: string;
  model: string;
  is_active: boolean;
  provider_name: string;
}

// ─── 编辑弹窗状态类型 ──────────────────────────────────────────────

interface ProviderEdit {
  mode: 'create' | 'edit';
  id?: number;
  data: { name: string; api_base: string; api_key: string };
  type: 'llm' | 'embed';
}

interface LlmModelEdit {
  providerId: number;
  mode: 'create' | 'edit';
  id?: number;
  data: { name: string; model: string; temperature: number; top_p: number; max_tokens: number };
}

interface EmbedModelEdit {
  providerId: number;
  mode: 'create' | 'edit';
  id?: number;
  data: { name: string; model: string };
}

interface PipelineForm {
  crawlInterval: number;
  simThreshold: number;
  embThreshold: number;
  timeWindow: number;
  autoClose: number;
}

const EMPTY_PROVIDER = { name: '', api_base: 'https://open.bigmodel.cn/api/paas/v4', api_key: '' };
const EMPTY_LLM_MODEL = { name: '', model: '', temperature: 0.3, top_p: 0.7, max_tokens: 300 };
const EMPTY_EMBED_MODEL = { name: '', model: '' };

// ─── 主组件 ────────────────────────────────────────────────────────

export function AdminSettings() {
  // ── Tab ──
  const [activeTab, setActiveTab] = useState<'providers' | 'embeddings' | 'routing' | 'pipeline'>('providers');

  // ── 全局状态 ──
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // ── LLM 供应商列表 ──
  const [providers, setProviders] = useState<Provider[]>([]);
  const [expandedProvider, setExpandedProvider] = useState<number | null>(null);

  // ── Embed 供应商列表 ──
  const [embedProviders, setEmbedProviders] = useState<EmbedProvider[]>([]);
  const [expandedEmbedProvider, setExpandedEmbedProvider] = useState<number | null>(null);

  // ── 供应商编辑弹窗（LLM + Embed 共用） ──
  const [editProvider, setEditProvider] = useState<ProviderEdit | null>(null);
  const [showKey, setShowKey] = useState(false);

  // ── LLM 模型编辑弹窗 ──
  const [editLlmModel, setEditLlmModel] = useState<LlmModelEdit | null>(null);

  // ── Embed 模型编辑弹窗 ──
  const [editEmbedModel, setEditEmbedModel] = useState<EmbedModelEdit | null>(null);

  // ── 模型发现 ──
  const [discovered, setDiscovered] = useState<DiscoveredModel[]>([]);
  const [loadingDiscover, setLoadingDiscover] = useState(false);

  // ── 编排 ──
  const [routing, setRouting] = useState<RoutingConfig | null>(null);
  const [savingRt, setSavingRt] = useState(false);

  // ── 管线参数 ──
  const [pipelineForm, setPipelineForm] = useState<PipelineForm>({
    crawlInterval: 1440,
    simThreshold: 0.5,
    embThreshold: 0.7,
    timeWindow: 30,
    autoClose: 14,
  });
  const [savingPipe, setSavingPipe] = useState(false);

  // ── 派生：扁平化模型列表（供编排 Tab 使用） ──
  const allLlmModels: FlatLlmModel[] = providers.flatMap(p =>
    p.models.map(m => ({ id: m.id, name: m.name, model: m.model, is_active: m.is_active, provider_name: p.name }))
  );
  const allEmbedModels: FlatEmbedModel[] = embedProviders.flatMap(p =>
    p.models.map(m => ({ id: m.id, name: m.name, model: m.model, is_active: m.is_active, provider_name: p.name }))
  );

  // ─── 初始化加载 ──────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get<Provider[]>('/admin/llm-providers').then(r => setProviders(r.data)).catch((e) => console.error('Failed to load LLM providers:', e)),
      api.get<EmbedProvider[]>('/admin/embed-providers').then(r => setEmbedProviders(r.data)).catch((e) => console.error('Failed to load embed providers:', e)),
      api.get<RoutingConfig>('/admin/llm-routing').then(r => setRouting(r.data)).catch((e) => console.error('Failed to load routing:', e)),
      api.get<SettingsData>('/admin/settings').then(r => {
        const d = r.data;
        setPipelineForm({
          crawlInterval: d.crawl_interval_minutes,
          simThreshold: d.similarity_threshold,
          embThreshold: d.embedding_threshold,
          timeWindow: d.event_time_window_days,
          autoClose: d.event_auto_close_days,
        });
      }).catch((e) => console.error('Failed to load settings:', e)),
    ]).finally(() => setLoading(false));
  }, []);

  // 消息自动消失
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(null), 4000);
    return () => clearTimeout(t);
  }, [message]);

  // ─── LLM 供应商操作 ──────────────────────────────────────────
  const refreshLlmProviders = async () => {
    const res = await api.get<Provider[]>('/admin/llm-providers');
    setProviders(res.data);
  };

  const refreshEmbedProviders = async () => {
    const res = await api.get<EmbedProvider[]>('/admin/embed-providers');
    setEmbedProviders(res.data);
  };

  const saveProvider = async () => {
    if (!editProvider || !editProvider.data.name) return;
    setSaving(true);
    const baseUrl = editProvider.type === 'llm' ? '/admin/llm-providers' : '/admin/embed-providers';
    try {
      if (editProvider.mode === 'create') {
        await api.post(baseUrl, editProvider.data);
        setMessage({ type: 'success', text: '供应商已创建' });
      } else {
        await api.put(`${baseUrl}/${editProvider.id}`, editProvider.data);
        setMessage({ type: 'success', text: '供应商已更新' });
      }
      setEditProvider(null);
      if (editProvider.type === 'llm') {
        await refreshLlmProviders();
      } else {
        await refreshEmbedProviders();
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const deleteLlmProvider = async (id: number) => {
    if (!confirm('确定删除此供应商及其所有模型？')) return;
    try {
      await api.delete(`/admin/llm-providers/${id}`);
      setEditProvider(null);
      await refreshLlmProviders();
      const res = await api.get<RoutingConfig>('/admin/llm-routing');
      setRouting(res.data);
      setMessage({ type: 'success', text: '供应商已删除' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '删除失败' });
    }
  };

  const deleteEmbedProvider = async (id: number) => {
    if (!confirm('确定删除此向量供应商及其所有模型？')) return;
    try {
      await api.delete(`/admin/embed-providers/${id}`);
      setEditProvider(null);
      await refreshEmbedProviders();
      const res = await api.get<RoutingConfig>('/admin/llm-routing');
      setRouting(res.data);
      setMessage({ type: 'success', text: '向量供应商已删除' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '删除失败' });
    }
  };

  // ─── 模型发现 ──────────────────────────────────────────────
  const discoverModels = async (baseUrl: string, providerId: number) => {
    setLoadingDiscover(true);
    setDiscovered([]);
    try {
      const res = await api.post<DiscoveredModel[]>(`${baseUrl}/${providerId}/discover-models`);
      setDiscovered(res.data);
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '获取模型失败' });
    } finally {
      setLoadingDiscover(false);
    }
  };

  // ─── LLM 模型操作 ──────────────────────────────────────────
  const saveLlmModel = async () => {
    if (!editLlmModel || !editLlmModel.data.name || !editLlmModel.data.model) return;
    setSaving(true);
    try {
      if (editLlmModel.mode === 'create') {
        await api.post(`/admin/llm-providers/${editLlmModel.providerId}/models`, editLlmModel.data);
        setMessage({ type: 'success', text: '模型已创建' });
      } else {
        await api.put(`/admin/llm-models/${editLlmModel.id}`, editLlmModel.data);
        setMessage({ type: 'success', text: '模型已更新' });
      }
      await refreshLlmProviders();
      setEditLlmModel(null);
      setDiscovered([]);
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const deleteLlmModel = async (id: number) => {
    if (!confirm('确定删除此模型？')) return;
    try {
      await api.delete(`/admin/llm-models/${id}`);
      await refreshLlmProviders();
      const res = await api.get<RoutingConfig>('/admin/llm-routing');
      setRouting(res.data);
      setMessage({ type: 'success', text: '模型已删除' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '删除失败' });
    }
  };

  // ─── Embed 模型操作 ────────────────────────────────────────
  const saveEmbedModel = async () => {
    if (!editEmbedModel || !editEmbedModel.data.name || !editEmbedModel.data.model) return;
    setSaving(true);
    try {
      if (editEmbedModel.mode === 'create') {
        await api.post(`/admin/embed-providers/${editEmbedModel.providerId}/models`, editEmbedModel.data);
        setMessage({ type: 'success', text: '向量模型已创建' });
      } else {
        await api.put(`/admin/embed-models/${editEmbedModel.id}`, editEmbedModel.data);
        setMessage({ type: 'success', text: '向量模型已更新' });
      }
      await refreshEmbedProviders();
      setEditEmbedModel(null);
      setDiscovered([]);
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const deleteEmbedModel = async (id: number) => {
    if (!confirm('确定删除此向量模型？')) return;
    try {
      await api.delete(`/admin/embed-models/${id}`);
      await refreshEmbedProviders();
      const res = await api.get<RoutingConfig>('/admin/llm-routing');
      setRouting(res.data);
      setMessage({ type: 'success', text: '向量模型已删除' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '删除失败' });
    }
  };

  // ─── 编排操作 ────────────────────────────────────────────────
  const saveRouting = async (updates: Record<string, number | null>) => {
    setSavingRt(true);
    try {
      const res = await api.put<RoutingConfig>('/admin/llm-routing', updates);
      setRouting(res.data);
      setMessage({ type: 'success', text: '编排已更新' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSavingRt(false);
    }
  };

  // ─── 管线参数保存 ────────────────────────────────────────────
  const savePipeline = async () => {
    setSavingPipe(true);
    try {
      await api.put('/admin/settings', {
        crawl_interval_minutes: pipelineForm.crawlInterval,
        similarity_threshold: pipelineForm.simThreshold,
        embedding_threshold: pipelineForm.embThreshold,
        event_time_window_days: pipelineForm.timeWindow,
        event_auto_close_days: pipelineForm.autoClose,
      });
      setMessage({ type: 'success', text: '管线参数已保存' });
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.response?.data?.detail || '保存失败' });
    } finally {
      setSavingPipe(false);
    }
  };

  // ─── 加载状态 ────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="w-6 h-6 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
      </div>
    );
  }

  // ─── 渲染 ────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center shadow-lg">
          <SettingsIcon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-800">系统设置</h1>
          <p className="text-sm text-slate-400">LLM 渠道管理、向量模型、编排配置、管线参数</p>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
          {message.text}
        </div>
      )}

      {/* Tab 栏 */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
        {([
          { key: 'providers' as const, label: 'LLM 模型', icon: Server },
          { key: 'embeddings' as const, label: '向量模型', icon: Zap },
          { key: 'routing' as const, label: '编排配置', icon: Cpu },
          { key: 'pipeline' as const, label: '管线参数', icon: Sliders },
        ]).map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══ Tab: LLM 供应商与模型 ═════════════════════════════ */}
      {activeTab === 'providers' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">
              添加 LLM 供应商，然后在每个供应商下添加多个对话模型
            </p>
            <button
              onClick={() => { setEditProvider({ mode: 'create', data: { ...EMPTY_PROVIDER }, type: 'llm' }); setShowKey(false); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30"
            >
              <Plus className="w-4 h-4" /> 添加供应商
            </button>
          </div>

          {providers.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border border-slate-200/80">
              <Server className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">还没有配置 LLM 供应商</p>
            </div>
          ) : (
            <div className="space-y-3">
              {providers.map(p => {
                const isExpanded = expandedProvider === p.id;
                return (
                  <div key={p.id} className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
                    <div
                      className="flex items-center gap-3 p-4 cursor-pointer hover:bg-slate-50/50"
                      onClick={() => setExpandedProvider(isExpanded ? null : p.id)}
                    >
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
                        : <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />}
                      <Server className="w-5 h-5 text-cyan-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{p.name}</span>
                          {p.is_active
                            ? <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-600">活跃</span>
                            : <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-400">停用</span>}
                          <span className="text-xs text-slate-400">{p.models.length} 个模型</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 truncate">{p.api_base}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => {
                            setEditProvider({ mode: 'edit', id: p.id, data: { name: p.name, api_base: p.api_base, api_key: '' }, type: 'llm' });
                            setShowKey(false);
                          }}
                          className="p-2 rounded-lg text-slate-400 hover:text-cyan-600 hover:bg-cyan-50"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteLlmProvider(p.id)}
                          className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-slate-100 px-4 pb-4">
                        {p.models.length > 0 && (
                          <div className="divide-y divide-slate-50 mt-2 mb-3">
                            {p.models.map(m => (
                              <div key={m.id} className="flex items-center gap-3 py-2.5">
                                <Bot className={`w-4 h-4 shrink-0 ${m.is_active ? 'text-cyan-500' : 'text-slate-300'}`} />
                                <div className="flex-1 min-w-0">
                                  <span className="text-sm font-medium text-slate-700">{m.name}</span>
                                  <span className="text-xs text-slate-400 ml-2">{m.model}</span>
                                  <span className="text-xs text-slate-300 ml-2">
                                    T={m.temperature} P={m.top_p} M={m.max_tokens}
                                  </span>
                                </div>
                                <div className="flex items-center gap-1 shrink-0">
                                  <button
                                    onClick={() => {
                                      setEditLlmModel({
                                        providerId: p.id, mode: 'edit', id: m.id,
                                        data: { name: m.name, model: m.model, temperature: m.temperature, top_p: m.top_p, max_tokens: m.max_tokens },
                                      });
                                      setDiscovered([]);
                                    }}
                                    className="p-1.5 rounded text-slate-400 hover:text-cyan-600 hover:bg-cyan-50"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => deleteLlmModel(m.id)}
                                    className="p-1.5 rounded text-slate-400 hover:text-red-600 hover:bg-red-50"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => {
                            setEditLlmModel({ providerId: p.id, mode: 'create', data: { ...EMPTY_LLM_MODEL } });
                            setDiscovered([]);
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-cyan-600 border border-cyan-200 bg-cyan-50 hover:bg-cyan-100"
                        >
                          <Plus className="w-3.5 h-3.5" /> 添加模型
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── LLM 模型编辑弹窗 ── */}
          {editLlmModel && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => { setEditLlmModel(null); setDiscovered([]); }}>
              <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                  <h3 className="font-semibold text-slate-800">
                    {editLlmModel.mode === 'create' ? '添加 LLM 模型' : '编辑 LLM 模型'}
                  </h3>
                  <button onClick={() => { setEditLlmModel(null); setDiscovered([]); }} className="p-1 rounded text-slate-400 hover:text-slate-600">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="p-5 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">模型名称</label>
                    <input
                      value={editLlmModel.data.name}
                      onChange={e => setEditLlmModel({ ...editLlmModel, data: { ...editLlmModel.data, name: e.target.value } })}
                      placeholder="如：GLM-4-Flash"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-sm font-medium text-slate-600">模型 ID</label>
                      <button
                        onClick={() => discoverModels('/admin/llm-providers', editLlmModel.providerId)}
                        disabled={loadingDiscover}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-cyan-50 text-cyan-600 border border-cyan-200 hover:bg-cyan-100 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 ${loadingDiscover ? 'animate-spin' : ''}`} />
                        {loadingDiscover ? '获取中...' : '自动发现'}
                      </button>
                    </div>
                    {discovered.length > 0 ? (
                      <select
                        value={editLlmModel.data.model}
                        onChange={e => {
                          const sel = e.target.value;
                          setEditLlmModel({
                            ...editLlmModel,
                            data: { ...editLlmModel.data, model: sel, name: editLlmModel.data.name || sel },
                          });
                        }}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                      >
                        <option value="">-- 选择模型 --</option>
                        {discovered.map(m => (
                          <option key={m.id} value={m.id}>
                            {m.id} {m.owned_by ? `(${m.owned_by})` : ''}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={editLlmModel.data.model}
                        onChange={e => setEditLlmModel({ ...editLlmModel, data: { ...editLlmModel.data, model: e.target.value } })}
                        placeholder="如：glm-4-flash"
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                      />
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-600 mb-1">
                        Temperature <span className="text-cyan-500 font-mono">{editLlmModel.data.temperature.toFixed(1)}</span>
                      </label>
                      <input type="range" min="0" max="2" step="0.1"
                        value={editLlmModel.data.temperature}
                        onChange={e => setEditLlmModel({ ...editLlmModel, data: { ...editLlmModel.data, temperature: parseFloat(e.target.value) } })}
                        className="w-full accent-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-600 mb-1">
                        Top P <span className="text-cyan-500 font-mono">{editLlmModel.data.top_p.toFixed(1)}</span>
                      </label>
                      <input type="range" min="0" max="1" step="0.1"
                        value={editLlmModel.data.top_p}
                        onChange={e => setEditLlmModel({ ...editLlmModel, data: { ...editLlmModel.data, top_p: parseFloat(e.target.value) } })}
                        className="w-full accent-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-600 mb-1">Max Tokens</label>
                      <input type="number" min="1" max="32000"
                        value={editLlmModel.data.max_tokens}
                        onChange={e => setEditLlmModel({ ...editLlmModel, data: { ...editLlmModel.data, max_tokens: parseInt(e.target.value) || 300 } })}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button onClick={() => { setEditLlmModel(null); setDiscovered([]); }} className="px-4 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100">取消</button>
                    <button
                      onClick={saveLlmModel}
                      disabled={saving || !editLlmModel.data.name || !editLlmModel.data.model}
                      className="flex items-center gap-1.5 px-5 py-2 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30 disabled:opacity-50"
                    >
                      <Save className="w-4 h-4" />
                      {saving ? '保存中...' : '保存'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ Tab: 向量模型（独立供应商） ═════════════════════════ */}
      {activeTab === 'embeddings' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">
              管理 Embedding 向量模型供应商与模型（独立于 LLM 供应商）
            </p>
            <button
              onClick={() => { setEditProvider({ mode: 'create', data: { ...EMPTY_PROVIDER }, type: 'embed' }); setShowKey(false); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-white text-sm font-medium shadow-md shadow-emerald-200/30 bg-gradient-to-r from-emerald-500 to-teal-500"
            >
              <Plus className="w-4 h-4" /> 添加向量供应商
            </button>
          </div>

          {embedProviders.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border border-slate-200/80">
              <Zap className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">还没有配置向量模型供应商</p>
            </div>
          ) : (
            <div className="space-y-3">
              {embedProviders.map(p => {
                const isExpanded = expandedEmbedProvider === p.id;
                return (
                  <div key={p.id} className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
                    <div
                      className="flex items-center gap-3 p-4 cursor-pointer hover:bg-slate-50/50"
                      onClick={() => setExpandedEmbedProvider(isExpanded ? null : p.id)}
                    >
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
                        : <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />}
                      <Zap className="w-5 h-5 text-emerald-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{p.name}</span>
                          {p.is_active
                            ? <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-600">活跃</span>
                            : <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-400">停用</span>}
                          <span className="text-xs text-slate-400">{p.models.length} 个向量模型</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 truncate">{p.api_base}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => {
                            setEditProvider({ mode: 'edit', id: p.id, data: { name: p.name, api_base: p.api_base, api_key: '' }, type: 'embed' });
                            setShowKey(false);
                          }}
                          className="p-2 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteEmbedProvider(p.id)}
                          className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-slate-100 px-4 pb-4">
                        {p.models.length > 0 && (
                          <div className="divide-y divide-slate-50 mt-2 mb-3">
                            {p.models.map(m => (
                              <div key={m.id} className="flex items-center gap-3 py-2.5">
                                <Bot className={`w-4 h-4 shrink-0 ${m.is_active ? 'text-emerald-500' : 'text-slate-300'}`} />
                                <div className="flex-1 min-w-0">
                                  <span className="text-sm font-medium text-slate-700">{m.name}</span>
                                  <span className="text-xs text-slate-400 ml-2">{m.model}</span>
                                </div>
                                <div className="flex items-center gap-1 shrink-0">
                                  <button
                                    onClick={() => {
                                      setEditEmbedModel({
                                        providerId: p.id, mode: 'edit', id: m.id,
                                        data: { name: m.name, model: m.model },
                                      });
                                      setDiscovered([]);
                                    }}
                                    className="p-1.5 rounded text-slate-400 hover:text-emerald-600 hover:bg-emerald-50"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => deleteEmbedModel(m.id)}
                                    className="p-1.5 rounded text-slate-400 hover:text-red-600 hover:bg-red-50"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => {
                            setEditEmbedModel({ providerId: p.id, mode: 'create', data: { ...EMPTY_EMBED_MODEL } });
                            setDiscovered([]);
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-emerald-600 border border-emerald-200 bg-emerald-50 hover:bg-emerald-100"
                        >
                          <Plus className="w-3.5 h-3.5" /> 添加向量模型
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Embed 模型编辑弹窗 ── */}
          {editEmbedModel && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => { setEditEmbedModel(null); setDiscovered([]); }}>
              <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                  <h3 className="font-semibold text-slate-800">
                    {editEmbedModel.mode === 'create' ? '添加向量模型' : '编辑向量模型'}
                  </h3>
                  <button onClick={() => { setEditEmbedModel(null); setDiscovered([]); }} className="p-1 rounded text-slate-400 hover:text-slate-600">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="p-5 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">模型名称</label>
                    <input
                      value={editEmbedModel.data.name}
                      onChange={e => setEditEmbedModel({ ...editEmbedModel, data: { ...editEmbedModel.data, name: e.target.value } })}
                      placeholder="如：BGE-M3"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-200"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-sm font-medium text-slate-600">模型 ID</label>
                      <button
                        onClick={() => discoverModels('/admin/embed-providers', editEmbedModel.providerId)}
                        disabled={loadingDiscover}
                        className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 ${loadingDiscover ? 'animate-spin' : ''}`} />
                        {loadingDiscover ? '获取中...' : '自动发现'}
                      </button>
                    </div>
                    {discovered.length > 0 ? (
                      <select
                        value={editEmbedModel.data.model}
                        onChange={e => {
                          const sel = e.target.value;
                          setEditEmbedModel({
                            ...editEmbedModel,
                            data: { ...editEmbedModel.data, model: sel, name: editEmbedModel.data.name || sel },
                          });
                        }}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-200"
                      >
                        <option value="">-- 选择模型 --</option>
                        {discovered.map(m => (
                          <option key={m.id} value={m.id}>
                            {m.id} {m.owned_by ? `(${m.owned_by})` : ''}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={editEmbedModel.data.model}
                        onChange={e => setEditEmbedModel({ ...editEmbedModel, data: { ...editEmbedModel.data, model: e.target.value } })}
                        placeholder="如：BAAI/bge-m3"
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-200"
                      />
                    )}
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button onClick={() => { setEditEmbedModel(null); setDiscovered([]); }} className="px-4 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100">取消</button>
                    <button
                      onClick={saveEmbedModel}
                      disabled={saving || !editEmbedModel.data.name || !editEmbedModel.data.model}
                      className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-sm font-medium shadow-md shadow-emerald-200/30 disabled:opacity-50"
                    >
                      <Save className="w-4 h-4" />
                      {saving ? '保存中...' : '保存'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ Tab: 编排配置 ═══════════════════════════════════════ */}
      {activeTab === 'routing' && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            为每个管线角色指定使用哪个模型。未指定时回退到默认配置。
          </p>
          {allLlmModels.length === 0 && allEmbedModels.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border border-slate-200/80">
              <Cpu className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">请先添加供应商和模型</p>
            </div>
          ) : (
            <div className="space-y-3">
              {ROLES.map(role => {
                const Icon = role.icon;
                const currentModelId = routing ? (routing as unknown as Record<string, unknown>)[`${role.key}_model_id`] as number | null : null;
                const currentModelName = routing ? (routing as unknown as Record<string, unknown>)[`${role.key}_model_name`] as string | null : null;
                const currentProviderName = routing ? (routing as unknown as Record<string, unknown>)[`${role.key}_provider_name`] as string | null : null;

                const isEmbed = role.key === 'embed';
                const modelList = isEmbed ? allEmbedModels : allLlmModels;

                return (
                  <div key={role.key} className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className={`w-9 h-9 rounded-lg ${role.bg} flex items-center justify-center ${role.color}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-slate-800 text-sm">{role.label}</p>
                        <p className="text-xs text-slate-400">{role.desc}</p>
                      </div>
                      {currentModelName && (
                        <span className={`px-2 py-1 rounded text-xs border ${
                          isEmbed ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-cyan-50 text-cyan-700 border-cyan-200'
                        }`}>
                          {currentProviderName} / {currentModelName}
                        </span>
                      )}
                    </div>
                    <select
                      value={currentModelId ?? ''}
                      onChange={e => {
                        const val = e.target.value ? parseInt(e.target.value) : null;
                        saveRouting({ [`${role.key}_model_id`]: val });
                      }}
                      disabled={savingRt}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200 disabled:opacity-50"
                    >
                      <option value="">-- 使用默认 --</option>
                      {modelList.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.provider_name} / {m.name} ({m.model})
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══ Tab: 管线参数 ═════════════════════════════════════ */}
      {activeTab === 'pipeline' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 bg-slate-50 border-b border-slate-100">
              <Sliders className="w-4 h-4 text-emerald-500" />
              <h2 className="text-sm font-semibold text-slate-700">聚合参数</h2>
            </div>
            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">关键词相似度阈值</label>
                <input
                  type="number" step="0.05" min="0.1" max="1.0"
                  value={pipelineForm.simThreshold}
                  onChange={e => setPipelineForm({ ...pipelineForm, simThreshold: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
                <p className="text-xs text-slate-400 mt-1">越低越容易关联到已有事件</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Embedding 阈值</label>
                <input
                  type="number" step="0.05" min="0.1" max="1.0"
                  value={pipelineForm.embThreshold}
                  onChange={e => setPipelineForm({ ...pipelineForm, embThreshold: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
                <p className="text-xs text-slate-400 mt-1">向量相似度达到此值自动关联</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 bg-slate-50 border-b border-slate-100">
              <Key className="w-4 h-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-slate-700">采集策略</h2>
            </div>
            <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">爬取间隔（分钟）</label>
                <input
                  type="number" min="1" max="10080"
                  value={pipelineForm.crawlInterval}
                  onChange={e => setPipelineForm({ ...pipelineForm, crawlInterval: parseInt(e.target.value) || 1440 })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">事件窗口（天）</label>
                <input
                  type="number" min="1" max="365"
                  value={pipelineForm.timeWindow}
                  onChange={e => setPipelineForm({ ...pipelineForm, timeWindow: parseInt(e.target.value) || 30 })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">自动关闭（天）</label>
                <input
                  type="number" min="1" max="365"
                  value={pipelineForm.autoClose}
                  onChange={e => setPipelineForm({ ...pipelineForm, autoClose: parseInt(e.target.value) || 14 })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={savePipeline}
              disabled={savingPipe}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30 disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {savingPipe ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      {/* ── 供应商编辑弹窗（LLM + Embed 共用） ── */}
      {editProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setEditProvider(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h3 className="font-semibold text-slate-800">
                {editProvider.mode === 'create' ? `添加${editProvider.type === 'llm' ? '' : '向量'}供应商` : `编辑${editProvider.type === 'llm' ? '' : '向量'}供应商`}
              </h3>
              <button onClick={() => setEditProvider(null)} className="p-1 rounded text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">供应商名称</label>
                <input
                  value={editProvider.data.name}
                  onChange={e => setEditProvider({ ...editProvider, data: { ...editProvider.data, name: e.target.value } })}
                  placeholder={editProvider.type === 'llm' ? '如：智谱AI、DeepSeek' : '如：硅基流动、智谱AI'}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">API Key</label>
                <div className="flex gap-2">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={editProvider.data.api_key}
                    onChange={e => setEditProvider({ ...editProvider, data: { ...editProvider.data, api_key: e.target.value } })}
                    placeholder={editProvider.mode === 'edit' ? '留空则不修改' : '输入 API Key...'}
                    className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                  />
                  <button onClick={() => setShowKey(!showKey)} className="px-3 py-2 border border-slate-200 rounded-lg text-slate-400 hover:text-slate-600">
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">API Base URL</label>
                <input
                  value={editProvider.data.api_base}
                  onChange={e => setEditProvider({ ...editProvider, data: { ...editProvider.data, api_base: e.target.value } })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {PRESET_BASES.map(pr => (
                    <button
                      key={pr.url}
                      onClick={() => setEditProvider({ ...editProvider, data: { ...editProvider.data, api_base: pr.url } })}
                      className={`px-2 py-1 rounded text-xs transition-colors ${
                        editProvider.data.api_base === pr.url
                          ? 'bg-cyan-50 text-cyan-700 border border-cyan-200'
                          : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {pr.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setEditProvider(null)} className="px-4 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100">取消</button>
                <button
                  onClick={saveProvider}
                  disabled={saving || !editProvider.data.name}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30 disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
