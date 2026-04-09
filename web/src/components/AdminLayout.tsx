import { Outlet, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Rss, FileText, Zap, ArrowLeft, Clock, GitMerge, Settings, Activity, ScrollText } from 'lucide-react';

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: '概览' },
  { to: '/admin/pipeline', icon: Activity, label: '管线可视化' },
  { to: '/admin/logs', icon: ScrollText, label: '管线日志' },
  { to: '/admin/sources', icon: Rss, label: 'RSS源' },
  { to: '/admin/articles', icon: FileText, label: '文章' },
  { to: '/admin/events', icon: Zap, label: '事件' },
  { to: '/admin/manage', icon: GitMerge, label: '事件整理' },
  { to: '/admin/settings', icon: Settings, label: '系统设置' },
];

export function AdminLayout() {
  const location = useLocation();

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col bg-slate-900">
        {/* Header */}
        <div className="p-4 border-b border-slate-700/50">
          <Link to="/" className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 transition-colors mb-3">
            <ArrowLeft className="w-3 h-3" /> 返回前台
          </Link>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg gradient-brand flex items-center justify-center">
              <Clock className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="text-sm font-bold text-white">TimeTrace</div>
              <div className="text-[10px] text-slate-500">管理后台</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label }) => {
            const active = location.pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${
                  active
                    ? 'gradient-brand text-white shadow-md shadow-cyan-500/20'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main */}
      <div className="flex-1 bg-slate-50 overflow-auto">
        <div className="max-w-5xl mx-auto p-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
