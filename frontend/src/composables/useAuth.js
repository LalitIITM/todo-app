import { computed, ref } from 'vue'
import { api, getToken, setToken, setUnauthorizedHandler } from '../api'

// Module-level state → shared singleton across components.
const user = ref(null)
const ready = ref(false) // true once the initial token check has finished

function clear() {
  setToken(null)
  user.value = null
}

// A rejected/expired token anywhere in the app signs the user out.
setUnauthorizedHandler(clear)

async function bootstrap() {
  if (!getToken()) {
    ready.value = true
    return
  }
  try {
    user.value = await api.me()
  } catch {
    clear()
  } finally {
    ready.value = true
  }
}

async function login(email, password) {
  const res = await api.login({ email, password })
  setToken(res.token)
  user.value = res.user
  return res.user
}

async function register(payload) {
  const res = await api.register(payload)
  setToken(res.token)
  user.value = res.user
  return res.user
}

async function logout() {
  try {
    await api.logout()
  } catch {
    /* the token may already be gone — that's fine */
  }
  clear()
}

/** Re-fetch the signed-in user (e.g. after verifying an email). */
async function refreshUser() {
  if (!getToken()) return null
  try {
    user.value = await api.me()
  } catch {
    /* a dead token is handled by the unauthorized handler */
  }
  return user.value
}

export function useAuth() {
  return {
    user,
    ready,
    isAuthenticated: computed(() => user.value !== null),
    bootstrap,
    login,
    register,
    logout,
    refreshUser,
    clear,
  }
}
