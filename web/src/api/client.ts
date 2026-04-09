import axios from 'axios';
import { getToken } from '../stores/auth';

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

// Request: attach JWT from zustand persist store
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response: auto-logout on 401 (with debounce to prevent race condition)
let _isRedirecting = false;

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !_isRedirecting) {
      _isRedirecting = true;
      // Clear auth state via zustand persist storage
      localStorage.removeItem('timetrace-auth');
      // Use SPA navigation instead of hard redirect
      if (!window.location.pathname.includes('/login')) {
        // Small delay to prevent multiple redirects
        setTimeout(() => {
          window.location.href = '/login';
          _isRedirecting = false;
        }, 100);
      } else {
        _isRedirecting = false;
      }
    }
    return Promise.reject(err);
  }
);

export default api;
