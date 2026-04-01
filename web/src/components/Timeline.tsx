import { format } from 'date-fns';
import { ExternalLink } from 'lucide-react';

interface TimelineArticle {
  id: number;
  title: string;
  summary: string;
  source_url: string;
  published_at: string | null;
}

interface TimelineProps {
  articles: TimelineArticle[];
}

export function Timeline({ articles }: TimelineProps) {
  if (!articles.length) {
    return (
      <div className="text-center py-12 text-slate-400 text-sm">暂无相关文章</div>
    );
  }

  return (
    <div className="relative pl-6">
      {/* Gradient line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-[2px] bg-gradient-to-b from-cyan-400 via-teal-400 to-emerald-400 rounded-full" />

      <div className="space-y-4">
        {articles.map((article, i) => (
          <div
            key={article.id}
            className="relative animate-fade-in-up"
            style={{ animationDelay: `${i * 0.06}s` }}
          >
            {/* Dot */}
            <div className="absolute -left-6 top-3.5 w-3 h-3 rounded-full gradient-brand ring-[3px] ring-white shadow-sm" />

            {/* Card */}
            <div className="bg-white rounded-xl p-4 shadow-sm card-lift">
              {article.published_at && (
                <span className="text-[11px] gradient-brand-text font-semibold">
                  {format(new Date(article.published_at), 'yyyy-MM-dd HH:mm')}
                </span>
              )}
              <h4 className="text-sm font-semibold text-slate-800 mt-0.5 line-clamp-2 group-hover:text-cyan-600">{article.title}</h4>
              {article.summary && (
                <p className="text-xs text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">{article.summary}</p>
              )}
              {article.source_url && (
                <a
                  href={article.source_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-2 text-[11px] text-cyan-500 hover:text-cyan-600 font-medium"
                >
                  <ExternalLink className="w-3 h-3" /> 查看原文
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
