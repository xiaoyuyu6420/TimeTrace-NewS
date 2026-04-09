import { useEffect, useState } from 'react';
import api from '../../api/client';
import { Plus, Trash2, RefreshCw, ToggleLeft, ToggleRight } from 'lucide-react';

interface Source {
  id: number;
  name: string;
  url: string;
  category: string;
  is_active: boolean;
  last_crawled: string | null;
}

export function AdminSources() {
  const [sources, setSources] = useState<Source[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [newCat, setNewCat] = useState('科技');
  const [crawling, setCrawling] = useState(false);

  const fetchSources = () => api.get<Source[]>('/rss').then((r) => setSources(r.data)).catch((e) => console.error('Failed to load RSS sources:', e));
  useEffect(() => { fetchSources(); }, []);

  const addSource = async () => {
    if (!newName || !newUrl) return;
    try {
      await api.post('/rss', { name: newName, url: newUrl, category: newCat });
      setNewName(''); setNewUrl(''); setShowAdd(false);
      fetchSources();
    } catch (e) {
      console.error('Failed to add RSS source:', e);
    }
  };

  const deleteSource = async (id: number) => {
    if (!confirm('确定删除此 RSS 源？')) return;
    try {
      await api.delete(`/rss/${id}`);
      fetchSources();
    } catch (e) {
      console.error('Failed to delete RSS source:', e);
    }
  };

  const toggleActive = async (src: Source) => {
    try {
      await api.put(`/rss/${src.id}`, { is_active: !src.is_active });
      fetchSources();
    } catch (e) {
      console.error('Failed to toggle RSS source:', e);
    }
  };

  const triggerCrawl = async () => {
    setCrawling(true);
    try { await api.post('/rss/crawl'); } catch (e) { console.error('Failed to trigger crawl:', e); } finally { setTimeout(() => setCrawling(false), 3000); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">RSS 源管理</h1>
        <div className="flex gap-2">
          <button onClick={triggerCrawl} disabled={crawling}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm gradient-brand text-white shadow-md shadow-cyan-200/30 disabled:opacity-50 transition-all">
            <RefreshCw className={`w-3.5 h-3.5 ${crawling ? 'animate-spin' : ''}`} />
            {crawling ? '采集中...' : '手动采集'}
          </button>
          <button onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm bg-slate-800 text-white hover:bg-slate-700 transition-colors">
            <Plus className="w-3.5 h-3.5" /> 添加源
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-4 mb-4 flex flex-wrap gap-3 animate-fade-in">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="名称"
            className="flex-1 min-w-[120px] px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-cyan-400 outline-none" />
          <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="RSS URL"
            className="flex-1 min-w-[180px] px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-cyan-400 outline-none" />
          <select value={newCat} onChange={(e) => setNewCat(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-200 text-sm">
            <option>科技</option><option>财经</option><option>社会</option><option>国际</option><option>综合</option>
          </select>
          <button onClick={addSource} className="px-4 py-2 rounded-lg gradient-brand text-white text-sm">确认</button>
          <button onClick={() => setShowAdd(false)} className="px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm">取消</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200/80 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80 text-slate-500 text-xs">
            <tr>
              <th className="text-left px-4 py-3 font-medium">名称</th>
              <th className="text-left px-4 py-3 font-medium">URL</th>
              <th className="text-left px-4 py-3 font-medium">分类</th>
              <th className="text-left px-4 py-3 font-medium">状态</th>
              <th className="text-left px-4 py-3 font-medium">最近采集</th>
              <th className="text-right px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((src) => (
              <tr key={src.id} className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-800">{src.name}</td>
                <td className="px-4 py-3 text-slate-400 max-w-[200px] truncate">{src.url}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs">{src.category}</span></td>
                <td className="px-4 py-3">
                  <button onClick={() => toggleActive(src)}>
                    {src.is_active ? <ToggleRight className="w-5 h-5 text-emerald-500" /> : <ToggleLeft className="w-5 h-5 text-slate-300" />}
                  </button>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{src.last_crawled ? new Date(src.last_crawled).toLocaleString('zh-CN') : '-'}</td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => deleteSource(src.id)} className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
