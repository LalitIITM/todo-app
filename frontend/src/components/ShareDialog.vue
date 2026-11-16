<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'

const props = defineProps({
  project: { type: Object, required: true },
  currentUserId: { type: Number, default: null },
})

const emit = defineEmits(['close', 'updated', 'left', 'notify'])

const inviteEmail = ref('')
const busy = ref(false)
const error = ref('')

const isOwner = computed(() => props.project.owner_id === props.currentUserId)
const members = computed(() => props.project.members || [])

function notify(msg, type = 'info') {
  emit('notify', { msg, type })
}

async function toggleSharing() {
  busy.value = true
  error.value = ''
  try {
    const updated = await api.updateProject(props.project.id, {
      is_shared: !props.project.is_shared,
    })
    emit('updated', updated)
    notify(updated.is_shared ? 'Sharing turned on' : 'Sharing turned off')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function invite() {
  const email = inviteEmail.value.trim()
  if (!email) return
  busy.value = true
  error.value = ''
  try {
    const updated = await api.addMember(props.project.id, email)
    inviteEmail.value = ''
    emit('updated', updated)
    notify(`Shared with ${email}`, 'success')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove(userId) {
  busy.value = true
  error.value = ''
  try {
    await api.removeMember(props.project.id, userId)
    if (userId === props.currentUserId) {
      emit('left')
      return
    }
    emit('updated', {
      ...props.project,
      members: members.value.filter((m) => m.user_id !== userId),
    })
    notify('Member removed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true">
      <header class="modal-head">
        <h2>Share “{{ project.name }}”</h2>
        <button class="icon-btn" title="Close" @click="emit('close')">✕</button>
      </header>

      <div v-if="error" class="error-banner" role="alert">{{ error }}</div>

      <label class="share-toggle">
        <span>
          <strong>Shared list</strong>
          <small>
            {{
              project.is_shared
                ? 'Everyone below can see and edit these tasks.'
                : 'Only you can see this list.'
            }}
          </small>
        </span>
        <input
          type="checkbox"
          :checked="project.is_shared"
          :disabled="!isOwner || busy"
          @change="toggleSharing"
        />
      </label>

      <template v-if="project.is_shared">
        <div class="share-section-title">Members</div>

        <ul class="member-list">
          <li class="member-row">
            <span class="member-avatar owner">
              {{ (project.owner_id === currentUserId ? 'You' : 'O').charAt(0) }}
            </span>
            <span class="member-name">
              {{ project.owner_id === currentUserId ? 'You' : 'Owner' }}
              <em>· owner</em>
            </span>
          </li>
          <li v-for="m in members" :key="m.user_id" class="member-row">
            <span class="member-avatar">{{ (m.name || m.email).charAt(0).toUpperCase() }}</span>
            <span class="member-name">
              {{ m.name || m.email }}
              <em v-if="m.user_id === currentUserId">· you</em>
            </span>
            <button
              v-if="isOwner || m.user_id === currentUserId"
              class="member-remove"
              :title="m.user_id === currentUserId ? 'Leave this list' : 'Remove member'"
              :disabled="busy"
              @click="remove(m.user_id)"
            >
              {{ m.user_id === currentUserId ? 'Leave' : '✕' }}
            </button>
          </li>
        </ul>

        <form v-if="isOwner" class="invite-row" @submit.prevent="invite">
          <input
            v-model="inviteEmail"
            type="email"
            class="invite-input"
            placeholder="teammate@example.com"
            aria-label="Invite by email"
          />
          <button class="mini-btn primary" type="submit" :disabled="busy || !inviteEmail.trim()">
            Invite
          </button>
        </form>

        <p class="share-hint">
          They need a Tasks account first — ask them to sign up with that email, then invite them.
        </p>
      </template>
    </div>
  </div>
</template>
