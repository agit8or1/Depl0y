<template>
  <div class="users-page">
    <div class="card">
      <div class="card-header">
        <h3>User Management</h3>
        <button @click="showCreateModal = true" class="btn btn-primary">+ Add User</button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="users.length === 0" class="text-center text-muted">
        <p>No users found.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>2FA</th>
              <th>Status</th>
              <th>Last Login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td><strong>{{ user.username }}</strong></td>
              <td>{{ user.email }}</td>
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
                  {{ user.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="text-sm">{{ formatDate(user.last_login) }}</td>
              <td>
                <div class="flex gap-1">
                  <button @click="editUser(user)" class="btn btn-outline btn-sm">
                    Edit
                  </button>
                  <button @click="deleteUser(user.id)" class="btn btn-danger btn-sm">
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create User Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Create New User</h3>
          <button @click="showCreateModal = false" class="modal-close">×</button>
        </div>

        <form @submit.prevent="createUser" class="modal-body">
          <div class="form-group">
            <label for="username" class="form-label">Username *</label>
            <input
              v-model="createForm.username"
              type="text"
              id="username"
              class="form-control"
              required
            />
          </div>

          <div class="form-group">
            <label for="email" class="form-label">Email *</label>
            <input
              v-model="createForm.email"
              type="email"
              id="email"
              class="form-control"
              required
            />
          </div>

          <div class="form-group">
            <label for="password" class="form-label">Password *</label>
            <input
              v-model="createForm.password"
              type="password"
              id="password"
              class="form-control"
              required
              minlength="8"
            />
          </div>

          <div class="form-group">
            <label for="role" class="form-label">Role *</label>
            <select v-model="createForm.role" id="role" class="form-control" required>
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div class="modal-footer">
            <button type="button" @click="showCreateModal = false" class="btn btn-outline">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? 'Creating...' : 'Create User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Edit User Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Edit User</h3>
          <button @click="showEditModal = false" class="modal-close">×</button>
        </div>

        <form @submit.prevent="updateUser" class="modal-body">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input
              :value="editForm.username"
              type="text"
              class="form-control"
              disabled
            />
          </div>

          <div class="form-group">
            <label for="edit-email" class="form-label">Email *</label>
            <input
              v-model="editForm.email"
              type="email"
              id="edit-email"
              class="form-control"
              required
            />
          </div>

          <div class="form-group">
            <label for="edit-role" class="form-label">Role *</label>
            <select v-model="editForm.role" id="edit-role" class="form-control" required>
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">
              <input v-model="editForm.is_active" type="checkbox" />
              Active
            </label>
          </div>

          <div class="modal-footer">
            <button type="button" @click="showEditModal = false" class="btn btn-outline">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary" :disabled="updating">
              {{ updating ? 'Updating...' : 'Update User' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
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
    const showCreateModal = ref(false)
    const showEditModal = ref(false)

    const createForm = ref({
      username: '',
      email: '',
      password: '',
      role: 'viewer'
    })

    const editForm = ref({
      id: null,
      username: '',
      email: '',
      role: '',
      is_active: true
    })

    const fetchUsers = async () => {
      loading.value = true
      try {
        const response = await api.users.list()
        users.value = response.data
      } catch (error) {
        console.error('Failed to fetch users:', error)
        toast.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const createUser = async () => {
      creating.value = true
      try {
        await api.users.create(createForm.value)
        toast.success('User created successfully')
        showCreateModal.value = false
        createForm.value = {
          username: '',
          email: '',
          password: '',
          role: 'viewer'
        }
        await fetchUsers()
      } catch (error) {
        console.error('Failed to create user:', error)
      } finally {
        creating.value = false
      }
    }

    const editUser = (user) => {
      editForm.value = {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        is_active: user.is_active
      }
      showEditModal.value = true
    }

    const updateUser = async () => {
      updating.value = true
      try {
        await api.users.update(editForm.value.id, {
          email: editForm.value.email,
          role: editForm.value.role,
          is_active: editForm.value.is_active
        })
        toast.success('User updated successfully')
        showEditModal.value = false
        await fetchUsers()
      } catch (error) {
        console.error('Failed to update user:', error)
      } finally {
        updating.value = false
      }
    }

    const deleteUser = async (userId) => {
      if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
        return
      }

      try {
        await api.users.delete(userId)
        toast.success('User deleted successfully')
        await fetchUsers()
      } catch (error) {
        console.error('Failed to delete user:', error)
      }
    }

    const formatRole = (role) => {
      const roleMap = {
        admin: 'Admin',
        operator: 'Operator',
        viewer: 'Viewer'
      }
      return roleMap[role] || role
    }

    const getRoleBadgeClass = (role) => {
      const classMap = {
        admin: 'badge-danger',
        operator: 'badge-warning',
        viewer: 'badge-info'
      }
      return classMap[role] || 'badge-secondary'
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return 'Never'
      const date = new Date(dateStr)
      return date.toLocaleString()
    }

    onMounted(() => {
      fetchUsers()
    })

    return {
      users,
      loading,
      creating,
      updating,
      showCreateModal,
      showEditModal,
      createForm,
      editForm,
      createUser,
      editUser,
      updateUser,
      deleteUser,
      formatRole,
      getRoleBadgeClass,
      formatDate
    }
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
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

.modal-close:hover {
  color: var(--text-primary);
}

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
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-control {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  background-color: var(--background);
  color: var(--text-primary);
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}
</style>
