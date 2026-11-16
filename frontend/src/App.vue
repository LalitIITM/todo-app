<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from './api'
import { daysUntil } from './dateUtils'
import { useAuth } from './composables/useAuth'
import AlertsBell from './components/AlertsBell.vue'
import AuthView from './components/AuthView.vue'
import ProjectSidebar from './components/ProjectSidebar.vue'
import ShareDialog from './components/ShareDialog.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import TodoFilters from './components/TodoFilters.vue'
import TodoInput from './components/TodoInput.vue'
import TodoItem from './components/TodoItem.vue'
import UserMenu from './components/UserMenu.vue'
import VerifyBanner from './components/VerifyBanner.vue'

const { user, ready: authReady, bootstrap, refreshUser } = useAuth()

const projects = ref([])
const todos = ref([])
const selectedProjectId = ref(Number(localStorage.getItem('selectedProject')) || null)
const assignedOnly = ref(false)
const filter = ref('all')
const loading = ref(true)
const error = ref('')

// A ?reset=<token> link opens the reset form; ?verify=<token> is handled on load.
const resetToken = ref(null)
const urlNotice = ref('')

// drag & drop state
const dragging = ref(null) // the todo being dragged
const dropTarget = ref(null) // { id, before }

const shareTarget = ref(null)
const flashTodoId = ref(null)
const toast = ref(null) // { id, msg, type }
let toastTimer = null
let loadToastShown = false

// ---------- computed ----------

const currentProject = computed(
  () => projects.value.find((p) => p.id === selectedProjectId.value) ?? null
)

const currentTodos = computed(() => {
  if (assignedOnly.value) {
    const mine = todos.value.filter((t) => t.assignee?.user_id === user.value?.id)
    return [...mine].sort(
      (a, b) => a.project_id - b.project_id || a.position - b.position || a.id - b.id
    )
  }
  const list = todos.value.filter((t) => t.project_id === selectedProjectId.value)
  return [...list].sort((a, b) => a.position - b.position || a.id - b.id)
})

const counts = computed(() => ({
  all: currentTodos.value.length,
  ongoing: currentTodos.value.filter((t) => !t.completed).length,
  late: currentTodos.value.filter((t) => !t.completed && daysUntil(t.due_date) < 0)
    .length,
  done: currentTodos.value.filter((t) => t.completed).length,
}))

const visible = computed(() => {
  if (filter.value === 'ongoing') return currentTodos.value.filter((t) => !t.completed)
  if (filter.value === 'done') return currentTodos.value.filter((t) => t.completed)
  if (filter.value === 'late')
    return currentTodos.value.filter(
      (t) => !t.completed && daysUntil(t.due_date) < 0
    )
  return currentTodos.value
})

const projectActiveCounts = computed(() => {
  const counts = {}
  for (const p of projects.value) counts[p.id] = 0
  for (const t of todos.value) {
    if (!t.completed && t.project_id in counts) counts[t.project_id] += 1
  }
  return counts
})

const projectNameById = computed(
  () => new Map(projects.value.map((p) => [p.id, p.name]))
)

// Everyone who can be assigned a task in each list: the owner plus members.
const membersByProject = computed(() => {
  const map = new Map()
  for (const p of projects.value) {
    const list = []
    if (p.owner) list.push(p.owner)
    for (const m of p.members || []) list.push(m)
    map.set(p.id, list)
  }
  return map
})

const assignedCount = computed(
  () =>
    todos.value.filter((t) => !t.completed && t.assignee?.user_id === user.value?.id)
      .length
)

// Only a list's owner may hand a task to somebody else.
function projectOf(todo) {
  return projects.value.find((p) => p.id === todo.project_id) ?? null
}

function canAssignOthers(todo) {
  return projectOf(todo)?.owner_id === user.value?.id
}

// Assignment is offered in shared lists.
function isSharedList(todo) {
  return !!projectOf(todo)?.is_shared
}

