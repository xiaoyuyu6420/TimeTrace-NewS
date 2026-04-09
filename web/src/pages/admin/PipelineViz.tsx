import { useEffect, useRef, useState, useCallback } from 'react';
import api from '../../api/client';
import type { Article, Distillation, Reasoning, PageResponse } from '../../types';
import {
  Rss, FlaskConical, Brain, ShieldCheck, GitMerge,
  Sparkles, CheckCircle, AlertTriangle, Eye, Activity,
  X, FileText, ExternalLink, ChevronLeft, ChevronRight,
  GripVertical,
} from 'lucide-react';

// ─── 类型 ──────────────────────────────────────────────────────────

interface PipelineStats {
  raw: number;
  distilled: number;
  reasoned: number;
  audited: number;
  safe_mode: number;
  active_events: number;
  resolved_events: number;
  audit_pass: number;
  audit_manual_review: number;
  total_articles: number;
  total_events: number;
}

// ─── 阶段配置 ──────────────────────────────────────────────────────

const STAGE_COLORS: Record<string, { hex: string; bg: string; border: string; iconBg: string; glow: string }> = {
  cyan:    { hex: '#06b6d4', bg: 'bg-cyan-500',   border: 'border-cyan-400/30', iconBg: 'bg-cyan-400/20',  glow: 'shadow-cyan-500/20' },
  blue:    { hex: '#3b82f6', bg: 'bg-blue-500',   border: 'border-blue-400/30', iconBg: 'bg-blue-400/20',  glow: 'shadow-blue-500/20' },
  violet:  { hex: '#8b5cf6', bg: 'bg-violet-500', border: 'border-violet-400/30', iconBg: 'bg-violet-400/20', glow: 'shadow-violet-500/20' },
  amber:   { hex: '#f59e0b', bg: 'bg-amber-500',  border: 'border-amber-400/30', iconBg: 'bg-amber-400/20', glow: 'shadow-amber-500/20' },
  emerald: { hex: '#10b981', bg: 'bg-emerald-500', border: 'border-emerald-400/30', iconBg: 'bg-emerald-400/20', glow: 'shadow-emerald-500/20' },
  rose:    { hex: '#f43f5e', bg: 'bg-rose-500',   border: 'border-rose-400/30', iconBg: 'bg-rose-400/20',  glow: 'shadow-rose-500/20' },
  red:     { hex: '#ef4444', bg: 'bg-red-500',    border: 'border-red-400/30', iconBg: 'bg-red-400/20',   glow: 'shadow-red-500/20' },
  orange:  { hex: '#f97316', bg: 'bg-orange-500',  border: 'border-orange-400/30', iconBg: 'bg-orange-400/20', glow: 'shadow-orange-500/20' },
};

const PIPELINE_STAGES = [
  { id: 'crawl',     label: '采集',   sublabel: 'Crawl',      icon: Rss,           color: 'cyan',    field: 'raw',                state: 'raw',           x: 60,  y: 80 },
  { id: 'distill',   label: '蒸馏',   sublabel: 'Distill',    icon: FlaskConical,  color: 'blue',    field: 'distilled',          state: 'distilled',     x: 290, y: 80 },
  { id: 'reason',    label: '推演',   sublabel: 'Reason',     icon: Brain,         color: 'violet',  field: 'reasoned',           state: 'reasoned',      x: 520, y: 80 },
  { id: 'audit',     label: '审计',   sublabel: 'Audit',      icon: ShieldCheck,   color: 'amber',   field: 'audited',            state: 'audited',       x: 750, y: 80 },
  { id: 'aggregate', label: '聚合',   sublabel: 'Aggregate',  icon: GitMerge,      color: 'emerald', field: 'active_events',      state: 'audited',       x: 750, y: 300 },
  { id: 'enhance',   label: '增强',   sublabel: 'Enhance',    icon: Sparkles,      color: 'rose',    field: 'active_events',      state: 'audited',       x: 520, y: 300 },
  { id: 'complete',  label: '完成',   sublabel: 'Complete',   icon: CheckCircle,   color: 'emerald', field: 'resolved_events',    state: 'audited',       x: 290, y: 300 },
  { id: 'safe_mode', label: '安全模式', sublabel: 'Safe',     icon: AlertTriangle, color: 'red',     field: 'safe_mode',          state: 'safe_mode',     x: 980, y: 40 },
  { id: 'manual_review', label: '人工审核', sublabel: 'Review', icon: Eye,          color: 'orange',  field: 'audit_manual_review', state: null,            x: 980, y: 180 },
] as const;

