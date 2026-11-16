const BASE = '/api'
const TOKEN_KEY = 'token'

let onUnauthorized = null

/** Registered by the auth store so a dead token drops us back to the login screen. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  // An expired/revoked token on an authenticated request → sign out.
  // (A 401 while signing in has no token and is left to the caller.)
  if (res.status === 401 && token && onUnauthorized) onUnauthorized()

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* body was not JSON, keep the status text */
    }
    throw new Error(detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Auth
  register: (payload) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  changePassword: (payload) =>
    request('/auth/password', { method: 'POST', body: JSON.stringify(payload) }),

  // Email verification & password reset
  verifyEmail: (token) =>
    request('/auth/verify', { method: 'POST', body: JSON.stringify({ token }) }),
  resendVerification: () => request('/auth/verify/resend', { method: 'POST' }),
  forgotPassword: (email) =>
    request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (token, newPassword) =>
    request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  // Projects (lists)
  listProjects: () => request('/projects'),
  createProject: (payload) =>
    request('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  updateProject: (id, changes) =>
    request(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),

  // Sharing
  listMembers: (id) => request(`/projects/${id}/members`),
  addMember: (id, email) =>
    request(`/projects/${id}/members`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  removeMember: (id, userId) =>
    request(`/projects/${id}/members/${userId}`, { method: 'DELETE' }),

  // Todos
  listTodos: () => request('/todos'),
  createTodo: (payload) =>
    request('/todos', { method: 'POST', body: JSON.stringify(payload) }),
  updateTodo: (id, changes) =>
    request(`/todos/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  deleteTodo: (id) => request(`/todos/${id}`, { method: 'DELETE' }),
  clearCompleted: (projectId) =>
    request(`/todos${projectId ? `?project_id=${projectId}` : ''}`, {
      method: 'DELETE',
    }),
  reorderTodos: (ids) =>
    request('/todos/reorder', { method: 'POST', body: JSON.stringify({ ids }) }),
}
