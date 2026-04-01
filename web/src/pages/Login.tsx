import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import api from '../api/client';
import { LogIn, Eye, EyeOff } from 'lucide-react';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/users/login', { username, password });
      auth.setAuth(res.data.access_token, res.data.username, res.data.role);
      navigate('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '登录失败';
      setError(msg);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm animate-fade-in-up">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 mx-auto mb-4 rounded-2xl gradient-brand flex items-center justify-center shadow-lg shadow-cyan-200/30">
            <LogIn className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800">欢迎回来</h1>
          <p className="text-sm text-slate-400 mt-1">登录以关注事件和获取推荐</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-6">
          {error && (
            <div className="mb-4 p-2.5 rounded-lg bg-red-50 text-red-600 text-sm text-center animate-fade-in">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">用户名</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-200 focus:border-cyan-400 focus:bg-white focus:ring-2 focus:ring-cyan-50 outline-none text-sm transition-all"
                placeholder="输入用户名" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">密码</label>
              <div className="relative">
                <input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required
                  className="w-full px-3.5 py-2.5 pr-10 rounded-xl bg-slate-50 border border-slate-200 focus:border-cyan-400 focus:bg-white focus:ring-2 focus:ring-cyan-50 outline-none text-sm transition-all"
                  placeholder="输入密码" />
                <button type="button" onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-xl gradient-brand text-white text-sm font-semibold shadow-md shadow-cyan-200/30 hover:shadow-cyan-300/40 disabled:opacity-50 transition-all">
              {loading ? '登录中...' : '登录'}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-slate-400 mt-5">
          没有账号？<Link to="/register" className="text-cyan-600 hover:text-cyan-700 font-medium">注册</Link>
        </p>
      </div>
    </div>
  );
}
