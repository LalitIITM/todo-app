<script setup>
import { computed, ref } from 'vue'
import { formatDue } from '../dateUtils'

const props = defineProps({
  overdue: { type: Array, required: true }, // [{ todo, projectName }]
  today: { type: Array, required: true },
  soon: { type: Array, required: true },
})

const emit = defineEmits(['open'])

const open = ref(false)

const badge = computed(() => props.overdue.length + props.today.length)
const empty = computed(() => badge.value === 0 && props.soon.length === 0)

const groups = computed(() => [
  { key: 'overdue', title: 'Overdue', items: props.overdue, cls: 'overdue' },
  { key: 'today', title: 'Due today', items: props.today, cls: 'today' },
  { key: 'soon', title: 'Coming up', items: props.soon, cls: 'soon' },
].filter((g) => g.items.length))
</script>

<template>
  <div class="alerts">
    <button
      class="alerts-bell"
      :class="{ attention: badge > 0 }"
      :title="badge ? `${badge} task(s) need attention` : 'No alerts'"
      @click="open = !open"
    >
      🔔
      <span v-if="badge" class="alerts-badge">{{ badge }}</span>
    </button>

    <div v-if="open" class="alerts-overlay" @click="open = false"></div>

    <div v-if="open" class="alerts-panel">
      <div class="alerts-title">Alerts</div>

      <div v-if="empty" class="alerts-empty">
        Nothing overdue or due today — enjoy 🎉
      </div>

      <div v-for="group in groups" :key="group.key" class="alerts-group">
        <div class="alerts-group-title" :class="group.cls">{{ group.title }}</div>
        <button
          v-for="{ todo, projectName } in group.items"
          :key="todo.id"
          class="alerts-row"
          @click="emit('open', todo)"
        >
          <span class="alerts-row-title">{{ todo.title }}</span>
          <span class="alerts-row-meta">
            {{ formatDue(todo.due_date) }} · {{ projectName }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
