import type { ReactNode } from 'react';

interface Props {
  title: string;
  count?: number;
  children: ReactNode;
}

export function TimelineSection({ title, count, children }: Props) {
  return (
    <section className="mb-2">
      {/* 时间线组标题 */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-2 h-2 rounded-full bg-cyan-400 shrink-0" />
        <h2 className="text-sm font-bold text-slate-800 whitespace-nowrap">{title}</h2>
        {count !== undefined && (
          <span className="text-xs text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full">{count}</span>
        )}
        <div className="flex-1 h-px bg-gradient-to-r from-slate-200 to-transparent" />
      </div>
      {/* 事件卡片列表 */}
      <div>{children}</div>
    </section>
  );
}
