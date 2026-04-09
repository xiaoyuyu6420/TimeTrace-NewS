import { Link } from 'react-router-dom';
import { Calendar, FileText, Users } from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { IMPORTANCE_CONFIG } from '../types';
import type { Event } from '../types';

interface Props {
  event: Event;
  index?: number;
  /** 是否显示时间线圆点（默认 true） */
  showDot?: boolean;
  /** 是否是组内最后一个（不画竖线延伸） */
  isLast?: boolean;
}

export function TimelineEventCard({ event, index = 0, showDot = true, isLast = false }: Props) {
  const imp = IMPORTANCE_CONFIG[event.importance] || IMPORTANCE_CONFIG[3];

  // 计算相对时间
  const timeLabel = event.updated_at
    ? formatDistanceToNow(new Date(event.updated_at), { addSuffix: true, locale: zhCN })
    : '';

  return (
    <div className="flex gap-3 animate-fade-in-up" style={{ animationDelay: `${index * 0.04}s` }}>
      {/* 左侧时间线轴 */}
      {showDot && (
        <div className="flex flex-col items-center shrink-0 w-6">
          {/* 圆点 */}
          <div className={`w-3 h-3 rounded-full border-2 border-white shadow-sm mt-4 ${imp.bar}`} />
          {/* 竖线 */}
          {!isLast && (
            <div className="flex-1 w-0.5 bg-slate-200 mt-1" />
          )}
        </div>
      )}

      {/* 卡片 */}
      <Link
        to={`/event/${event.id}`}
        className="group block flex-1 min-w-0 pb-3"
      >
        <div className="relative flex bg-white rounded-xl shadow-sm card-lift overflow-hidden border border-slate-100 hover:border-slate-200 transition-colors">
          {/* 左侧重要度色条 */}
          <div className={`w-1.5 shrink-0 ${imp.bar}`} />

          <div className="flex-1 p-3.5 pl-3 min-w-0">
            {/* 顶部行：分类 + 时间 + 状态 */}
            <div className="flex items-center gap-2 mb-1 text-xs text-slate-400">
              {event.category && (
                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-medium">
                  {event.category}
                </span>
              )}
              {imp.label && (
                <span className={`px-1.5 py-0.5 rounded font-semibold ${imp.color}`}>
                  {imp.label}
                </span>
              )}
              <span className="ml-auto shrink-0">{timeLabel}</span>
              {event.status === 'resolved' && (
                <span className="px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-medium shrink-0">
                  已完结
                </span>
              )}
            </div>

            {/* 标题 */}
            <h3 className="text-[15px] font-semibold text-slate-800 group-hover:text-cyan-600 transition-colors line-clamp-2 leading-snug mb-1">
              {event.title}
            </h3>

            {/* 摘要 */}
            {event.summary && (
              <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed mb-1.5">
                {event.summary}
              </p>
            )}

            {/* 底部统计 */}
            <div className="flex items-center gap-3 text-xs text-slate-400">
              {event.start_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {format(new Date(event.start_date), 'MM/dd')}
                </span>
              )}
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />{event.article_count}篇
              </span>
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />{event.follow_count}
              </span>
            </div>
          </div>
        </div>
      </Link>
    </div>
  );
}
