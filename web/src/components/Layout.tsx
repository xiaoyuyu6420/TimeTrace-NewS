import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import { Clock, LogOut, User, Shield, Menu, X } from 'lucide-react';
import { useState } from 'react';

export function Layout() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    auth.logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="sticky top-0 z-50 glass border-b border-white/20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            <Link to="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg gradient-brand flex items-center justify-center shadow-md shadow-cyan-200/50">
                <Clock className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-slate-800">TimeTrace</span>
            </Link>

            <div className="hidden md:flex items-center gap-1">
              {auth.token ? (
                <>
                  <Link to="/profile" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-600 hover:bg-white/60 transition-colors">
                    <User className="w-4 h-4" />{auth.username}
                  </Link>
                  {auth.role === 'admin' && (
                    <Link to="/admin" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-600 hover:bg-white/60 transition-colors">
                      <Shield className="w-4 h-4" />管理
                    </Link>
                  )}
                  <button onClick={handleLogout} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-500 hover:bg-red-50 hover:text-red-500 transition-colors">
                    <LogOut className="w-4 h-4" />
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" className="px-3 py-1.5 rounded-lg text-sm text-slate-600 hover:bg-white/60 transition-colors">登录</Link>
                  <Link to="/register" className="px-4 py-1.5 rounded-lg text-sm font-medium gradient-brand text-white shadow-md shadow-cyan-200/40 hover:shadow-cyan-300/50 transition-shadow">注册</Link>
                </>
              )}
            </div>

            <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden p-1.5 rounded-lg text-slate-500 hover:bg-white/60">
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="md:hidden border-t border-slate-200/50 bg-white animate-fade-in">
            <div className="px-4 py-2 space-y-0.5">
              {auth.token ? (
                <>
                  <Link to="/profile" onClick={() => setMobileOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50">{auth.username}</Link>
                  {auth.role === 'admin' && (
                    <Link to="/admin" onClick={() => setMobileOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50">管理后台</Link>
                  )}
                  <button onClick={() => { handleLogout(); setMobileOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg text-sm text-red-500 hover:bg-red-50">退出</button>
                </>
              ) : (
                <>
                  <Link to="/login" onClick={() => setMobileOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50">登录</Link>
                  <Link to="/register" onClick={() => setMobileOpen(false)} className="block px-3 py-2 rounded-lg text-sm font-medium text-cyan-600 hover:bg-cyan-50">注册</Link>
                </>
              )}
            </div>
          </div>
        )}
      </nav>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200/50 py-6">
        <div className="max-w-6xl mx-auto px-4 text-center text-xs text-slate-400">
          TimeTrace — 碎片新闻，完整叙事
        </div>
      </footer>
    </div>
  );
}
