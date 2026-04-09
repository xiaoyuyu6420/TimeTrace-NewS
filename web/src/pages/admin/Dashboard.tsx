import { useEffect, useState } from 'react';
import api from '../../api/client';
import { Users, FileText, Zap, Rss, TrendingUp, Activity, Play, CheckCircle, AlertCircle, Clock, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

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
  const [running, setRunning] = useState('');
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api.get<Stats>('/admin/stats').then((r) => setStats(r.data)).catch((e) => console.error('Failed to load stats:', e));
  }, []);

  const runDaily = async () => {
    setRunning('daily');
    setMsg('');
    try {
      // 使用新的统一管线接口
      await api.post('/admin/pipeline');
      setMsg('管线执行完成');

      // Refresh stats
      const statsRes = await api.get<Stats>('/admin/stats');
      setStats(statsRes.data);
    } catch {
      setMsg('更新失败，请检查日志');
    }
    setRunning('');
  };

  if (!stats) return <div className="py-20 text-center text-slate-400 text-sm">Loading...</div>;

  const cards = [
    { label: '总用户', value: stats.total_users, icon: Users, color: 'from-cyan-500 to-blue-500' },
    { label: '总文章', value: stats.total_articles, icon: FileText, color: 'from-blue-500 to-indigo-500' },
    { label: '总事件', value: stats.total_events, icon: Zap, color: 'from-emerald-500 to-teal-500' },
    { label: '活跃事件', value: stats.active_events, icon: Activity, color: 'from-amber-500 to-orange-500' },
    { label: 'RSS源', value: stats.total_sources, icon: Rss, color: 'from-violet-500 to-purple-500' },
    { label: '今日新增', value: stats.articles_today, icon: TrendingUp, color: 'from-rose-500 to-pink-500' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">管理后台</h1>
        <span className="text-xs text-slate-400">账号: admin</span>
      </div>

      {/* 每日任务卡片 — 核心操作 */}
      <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-cyan-900 rounded-2xl p-6 text-white relative overflow-hidden">
        <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-cyan-500/10 blur-2xl" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-cyan-300" />
            </div>
            <div>
              <h2 className="font-semibold text-lg">每日更新</h2>
              <p className="text-sm text-slate-400">一键执行：爬取 → 处理 → 聚合 → 阶段标注</p>
            </div>
          </div>

          {msg && (
            <div className={`mb-4 px-4 py-2 rounded-lg text-sm flex items-center gap-2 ${
              msg.includes('完成') ? 'bg-emerald-500/20 text-emerald-300' : 'bg-cyan-500/20 text-cyan-300'
            }`}>
              {msg.includes('完成') ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              {msg}
            </div>
          )}

          <div className="flex items-center gap-4">
            <button
              onClick={runDaily}
              disabled={!!running}
              className="flex items-center gap-2 px-6 py-3 rounded-xl gradient-brand text-white font-medium shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 transition-shadow disabled:opacity-40"
            >
              <Play className="w-4 h-4" />
              {running === 'daily' ? '执行中...' : '执行每日更新'}
            </button>
            <div className="text-xs text-slate-500 space-y-0.5">
              <div>1. 爬取所有活跃 RSS 源</div>
              <div>2. 提取关键词 + 生成 Embedding</div>
              <div>3. 聚合为事件 + 阶段标注</div>
            </div>
          </div>
        </div>
      </div>

      {/* 快捷入口 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { to: '/admin/sources', label: 'RSS源管理', desc: '添加/启停数据源', icon: Rss },
          { to: '/admin/articles', label: '文章管理', desc: '查看/删除文章', icon: FileText },
          { to: '/admin/events', label: '事件管理', desc: '事件列表/状态', icon: Zap },
          { to: '/admin/manage', label: '事件整理', desc: '合并/分配/工具', icon: Activity },
        ].map(({ to, label, desc, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="bg-white rounded-xl border border-slate-200/80 p-4 card-lift group"
          >
            <div className="flex items-center justify-between mb-2">
              <Icon className="w-5 h-5 text-cyan-500" />
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-cyan-500 transition-colors" />
            </div>
            <div className="font-medium text-slate-800 text-sm">{label}</div>
            <div className="text-xs text-slate-400 mt-0.5">{desc}</div>
          </Link>
        ))}
      </div>

      {/* 统计卡片 */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 mb-3">数据统计</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 stagger">
          {cards.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-xl border border-slate-200/80 p-5 card-lift">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-400">{label}</span>
                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center`}>
                  <Icon className="w-4 h-4 text-white" />
                </div>
              </div>
              <div className="text-2xl font-bold text-slate-800">{value.toLocaleString()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