const alertsOverdue = computed(() =>
  todos.value
    .filter((t) => !t.completed && daysUntil(t.due_date) < 0)
    .map((t) => ({ todo: t, projectName: projectNameById.value.get(t.project_id) ?? '' }))
)
const alertsToday = computed(() =>
  todos.value
    .filter((t) => !t.completed && daysUntil(t.due_date) === 0)
    .map((t) => ({ todo: t, projectName: projectNameById.value.get(t.project_id) ?? '' }))
)
const alertsSoon = computed(() =>
  todos.value
    .filter((t) => {
      const days = daysUntil(t.due_date)
      return !t.completed && days !== null && days > 0 && days <= 2
    })
    .map((t) => ({ todo: t, projectName: projectNameById.value.get(t.project_id) ?? '' }))
)

const subtitle = computed(() => {
  if (counts.value.ongoing === 0 && counts.value.all > 0)
    return 'All done — enjoy your day 🎉'
  const active = counts.value.ongoing
  return `${active} ${active === 1 ? 'task' : 'tasks'} left`
})

const emptyMessage = computed(() => {
  if (filter.value === 'done') return 'Nothing completed yet — go finish something!'
  if (filter.value === 'late') return 'No late tasks. Right on schedule! ✨'
  if (filter.value === 'ongoing' && counts.value.all > 0)
    return 'Nothing ongoing — everything is done! 🎉'
  if (assignedOnly.value) return 'Nothing is assigned to you right now.'
  if (!currentProject.value) return 'Create a list in the sidebar to get started!'
  return 'This list is empty. Add your first task above!'
})

// ---------- auth lifecycle ----------

function stripUrlTokens() {
  const url = new URL(window.location.href)
  url.searchParams.delete('verify')
  url.searchParams.delete('reset')
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
}

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const verifyToken = params.get('verify')
  const reset = params.get('reset')
  if (reset) resetToken.value = reset

  await bootstrap()

  if (verifyToken) {
    try {
      const verified = await api.verifyEmail(verifyToken)
      urlNotice.value = `Thanks! ${verified.email} is now verified.`
      // If we're signed in, pick up the new flag so the banner disappears.
      if (user.value) await refreshUser()
    } catch (e) {
      urlNotice.value = `Verification failed: ${e.message}`
    }
  }

  if (verifyToken || reset) stripUrlTokens()
  if (!user.value) loading.value = false
})

watch(user, (next) => {
  if (next) {
    loadToastShown = false
    loading.value = true
    load()
  } else {
    projects.value = []
    todos.value = []
    error.value = ''
    shareTarget.value = null
    loading.value = false
  }
})

// ---------- loading ----------

