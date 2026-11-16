<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  projects: { type: Array, required: true },
  selectedId: { type: Number, default: null },
  activeCounts: { type: Object, required: true },
  currentUserId: { type: Number, default: null },
  // Project id of the todo being dragged (null when not dragging)
  draggingFromProjectId: { type: Number, default: null },
  // "Assigned to me" cross-list view.
  assignedCount: { type: Number, default: 0 },
  assignedSelected: { type: Boolean, default: false },
  // Cross-list stats view.
  statsSelected: { type: Boolean, default: false },
})

const emit = defineEmits([
  'select',
  'select-assigned',
  'select-stats',
  'create',
  'rename',
  'remove',
  'move-todo',
  'share',
])

const personalLists = computed(() => props.projects.filter((p) => !p.is_shared))
const sharedLists = computed(() => props.projects.filter((p) => p.is_shared))

const creating = ref(false)
const newName = ref('')
const newShared = ref(false)
const newInputEl = ref(null)
const renamingId = ref(null)
const renameDraft = ref('')
const renameEl = ref(null)
const dropTargetId = ref(null)

function isOwner(project) {
  return project.owner_id === props.currentUserId
}

async function startCreating(shared) {
  creating.value = true
  newShared.value = shared
  await nextTick()
  firstEl(newInputEl.value)?.focus()
}

function commitCreate() {
  if (!creating.value) return
  const name = newName.value.trim()
  creating.value = false
  newName.value = ''
  if (name) emit('create', { name, isShared: newShared.value })
}

function cancelCreate() {
  creating.value = false
  newName.value = ''
}

function firstEl(value) {
  return Array.isArray(value) ? value[0] : value
}

async function startRename(project) {
  if (!isOwner(project)) return
  renamingId.value = project.id
  renameDraft.value = project.name
  await nextTick()
  firstEl(renameEl.value)?.focus()
}

function commitRename() {
  const id = renamingId.value
  if (id === null) return
  const name = renameDraft.value.trim()
  renamingId.value = null
  const project = props.projects.find((p) => p.id === id)
  if (name && project && name !== project.name) emit('rename', { id, name })
}

// ---- drop-to-move: dragging a task onto a list moves it there ----
function onDragOver(project, e) {
  if (props.draggingFromProjectId === null) return
  if (props.draggingFromProjectId === project.id) return // same list
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  dropTargetId.value = project.id
}

function onDragLeave(project, e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    if (dropTargetId.value === project.id) dropTargetId.value = null
  }
}

