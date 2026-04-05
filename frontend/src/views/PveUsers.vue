<template>
  <div class="pve-users-page">
    <div class="page-header mb-2">
      <h2>Proxmox Users</h2>
      <p class="text-muted">Manage users on Proxmox host {{ hostId }}</p>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Users</h3>
        <button @click="showAddModal = true" class="btn btn-primary">+ Add User</button>
      </div>

      <div v-if="loading" class="loading-spinner"></div>

      <div v-else-if="users.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No users found.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Realm</th>
              <th>Groups</th>
              <th>Tokens</th>
              <th>Expires</th>
              <th>Enabled</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.userid">
              <td><strong>{{ user.userid }}</strong></td>
              <td>{{ [user.firstname, user.lastname].filter(Boolean).join(' ') || '—' }}</td>
              <td>{{ user.email || '—' }}</td>
              <td>
                <span class="badge badge-info">{{ extractRealm(user.userid) }}</span>
              </td>
              <td class="text-sm">{{ user.groups || '—' }}</td>
              <td>
                <button @click="openTokens(user)" class="btn btn-outline btn-sm">
                  Tokens {{ user.tokens ? `(${Object.keys(user.tokens).length})` : '(0)' }}
                </button>
              </td>
              <td class="text-sm">
                <span v-if="user.expire && user.expire > 0">{{ formatExpiry(user.expire) }}</span>
                <span v-else class="text-muted">Never</span>
              </td>
              <td>
                <span :class="['badge', user.enable !== false && user.enable !== 0 ? 'badge-success' : 'badge-danger']">
                  {{ user.enable !== false && user.enable !== 0 ? 'Enabled' : 'Disabled' }}
                </span>
              </td>
              <td>
                <div class="flex gap-1">
                  <button @click="deleteUser(user.userid)" class="btn btn-danger btn-sm">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add User Modal -->
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Proxmox User</h3>
          <button @click="showAddModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addUser" class="modal-body">
          <div class="form-group">
            <label class="form-label">User ID <span class="text-muted text-sm">(user@realm format)</span></label>
            <input v-model="newUser.userid" class="form-control" placeholder="user@pam or user@pve" required />
          </div>

          <div class="form-group">
            <label class="form-label">Password</label>
            <input v-model="newUser.password" type="password" autocomplete="new-password" class="form-control" required />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">First Name</label>
              <input v-model="newUser.firstname" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Last Name</label>
              <input v-model="newUser.lastname" class="form-control" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Email</label>
            <input v-model="newUser.email" type="email" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">
              <input type="checkbox" v-model="newUser.enable" :true-value="1" :false-value="0" />
              Enabled
            </label>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Adding...' : 'Add User' }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Tokens Sub-Modal -->
    <div v-if="showTokensModal" class="modal" @click="showTokensModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Tokens — {{ selectedUser?.userid }}</h3>
          <button @click="showTokensModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <!-- Existing Tokens -->
          <h4 style="margin-bottom: 1rem;">Existing Tokens</h4>
          <div v-if="loadingTokens" class="loading-spinner"></div>
          <div v-else-if="tokens.length === 0" class="text-muted text-sm" style="margin-bottom: 1.5rem;">
            No tokens found for this user.
          </div>
          <div v-else class="table-container" style="margin-bottom: 1.5rem;">
            <table class="table">
              <thead>
                <tr>
                  <th>Token ID</th>
                  <th>Comment</th>
                  <th>Expires</th>
                  <th>Priv Sep</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="token in tokens" :key="token.tokenid">
                  <td><code>{{ token.tokenid }}</code></td>
                  <td>{{ token.comment || '—' }}</td>
                  <td class="text-sm">
                    <span v-if="token.expire && token.expire > 0">{{ formatExpiry(token.expire) }}</span>
                    <span v-else class="text-muted">Never</span>
                  </td>
                  <td>
                    <span :class="['badge', token.privsep !== 0 ? 'badge-warning' : 'badge-success']">
                      {{ token.privsep !== 0 ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <button @click="revokeToken(token.tokenid)" class="btn btn-danger btn-sm">Revoke</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Create New Token -->
          <h4 style="margin-bottom: 1rem;">Create New Token</h4>
          <form @submit.prevent="createToken">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Token Name</label>
                <input v-model="newToken.tokenid" class="form-control" placeholder="mytoken" required />
              </div>
              <div class="form-group">
                <label class="form-label">Comment</label>
                <input v-model="newToken.comment" class="form-control" placeholder="Optional description" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="newToken.privsep" :true-value="1" :false-value="0" />
                Privilege Separation (restrict to user permissions)
              </label>
            </div>
            <button type="submit" class="btn btn-primary" :disabled="savingToken">
              {{ savingToken ? 'Creating...' : 'Create Token' }}
            </button>
          </form>

          <!-- Token Value Display -->
          <div v-if="createdTokenValue" class="token-value-box">
            <h5>Token Created Successfully!</h5>
            <p class="text-sm text-muted">Copy this token value — it will not be shown again:</p>
            <code class="token-value">{{ createdTokenValue }}</code>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'PveUsers',
  setup() {
    const route = useRoute()
    const toast = useToast()
    const hostId = ref(route.params.hostId)
    const users = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)
    const showTokensModal = ref(false)
    const selectedUser = ref(null)
    const tokens = ref([])
    const loadingTokens = ref(false)
    const savingToken = ref(false)
    const createdTokenValue = ref(null)

    const newUser = ref({
      userid: '',
      password: '',
      firstname: '',
      lastname: '',
      email: '',
      enable: 1
    })

    const newToken = ref({
      tokenid: '',
      comment: '',
      privsep: 0
    })

    const fetchUsers = async () => {
      loading.value = true
      try {
        const response = await api.pveNode.listUsers(hostId.value)
        users.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch users:', error)
        toast.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const addUser = async () => {
      saving.value = true
      try {
        const payload = { ...newUser.value }
        Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k] })
        await api.pveNode.createUser(hostId.value, payload)
        toast.success('User added successfully')
        showAddModal.value = false
        newUser.value = { userid: '', password: '', firstname: '', lastname: '', email: '', enable: 1 }
        await fetchUsers()
      } catch (error) {
        console.error('Failed to add user:', error)
        toast.error(error.response?.data?.detail || 'Failed to add user')
      } finally {
        saving.value = false
      }
    }

    const deleteUser = async (userid) => {
      if (!confirm(`Delete user "${userid}"? This cannot be undone.`)) return
      try {
        await api.pveNode.deleteUser(hostId.value, encodeURIComponent(userid))
        toast.success('User deleted')
        await fetchUsers()
      } catch (error) {
        console.error('Failed to delete user:', error)
        toast.error('Failed to delete user')
      }
    }

    const openTokens = async (user) => {
      selectedUser.value = user
      tokens.value = []
      createdTokenValue.value = null
      newToken.value = { tokenid: '', comment: '', privsep: 0 }
      showTokensModal.value = true
      loadingTokens.value = true
      try {
        const response = await api.pveNode.listUserTokens(hostId.value, encodeURIComponent(user.userid))
        tokens.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch tokens:', error)
      } finally {
        loadingTokens.value = false
      }
    }

    const createToken = async () => {
      if (!selectedUser.value) return
      savingToken.value = true
      createdTokenValue.value = null
      try {
        const response = await api.pveNode.createUserToken(
          hostId.value,
          encodeURIComponent(selectedUser.value.userid),
          newToken.value.tokenid
        )
        toast.success('Token created')
        createdTokenValue.value = response.data?.value || response.data?.full_tokenid || JSON.stringify(response.data)
        newToken.value = { tokenid: '', comment: '', privsep: 0 }
        await openTokens(selectedUser.value)
      } catch (error) {
        console.error('Failed to create token:', error)
        toast.error('Failed to create token')
      } finally {
        savingToken.value = false
      }
    }

    const revokeToken = async (tokenid) => {
      if (!selectedUser.value) return
      if (!confirm(`Revoke token "${tokenid}"?`)) return
      try {
        await api.pveNode.deleteUserToken(
          hostId.value,
          encodeURIComponent(selectedUser.value.userid),
          tokenid
        )
        toast.success('Token revoked')
        await openTokens(selectedUser.value)
      } catch (error) {
        console.error('Failed to revoke token:', error)
        toast.error('Failed to revoke token')
      }
    }

    const extractRealm = (userid) => {
      if (!userid) return '—'
      const parts = userid.split('@')
      return parts.length > 1 ? parts[parts.length - 1] : 'unknown'
    }

    const formatExpiry = (epoch) => {
      if (!epoch) return 'Never'
      return new Date(epoch * 1000).toLocaleDateString()
    }

    onMounted(() => {
      fetchUsers()
    })

    return {
      hostId,
      users,
      loading,
      saving,
      showAddModal,
      showTokensModal,
      selectedUser,
      tokens,
      loadingTokens,
      savingToken,
      createdTokenValue,
      newUser,
      newToken,
      addUser,
      deleteUser,
      openTokens,
      createToken,
      revokeToken,
      extractRealm,
      formatExpiry
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 0.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content.modal-large {
  max-width: 800px;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; }

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
}

.token-value-box {
  margin-top: 1.5rem;
  padding: 1rem;
  background: #d1fae5;
  border: 1px solid #10b981;
  border-radius: 0.5rem;
  color: #065f46;
}

.token-value-box h5 {
  margin: 0 0 0.5rem 0;
}

.token-value {
  display: block;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #065f46;
  color: #d1fae5;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  word-break: break-all;
}
</style>
