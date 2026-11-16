<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../composables/useAuth'

const { user, refreshUser } = useAuth()

const busy = ref(false)
const notice = ref('')
const error = ref('')

const visible = computed(() => user.value && !user.value.email_verified)

async function resend() {
  if (busy.value) return
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    const res = await api.resendVerification()
    notice.value = res.detail
    await refreshUser()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="visible" class="verify-banner" role="status">
    <span class="verify-icon">✉️</span>
    <div class="verify-text">
      <strong>Verify your email</strong>
      <span v-if="notice" class="verify-note">{{ notice }}</span>
      <span v-else-if="error" class="verify-note error">{{ error }}</span>
      <span v-else>
        We sent a link to <b>{{ user.email }}</b>. Click it to confirm your address.
      </span>
    </div>
    <button class="verify-btn" type="button" :disabled="busy" @click="resend">
      {{ busy ? 'Sending…' : 'Resend' }}
    </button>
  </div>
</template>
