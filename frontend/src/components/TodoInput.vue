<script setup>
import { computed, ref } from 'vue'

const emit = defineEmits(['add'])

const title = ref('')
const priority = ref('medium')
const dueDate = ref('')
const canSubmit = computed(() => title.value.trim().length > 0)

function submit() {
  if (!canSubmit.value) return
  emit('add', {
    title: title.value.trim(),
    priority: priority.value,
    due_date: dueDate.value || null,
  })
  title.value = ''
  priority.value = 'medium'
  dueDate.value = ''
}
</script>

<template>
  <form class="add-form" @submit.prevent="submit">
    <input
      v-model="title"
      class="add-input"
      type="text"
      placeholder="What needs doing?"
      maxlength="200"
      autocomplete="off"
    />
    <input
      v-model="dueDate"
      class="add-input date"
      type="date"
      aria-label="Due date"
      title="Due date (optional)"
    />
    <select v-model="priority" class="priority-select" aria-label="Priority">
      <option value="low">🌱 Low</option>
      <option value="medium">⚡ Medium</option>
      <option value="high">🔥 High</option>
    </select>
    <button class="add-btn" type="submit" :disabled="!canSubmit">Add</button>
  </form>
</template>
