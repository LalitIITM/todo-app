<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../composables/useAuth'

const { user, logout } = useAuth()

const open = ref(false)
const showPassword = ref(false)
const current = ref('')
const next = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')

const label = computed(() => user.value?.name || user.value?.email || 'Account')
const initial = computed(() => label.value.trim().charAt(0).toUpperCase())

function toggle() {
  open.value = !open.value
  if (!open.value) reset()
}

function reset() {
  showPassword.value = false
  current.value = ''
  next.value = ''
  error.value = ''
  notice.value = ''
}

async function changePassword() {
  error.value = ''
  notice.value = ''
  if (next.value.length < 8) {
    error.value = 'New password must be at least 8 characters'
    return
  }
  busy.value = true
  try {
    await api.changePassword({
      current_password: current.value,
      new_password: next.value,
    })
    notice.value = 'Password updated ✓'
    current.value = ''
    next.value = ''
    setTimeout(() => {
      showPassword.value = false
      notice.value = ''
    }, 1200)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="user-menu">
    <button class="user-btn" :title="label" @click="toggle">
      <span class="user-avatar">{{ initial }}</span>
    </button>

    <div v-if="open" class="menu-overlay" @click="toggle"></div>

    <div v-if="open" class="user-panel">
      <div class="user-head">
        <span class="user-avatar large">{{ initial }}</span>
        <div class="user-id">
          <div class="user-name">{{ user?.name || 'Signed in' }}</div>
          <div class="user-email">{{ user?.email }}</div>
        </div>
      </div>

      <template v-if="!showPassword">
        <button class="menu-item" @click="showPassword = true">🔑 Change password</button>
        <button class="menu-item danger" @click="logout">↩︎ Sign out</button>
      </template>

      <form v-else class="password-form" @submit.prevent="changePassword">
        <label class="auth-field compact">
          <span>Current password</span>
          <input v-model="current" type="password" autocomplete="current-password" />
        </label>
        <label class="auth-field compact">
          <span>New password</span>
          <input
            v-model="next"
            type="password"
            autocomplete="new-password"
            placeholder="At least 8 characters"
          />
        </label>

        <div v-if="error" class="menu-error">{{ error }}</div>
        <div v-if="notice" class="menu-notice">{{ notice }}</div>

        <div class="menu-actions">
          <button class="mini-btn primary" type="submit" :disabled="busy">
            {{ busy ? 'Saving…' : 'Save' }}
          </button>
          <button class="mini-btn" type="button" @click="reset">Cancel</button>
        </div>
      </form>
    </div>
  </div>
</template>
