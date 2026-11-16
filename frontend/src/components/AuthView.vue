<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import { useAuth } from '../composables/useAuth'
import ThemeToggle from './ThemeToggle.vue'

const props = defineProps({
  // When set (from a ?reset=<token> link) we open straight into the reset form.
  resetToken: { type: String, default: null },
})

const { login, register } = useAuth()

const mode = ref(props.resetToken ? 'reset' : 'login') // login | register | forgot | reset
const email = ref('')
const password = ref('')
const name = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')

const isRegister = computed(() => mode.value === 'register')
const isForgot = computed(() => mode.value === 'forgot')
const isReset = computed(() => mode.value === 'reset')

const subtitle = computed(() => {
  if (isRegister.value) return 'Create your account'
  if (isForgot.value) return 'Reset your password'
  if (isReset.value) return 'Choose a new password'
  return 'Sign in to your lists'
})

const canSubmit = computed(() => {
  if (busy.value) return false
  if (isForgot.value) return !!email.value.trim()
  // The reset form has no email field — only a new password.
  if (isReset.value) return password.value.length >= 8
  if (!email.value.trim() || !password.value) return false
  return !isRegister.value || password.value.length >= 8
})

// A reset link arriving while the form is already open switches it over.
watch(
  () => props.resetToken,
  (token) => {
    if (token) {
      mode.value = 'reset'
      error.value = ''
      notice.value = ''
    }
  }
)

function switchMode(next) {
  mode.value = next
  error.value = ''
  notice.value = ''
}

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    if (isForgot.value) {
      const res = await api.forgotPassword(email.value.trim())
      notice.value = res.detail
    } else if (isReset.value) {
      await api.resetPassword(props.resetToken, password.value)
      notice.value = 'Password updated — sign in with your new password.'
      mode.value = 'login'
      email.value = ''
      password.value = ''
    } else if (isRegister.value) {
      await register({
        email: email.value.trim(),
        password: password.value,
        name: name.value.trim() || null,
      })
    } else {
      await login(email.value.trim(), password.value)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function backToLogin() {
  switchMode('login')
}
</script>

<template>
  <div class="auth-shell">
    <div class="auth-top">
      <ThemeToggle />
    </div>

    <form class="auth-card" @submit.prevent="submit">
      <div class="auth-logo">✅</div>
      <h1 class="auth-title">Tasks</h1>
      <p class="auth-subtitle">{{ subtitle }}</p>

      <div v-if="!isForgot && !isReset" class="auth-tabs" role="tablist">
        <button
          type="button"
          class="auth-tab"
          :class="{ active: mode === 'login' }"
          @click="switchMode('login')"
        >
          Sign in
        </button>
        <button
          type="button"
          class="auth-tab"
          :class="{ active: mode === 'register' }"
          @click="switchMode('register')"
        >
          Create account
        </button>
      </div>

      <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
      <div v-if="notice" class="auth-notice" role="status">{{ notice }}</div>

      <p v-if="isForgot" class="auth-blurb">
        Enter the email you signed up with and we'll send you a link to choose a
        new password.
      </p>
      <p v-if="isReset" class="auth-blurb">
        Pick a new password for your account. You'll be signed out everywhere
        else.
      </p>

      <label v-if="isRegister" class="auth-field">
        <span>Name <em>(optional)</em></span>
        <input v-model="name" type="text" maxlength="100" autocomplete="name" placeholder="Your name" />
      </label>

      <label v-if="!isReset" class="auth-field">
        <span>Email</span>
        <input
          v-model="email"
          type="email"
          required
          autocomplete="email"
          placeholder="you@example.com"
        />
      </label>

      <label v-if="!isForgot" class="auth-field">
        <span>{{ isReset ? 'New password' : 'Password' }}</span>
        <input
          v-model="password"
          type="password"
          required
          :autocomplete="isRegister || isReset ? 'new-password' : 'current-password'"
          :placeholder="isRegister || isReset ? 'At least 8 characters' : 'Your password'"
        />
      </label>

      <button class="auth-submit" type="submit" :disabled="!canSubmit">
        <template v-if="busy">Please wait…</template>
        <template v-else-if="isForgot">Send reset link</template>
        <template v-else-if="isReset">Set new password</template>
        <template v-else-if="isRegister">Create account</template>
        <template v-else>Sign in</template>
      </button>

      <p v-if="isForgot || isReset" class="auth-hint">
        <a class="auth-link" href="#" @click.prevent="backToLogin">← Back to sign in</a>
      </p>

      <p v-else-if="!isRegister" class="auth-hint">
        <a class="auth-link" href="#" @click.prevent="switchMode('forgot')">
          Forgot password?
        </a>
      </p>

      <p v-if="!isRegister && !isForgot && !isReset" class="auth-hint">
        First time here? Use the seeded account
        <code>you@example.com</code> / <code>changeme123</code>, or create your own.
      </p>
    </form>
  </div>
</template>
