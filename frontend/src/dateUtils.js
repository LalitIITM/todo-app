// Due dates are stored as 'YYYY-MM-DD' strings and interpreted in the
// user's local timezone, so "today" always means *their* today.

export function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

export function toLocalDateStr(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Whole days from today to a 'YYYY-MM-DD' date; negative = past. */
export function daysUntil(dateStr) {
  if (!dateStr) return null
  const target = new Date(`${dateStr}T00:00:00`)
  return Math.round((target - startOfToday()) / 86_400_000)
}

/** Friendly label for a due date chip. */
export function formatDue(dateStr) {
  const days = daysUntil(dateStr)
  if (days === null) return ''
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  if (days === -1) return 'Yesterday'
  if (days < -1) return `${-days}d overdue`
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

/** Urgency bucket for an *incomplete* task: overdue | today | soon | later | null. */
export function dueState(todo) {
  if (!todo.due_date || todo.completed) return null
  const days = daysUntil(todo.due_date)
  if (days === null) return null
  if (days < 0) return 'overdue'
  if (days === 0) return 'today'
  if (days <= 2) return 'soon'
  return 'later'
}

export function isLate(todo) {
  return !todo.completed && daysUntil(todo.due_date) < 0
}

/** Finished after its deadline? */
export function wasCompletedLate(todo) {
  if (!todo.completed || !todo.due_date || !todo.completed_at) return false
  return toLocalDateStr(new Date(todo.completed_at)) > todo.due_date
}

export function formatCreated(iso) {
  const d = new Date(iso)
  const now = new Date()
  const yesterday = new Date(Date.now() - 86_400_000)
  if (d.toDateString() === now.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
