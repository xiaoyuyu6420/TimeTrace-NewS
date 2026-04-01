import { Link } from 'react-router-dom';
import { Calendar, FileText, Users } from 'lucide-react';
import { format } from 'date-fns';

interface EventCardProps {
  id: number;
  title: string;
  summary: string;
  importance: number;
  articleCount: number;
  followCount: number;
  startDate: string | null;
  status: string;
  index?: number;
}

export function EventCard({
  id, title, summary, importance, articleCount, followCount, startDate, status, index = 0,
}: EventCardProps) {
  const impStyle: Record<number, { bg: string; text: string; label: string }> = {
    1: { bg: 'bg-slate-100', text: 'text-slate-500', label: '' },
    2: { bg: 'bg-blue-50', text: 'text-blue-500', label: '' },
    3: { bg: 'bg-amber-50', text: 'text-amber-600', label: '重要' },
    4: { bg: 'bg-orange-50', text: 'text-orange-600', label: '热点' },
    5: { bg: 'bg-red-50', text: 'text-red-600', label: '头条' },
  };
  const imp = impStyle[importance] || impStyle[3];

  return (
    <Link
      to={`/event/${id}`}
      className="group block animate-fade-in-up"
      style={{ animationDelay: `${index * 0.04}s` }}
    >
      <div className="relative h-full bg-white rounded-xl p-4 shadow-sm card-lift overflow-hidden">
        {/* Left accent bar */}
        <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl gradient-brand opacity-60 group-hover:opacity-100 transition-opacity" />

        <div className="pl-2">
          {/* Title + badge */}
          <div className="flex items-start gap-2 mb-1.5">
            <h3 className="flex-1 text-[15px] font-semibold text-slate-800 group-hover:text-cyan-600 transition-colors line-clamp-2 leading-snug">
              {title}
            </h3>
            {imp.label && (
              <span className={`shrink-0 mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${imp.bg} ${imp.text}`}>
                {imp.label}
              </span>
            )}
          </div>

          {/* Summary */}
          {summary && (
            <p className="text-sm text-slate-500 line-clamp-2 mb-3 leading-relaxed">{summary}</p>
          )}

          {/* Footer */}
          <div className="flex items-center gap-3 text-xs text-slate-400">
            {startDate && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {format(new Date(startDate), 'MM/dd')}
              </span>
            )}
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3" />{articleCount}篇
            </span>
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3" />{followCount}
            </span>
            {status === 'resolved' && (
              <span className="px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-medium">已完结</span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
