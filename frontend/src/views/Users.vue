<template>
  <div class="users-page">
    <div class="page-header">
      <div>
        <h2>User Management</h2>
        <p class="text-muted">Create, edit, and manage platform user accounts</p>
      </div>
      <button @click="openCreateModal" class="btn btn-primary">+ Add User</button>
    </div>

    <!-- Search + Filter bar -->
    <div class="toolbar card mb-2">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control search-input"
        placeholder="Search by username or email…"
      />
      <div class="filter-buttons">
        <button
          v-for="r in ['all', 'admin', 'operator', 'viewer']"
          :key="r"
          :class="['btn btn-sm', roleFilter === r ? 'btn-primary' : 'btn-outline']"
          @click="roleFilter = r"
        >
          {{ r === 'all' ? 'All Roles' : formatRole(r) }}
        </button>
      </div>
      <span class="text-muted text-sm">{{ filteredUsers.length }} user{{ filteredUsers.length !== 1 ? 's' : '' }}</span>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-else-if="filteredUsers.length === 0" class="card empty-state">
      <p>No users found.</p>
    </div>

    <div v-else class="card table-container">
      <table class="table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Email</th>
            <th>Role</th>
            <th>2FA</th>
            <th>Status</th>
            <th>Last Login</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in filteredUsers" :key="user.id" :class="{ 'row-disabled': !user.is_active }">
            <td>
              <strong>{{ user.username }}</strong>
            </td>
            <td class="text-sm text-muted">{{ user.email }}</td>
            <td>
              <span :class="['badge', getRoleBadgeClass(user.role)]">
                {{ formatRole(user.role) }}
              </span>
            </td>
            <td>
              <span :class="['badge', user.totp_enabled ? 'badge-success' : 'badge-secondary']">
                {{ user.totp_enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </td>
            <td>
              <span :class="['badge', user.is_active ? 'badge-success' : 'badge-danger']">
                {{ user.is_active ? 'Active' : 'Disabled' }}
              </span>
            </td>
            <td class="text-sm text-muted">{{ formatDate(user.last_login) }}</td>
            <td class="text-sm text-muted">{{ formatDateShort(user.created_at) }}</td>
            <td>
              <div class="action-btns">
                <button @click="openEditModal(user)" class="btn btn-outline btn-sm" title="Edit user">
                  Edit
                </button>
                <button
                  @click="toggleStatus(user)"
                  :class="['btn btn-sm', user.is_active ? 'btn-warning' : 'btn-outline']"
                  :title="user.is_active ? 'Disable user' : 'Enable user'"
                >
                  {{ user.is_active ? 'Disable' : 'Enable' }}
                </button>
                <button
                  @click="openResetPasswordModal(user)"
                  class="btn btn-outline btn-sm"
                  title="Reset password"
                >
                  Reset Pwd
                </button>
                <button
                  v-if="user.totp_enabled"
                  @click="disableTotp(user)"
                  class="btn btn-outline btn-sm"
                  title="Force-disable 2FA (account recovery)"
                >
                  Disable 2FA
                </button>
                <button
                  @click="confirmDelete(user)"
                  class="btn btn-danger btn-sm"
                  title="Delete user"
                >
                  Delete
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Create User Modal ──────────────────────────────── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Create New User</h3>
          <button @click="showCreateModal = false" class="modal-close">×</button>
        </div>
        <form @submit.prevent="createUser" class="modal-body">
          <div class="form-group">
            <label class="form-label">Username *</label>
            <input v-model="createForm.username" type="text" class="form-control" required autocomplete="off" />
          </div>
          <div class="form-group">
            <label class="form-label">Email *</label>
            <input v-model="createForm.email" type="email" class="form-control" required autocomplete="off" />
          </div>
          <div class="form-group">
            <label class="form-label">Password *</label>
            <div class="input-with-btn">
              <input
                v-model="createForm.password"
                :type="showCreatePassword ? 'text' : 'password'"
                class="form-control"
                required
                minlength="8"
                autocomplete="new-password"
              />
              <button type="button" @click="showCreatePassword = !showCreatePassword" class="btn btn-outline btn-sm">
                {{ showCreatePassword ? 'Hide' : 'Show' }}
              </button>
            </div>
            <p class="form-hint">Minimum 8 characters</p>
          </div>
          <div class="form-group">
            <label class="form-label">Role *</label>
            <select v-model="createForm.role" class="form-control" required>
              <option value="admin">Admin — full access</option>
              <option value="operator">Operator — manage VMs, no user admin</option>
              <option value="viewer">Viewer — read-only</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" @click="showCreateModal = false" class="btn btn-outline">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? 'Creating…' : 'Create User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Edit User Modal ────────────────────────────────── -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Edit User — {{ editForm.username }}</h3>
          <button @click="showEditModal = false" class="modal-close">×</button>
        </div>
        <form @submit.prevent="updateUser" class="modal-body">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input :value="editForm.username" type="text" class="form-control" disabled />
          </div>
          <div class="form-group">
            <label class="form-label">Email *</label>
            <input v-model="editForm.email" type="email" class="form-control" required />
          </div>
          <div class="form-group">
            <label class="form-label">Role *</label>
            <select v-model="editForm.role" class="form-control" required>
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          <div class="form-group">
            <label class="toggle-label">
              <input v-model="editForm.is_active" type="checkbox" />
              <span>Account Active</span>
            </label>
          </div>
          <div class="modal-footer">
            <button type="button" @click="showEditModal = false" class="btn btn-outline">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="updating">
              {{ updating ? 'Saving…' : 'Save Changes' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Reset Password Modal ───────────────────────────── -->
    <div v-if="showResetModal" class="modal-overlay" @click.self="closeResetModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Reset Password — {{ resetUser?.username }}</h3>
          <button @click="closeResetModal" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="!tempPassword">
            <p class="text-muted mb-1">
              This will generate a new temporary password for <strong>{{ resetUser?.username }}</strong>
              and invalidate all their active sessions.
            </p>
            <p class="text-muted">The temporary password will be shown <strong>once only</strong> — make sure to copy it.</p>
          </div>

          <div v-else class="temp-password-box">
            <p class="form-label mb-1">Temporary Password (copy now):</p>
            <div class="password-display">
              <code>{{ tempPassword }}</code>
              <button @click="copyTempPassword" class="btn btn-outline btn-sm">
                {{ copied ? 'Copied!' : 'Copy' }}
              </button>
            </div>
            <p class="text-muted text-sm mt-1">This password will NOT be shown again. Share it securely with the user.</p>
          </div>

          <div class="modal-footer">
            <button v-if="!tempPassword" type="button" @click="closeResetModal" class="btn btn-outline">Cancel</button>
            <button v-if="!tempPassword" @click="doResetPassword" class="btn btn-danger" :disabled="resetting">
              {{ resetting ? 'Resetting…' : 'Reset Password' }}
            </button>
            <button v-else @click="closeResetModal" class="btn btn-primary">Done</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Delete Confirm Modal ───────────────────────────── -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="showDeleteModal = false">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h3>Delete User</h3>
          <button @click="showDeleteModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to permanently delete <strong>{{ deleteTarget?.username }}</strong>?</p>
          <p class="text-muted text-sm">This action cannot be undone.</p>
          <div class="modal-footer">
            <button @click="showDeleteModal = false" class="btn btn-outline">Cancel</button>
            <button @click="doDelete" class="btn btn-danger" :disabled="deleting">
              {{ deleting ? 'Deleting…' : 'Delete User' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Users',
  setup() {
    const toast = useToast()
    const users = ref([])
    const loading = ref(false)
    const creating = ref(false)
    const updating = ref(false)
    const resetting = ref(false)
    const deleting = ref(false)

    const searchQuery = ref('')
    const roleFilter = ref('all')

    const showCreateModal = ref(false)
    const showEditModal = ref(false)
    const showResetModal = ref(false)
    const showDeleteModal = ref(false)
    const showCreatePassword = ref(false)

    const resetUser = ref(null)
    const tempPassword = ref('')
    const copied = ref(false)
    const deleteTarget = ref(null)

    const createForm = ref({ username: '', email: '', password: '', role: 'viewer' })
    const editForm = ref({ id: null, username: '', email: '', role: '', is_active: true })

    const filteredUsers = computed(() => {
      let list = users.value
      if (roleFilter.value !== 'all') {
        list = list.filter(u => u.role === roleFilter.value)
      }
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase().trim()
        list = list.filter(u =>
          u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
        )
      }
      return list
    })

    const fetchUsers = async () => {
      loading.value = true
      try {
        const response = await api.users.list()
        users.value = response.data
      } catch (error) {
        toast.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const openCreateModal = () => {
      createForm.value = { username: '', email: '', password: '', role: 'viewer' }
      showCreatePassword.value = false
      showCreateModal.value = true
    }

    const createUser = async () => {
      creating.value = true
      try {
        await api.users.create(createForm.value)
        toast.success('User created successfully')
        showCreateModal.value = false
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || 'Failed to create user'
        toast.error(msg)
      } finally {
        creating.value = false
      }
    }

    const openEditModal = (user) => {
      editForm.value = {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        is_active: user.is_active,
      }
      showEditModal.value = true
    }

    const updateUser = async () => {
      updating.value = true
      try {
        await api.users.patch(editForm.value.id, {
          email: editForm.value.email,
          role: editForm.value.role,
          is_active: editForm.value.is_active,
        })
        toast.success('User updated')
        showEditModal.value = false
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || 'Failed to update user'
        toast.error(msg)
      } finally {
        updating.value = false
      }
    }

    const toggleStatus = async (user) => {
      const action = user.is_active ? 'disable' : 'enable'
      if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} ${user.username}?`)) return
      try {
        await api.users.setStatus(user.id, !user.is_active)
        toast.success(`User ${action}d`)
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || `Failed to ${action} user`
        toast.error(msg)
      }
    }

    const openResetPasswordModal = (user) => {
      resetUser.value = user
      tempPassword.value = ''
      copied.value = false
      showResetModal.value = true
    }

    const closeResetModal = () => {
      showResetModal.value = false
      resetUser.value = null
      tempPassword.value = ''
      copied.value = false
    }

    const doResetPassword = async () => {
      resetting.value = true
      try {
        const response = await api.users.resetPassword(resetUser.value.id)
        tempPassword.value = response.data.temporary_password
        toast.success('Password reset successfully')
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || 'Failed to reset password'
        toast.error(msg)
      } finally {
        resetting.value = false
      }
    }

    const copyTempPassword = async () => {
      try {
        await navigator.clipboard.writeText(tempPassword.value)
        copied.value = true
        setTimeout(() => { copied.value = false }, 2000)
      } catch {
        toast.error('Could not copy to clipboard')
      }
    }

    const disableTotp = async (user) => {
      if (!confirm(`Force-disable 2FA for ${user.username}? Use this only for account recovery.`)) return
      try {
        await api.users.disableTotp(user.id)
        toast.success(`2FA disabled for ${user.username}`)
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || 'Failed to disable 2FA'
        toast.error(msg)
      }
    }

    const confirmDelete = (user) => {
      deleteTarget.value = user
      showDeleteModal.value = true
    }

    const doDelete = async () => {
      deleting.value = true
      try {
        await api.users.delete(deleteTarget.value.id)
        toast.success('User deleted')
        showDeleteModal.value = false
        await fetchUsers()
      } catch (error) {
        const msg = error.response?.data?.detail || 'Failed to delete user'
        toast.error(msg)
      } finally {
        deleting.value = false
      }
    }

    const formatRole = (role) => ({ admin: 'Admin', operator: 'Operator', viewer: 'Viewer' }[role] || role)

    const getRoleBadgeClass = (role) => ({
      admin: 'badge-danger',
      operator: 'badge-warning',
      viewer: 'badge-info',
    }[role] || 'badge-secondary')

    const formatDate = (d) => {
      if (!d) return 'Never'
      return new Date(d).toLocaleString()
    }

    const formatDateShort = (d) => {
      if (!d) return '—'
      return new Date(d).toLocaleDateString()
    }

    onMounted(fetchUsers)

    return {
      users, loading, creating, updating, resetting, deleting,
      searchQuery, roleFilter, filteredUsers,
      showCreateModal, showEditModal, showResetModal, showDeleteModal,
      showCreatePassword,
      createForm, editForm,
      resetUser, tempPassword, copied,
      deleteTarget,
      openCreateModal, createUser,
      openEditModal, updateUser,
      toggleStatus,
      openResetPasswordModal, closeResetModal, doResetPassword, copyTempPassword,
      disableTotp,
      confirmDelete, doDelete,
      formatRole, getRoleBadgeClass, formatDate, formatDateShort,
    }
  }
}
</script>

<style scoped>
.users-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  flex-wrap: wrap;
}

.search-input {
  width: 260px;
  flex-shrink: 0;
}

.filter-buttons {
  display: flex;
  gap: 0.35rem;
}

.action-btns {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.row-disabled td {
  opacity: 0.55;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--card-bg);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-sm {
  max-width: 360px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.1rem;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-close:hover { color: var(--text-primary); }

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  margin-bottom: 0.4rem;
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background: var(--background);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(var(--primary-rgb, 59, 130, 246), 0.15);
}

.form-control:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-hint {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  margin-bottom: 0;
}

.input-with-btn {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.input-with-btn .form-control {
  flex: 1;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary);
}

/* Temp password display */
.temp-password-box {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 1rem;
}

.password-display {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.6rem 0.75rem;
  margin-top: 0.5rem;
}

.password-display code {
  flex: 1;
  font-size: 1rem;
  letter-spacing: 0.05em;
  color: var(--text-primary);
  word-break: break-all;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
}

.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.5rem; }
</style>
