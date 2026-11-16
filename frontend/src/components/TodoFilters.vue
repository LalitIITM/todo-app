<script setup>
defineProps({
  modelValue: { type: String, required: true },
  counts: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

const filters = [
  { value: 'all', label: 'All' },
  { value: 'ongoing', label: 'Ongoing' },
  { value: 'late', label: 'Late' },
  { value: 'done', label: 'Done' },
]
</script>

<template>
  <div class="filters" role="tablist" aria-label="Filter tasks">
    <button
      v-for="f in filters"
      :key="f.value"
      class="filter-btn"
      :class="{ active: modelValue === f.value }"
      type="button"
      @click="emit('update:modelValue', f.value)"
    >
      {{ f.label }}<span class="filter-count">· {{ counts[f.value] }}</span>
    </button>
  </div>
</template>
