import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import { Bookmark, TrendingUp, ExternalLink } from 'lucide-react';
import api from '../api/client';
import { format } from 'date-fns';

interface FollowItem {
  event_id: number;
  event_title: string;
  event_status: string;
  followed_at: string | null;
}

export function Profile() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [follows, setFollows] = useState<FollowItem[]>([]);
  const [recs, setRecs] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [fRes, rRes] = await Promise.all([
          api.get<FollowItem[]>('/users/follows'),
          api.get<number[]>('/users/recommendations'),
        ]);
        setFollows(fRes.data);
        setRecs(rRes.data);
      } catch (e) { console.error('Failed to load profile data:', e); } finally { setLoading(false); }
    };
    fetch();
  }, []);

  const unfollow = async (eventId: number) => {
    if (!confirm('确定取消关注此事件？')) return;
    try {
      await api.delete(`/users/follow/${eventId}`);
      setFollows((prev) => prev.filter((f) => f.event_id !== eventId));
    } catch (e) { console.error('Failed to unfollow:', e); }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="w-5 h-5 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* User card */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-6 mb-8 animate-fade-in-up relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 gradient-brand" />
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl gradient-brand flex items-center justify-center text-white text-xl font-bold shadow-md shadow-cyan-200/30">
            {auth.username?.[0]?.toUpperCase()}
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-800">{auth.username}</h1>
            <p className="text-sm text-slate-400">
              {auth.role === 'admin' ? '管理员' : '用户'} · 关注了 {follows.length} 个事件
            </p>
          </div>
        </div>
      </div>

      {/* Followed events */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <div className="w-1 h-4 rounded-full gradient-brand" />
          我关注的事件
        </h2>
        {follows.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-slate-200/80">
            <Bookmark className="w-8 h-8 mx-auto mb-2 text-slate-200" />
            <p className="text-sm text-slate-400">还没有关注任何事件</p>
            <Link to="/" className="text-sm text-cyan-500 hover:text-cyan-600 mt-1 inline-block">去首页看看</Link>
          </div>
        ) : (
          <div className="space-y-2 stagger">
            {follows.map((f) => (
              <div key={f.event_id} className="flex items-center justify-between bg-white rounded-xl border border-slate-200/80 p-4 card-lift">
                <div className="flex-1 min-w-0">
                  <Link to={`/event/${f.event_id}`} className="text-sm font-medium text-slate-800 hover:text-cyan-600 transition-colors truncate block">
                    {f.event_title}
                  </Link>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${f.event_status === 'active' ? 'bg-cyan-50 text-cyan-600' : 'bg-emerald-50 text-emerald-600'}`}>
                      {f.event_status === 'active' ? '进行中' : '已完结'}
                    </span>
                    {f.followed_at && (
                      <span className="text-[10px] text-slate-400">{format(new Date(f.followed_at), 'yyyy-MM-dd')}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-3">
                  <Link to={`/event/${f.event_id}`} className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-500 hover:bg-cyan-50 transition-colors">
                    <ExternalLink className="w-4 h-4" />
                  </Link>
                  <button onClick={() => unfollow(f.event_id)} className="px-2.5 py-1 rounded-lg text-xs text-red-500 hover:bg-red-50 transition-colors">取关</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recommendations */}
      {recs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <div className="w-1 h-4 rounded-full gradient-brand" />
            为你推荐
          </h2>
          <div className="flex flex-wrap gap-2">
            {recs.map((eid) => (
              <Link key={eid} to={`/event/${eid}`} className="px-3 py-1.5 rounded-lg bg-white border border-slate-200/80 text-sm text-cyan-600 hover:border-cyan-200 card-lift">
                事件 #{eid}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