function onDrop(project) {
  if (dropTargetId.value !== project.id) return
  dropTargetId.value = null
  emit('move-todo', project.id)
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-label">Lists</div>

    <!-- Cross-list view: everything assigned to the signed-in user -->
    <ul class="project-list assigned-list">
      <li
        class="project-item assigned-item"
        :class="{ selected: assignedSelected }"
        title="Tasks assigned to you across every list"
        @click="emit('select-assigned')"
      >
        <span class="assigned-icon">📌</span>
        <span class="project-name">Assigned to me</span>
        <span v-if="assignedCount" class="project-count">{{ assignedCount }}</span>
      </li>
      <li
        class="project-item assigned-item"
        :class="{ selected: statsSelected }"
        title="Your task accomplishments at a glance"
        @click="emit('select-stats')"
      >
        <span class="assigned-icon">📊</span>
        <span class="project-name">Stats</span>
      </li>
    </ul>

    <!-- Personal (private) lists -->
    <div class="sidebar-section">
      <div class="sidebar-section-title">
        <span>Personal</span>
        <span class="sidebar-section-note">only you</span>
      </div>

      <ul class="project-list">
        <li
          v-for="p in personalLists"
          :key="p.id"
          class="project-item"
          :class="{ selected: p.id === selectedId, 'drop-target': dropTargetId === p.id }"
          @click="emit('select', p.id)"
          @dblclick="startRename(p)"
          @dragover="onDragOver(p, $event)"
          @dragleave="onDragLeave(p, $event)"
          @drop.prevent="onDrop(p)"
        >
          <span class="project-dot" :style="{ background: p.color }"></span>

          <input
            v-if="renamingId === p.id"
            ref="renameEl"
            v-model="renameDraft"
            class="project-rename"
            maxlength="100"
            @click.stop
            @keyup.enter="commitRename"
            @keyup.esc="renamingId = null"
            @blur="commitRename"
          />
          <span v-else class="project-name" :title="isOwner(p) ? 'Double-click to rename' : p.name">
            {{ p.name }}
          </span>

          <span v-if="activeCounts[p.id]" class="project-count">{{ activeCounts[p.id] }}</span>

          <button
            class="project-action"
            title="Share this list"
            @click.stop="emit('share', p)"
          >
            👥
          </button>

          <button
            v-if="isOwner(p)"
            class="project-action danger"
            title="Delete this list (and its tasks)"
            @click.stop="emit('remove', p)"
          >
            ✕
          </button>
        </li>

        <li v-if="!personalLists.length && !creating" class="project-empty">No personal lists</li>
      </ul>
    </div>

    <!-- Shared lists -->
    <div class="sidebar-section">
      <div class="sidebar-section-title">
        <span>Shared</span>
        <span class="sidebar-section-note">with others</span>
      </div>

      <ul class="project-list">
        <li
          v-for="p in sharedLists"
          :key="p.id"
          class="project-item"
          :class="{ selected: p.id === selectedId, 'drop-target': dropTargetId === p.id }"
          @click="emit('select', p.id)"
          @dblclick="startRename(p)"
          @dragover="onDragOver(p, $event)"
          @dragleave="onDragLeave(p, $event)"
          @drop.prevent="onDrop(p)"
        >
          <span class="project-dot" :style="{ background: p.color }"></span>

          <input
            v-if="renamingId === p.id"
            ref="renameEl"
            v-model="renameDraft"
            class="project-rename"
            maxlength="100"
            @click.stop
            @keyup.enter="commitRename"
            @keyup.esc="renamingId = null"
            @blur="commitRename"
          />
          <span v-else class="project-name" :title="isOwner(p) ? 'Double-click to rename' : p.name">
            {{ p.name }}
          </span>

          <span class="project-members" :title="`${(p.members?.length ?? 0) + 1} people`">
            👥 {{ (p.members?.length ?? 0) + 1 }}
          </span>

          <span v-if="activeCounts[p.id]" class="project-count">{{ activeCounts[p.id] }}</span>

          <button
            class="project-action"
            title="Manage sharing"
            @click.stop="emit('share', p)"
          >
            ⚙️
          </button>

          <button
            v-if="isOwner(p)"
            class="project-action danger"
            title="Delete this list (and its tasks)"
            @click.stop="emit('remove', p)"
          >
            ✕
          </button>
        </li>

        <li v-if="!sharedLists.length && !creating" class="project-empty">
          Nothing shared yet
        </li>
      </ul>
    </div>

    <!-- Create -->
    <form v-if="creating" class="project-create" @submit.prevent="commitCreate">
      <input
        ref="newInputEl"
        v-model="newName"
        class="project-rename"
        placeholder="List name"
        maxlength="100"
        @keyup.esc="cancelCreate"
        @blur="commitCreate"
      />
      <div class="seg">
        <button
          type="button"
          class="seg-btn"
          :class="{ active: !newShared }"
          @mousedown.prevent
          @click="newShared = false"
        >
          Personal
        </button>
        <button
          type="button"
          class="seg-btn"
          :class="{ active: newShared }"
          @mousedown.prevent
          @click="newShared = true"
        >
          Shared
        </button>
      </div>
    </form>

    <div v-else class="project-add-row">
      <button class="project-add" type="button" @click="startCreating(false)">
        ＋ Personal
      </button>
      <button class="project-add" type="button" @click="startCreating(true)">
        ＋ Shared
      </button>
    </div>
  </aside>
</template>
