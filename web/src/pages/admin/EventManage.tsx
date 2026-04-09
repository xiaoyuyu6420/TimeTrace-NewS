import { useEffect, useState } from 'react';
import api from '../../api/client';
import {
  Merge, ArrowRight, Zap, Upload,
  ChevronLeft, ChevronRight, Check, X,
  Play, FastForward, RefreshCw, Cpu,
} from 'lucide-react';
import type { Article, Event, PageResponse } from '../../types';

// ─── Types ─────────────────────────────────────────────

// ─── Component ─────────────────────────────────────────

export function AdminEventManage() {
  const [activeTab, setActiveTab] = useState<'merge' | 'assign' | 'tools' | 'import'>('merge');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">事件整理</h1>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-xl w-fit">
        {[
          { key: 'merge' as const, label: '合并事件', icon: Merge },
          { key: 'assign' as const, label: '分配文章', icon: ArrowRight },
          { key: 'tools' as const, label: '工具', icon: Zap },
          { key: 'import' as const, label: '导入历史', icon: Upload },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === key
                ? 'gradient-brand text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700 hover:bg-white'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'merge' && <MergePanel />}
      {activeTab === 'assign' && <AssignPanel />}
      {activeTab === 'tools' && <ToolsPanel />}
      {activeTab === 'import' && <ImportPanel />}
    </div>
  );
}

// ─── Merge Events Panel ────────────────────────────────

