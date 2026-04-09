/** User API 封装。 */

import api from './client';

export function login(username: string, password: string) {
  return api.post<{ access_token: string; role: string; username: string }>('/users/login', {
    username,
    password,
  });
}

export function register(username: string, email: string, password: string) {
  return api.post('/users/register', { username, email, password });
}

export function fetchProfile() {
  return api.get('/users/me');
}

export function followEvent(eventId: number) {
  return api.post(`/users/follow/${eventId}`);
}

export function unfollowEvent(eventId: number) {
  return api.delete(`/users/follow/${eventId}`);
}

export function fetchFollows() {
  return api.get('/users/follows');
}
