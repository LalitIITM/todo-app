<script setup>
import { computed, nextTick, ref } from 'vue'
import { dueState, formatCreated, formatDue, wasCompletedLate } from '../dateUtils'

const props = defineProps({
  todo: { type: Object, required: true },
  dragging: { type: Boolean, default: false },
  dropIndicator: { type: String, default: null }, // 'before' | 'after' | null
  flash: { type: Boolean, default: false },
  // Everyone who can be assigned this task (owner + members of its list).
  members: { type: Array, default: () => [] },
  // True when the task's list is shared — assignment is offered there.
  shared: { type: Boolean, default: false },
  // True when the current user owns the task's list and may assign anyone.
  canAssignOthers: { type: Boolean, default: false },
  // Async save function; returns false on failure so the form can stay open.
  saveHandler: { type: Function, default: null },
  currentUserId: { type: Number, default: null },
  // False in the cross-list "Assigned to me" view (no manual reordering there).
  sortable: { type: Boolean, default: true },
  showProject: { type: Boolean, default: false },
  projectName: { type: String, default: '' },
})

const emit = defineEmits([
  'toggle',
  'save',
  'remove',
  'dragstart',
  'dragover',
  'drop',
  'dragend',
])

const editing = ref(false)
const draftTitle = ref('')
const draftDue = ref('')
const draftPriority = ref('medium')
const draftAssigneeEmail = ref('')
const inputEl = ref(null)

const labels = { low: 'Low', medium: 'Medium', high: 'High' }
const priorityLabel = computed(() => labels[props.todo.priority] ?? 'Medium')
const state = computed(() => dueState(props.todo))
const dueLabel = computed(() => (props.todo.due_date ? formatDue(props.todo.due_date) : ''))
const finishedLate = computed(() => wasCompletedLate(props.todo))

// Assignment is offered in shared lists (and always shown if already assigned).
const showAssignee = computed(() => props.shared || props.todo.assignee != null)

// A member (not the owner) may only touch an unassigned task or one that is
// already theirs — otherwise the field is locked.
const assigneeLocked = computed(() => {
  if (props.canAssignOthers) return false
  const current = props.todo.assignee?.user_id ?? null
  return current !== null && current !== props.currentUserId
})

// People this user may assign the task to (owner: everyone; member: just self).
const assignableMembers = computed(() =>
  props.canAssignOthers
    ? props.members
    : props.members.filter((m) => m.user_id === props.currentUserId)
)

// Suggestion dropdown — filtered by whatever is typed (matches name or email).
const assigneeEl = ref(null)
const suggestionsOpen = ref(false)
const highlightedIndex = ref(0)

const filteredSuggestions = computed(() => {
  const q = draftAssigneeEmail.value.trim().toLowerCase()
  const list = assignableMembers.value
  if (!q) return list
  return list.filter(
    (m) =>
      (m.name || '').toLowerCase().includes(q) ||
      (m.email || '').toLowerCase().includes(q)
  )
})

function memberLabel(member) {
  if (member.user_id === props.currentUserId) return 'You'
  return member.name || member.email
}

// Turn whatever was typed into the email we send: match a member by name or
// email, otherwise pass the raw value through (the server reports the error).
function resolveAssigneeInput() {
  const raw = draftAssigneeEmail.value.trim()
  if (!raw) return null
  const q = raw.toLowerCase()
  const match = assignableMembers.value.find(
    (m) =>
      (m.email || '').toLowerCase() === q || (m.name || '').toLowerCase() === q
  )
  return match ? match.email : raw
}

function openSuggestions() {
  if (assigneeLocked.value) return
  highlightedIndex.value = 0
  suggestionsOpen.value = true
}

function onAssigneeInput() {
  highlightedIndex.value = 0
  suggestionsOpen.value = true
}

function moveHighlight(delta) {
  if (!suggestionsOpen.value) {
    suggestionsOpen.value = true
    return
  }
  const list = filteredSuggestions.value
  if (!list.length) return
  highlightedIndex.value =
    (highlightedIndex.value + delta + list.length) % list.length
}

function pickSuggestion(member) {
  draftAssigneeEmail.value = member.email
  suggestionsOpen.value = false
  assigneeEl.value?.focus()
}

function onAssigneeEnter() {
  const typed = draftAssigneeEmail.value.trim().toLowerCase()
  if (typed && assignableMembers.value.some((m) => m.email.toLowerCase() === typed)) {
    suggestionsOpen.value = false
    commitEdit()
    return
  }
  const list = filteredSuggestions.value
  if (suggestionsOpen.value && list.length) {
    pickSuggestion(list[highlightedIndex.value])
    return
  }
  commitEdit()
}

function onAssigneeEsc() {
  if (suggestionsOpen.value) {
    suggestionsOpen.value = false
    return
  }
  cancelEdit()
}

const assigneeName = computed(() => {
  const a = props.todo.assignee
  if (!a) return ''
  return a.name || a.email
})
const assigneeIsSelf = computed(
  () => props.todo.assignee?.user_id === props.currentUserId
)

async function startEdit() {
  if (props.todo.completed) return
  draftTitle.value = props.todo.title
  draftDue.value = props.todo.due_date ?? ''
  draftPriority.value = props.todo.priority
  draftAssigneeEmail.value = props.todo.assignee?.email ?? ''
  suggestionsOpen.value = false
  editing.value = true
  await nextTick()
  inputEl.value?.focus()
}