function MergePanel() {
  const [events, setEvents] = useState<PageResponse<Event>>({ items: [], total: 0, page: 1, page_size: 50, total_pages: 0 });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [merging, setMerging] = useState(false);
  const [msg, setMsg] = useState('');

  const fetchEvents = () => {
    api.get<PageResponse<Event>>('/events', { params: { page, page_size: 50, status: 'active' } })
      .then(r => setEvents(r.data))
      .catch((e) => console.error('Failed to load events:', e));
  };

  useEffect(() => { fetchEvents(); }, [page]);

  const toggleSelect = (id: number) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleMerge = async () => {
    if (selected.length < 2) return;
    setMerging(true);
    setMsg('');
    try {
      // Merge all into the first selected
      const targetId = selected[0];
      for (let i = 1; i < selected.length; i++) {
        await api.post('/admin/events/merge', {
          source_id: selected[i],
          target_id: targetId,
        });
      }
      setMsg(`成功合并 ${selected.length} 个事件`);
      setSelected([]);
      fetchEvents();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || '合并失败');
    }
    setMerging(false);
  };

  return (
    <div>
      {msg && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${msg.includes('成功') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-slate-500">已选 {selected.length} 个事件</span>
        <button
          onClick={handleMerge}
          disabled={selected.length < 2 || merging}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl gradient-brand text-white text-sm shadow-sm disabled:opacity-40"
        >
          <Merge className="w-3.5 h-3.5" />
          {merging ? '合并中...' : '合并选中'}
        </button>
        {selected.length >= 2 && (
          <span className="text-xs text-slate-400">
            将合并到: {events.items.find(e => e.id === selected[0])?.title || '第一个'}
          </span>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200/80 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80 text-slate-500 text-xs">
            <tr>
              <th className="w-10 px-3 py-3"></th>
              <th className="text-left px-3 py-3 font-medium">标题</th>
              <th className="text-left px-3 py-3 font-medium">文章数</th>
              <th className="text-left px-3 py-3 font-medium">类别</th>
            </tr>
          </thead>
          <tbody>
            {events.items.map(e => (
              <tr
                key={e.id}
                className={`border-t border-slate-100 transition-colors cursor-pointer ${
                  selected.includes(e.id) ? 'bg-cyan-50/50' : 'hover:bg-slate-50/50'
                }`}
                onClick={() => toggleSelect(e.id)}
              >
                <td className="px-3 py-3">
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                    selected.includes(e.id) ? 'border-cyan-500 bg-cyan-500' : 'border-slate-300'
                  }`}>
                    {selected.includes(e.id) && <Check className="w-3 h-3 text-white" />}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <div className="font-medium text-slate-800 line-clamp-1">{e.title}</div>
                  {e.summary && <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{e.summary}</div>}
                </td>
                <td className="px-3 py-3 text-slate-500">{e.article_count}</td>
                <td className="px-3 py-3">
                  {e.category && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 text-xs">{e.category}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {events.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">上一页</button>
          <span className="px-3 py-1.5 text-sm text-slate-400">{page} / {events.total_pages}</span>
          <button onClick={() => setPage(Math.min(events.total_pages, page + 1))} disabled={page === events.total_pages}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">下一页</button>
        </div>
      )}
    </div>
  );
}

// ─── Assign Articles Panel ─────────────────────────────

function AssignPanel() {
  const [unassigned, setUnassigned] = useState<PageResponse<Article>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  const [events, setEvents] = useState<Event[]>([]);
  const [page, setPage] = useState(1);
  const [assigning, setAssigning] = useState<Record<number, number>>({}); // articleId -> eventId
  const [msg, setMsg] = useState('');

  const fetchData = () => {
    api.get<PageResponse<Article>>('/admin/articles/unassigned', { params: { page, page_size: 20 } })
      .then(r => setUnassigned(r.data))
      .catch((e) => console.error('Failed to load unassigned articles:', e));
    api.get<PageResponse<Event>>('/events', { params: { page: 1, page_size: 100, status: 'active' } })
      .then(r => setEvents(r.data.items))
      .catch((e) => console.error('Failed to load events for assign:', e));
  };

  useEffect(() => { fetchData(); }, [page]);

  const handleAssign = async (articleId: number, eventId: number) => {
    setMsg('');
    try {
      await api.post(`/admin/articles/${articleId}/assign`, { event_id: eventId });
      setMsg('分配成功');
      setAssigning(prev => {
        const next = { ...prev };
        delete next[articleId];
        return next;
      });
      fetchData();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || '分配失败');
    }
  };

  return (
    <div>
      {msg && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${msg.includes('成功') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      <div className="mb-4 text-sm text-slate-500">
        未分组文章: {unassigned.total} 篇
      </div>

      <div className="space-y-2">
        {unassigned.items.map(a => (
          <div key={a.id} className="bg-white rounded-xl border border-slate-200/80 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-800 line-clamp-2">{a.title}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(a.keywords || []).slice(0, 5).map(kw => (
                    <span key={kw} className="px-1.5 py-0.5 rounded bg-cyan-50 text-cyan-600 text-[10px]">{kw}</span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <select
                  value={assigning[a.id] || ''}
                  onChange={e => setAssigning(prev => ({ ...prev, [a.id]: Number(e.target.value) }))}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm outline-none focus:border-cyan-400 max-w-[200px]"
                >
                  <option value="">选择事件...</option>
                  {events.map(ev => (
                    <option key={ev.id} value={ev.id}>{ev.title}</option>
                  ))}
                </select>
                <button
                  onClick={() => assigning[a.id] && handleAssign(a.id, assigning[a.id])}
                  disabled={!assigning[a.id]}
                  className="p-2 rounded-lg gradient-brand text-white disabled:opacity-30"
                >
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {unassigned.items.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <Check className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
            所有文章都已分组
          </div>
        )}
      </div>

      {unassigned.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">上一页</button>
          <span className="px-3 py-1.5 text-sm text-slate-400">{page} / {unassigned.total_pages}</span>
          <button onClick={() => setPage(Math.min(unassigned.total_pages, page + 1))} disabled={page === unassigned.total_pages}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">下一页</button>
        </div>
      )}
    </div>
  );
}

// ─── Tools Panel ───────────────────────────────────────

function ToolsPanel() {
  const [running, setRunning] = useState('');
  const [msg, setMsg] = useState('');

  const triggerAction = async (action: string, endpoint: string, params?: Record<string, unknown>) => {
    setRunning(action);
    setMsg('');
    try {
      const res = await api.post(endpoint, null, { params });
      setMsg(res.data.message || `${action}已启动`);
    } catch {
      setMsg(`${action}失败`);
    }
    setRunning('');
  };

  const tools = [
    {
      key: '完整管线',
      icon: Play,
      gradient: 'from-cyan-500 to-blue-600',
      title: '运行完整管线',
      desc: 'RSS 爬取 → 蒸馏 → 推演 → 审计 → 聚合 → 精炼',
      detail: '爬取所有活跃 RSS 源的新文章，然后对 raw 文章依次执行 LLM 蒸馏（原子事实提取）、推演（事件关联判定）、审计（质量验证），最终聚合为事件。',
      endpoint: '/admin/pipeline',
      params: {},
    },
    {
      key: '重跑管线',
      icon: FastForward,
      gradient: 'from-violet-500 to-purple-600',
      title: '重跑管线（不爬取）',
      desc: '对已有的 raw 文章执行蒸馏 → 推演 → 审计',
      detail: '跳过 RSS 爬取，只处理数据库中 pipeline_state=raw 的文章。适合调整 LLM 编排或修改算法后重跑。',
      endpoint: '/admin/pipeline',
      params: { skip_crawl: true },
    },
    {
      key: '重新向量化',
      icon: Cpu,
      gradient: 'from-amber-400 to-orange-500',
      title: '重新向量化',
      desc: '为缺少 Embedding 的文章生成语义向量',
      detail: '使用配置的向量模型为缺少向量的文章生成语义向量。向量用于文章与事件之间的相似度匹配。',
      endpoint: '/admin/reembed',
      params: {},
    },
    {
      key: '旧式聚合',
      icon: RefreshCw,
      gradient: 'from-slate-400 to-slate-600',
      title: '旧式聚合',
      desc: '关键词提取 + Embedding 相似度匹配（不含三级管线）',
      detail: '旧的处理方式：jieba 关键词提取 + Embedding 向量相似度匹配。不经过蒸馏/推演/审计。仅作为备用方案。',
      endpoint: '/admin/aggregate',
      params: {},
    },
  ];

  return (
    <div className="space-y-4">
      {msg && (
        <div className="px-4 py-2 rounded-lg text-sm bg-cyan-50 text-cyan-700">{msg}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {tools.map(tool => {
          const Icon = tool.icon;
          const isRunning = running === tool.key;
          return (
            <div key={tool.key} className="bg-white rounded-xl border border-slate-200/80 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="font-medium text-slate-800">{tool.title}</div>
                  <div className="text-xs text-slate-400">{tool.desc}</div>
                </div>
              </div>
              <p className="text-sm text-slate-500 mb-4">{tool.detail}</p>
              <button
                onClick={() => triggerAction(tool.key, tool.endpoint, tool.params)}
                disabled={!!running}
                className={`px-4 py-2 rounded-xl bg-gradient-to-r ${tool.gradient} text-white text-sm disabled:opacity-40 transition-opacity`}
              >
                {isRunning ? '运行中...' : '开始执行'}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Import History Panel ─────────────────────────────────

function ImportPanel() {
  const [jsonText, setJsonText] = useState('');
  const [importing, setImporting] = useState(false);
  const [msg, setMsg] = useState('');
  const [fileInfo, setFileInfo] = useState('');

  const handleImport = async () => {
    if (!jsonText.trim()) return;
    setImporting(true);
    setMsg('');
    try {
      const articles = JSON.parse(jsonText);
      if (!Array.isArray(articles)) {
        setMsg('数据必须是数组格式');
        setImporting(false);
        return;
      }
      const res = await api.post('/admin/import-articles', { articles });
      setMsg(`导入完成：${res.data.imported} 篇导入，${res.data.skipped} 篇跳过（重复）`);
      setJsonText('');
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || e?.message || '导入失败');
    }
    setImporting(false);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileInfo(`${file.name} (${(file.size / 1024).toFixed(1)}KB)`);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setJsonText(text);
    };
    reader.readAsText(file);
  };

  return (
    <div className="space-y-6">
      {/* 说明 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <h3 className="font-medium text-amber-800 mb-2">历史数据导入</h3>
        <p className="text-sm text-amber-700 leading-relaxed">
          通过以下方式导入历史新闻数据，系统会自动去重、提取关键词并聚合为事件。
        </p>
        <div className="mt-3 text-xs text-amber-600 space-y-1">
          <div>• <strong>方式1</strong>：粘贴 JSON 数组数据</div>
          <div>• <strong>方式2</strong>：上传 JSON/CSV 文件</div>
          <div>• <strong>方式3</strong>：运行 <code className="bg-amber-100 px-1 rounded">python scripts/fetch_history.py</code> 脚本</div>
        </div>
      </div>

      {/* JSON 格式示例 */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">数据格式（JSON数组）</h3>
        <pre className="bg-slate-900 text-green-400 text-xs rounded-lg p-4 overflow-x-auto">
{`[
  {
    "title": "文章标题",
    "content": "文章内容...",
    "source_url": "https://...",
    "published_at": "2026-03-15T10:00:00Z",
    "source_name": "新华网"
  }
]`}
        </pre>
      </div>

      {/* 文件上传 */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">上传文件</h3>
        <input
          type="file"
          accept=".json,.csv"
          onChange={handleFileUpload}
          className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-cyan-50 file:text-cyan-700 hover:file:bg-cyan-100"
        />
        {fileInfo && <p className="mt-2 text-xs text-slate-400">{fileInfo}</p>}
      </div>

      {/* JSON 输入 */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">粘贴 JSON 数据</h3>
        <textarea
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          placeholder='[{"title": "...", "content": "...", "source_name": "新华网"}]'
          rows={10}
          className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm font-mono focus:border-cyan-400 outline-none resize-y"
        />
      </div>

      {msg && (
        <div className={`px-4 py-3 rounded-xl text-sm ${
          msg.includes('完成') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
        }`}>
          {msg}
        </div>
      )}

      <button
        onClick={handleImport}
        disabled={!jsonText.trim() || importing}
        className="flex items-center gap-2 px-6 py-3 rounded-xl gradient-brand text-white font-medium shadow-md disabled:opacity-40 transition-all"
      >
        <Upload className="w-4 h-4" />
        {importing ? '导入中...' : '导入数据'}
      </button>

      {/* 命令行方式 */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">命令行批量获取</h3>
        <p className="text-xs text-slate-500 mb-3">
          在终端运行以下命令，通过 RSSHub 深度爬取所有源的历史数据：
        </p>
        <pre className="bg-slate-900 text-cyan-400 text-xs rounded-lg p-4 overflow-x-auto">
{`# 确保后端正在运行
cd backend
python scripts/fetch_history.py

# 只从 RSSHub 获取
python scripts/fetch_history.py --source rsshub --pages 5

# 从文件导入
python scripts/fetch_history.py --source file --file data.json`}
        </pre>
      </div>
    </div>
  );
}
