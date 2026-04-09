import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import { fetchPublicEventDetail, fetchEventDetail } from '../api/events';
import { followEvent, unfollowEvent } from '../api/users';
import {
  ArrowLeft, Calendar, FileText, Users, Bookmark, BookmarkCheck,
  Tag, Activity, ExternalLink, Clock,
} from 'lucide-react';
import { format } from 'date-fns';
import type { EventDetail as EventDetailType, TimelinePhase } from '../types';
import { PHASE_LABELS, PHASE_COLORS, IMPORTANCE_CONFIG } from '../types';

/** 阶段时间线区块 */
function PhaseBlock({ phase }: { phase: TimelinePhase }) {
  const colors = PHASE_COLORS[phase.phase] || PHASE_COLORS.development;
  const label = phase.phase_label || PHASE_LABELS[phase.phase] || phase.phase;

  return (
    <div className="mb-6 last:mb-0">
      {/* 阶段标题 */}
      <div className={`phase-divider ${colors.text} mb-3`}>
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold ${colors.bg} ${colors.text} ${colors.border} border`}>
          <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
          {label}
          {phase.date && <span className="text-[10px] opacity-60 ml-1">{phase.date}</span>}
        </span>
      </div>

      {/* 文章列表 */}
      <div className="timeline-line pl-2 space-y-3">
        {phase.articles.map((article) => (
          <div key={article.id} className="flex gap-3 items-start">
            {/* 时间线圆点 */}
            <div className={`timeline-dot ${colors.text}`}>
              <div className={`timeline-dot-inner ${colors.dot}`} />
            </div>

            {/* 文章内容 */}
            <div className="flex-1 min-w-0 pb-1">
              <div className="bg-white rounded-lg p-3 shadow-sm border border-slate-100 hover:border-slate-200 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-slate-800 line-clamp-2 leading-snug mb-1">
                      {article.title}
                    </h4>
                    {article.summary && (
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                        {article.summary}
                      </p>
                    )}
                  </div>
                  {article.source_url && (
                    <a
                      href={article.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 p-1 text-slate-400 hover:text-cyan-500 transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>

                {/* 元信息 */}
                <div className="flex items-center gap-2 mt-2 text-[11px] text-slate-400">
                  {article.published_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {format(new Date(article.published_at), 'MM/dd HH:mm')}
                    </span>
                  )}
                  {article.rss_source_name && (
                    <span>{article.rss_source_name}</span>
                  )}
                  {article.credibility_score > 0 && (
                    <span className="px-1 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[10px]">
                      {Math.round(article.credibility_score)}分
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 事件详情页 */
export function EventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const [event, setEvent] = useState<EventDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [following, setFollowing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const fn = auth.token ? fetchEventDetail : fetchPublicEventDetail;
        const res = await fn(Number(id));
        setEvent(res.data);
        setFollowing(res.data.is_followed);
      } catch (e: any) {
        setError(e?.response?.data?.detail || '加载失败');
      } finally {
        setLoading(false);
      }
    };
    if (id) load();
  }, [id, auth.token]);

  const toggleFollow = async () => {
    if (!auth.token) { navigate('/login'); return; }
    try {
      if (following) {
        await unfollowEvent(Number(id));
      } else {
        await followEvent(Number(id));
      }
      setFollowing(!following);
      if (event) {
        setEvent({ ...event, follow_count: event.follow_count + (following ? -1 : 1) });
      }
    } catch {
      /* silent */
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="w-5 h-5 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!event) {
    if (error) {
      return (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 transition-colors mb-5"
          >
            <ArrowLeft className="w-4 h-4" /> 返回首页
          </button>
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-50 flex items-center justify-center">
              <FileText className="w-7 h-7 text-red-300" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-1">事件未找到</h3>
            <p className="text-sm text-slate-400 mb-4">{error}</p>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 rounded-lg gradient-brand text-white text-sm font-medium"
            >
              回到首页
            </button>
          </div>
        </div>
      );
    }
    return null;
  }

  const imp = IMPORTANCE_CONFIG[event.importance] || IMPORTANCE_CONFIG[3];

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 transition-colors mb-5"
      >
        <ArrowLeft className="w-4 h-4" /> 返回
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：主内容（2/3 宽度） */}
        <div className="lg:col-span-2 space-y-6">
          {/* 事件 Hero */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 overflow-hidden animate-fade-in-up">
            {/* 顶部色条 */}
            <div className={`h-1.5 ${imp.bar}`} />

            <div className="p-5">
              {/* 状态 + 分类 */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                {event.status === 'active' ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-600 text-xs font-medium">
                    <Activity className="w-3 h-3" /> 进行中
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-xs font-medium">已完结</span>
                )}
                {event.category && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs">
                    <Tag className="w-3 h-3" /> {event.category}
                  </span>
                )}
                {imp.label && (
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${imp.color}`}>{imp.label}</span>
                )}
              </div>

              {/* 标题 */}
              <h1 className="text-xl md:text-2xl font-bold text-slate-900 mb-2 leading-tight">
                {event.title}
              </h1>

              {/* 摘要 */}
              {event.summary && (
                <p className="text-sm text-slate-500 leading-relaxed mb-3">{event.summary}</p>
              )}

              {/* 统计 */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                {event.start_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {format(new Date(event.start_date), 'yyyy-MM-dd')}
                    {event.end_date && ` ~ ${format(new Date(event.end_date), 'yyyy-MM-dd')}`}
                  </span>
                )}
                <span className="flex items-center gap-1"><FileText className="w-3.5 h-3.5" /> {event.article_count} 篇</span>
                <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" /> {event.follow_count} 人关注</span>
              </div>
            </div>
          </div>

          {/* 阶段时间线 */}
          {event.timeline.length > 0 ? (
            <div>
              <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                <div className="w-1 h-4 rounded-full gradient-brand" />
                事件时间线
              </h2>
              {event.timeline.map((phase) => (
                <PhaseBlock key={phase.phase} phase={phase} />
              ))}
            </div>
          ) : event.articles.length > 0 ? (
            /* 回退：无 timeline 时显示文章列表 */
            <div>
              <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                <div className="w-1 h-4 rounded-full gradient-brand" />
                相关报道 ({event.articles.length})
              </h2>
              <div className="space-y-2">
                {event.articles.map((a) => (
                  <div key={a.id} className="bg-white rounded-lg p-3 shadow-sm border border-slate-100">
                    <h4 className="text-sm font-medium text-slate-800 line-clamp-2">{a.title}</h4>
                    {a.published_at && (
                      <span className="text-[11px] text-slate-400 mt-1 block">
                        {format(new Date(a.published_at), 'yyyy-MM-dd HH:mm')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {/* 右侧边栏（1/3 宽度） */}
        <div className="space-y-4 animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
          {/* 关注按钮 */}
          <button
            onClick={toggleFollow}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              following
                ? 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                : 'gradient-brand text-white shadow-md shadow-cyan-200/30'
            }`}
          >
            {following ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
            {following ? '已关注' : '关注事件'}
          </button>

          {/* 事件信息卡 */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">事件信息</h3>

            <div className="space-y-3 text-sm">
              {/* 重要度 */}
              <div className="flex items-center justify-between">
                <span className="text-slate-500">重要度</span>
                <div className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <div
                      key={n}
                      className={`w-4 h-1.5 rounded-full ${n <= event.importance ? imp.bar : 'bg-slate-200'}`}
                    />
                  ))}
                </div>
              </div>

              {/* 分类 */}
              <div className="flex items-center justify-between">
                <span className="text-slate-500">分类</span>
                <span className="text-slate-700">{event.category || '未分类'}</span>
              </div>

              {/* 状态 */}
              <div className="flex items-center justify-between">
                <span className="text-slate-500">状态</span>
                <span className={event.status === 'active' ? 'text-cyan-600' : 'text-emerald-600'}>
                  {event.status === 'active' ? '进行中' : '已完结'}
                </span>
              </div>

              {/* 文章数 */}
              <div className="flex items-center justify-between">
                <span className="text-slate-500">报道数</span>
                <span className="text-slate-700">{event.article_count} 篇</span>
              </div>
            </div>
          </div>

          {/* 阶段概览 */}
          {event.timeline.length > 0 && (
            <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200/80">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">阶段概览</h3>
              <div className="space-y-2">
                {event.timeline.map((phase) => {
                  const colors = PHASE_COLORS[phase.phase] || PHASE_COLORS.development;
                  return (
                    <div key={phase.phase} className="flex items-center gap-2 text-sm">
                      <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
                      <span className="text-slate-600 flex-1">{phase.phase_label}</span>
                      <span className="text-slate-400 text-xs">{phase.articles.length}篇</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