const EDGES: [string, string][] = [
  ['crawl', 'distill'],
  ['distill', 'reason'],
  ['reason', 'audit'],
  ['audit', 'aggregate'],
  ['aggregate', 'enhance'],
  ['enhance', 'complete'],
  ['audit', 'safe_mode'],
  ['audit', 'manual_review'],
];

const NODE_W = 180;
const NODE_H = 80;

// ─── 粒子背景 ──────────────────────────────────────────────────────

function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const mouseRef = { x: -999, y: -999 };
    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.x = e.clientX - rect.left;
      mouseRef.y = e.clientY - rect.top;
    });
    canvas.addEventListener('mouseleave', () => { mouseRef.x = -999; mouseRef.y = -999; });

    const colors = ['rgba(6,182,212,', 'rgba(16,185,129,', 'rgba(99,102,241,'];
    const particles = Array.from({ length: 50 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 1.5 + 0.5,
      opacity: Math.random() * 0.25 + 0.05,
      colorBase: colors[Math.floor(Math.random() * colors.length)],
    }));

    let animId: number;
    const animate = () => {
      ctx!.clearRect(0, 0, canvas.width, canvas.height);
      const mx = mouseRef.x, my = mouseRef.y;
      for (const p of particles) {
        const dx = mx - p.x, dy = my - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 200 && dist > 1) { p.vx += (dx / dist) * 0.012; p.vy += (dy / dist) * 0.012; }
        p.vx *= 0.99; p.vy *= 0.99; p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;
        ctx!.beginPath(); ctx!.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx!.fillStyle = p.colorBase + p.opacity + ')'; ctx!.fill();
      }
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            ctx!.beginPath(); ctx!.moveTo(particles[i].x, particles[i].y); ctx!.lineTo(particles[j].x, particles[j].y);
            ctx!.strokeStyle = `rgba(100,116,139,${0.06 * (1 - dist / 100)})`; ctx!.lineWidth = 0.5; ctx!.stroke();
          }
        }
      }
      animId = requestAnimationFrame(animate);
    };
    animate();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" style={{ zIndex: 0 }} />;
}

// ─── SVG 连接线 ────────────────────────────────────────────────────

function SVGConnections({ positions }: { positions: Record<string, { x: number; y: number }> }) {
  const stageMap = Object.fromEntries(PIPELINE_STAGES.map(s => [s.id, s]));

  const buildPath = (from: { x: number; y: number }, to: { x: number; y: number }) => {
    const sx = from.x + NODE_W / 2, sy = from.y + NODE_H;
    const ex = to.x + NODE_W / 2, ey = to.y;
    if (Math.abs(sy - ey) < 10) {
      // 同行水平连接
      const mx = (sx + ex) / 2;
      return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ey}, ${ex} ${ey}`;
    }
    // 跨行连接
    return `M ${sx} ${sy} C ${sx} ${sy + 40}, ${ex} ${ey - 40}, ${ex} ${ey}`;
  };

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
      <defs>
        {EDGES.map(([fromId, toId]) => {
          const fc = STAGE_COLORS[stageMap[fromId]?.color]?.hex || '#06b6d4';
          const tc = STAGE_COLORS[stageMap[toId]?.color]?.hex || '#06b6d4';
          const f = positions[fromId], t = positions[toId];
          if (!f || !t) return null;
          return (
            <linearGradient key={`g-${fromId}-${toId}`} id={`g-${fromId}-${toId}`}
              gradientUnits="userSpaceOnUse"
              x1={f.x + NODE_W / 2} y1={f.y + NODE_H / 2}
              x2={t.x + NODE_W / 2} y2={t.y + NODE_H / 2}>
              <stop offset="0%" stopColor={fc} stopOpacity="0.4" />
              <stop offset="100%" stopColor={tc} stopOpacity="0.4" />
            </linearGradient>
          );
        })}
      </defs>
      {EDGES.map(([fromId, toId]) => {
        const f = positions[fromId], t = positions[toId];
        if (!f || !t) return null;
        const d = buildPath(f, t);
        return (
          <g key={`e-${fromId}-${toId}`}>
            <path d={d} fill="none" stroke={`url(#g-${fromId}-${toId})`}
              strokeWidth="1.5" strokeDasharray="6 3" className="animate-flow-dash" opacity="0.6" />
            <circle r="2.5" fill={`url(#g-${fromId}-${toId})`} opacity="0.7">
              <animateMotion dur="2.5s" repeatCount="indefinite" path={d} />
            </circle>
          </g>
        );
      })}
    </svg>
  );
}

