import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import { Timeline } from '../components/Timeline';
import api from '../api/client';
import { ArrowLeft, Calendar, FileText, Users, Bookmark, BookmarkCheck, Tag, Activity } from 'lucide-react';
import { format } from 'date-fns';

interface ArticleItem {
  id: number;
  title: string;
  summary: string;
  source_url: string;
  published_at: string | null;
  keywords: string[];
}

interface EventDetailData {
  id: number;
  title: string;
  summary: string;
  category: string;
  importance: number;
  status: string;
  start_date: string | null;
  end_date: string | null;
  article_count: number;
  follow_count: number;
  is_followed: boolean;
  articles: ArticleItem[];
}

export function EventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const [event, setEvent] = useState<EventDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [following, setFollowing] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const endpoint = auth.token ? `/events/${id}` : `/events/${id}/public`;
        const res = await api.get<EventDetailData>(endpoint);
        setEvent(res.data);
        setFollowing(res.data.is_followed);
      } catch {
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    if (id) fetch();
  }, [id]);

  const toggleFollow = async () => {
    if (!auth.token) { navigate('/login'); return; }
    try {
      if (following) {
        await api.delete(`/users/follow/${id}`);
      } else {
        await api.post(`/users/follow/${id}`);
      }
      setFollowing(!following);
      if (event) {
        setEvent({ ...event, follow_count: event.follow_count + (following ? -1 : 1) });
      }
    } catch {
      // Silent
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="w-5 h-5 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!event) return null;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <button onClick={() => navigate('/')} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 transition-colors mb-6">
        <ArrowLeft className="w-4 h-4" /> 返回
      </button>

      {/* Event header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-5 md:p-6 mb-8 animate-fade-in-up relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 gradient-brand" />

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              {event.status === 'active' ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-600 text-xs font-medium">
                  <Activity className="w-3 h-3" /> 进行中
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-xs font-medium">已完结</span>
              )}
              {event.category && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs">
                  <Tag className="w-3 h-3" /> {event.category}
                </span>
              )}
            </div>

            <h1 className="text-xl md:text-2xl font-bold text-slate-900 mb-2 leading-tight">{event.title}</h1>

            {event.summary && (
              <p className="text-sm text-slate-500 leading-relaxed mb-3">{event.summary}</p>
            )}

            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
              {event.start_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  {format(new Date(event.start_date), 'yyyy-MM-dd')}
                  {event.end_date && ` ~ ${format(new Date(event.end_date), 'yyyy-MM-dd')}`}
                </span>
              )}
              <span className="flex items-center gap-1"><FileText className="w-3.5 h-3.5" /> {event.article_count} 篇</span>
              <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" /> {event.follow_count} 人关注</span>
            </div>
          </div>

          <button
            onClick={toggleFollow}
            className={`shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              following
                ? 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                : 'gradient-brand text-white shadow-md shadow-cyan-200/30'
            }`}
          >
            {following ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
            {following ? '已关注' : '关注'}
          </button>
        </div>
      </div>

      {/* Timeline */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-slate-700 mb-5 flex items-center gap-2">
          <div className="w-1 h-4 rounded-full gradient-brand" />
          事件时间线
        </h2>
        <Timeline articles={event.articles} />
      </div>
    </div>
  );
}
