<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  projects: { type: Array, required: true },
})

// null → analyse every list; otherwise a single list id.
const scopeId = ref(null)
const data = ref(null)
const loading = ref(true)
const error = ref('')

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.stats(scopeId.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
watch(scopeId, loadStats)

const rate = computed(() => Math.round((data.value?.completion_rate ?? 0) * 100))

const maxTrend = computed(() =>
  Math.max(1, ...(data.value?.last_7_days ?? []).map((d) => d.completed))
)

function pct(part, total) {
  return total ? Math.round((part / total) * 100) : 0
}

function dayLabel(iso) {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString(undefined, { weekday: 'short' })
}

function formatDays(value) {
  if (value === null || value === undefined) return '—'
  if (value < 1) return '< 1'
  return value.toFixed(1)
}
</script>

<template>
  <section class="stats-panel">
    <div class="stats-toolbar">
      <label class="stats-scope">
        <span>Showing</span>
        <select v-model="scopeId">
          <option :value="null">All lists</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>
      <button class="stats-refresh" type="button" @click="loadStats">↻ Refresh</button>
    </div>

    <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

    <div v-if="loading" aria-label="Loading stats">
      <div v-for="n in 2" :key="n" class="skeleton"></div>
    </div>

    <template v-else-if="data">
      <div class="stats-cards">
        <div class="stat-card featured">
          <span class="stat-value">{{ rate }}%</span>
          <span class="stat-label">Completion rate</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">
            {{ data.completed }}<span class="stat-of">/{{ data.total }}</span>
          </span>
          <span class="stat-label">Completed</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ data.open }}</span>
          <span class="stat-label">Open</span>
        </div>
        <div class="stat-card" :class="{ danger: data.overdue > 0 }">
          <span class="stat-value">{{ data.overdue }}</span>
          <span class="stat-label">Overdue</span>
        </div>
      </div>

      <div class="stats-highlights">
        <div class="highlight">
          <span class="highlight-value">{{ data.completed_today }}</span>
          <span class="highlight-label">done today</span>
        </div>
        <div class="highlight">
          <span class="highlight-value">{{ data.completed_this_week }}</span>
          <span class="highlight-label">this week</span>
        </div>
        <div class="highlight">
          <span class="highlight-value">{{ data.completed_on_time }}</span>
          <span class="highlight-label">on time</span>
        </div>
        <div class="highlight">
          <span class="highlight-value">{{ data.completed_late }}</span>
          <span class="highlight-label">late</span>
        </div>
        <div class="highlight">
          <span class="highlight-value">{{ formatDays(data.avg_completion_days) }}</span>
          <span class="highlight-label">avg days to finish</span>
        </div>
      </div>

      <div class="stats-block">
        <h3 class="stats-heading">Last 7 days</h3>
        <div class="trend">
          <div v-for="day in data.last_7_days" :key="day.label" class="trend-col">
            <div class="trend-bar-track">
              <div
                class="trend-bar"
                :style="{ height: `${(day.completed / maxTrend) * 100}%` }"
                :title="`${day.completed} completed · ${day.total} added`"
              ></div>
            </div>
            <span class="trend-count">{{ day.completed }}</span>
            <span class="trend-day">{{ dayLabel(day.label) }}</span>
          </div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stats-block">
          <h3 class="stats-heading">By priority</h3>
          <ul class="breakdown">
            <li v-for="row in data.by_priority" :key="row.label" class="breakdown-row">
              <span class="breakdown-label">
                <span class="prio-dot" :class="`prio-${row.label}`"></span>
                {{ row.label }}
              </span>
              <span class="breakdown-nums">{{ row.completed }}/{{ row.total }}</span>
              <span class="breakdown-track">
                <span
                  class="breakdown-fill"
                  :style="{ width: `${pct(row.completed, row.total)}%` }"
                ></span>
              </span>
            </li>
          </ul>
        </div>

        <div class="stats-block">
          <h3 class="stats-heading">By list</h3>
          <ul class="breakdown">
            <li v-for="row in data.by_list" :key="row.label" class="breakdown-row">
              <span class="breakdown-label">{{ row.label }}</span>
              <span class="breakdown-nums">{{ row.completed }}/{{ row.total }}</span>
              <span class="breakdown-track">
                <span
                  class="breakdown-fill"
                  :style="{ width: `${pct(row.completed, row.total)}%` }"
                ></span>
              </span>
            </li>
            <li v-if="!data.by_list.length" class="breakdown-empty">No lists yet</li>
          </ul>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <span class="empty-icon">📊</span>
      <p>No stats to show yet.</p>
    </div>
  </section>
</template>