// ─── 管线节点卡片 ──────────────────────────────────────────────────

function PipelineNode({
  stage, count, position, isActive, delay,
  onPointerDown, onPointerUp,
}: {
  stage: typeof PIPELINE_STAGES[number];
  count: number;
  position: { x: number; y: number };
  isActive: boolean;
  delay: number;
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
}) {
  const Icon = stage.icon;
  const sc = STAGE_COLORS[stage.color];
  const hasItems = count > 0;

  return (
    <div
      className={`absolute w-[180px] rounded-xl overflow-hidden select-none touch-none
        bg-slate-800/90 backdrop-blur-sm border ${sc.border}
        shadow-lg ${isActive ? sc.glow : ''} animate-node-enter
        cursor-pointer hover:bg-slate-700/90 transition-all duration-150`}
      style={{ left: position.x, top: position.y, zIndex: 10, animationDelay: `${delay}s` }}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
    >
      {/* 顶部色条 */}
      <div className={`h-1 ${sc.bg}`} />
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2 mb-1.5">
          <div className={`w-7 h-7 rounded-md flex items-center justify-center ${sc.iconBg}`}>
            <Icon className={`w-3.5 h-3.5 text-white`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-medium text-xs text-white/90">{stage.label}</div>
            <div className="text-[9px] text-white/30">{stage.sublabel}</div>
          </div>
          {hasItems && (
            <GripVertical className="w-3 h-3 text-white/20" />
          )}
        </div>
        <div className="flex items-end justify-between">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-white tabular-nums">{count}</span>
            {hasItems && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
          </div>
          <span className="text-[9px] text-white/25">
            {hasItems ? `${stage.state}` : '空闲'}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── 文章详情模态框 ────────────────────────────────────────────────

function ArticleModal({
  stage, isOpen, onClose,
}: {
  stage: typeof PIPELINE_STAGES[number] | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [pageData, setPageData] = useState<PageResponse<Article> | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => { setPage(1); setExpandedId(null); }, [stage?.id]);

  useEffect(() => {
    if (!stage || !isOpen || !stage.state) return;
    setLoading(true);
    api.get<PageResponse<Article>>('/admin/pipeline-articles', {
      params: { state: stage.state, page, page_size: 10 },
    }).then(r => setPageData(r.data))
      .catch((e) => { console.error('Failed to load pipeline articles:', e); setPageData(null); })
      .finally(() => setLoading(false));
  }, [stage, isOpen, page]);

  if (!stage) return null;
  const Icon = stage.icon;
  const sc = STAGE_COLORS[stage.color];

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center transition-all duration-200
        ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      onClick={onClose}
    >
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* 模态框 */}
      <div
        className={`relative bg-slate-800 rounded-2xl shadow-2xl border border-slate-700/50
          w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden
          transition-transform duration-200 ${isOpen ? 'scale-100' : 'scale-95'}`}
        onClick={e => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-700/50">
          <div className={`w-9 h-9 rounded-lg ${sc.bg} flex items-center justify-center shadow-lg`}>
            <Icon className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-white text-sm">{stage.label} 阶段</h2>
            <p className="text-[10px] text-slate-400">state: {stage.state} · {pageData?.total ?? '...'} 篇文章</p>
          </div>
          <button onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-auto">
          {loading && !pageData ? (
            <div className="flex justify-center py-16">
              <div className="w-5 h-5 border-2 border-slate-600 border-t-cyan-400 rounded-full animate-spin" />
            </div>
          ) : !pageData || pageData.items.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="w-8 h-8 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-500">该阶段暂无文章</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700/50">
              {pageData.items.map(a => {
                const open = expandedId === a.id;
                return (
                  <div key={a.id} className="px-5">
                    <div
                      className="flex items-start gap-3 py-3.5 cursor-pointer group"
                      onClick={() => setExpandedId(open ? null : a.id)}
                    >
                      <div className={`w-6 h-6 rounded flex items-center justify-center mt-0.5 shrink-0
                        ${open ? sc.bg : 'bg-slate-700'} transition-colors`}>
                        <FileText className="w-3 h-3 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white/90 leading-snug group-hover:text-white">{a.title}</p>
                        <div className="flex items-center gap-2 mt-1.5">
                          {a.rss_source_name && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">{a.rss_source_name}</span>
                          )}
                          {a.published_at && (
                            <span className="text-[10px] text-slate-500">{new Date(a.published_at).toLocaleDateString('zh-CN')}</span>
                          )}
                          {a.keywords?.slice(0, 3).map((kw, i) => (
                            <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-400">{kw}</span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {open && (
                      <div className="pb-3.5 pl-9 space-y-2">
                        {a.summary && <p className="text-xs text-slate-300 leading-relaxed">{a.summary}</p>}

                        {/* 蒸馏数据 */}
                        {a.distillation && (
                          <div className="space-y-1.5 rounded-lg bg-slate-700/40 p-3">
                            <div className="flex items-center gap-2 text-[10px]">
                              <span className="font-medium text-slate-300">蒸馏结果</span>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                                a.distillation.is_llm_generated ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                              }`}>
                                {a.distillation.is_llm_generated ? 'LLM' : 'jieba'}
                              </span>
                              <span className="text-slate-500">置信度: {(a.distillation.confidence * 100).toFixed(0)}%</span>
                              <span className="text-slate-500">耗时: {a.distillation.processing_time_ms}ms</span>
                            </div>
                            {a.distillation.summary_line && (
                              <p className="text-xs text-cyan-300">{a.distillation.summary_line}</p>
                            )}
                            {a.distillation.core_entities?.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {a.distillation.core_entities.map((e, i) => (
                                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400">{e}</span>
                                ))}
                              </div>
                            )}
                            {a.distillation.key_numbers?.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {a.distillation.key_numbers.map((n, i) => (
                                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400">{n}</span>
                                ))}
                              </div>
                            )}
                            {a.distillation.facts?.length > 0 && (
                              <div className="space-y-0.5 mt-1">
                                {a.distillation.facts.slice(0, 5).map((f, i) => (
                                  <p key={i} className="text-[10px] text-slate-400 leading-relaxed">
                                    <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${
                                      f.fact_type === 'action' ? 'bg-orange-400' : f.fact_type === 'number' ? 'bg-amber-400' : 'bg-slate-500'
                                    }`} />
                                    {f.content}
                                  </p>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* 推演数据 */}
                        {a.reasoning && (
                          <div className="space-y-1.5 rounded-lg bg-slate-700/40 p-3">
                            <div className="flex items-center gap-2 text-[10px]">
                              <span className="font-medium text-slate-300">推演结果</span>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                                a.reasoning.action === 'link' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'
                              }`}>
                                {a.reasoning.action === 'link' ? `关联 → ${a.reasoning.target_event_title || `#${a.reasoning.target_event_id}`}` :
                                 a.reasoning.action === 'new' ? '新事件' : '跳过'}
                              </span>
                              <span className="text-slate-500">置信度: {(a.reasoning.confidence * 100).toFixed(0)}%</span>
                            </div>
                            {a.reasoning.event_title && (
                              <p className="text-xs text-purple-300">{a.reasoning.event_title}</p>
                            )}
                            {a.reasoning.suggested_category && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-400">{a.reasoning.suggested_category}</span>
                            )}
                            {a.reasoning.has_conflict && (
                              <p className="text-[10px] text-red-400">冲突: {a.reasoning.conflict_details}</p>
                            )}
                          </div>
                        )}

                        {/* 无管线数据时显示原文 */}
                        {!a.distillation && !a.reasoning && a.content && (
                          <p className="text-xs text-slate-400 leading-relaxed line-clamp-8">{a.content}</p>
                        )}

                        <div className="flex items-center gap-4 pt-1">
                          <span className="text-[10px] text-slate-500">
                            可信度: <span className={a.credibility_score > 0.7 ? 'text-emerald-400' : a.credibility_score > 0.4 ? 'text-amber-400' : 'text-red-400'}>
                              {(a.credibility_score * 100).toFixed(0)}%
                            </span>
                          </span>
                          {a.source_url && (
                            <a href={a.source_url} target="_blank" rel="noopener noreferrer"
                              className="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
                              <ExternalLink className="w-2.5 h-2.5" /> 查看原文
                            </a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 分页 */}
        {pageData && pageData.total_pages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-700/50">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-3 h-3" /> 上一页
            </button>
            <span className="text-xs text-slate-500">{page} / {pageData.total_pages}</span>
            <button onClick={() => setPage(p => Math.min(pageData.total_pages, p + 1))} disabled={page >= pageData.total_pages}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-30 transition-colors">
              下一页 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 主组件 ────────────────────────────────────────────────────────

export function PipelineViz() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>(() =>
    Object.fromEntries(PIPELINE_STAGES.map(s => [s.id, { x: s.x, y: s.y }]))
  );
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const dragMovedRef = useRef(false);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 拓宽父容器
  useEffect(() => {
    const el = containerRef.current?.closest('.max-w-5xl');
    if (el) {
      el.classList.remove('max-w-5xl');
      el.classList.add('max-w-full');
      return () => { el.classList.remove('max-w-full'); el.classList.add('max-w-5xl'); };
    }
  }, []);

  // 数据轮询
  useEffect(() => {
    const load = () => api.get<PipelineStats>('/admin/pipeline-stats')
      .then(r => setStats(r.data)).catch((e) => console.error('Failed to load pipeline stats:', e));
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, []);

  const handlePointerDown = useCallback((id: string, e: React.PointerEvent) => {
    e.stopPropagation();
    setDragging(id);
    dragMovedRef.current = false;
    setDragStart({ x: e.clientX, y: e.clientY });
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setDragOffset({ x: e.clientX - rect.left - positions[id].x, y: e.clientY - rect.top - positions[id].y });
  }, [positions]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return;
    if (Math.abs(e.clientX - dragStart.x) > 3 || Math.abs(e.clientY - dragStart.y) > 3) dragMovedRef.current = true;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPositions(prev => ({
      ...prev,
      [dragging]: {
        x: Math.max(0, e.clientX - rect.left - dragOffset.x),
        y: Math.max(0, e.clientY - rect.top - dragOffset.y),
      },
    }));
  }, [dragging, dragOffset, dragStart]);

  const handleNodePointerUp = useCallback((id: string) => {
    if (!dragMovedRef.current) {
      const stage = PIPELINE_STAGES.find(s => s.id === id);
      if (stage?.state) setSelectedStage(id);
    }
    setDragging(null);
  }, []);

  const getCount = (field: string) => stats ? ((stats as unknown as Record<string, unknown>)[field] as number || 0) : 0;
  const isActive = (stageId: string) => {
    if (!stats) return false;
    const field = PIPELINE_STAGES.find(s => s.id === stageId)?.field;
    return field ? ((stats as unknown as Record<string, unknown>)[field] as number || 0) > 0 : false;
  };

  const selectedStageObj = PIPELINE_STAGES.find(s => s.id === selectedStage) || null;

  return (
    <div className="space-y-4">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center shadow-lg">
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-800">管线可视化</h1>
            <p className="text-xs text-slate-400">拖拽节点调整布局 · 单击查看详情</p>
          </div>
        </div>
        {stats && (
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span>{stats.total_articles} 篇文章</span>
            <span>{stats.total_events} 个事件</span>
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>10s 刷新</span>
            </div>
          </div>
        )}
      </div>

      {/* 可视化区域 */}
      <div
        ref={containerRef}
        className="relative w-full h-[calc(100vh-180px)] min-h-[500px]
          bg-slate-900 rounded-2xl border border-slate-700/50 overflow-hidden"
        onPointerMove={handlePointerMove}
      >
        <ParticleCanvas />
        <SVGConnections positions={positions} />
        {PIPELINE_STAGES.map((stage, idx) => (
          <PipelineNode
            key={stage.id}
            stage={stage}
            count={getCount(stage.field)}
            position={positions[stage.id]}
            isActive={isActive(stage.id)}
            delay={idx * 0.06}
            onPointerDown={(e) => handlePointerDown(stage.id, e)}
            onPointerUp={() => handleNodePointerUp(stage.id)}
          />
        ))}
      </div>

      {/* 模态框 */}
      <ArticleModal
        stage={selectedStageObj}
        isOpen={!!selectedStage}
        onClose={() => setSelectedStage(null)}
      />
    </div>
  );
}
