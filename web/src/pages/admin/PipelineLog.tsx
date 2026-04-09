import { useEffect, useState } from 'react';
import api from '../../api/client';
import {
  ScrollText, Filter, ChevronLeft, ChevronRight,
  FileText, AlertTriangle, CheckCircle, XCircle, Eye,
  ExternalLink, Search,
} from 'lucide-react';

// ─── 类型 ──────────────────────────────────────────────────────────

interface AuditLog {
  id: number;
  article_id: number;
  event_id: number | null;
  stage: string;
  status: string;
  confidence: number;
  entity_check: Record<string, unknown> | null;
  issues: string[] | null;
  raw_snapshot: Record<string, unknown> | null;
  result_snapshot: Record<string, unknown> | null;
  created_at: string | null;
  article_title: string;
  event_title: string;
}

interface PageData {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const STAGES = [
  { value: '', label: '全部阶段' },
  { value: 'distill', label: '蒸馏' },
  { value: 'reason', label: '推演' },
  { value: 'audit', label: '审计' },
];

const STATUSES = [
  { value: '', label: '全部状态' },
  { value: 'pass', label: '通过' },
  { value: 'manual_review', label: '人工审核' },
  { value: 'safe_mode', label: '安全模式' },
  { value: 'fail', label: '失败' },
];

const STAGE_STYLE: Record<string, { bg: string; text: string }> = {
  distill: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  reason: { bg: 'bg-violet-500/10', text: 'text-violet-400' },
  audit: { bg: 'bg-amber-500/10', text: 'text-amber-400' },
};

const STATUS_ICON: Record<string, { icon: typeof CheckCircle; color: string }> = {
  pass: { icon: CheckCircle, color: 'text-emerald-400' },
  manual_review: { icon: Eye, color: 'text-amber-400' },
  safe_mode: { icon: AlertTriangle, color: 'text-red-400' },
  fail: { icon: XCircle, color: 'text-red-500' },
};

// ─── 组件 ──────────────────────────────────────────────────────────

export function PipelineLog() {
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [stage, setStage] = useState('');
  const [status, setStatus] = useState('');
  const [articleId, setArticleId] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = async (p = page) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page: p, page_size: 20 };
      if (stage) params.stage = stage;
      if (status) params.status = status;
      if (articleId) params.article_id = parseInt(articleId) || undefined;
      const res = await api.get<PageData>('/admin/audit-logs', { params });
      setData(res.data);
    } catch (e) { console.error('Failed to load audit logs:', e); setData(null); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(1); }, [stage, status]);
  useEffect(() => { load(); }, [page]);

  const handleSearch = () => { setPage(1); load(1); };

  const stageLabel = (s: string) => STAGES.find(x => x.value === s)?.label ?? s;
  const statusLabel = (s: string) => STATUSES.find(x => x.value === s)?.label ?? s;

  return (
    <div className="space-y-4">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center shadow-lg">
          <ScrollText className="w-5 h-5 text-cyan-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-800">管线日志</h1>
          <p className="text-xs text-slate-400">审计日志 · 排查管线处理问题</p>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-slate-200">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select value={stage} onChange={e => { setStage(e.target.value); setPage(1); }}
            className="text-sm text-slate-700 bg-transparent outline-none cursor-pointer">
            {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-700 outline-none cursor-pointer">
          {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <div className="flex items-center gap-1">
          <input
            value={articleId}
            onChange={e => setArticleId(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="文章 ID"
            className="w-24 px-3 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-700 outline-none focus:ring-2 focus:ring-cyan-200"
          />
          <button onClick={handleSearch}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-cyan-500 hover:border-cyan-200 transition-colors">
            <Search className="w-4 h-4" />
          </button>
        </div>
        {data && (
          <span className="text-xs text-slate-400 ml-auto">共 {data.total} 条</span>
        )}
      </div>

      {/* 日志列表 */}
      {loading && !data ? (
        <div className="flex justify-center py-16">
          <div className="w-5 h-5 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200/80">
          <ScrollText className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">暂无审计日志</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map(log => {
            const open = expandedId === log.id;
            const ss = STAGE_STYLE[log.stage] || { bg: 'bg-slate-500/10', text: 'text-slate-400' };
            const si = STATUS_ICON[log.status] || STATUS_ICON.fail;
            const StatusIcon = si.icon;
            const confPct = (log.confidence * 100).toFixed(0);
            const confColor = log.confidence >= 0.7 ? 'text-emerald-400' : log.confidence >= 0.4 ? 'text-amber-400' : 'text-red-400';

            return (
              <div key={log.id} className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
                {/* 摘要行 */}
                <div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50/50"
                  onClick={() => setExpandedId(open ? null : log.id)}
                >
                  <StatusIcon className={`w-4 h-4 shrink-0 ${si.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-700 truncate">{log.article_title}</span>
                      {log.event_title && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 shrink-0">
                          {log.event_title}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${ss.bg} ${ss.text}`}>
                        {stageLabel(log.stage)}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        log.status === 'pass' ? 'bg-emerald-50 text-emerald-600' :
                        log.status === 'manual_review' ? 'bg-amber-50 text-amber-600' :
                        'bg-red-50 text-red-600'
                      }`}>
                        {statusLabel(log.status)}
                      </span>
                      {log.issues && log.issues.length > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                          {log.issues.length} 个问题
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-xs font-mono ${confColor}`}>{confPct}%</span>
                    {log.created_at && (
                      <span className="text-[10px] text-slate-400 w-28 text-right">
                        {new Date(log.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                </div>

                {/* 展开详情 */}
                {open && (
                  <div className="border-t border-slate-100 px-4 py-3 space-y-3 bg-slate-50/30">
                    {/* 基本信息 */}
                    <div className="grid grid-cols-4 gap-3 text-xs">
                      <div>
                        <span className="text-slate-400">日志 ID</span>
                        <p className="text-slate-700 font-mono">{log.id}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">文章 ID</span>
                        <p className="text-slate-700 font-mono">{log.article_id}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">事件 ID</span>
                        <p className="text-slate-700 font-mono">{log.event_id ?? '-'}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">置信度</span>
                        <p className={`font-mono ${confColor}`}>{log.confidence.toFixed(3)}</p>
                      </div>
                    </div>

                    {/* 问题列表 */}
                    {log.issues && log.issues.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-400 mb-1">问题</p>
                        <div className="space-y-1">
                          {log.issues.map((issue, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                              <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />
                              <span className="text-slate-600">{issue}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 实体检查 */}
                    {log.entity_check && (
                      <div>
                        <p className="text-xs text-slate-400 mb-1">实体检查</p>
                        <pre className="text-xs text-slate-600 bg-white rounded-lg p-2 border border-slate-200 overflow-auto max-h-32">
                          {JSON.stringify(log.entity_check, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* 快照对比 */}
                    <div className="grid grid-cols-2 gap-3">
                      {log.raw_snapshot && (
                        <div>
                          <p className="text-xs text-slate-400 mb-1">原始数据</p>
                          <pre className="text-xs text-slate-600 bg-white rounded-lg p-2 border border-slate-200 overflow-auto max-h-40">
                            {JSON.stringify(log.raw_snapshot, null, 2)}
                          </pre>
                        </div>
                      )}
                      {log.result_snapshot && (
                        <div>
                          <p className="text-xs text-slate-400 mb-1">处理后数据</p>
                          <pre className="text-xs text-slate-600 bg-white rounded-lg p-2 border border-slate-200 overflow-auto max-h-40">
                            {JSON.stringify(log.result_snapshot, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>

                    {/* 跳转 */}
                    <div className="flex gap-3 pt-1">
                      <a href={`/admin/articles`} className="text-xs text-cyan-500 hover:text-cyan-700 flex items-center gap-1">
                        <FileText className="w-3 h-3" /> 查看文章
                      </a>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 分页 */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between px-1">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-white hover:shadow-sm disabled:opacity-30">
            <ChevronLeft className="w-4 h-4" /> 上一页
          </button>
          <span className="text-sm text-slate-400">{page} / {data.total_pages}</span>
          <button onClick={() => setPage(p => Math.min(data.total_pages, p + 1))} disabled={page >= data.total_pages}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-white hover:shadow-sm disabled:opacity-30">
            下一页 <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