async function commitEdit() {
  if (!editing.value) return
  const title = draftTitle.value.trim()
  if (!title) return
  const changes = {
    title,
    due_date: draftDue.value || null,
    priority: draftPriority.value,
  }
  if (showAssignee.value && !assigneeLocked.value) {
    changes.assignee_email = resolveAssigneeInput()
  }
  suggestionsOpen.value = false
  // Prefer the async handler so a failed save keeps the form open for fixing.
  if (props.saveHandler) {
    const ok = await props.saveHandler(changes)
    if (ok === false) return
    editing.value = false
    return
  }
  editing.value = false
  emit('save', changes)
}

function cancelEdit() {
  editing.value = false
  suggestionsOpen.value = false
}

// ---- drag & drop (delegated up to App.vue) ----
function onDragStart(e) {
  if (editing.value || !props.sortable) {
    e.preventDefault()
    return
  }
  emit('dragstart', props.todo, e)
}

function onDragOver(e) {
  if (!props.sortable) return
  e.preventDefault()
  emit('dragover', props.todo, e)
}

function onDrop(e) {
  if (!props.sortable) return
  e.preventDefault()
  e.stopPropagation()
  emit('drop', props.todo, e)
}
</script>

<template>
  <li
    class="todo-item"
    :class="{
      completed: todo.completed,
      dragging,
      'drop-before': dropIndicator === 'before',
      'drop-after': dropIndicator === 'after',
      flash,
    }"
    :draggable="!editing && sortable"
    @dragstart="onDragStart"
    @dragover="onDragOver"
    @drop="onDrop"
    @dragend="emit('dragend')"
  >
    <input
      class="todo-checkbox"
      type="checkbox"
      :checked="todo.completed"
      :aria-label="todo.completed ? 'Mark as not done' : 'Mark as done'"
      @change="emit('toggle')"
    />

    <div class="todo-body">
      <template v-if="editing">
        <div class="edit-row">
          <input
            ref="inputEl"
            v-model="draftTitle"
            class="todo-edit-input"
            maxlength="200"
            placeholder="Task title"
            @keyup.enter="commitEdit"
            @keyup.esc="cancelEdit"
          />
          <input
            v-model="draftDue"
            class="todo-edit-input date"
            type="date"
            aria-label="Due date"
            @keyup.enter="commitEdit"
            @keyup.esc="cancelEdit"
          />
          <select v-model="draftPriority" class="todo-edit-select" aria-label="Priority">
            <option value="low">🌱</option>
            <option value="medium">⚡</option>
            <option value="high">🔥</option>
          </select>
          <div v-if="showAssignee" class="assignee-field">
            <input
              ref="assigneeEl"
              v-model="draftAssigneeEmail"
              class="todo-edit-input assignee"
              type="text"
              placeholder="Assign by name or email"
              autocomplete="off"
              :disabled="assigneeLocked"
              :title="
                assigneeLocked
                  ? 'Only the list owner can reassign this task'
                  : 'Assign to a member by name or email (leave blank to unassign)'
              "
              @focus="openSuggestions"
              @input="onAssigneeInput"
              @blur="suggestionsOpen = false"
              @keydown.down.prevent="moveHighlight(1)"
              @keydown.up.prevent="moveHighlight(-1)"
              @keydown.enter.prevent="onAssigneeEnter"
              @keydown.esc.prevent="onAssigneeEsc"
            />
            <ul
              v-if="suggestionsOpen && filteredSuggestions.length"
              class="assignee-suggestions"
            >
              <li
                v-for="(m, i) in filteredSuggestions"
                :key="m.user_id"
                :class="{ active: i === highlightedIndex }"
                @mousedown.prevent="pickSuggestion(m)"
              >
                <span class="assignee-avatar">
                  {{ (m.name || m.email).charAt(0).toUpperCase() }}
                </span>
                <span class="suggestion-name">{{ memberLabel(m) }}</span>
                <span class="suggestion-email">{{ m.email }}</span>
              </li>
            </ul>
          </div>
        </div>
        <div class="edit-actions">
          <button class="mini-btn primary" @click="commitEdit">Save</button>
          <button class="mini-btn" @click="cancelEdit">Cancel</button>
        </div>
      </template>
      <template v-else>
        <div class="todo-title" title="Double-click to edit" @dblclick="startEdit">
          {{ todo.title }}
        </div>
        <div class="todo-meta">
          <span class="todo-priority" :class="todo.priority">{{ priorityLabel }}</span>
          <span v-if="dueLabel" class="due-chip" :class="state">{{ dueLabel }}</span>
          <span v-if="showProject && projectName" class="project-tag">📁 {{ projectName }}</span>
          <span
            v-if="todo.assignee"
            class="assignee-chip"
            :class="{ self: assigneeIsSelf }"
            :title="assigneeIsSelf ? 'Assigned to you' : `Assigned to ${assigneeName}`"
          >
            <span class="assignee-avatar">{{ assigneeName.charAt(0).toUpperCase() }}</span>
            {{ assigneeIsSelf ? 'You' : assigneeName }}
          </span>
          <span v-if="finishedLate" class="late-tag">finished late</span>
          <span class="todo-created">added {{ formatCreated(todo.created_at) }}</span>
        </div>
      </template>
    </div>

    <button v-if="!editing" class="icon-btn" title="Edit" @click="startEdit">✏️</button>
    <button class="icon-btn danger" title="Delete" @click="emit('remove')">🗑️</button>
  </li>
</template>