async function load() {
  try {
    const [projectList, todoList] = await Promise.all([
      api.listProjects(),
      api.listTodos(),
    ])
    projects.value = projectList
    todos.value = todoList
    error.value = ''
    if (!projects.value.some((p) => p.id === selectedProjectId.value)) {
      selectedProjectId.value = projects.value[0]?.id ?? null
      if (selectedProjectId.value)
        localStorage.setItem('selectedProject', String(selectedProjectId.value))
    }
    maybeShowAlertToast()
  } catch (e) {
    error.value = `Could not load tasks: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function run(action) {
  error.value = ''
  try {
    await action()
    await load()
    return true
  } catch (e) {
    error.value = e.message
    return false
  }
}

// ---------- todos ----------

const addTodo = (payload) =>
  run(() => api.createTodo({ ...payload, project_id: selectedProjectId.value }))

const toggleTodo = (todo) => run(() => api.updateTodo(todo.id, { completed: !todo.completed }))

const saveTodo = (todo, changes) => run(() => api.updateTodo(todo.id, changes))

const removeTodo = (todo) => run(() => api.deleteTodo(todo.id))

const clearCompleted = () => run(() => api.clearCompleted(selectedProjectId.value))

// ---------- projects ----------

function selectProject(id) {
  assignedOnly.value = false
  selectedProjectId.value = id
  filter.value = 'all'
  localStorage.setItem('selectedProject', String(id))
}

function selectAssigned() {
  assignedOnly.value = true
  filter.value = 'all'
}

async function createProject({ name, isShared }) {
  error.value = ''
  try {
    const project = await api.createProject({ name, is_shared: isShared })
    await load()
    selectProject(project.id)
    showToast(
      isShared ? `Shared list “${name}” created` : `List “${name}” created`,
      'success'
    )
  } catch (e) {
    error.value = e.message
  }
}

const renameProject = ({ id, name }) => run(() => api.updateProject(id, { name }))

async function removeProject(project) {
  const taskCount = todos.value.filter((t) => t.project_id === project.id).length
  const message = taskCount
    ? `Delete “${project.name}” and its ${taskCount} task${taskCount === 1 ? '' : 's'}?`
    : `Delete “${project.name}”?`
  if (!window.confirm(message)) return
  await run(() => api.deleteProject(project.id))
  if (!error.value) showToast(`List “${project.name}” deleted`, 'info')
}

// ---------- sharing ----------

function openShare(project) {
  shareTarget.value = project
}

function closeShare() {
  shareTarget.value = null
}

function onProjectUpdated(updated) {
  projects.value = projects.value.map((p) => (p.id === updated.id ? updated : p))
  if (shareTarget.value?.id === updated.id) shareTarget.value = updated
}

async function onLeftShared() {
  shareTarget.value = null
  showToast('You left the list', 'info')
  await load()
}

// ---------- drag & drop ----------

function onDragStart(todo, e) {
  dragging.value = todo
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(todo.id))
}

function onDragOver(todo, e) {
  if (!dragging.value || dragging.value.id === todo.id) return
  const rect = e.currentTarget.getBoundingClientRect()
  dropTarget.value = { id: todo.id, before: e.clientY < rect.top + rect.height / 2 }
}

function onDrop(todo) {
  if (dragging.value && dropTarget.value && dragging.value.id !== todo.id) {
    performReorder(dropTarget.value.id, dropTarget.value.before)
  }
  clearDragState()
}

function onDropList() {
  // Dropped on the list itself (not an item) → append to the end.
  if (!dragging.value) return
  const last = currentTodos.value[currentTodos.value.length - 1]
  if (last && last.id !== dragging.value.id) performReorder(last.id, false)
  clearDragState()
}

function onDragEnd() {
  clearDragState()
}

function clearDragState() {
  dragging.value = null
  dropTarget.value = null
}

function performReorder(targetId, before) {
  const dragged = dragging.value
  if (!dragged) return
  const list = [...currentTodos.value]
  const from = list.findIndex((t) => t.id === dragged.id)
  if (from === -1) return
  const [moved] = list.splice(from, 1)
  let to = list.findIndex((t) => t.id === targetId)
  if (to === -1) return
  if (!before) to += 1
  list.splice(to, 0, moved)

  // Optimistic local update so the reorder feels instant.
  const ids = list.map((t) => t.id)
  const indexOf = new Map(ids.map((id, i) => [id, i]))
  todos.value = todos.value.map((t) =>
    indexOf.has(t.id) ? { ...t, position: indexOf.get(t.id) } : t
  )

  api.reorderTodos(ids).catch((e) => {
    showToast(`Could not save order: ${e.message}`, 'danger')
    load()
  })
}

function indicatorFor(todo) {
  if (!dragging.value || !dropTarget.value) return null
  if (dropTarget.value.id !== todo.id || dropTarget.value.id === dragging.value.id)
    return null
  return dropTarget.value.before ? 'before' : 'after'
}

async function moveTodoToProject(projectId) {
  const dragged = dragging.value
  if (!dragged) return
  if (dragged.project_id === projectId) {
    clearDragState()
    return
  }
  const name = projectNameById.value.get(projectId)
  await run(() => api.updateTodo(dragged.id, { project_id: projectId }))
  if (!error.value) showToast(`Moved to “${name}”`, 'success')
  clearDragState()
}

// ---------- alerts ----------

function openAlert(todo) {
  if (todo.project_id) selectProject(todo.project_id)
  flashTodoId.value = todo.id
  setTimeout(() => {
    if (flashTodoId.value === todo.id) flashTodoId.value = null
  }, 1800)
}

function maybeShowAlertToast() {
  if (loadToastShown) return
  loadToastShown = true
  const overdue = alertsOverdue.value.length
  const today = alertsToday.value.length
  if (overdue)
    showToast(
      `${overdue} task${overdue === 1 ? '' : 's'} overdue — check the alerts 🔔`,
      'danger'
    )
  else if (today)
    showToast(`${today} task${today === 1 ? '' : 's'} due today`, 'warn')
}

// ---------- toast ----------

function showToast(msg, type = 'info') {
  toast.value = { id: Date.now(), msg, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = null), 4000)
}
</script>

<template>
  <div v-if="!authReady" class="boot-screen" aria-label="Loading">
    <div class="boot-spinner"></div>
  </div>

  <AuthView v-else-if="!user" :reset-token="resetToken" />

  <div v-else class="app-shell">
    <ProjectSidebar
      :projects="projects"
      :selected-id="selectedProjectId"
      :active-counts="projectActiveCounts"
      :current-user-id="user.id"
      :dragging-from-project-id="dragging?.project_id ?? null"
      :assigned-count="assignedCount"
      :assigned-selected="assignedOnly"
      @select="selectProject"
      @select-assigned="selectAssigned"
      @create="createProject"
      @rename="renameProject"
      @remove="removeProject"
      @share="openShare"
      @move-todo="moveTodoToProject"
    />

    <main class="app-card">
      <VerifyBanner />

      <header class="app-header">
        <div>
          <h1 class="app-title">
            {{ assignedOnly ? '📌 Assigned to me' : (currentProject?.name ?? 'Tasks') }}
            <span
              v-if="!assignedOnly && currentProject?.is_shared"
              class="shared-pill"
            >👥 shared</span>
          </h1>
          <p class="app-subtitle">{{ subtitle }}</p>
        </div>
        <div class="header-actions">
          <AlertsBell
            :overdue="alertsOverdue"
            :today="alertsToday"
            :soon="alertsSoon"
            @open="openAlert"
          />
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

      <TodoInput v-if="!assignedOnly" @add="addTodo" />
      <TodoFilters v-model="filter" :counts="counts" />

      <div v-if="loading" aria-label="Loading tasks">
        <div v-for="n in 3" :key="n" class="skeleton"></div>
      </div>

      <TransitionGroup
        v-else-if="visible.length"
        name="list"
        tag="ul"
        class="todo-list"
        @dragover.prevent
        @drop="onDropList"
      >
        <TodoItem
          v-for="todo in visible"
          :key="todo.id"
          :todo="todo"
          :dragging="dragging?.id === todo.id"
          :drop-indicator="indicatorFor(todo)"
          :flash="flashTodoId === todo.id"
          :members="membersByProject.get(todo.project_id) || []"
          :shared="isSharedList(todo)"
          :can-assign-others="canAssignOthers(todo)"
          :current-user-id="user.id"
          :sortable="!assignedOnly"
          :show-project="assignedOnly"
          :project-name="projectNameById.get(todo.project_id) || ''"
          :save-handler="(changes) => saveTodo(todo, changes)"
          @toggle="toggleTodo(todo)"
          @save="(changes) => saveTodo(todo, changes)"
          @remove="removeTodo(todo)"
          @dragstart="onDragStart"
          @dragover="onDragOver"
          @drop="onDrop"
          @dragend="onDragEnd"
        />
      </TransitionGroup>

      <div v-else class="empty-state">
        <span class="empty-icon">
          {{ filter === 'done' ? '🗂️' : filter === 'late' ? '⏰' : '🌱' }}
        </span>
        <p>{{ emptyMessage }}</p>
      </div>

      <footer v-if="!assignedOnly && currentTodos.length" class="list-footer">
        <span>
          {{ counts.done }} of {{ counts.all }} completed
          <template v-if="counts.done === counts.all">🎉</template>
        </span>
        <button class="clear-btn" :disabled="counts.done === 0" @click="clearCompleted">
          Clear completed
        </button>
      </footer>
    </main>

    <ShareDialog
      v-if="shareTarget"
      :project="shareTarget"
      :current-user-id="user.id"
      @close="closeShare"
      @updated="onProjectUpdated"
      @left="onLeftShared"
      @notify="({ msg, type }) => showToast(msg, type)"
    />

    <Transition name="toast">
      <div v-if="toast" class="toast" :class="toast.type" role="status">
        {{ toast.msg }}
      </div>
    </Transition>
  </div>

  <Transition name="toast">
    <div
      v-if="urlNotice"
      class="url-notice"
      role="status"
      title="Dismiss"
      @click="urlNotice = ''"
    >
      {{ urlNotice }}
    </div>
  </Transition>
</template>
