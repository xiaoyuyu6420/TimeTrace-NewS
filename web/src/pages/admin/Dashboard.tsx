import { useEffect, useState } from 'react';
import api from '../../api/client';
import { Users, FileText, Zap, Rss, TrendingUp, Activity } from 'lucide-react';

interface Stats {
  total_users: number;
  total_articles: number;
  total_events: number;
  active_events: number;
  total_sources: number;
  articles_today: number;
}

export function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.get<Stats>('/admin/stats').then((r) => setStats(r.data)).catch(() => {});
  }, []);

  if (!stats) return <div className="py-20 text-center text-slate-400 text-sm">Loading...</div>;

  const cards = [
    { label: '总用户', value: stats.total_users, icon: Users, gradient: 'from-cyan-500 to-blue-500' },
    { label: '总文章', value: stats.total_articles, icon: FileText, gradient: 'from-blue-500 to-indigo-500' },
    { label: '总事件', value: stats.total_events, icon: Zap, gradient: 'from-emerald-500 to-teal-500' },
    { label: '活跃事件', value: stats.active_events, icon: Activity, gradient: 'from-amber-500 to-orange-500' },
    { label: 'RSS源', value: stats.total_sources, icon: Rss, gradient: 'from-violet-500 to-purple-500' },
    { label: '今日新增', value: stats.articles_today, icon: TrendingUp, gradient: 'from-rose-500 to-pink-500' },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold text-slate-800 mb-6">数据概览</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 stagger">
        {cards.map(({ label, value, icon: Icon, gradient }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200/80 p-5 card-lift">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-slate-400">{label}</span>
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center`}>
                <Icon className="w-4 h-4 text-white" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-800">{value.toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
