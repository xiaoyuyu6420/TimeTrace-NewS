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
        localStorage.setItem('token', token);
        set({ token, username, role });
      },
      logout: () => {
        localStorage.removeItem('token');
        set({ token: null, username: null, role: null });
      },
      isAuthenticated: () => !!get().token,
      isAdmin: () => get().role === 'admin',
    }),
    { name: 'timetrace-auth' }
  )
);
