import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  username: string | null;
  role: string | null;
  setAuth: (token: string, username: string, role: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
  isAdmin: () => boolean;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      username: null,
      role: null,
      setAuth: (token, username, role) => {
        // 唯一 Token 存储点：zustand persist (localStorage key: timetrace-auth)
        // 不再额外使用 localStorage.setItem('token', ...)
        set({ token, username, role });
      },
      logout: () => {
        set({ token: null, username: null, role: null });
      },
      isAuthenticated: () => !!get().token,
      isAdmin: () => get().role === 'admin',
    }),
    { name: 'timetrace-auth' }
  )
);

/** 获取当前 Token — 供 API client 等非 React 上下文使用。 */
export function getToken(): string | null {
  try {
    const raw = localStorage.getItem('timetrace-auth');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.token ?? null;
  } catch {
    return null;
  }
}
