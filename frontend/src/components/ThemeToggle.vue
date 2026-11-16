<script setup>
import { useTheme } from '../composables/useTheme'

const { theme, toggle } = useTheme()
</script>

<template>
  <button
    class="theme-toggle"
    :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
    :title="theme === 'dark' ? 'Light mode' : 'Dark mode'"
    @click="toggle"
  >
    {{ theme === 'dark' ? '☀️' : '🌙' }}
  </button>
</template>
