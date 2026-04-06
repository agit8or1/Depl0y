<template>
  <div class="pve-users-page">
    <div class="page-header mb-2">
      <h2>Proxmox Users</h2>
      <p class="text-muted">Manage users on Proxmox host {{ hostId }}</p>
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="switchTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'" class="card">
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
                  <button @click="openPermissions(user)" class="btn btn-outline btn-sm">Permissions</button>
                  <button @click="deleteUser(user.userid)" class="btn btn-danger btn-sm">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Access Control Tab -->
    <div v-if="activeTab === 'acl'" class="card">
      <div class="card-header">
        <h3>Access Control List</h3>
        <button @click="openGrantModal" class="btn btn-primary">+ Grant Permission</button>
      </div>

      <div v-if="loadingAcl" class="loading-spinner"></div>

      <div v-else-if="aclEntries.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No ACL entries found.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Path</th>
              <th>User / Group / Token</th>
              <th>Role</th>
              <th>Propagate</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, idx) in aclEntries" :key="idx">
              <td><code>{{ entry.path }}</code></td>
              <td>
                <span v-if="entry.type === 'group'" class="badge badge-warning" style="margin-right: 0.4rem;">group</span>
                <span v-else-if="entry.type === 'token'" class="badge badge-info" style="margin-right: 0.4rem;">token</span>
                <span v-else class="badge badge-secondary" style="margin-right: 0.4rem;">user</span>
                {{ entry.ugid }}
              </td>
              <td><span class="badge badge-info">{{ entry.roleid }}</span></td>
              <td>
                <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                  {{ entry.propagate ? 'Yes' : 'No' }}
                </span>
              </td>
              <td>
                <button @click="deleteAclEntry(entry)" class="btn btn-danger btn-sm">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Roles Tab -->
    <div v-if="activeTab === 'roles'" class="card">
      <div class="card-header">
        <h3>Roles</h3>
        <button @click="openCreateRoleModal" class="btn btn-primary">+ Create Role</button>
      </div>

      <div v-if="loadingRolesList" class="loading-spinner"></div>

      <div v-else-if="rolesList.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No roles found.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Role ID</th>
              <th>Type</th>
              <th>Privileges</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="role in rolesList" :key="role.roleid">
              <tr>
                <td>
                  <strong>{{ role.roleid }}</strong>
                </td>
                <td>
                  <span :class="['badge', role.special ? 'badge-warning' : 'badge-info']">
                    {{ role.special ? 'Built-in' : 'Custom' }}
                  </span>
                </td>
                <td>
                  <button
                    @click="toggleRoleExpand(role.roleid)"
                    class="btn btn-outline btn-sm"
                  >
                    {{ expandedRoles.has(role.roleid) ? 'Hide' : 'Show' }}
                    {{ countPrivileges(role) }} privileges
                  </button>
                </td>
                <td>
                  <div class="flex gap-1">
                    <button
                      v-if="!role.special"
                      @click="openEditRoleModal(role)"
                      class="btn btn-outline btn-sm"
                    >Edit</button>
                    <button
                      v-if="!role.special"
                      @click="deleteRole(role.roleid)"
                      class="btn btn-danger btn-sm"
                    >Delete</button>
                    <span v-if="role.special" class="text-muted text-sm">Read-only</span>
                  </div>
                </td>
              </tr>
              <!-- Expanded privileges row -->
              <tr v-if="expandedRoles.has(role.roleid)">
                <td colspan="4" style="padding: 0.5rem 1rem 1rem; background: var(--background, #f9fafb);">
                  <div class="privilege-grid">
                    <span
                      v-for="priv in getPrivileges(role)"
                      :key="priv"
                      class="priv-badge"
                    >{{ priv }}</span>
                    <span v-if="getPrivileges(role).length === 0" class="text-muted text-sm">No privileges</span>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Groups Tab -->
    <div v-if="activeTab === 'groups'" class="card">
      <div class="card-header">
        <h3>Groups</h3>
        <button @click="showCreateGroupModal = true" class="btn btn-primary">+ Create Group</button>
      </div>

      <div v-if="loadingGroups" class="loading-spinner"></div>

      <div v-else-if="groups.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No groups found.</p>
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Group ID</th>
              <th>Comment</th>
              <th>Members</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in groups" :key="group.groupid">
              <td><strong>{{ group.groupid }}</strong></td>
              <td>{{ group.comment || '—' }}</td>
              <td>
                <span class="badge badge-secondary">
                  {{ group.members ? group.members.length : 0 }}
                </span>
              </td>
              <td>
                <button @click="deleteGroup(group.groupid)" class="btn btn-danger btn-sm">Delete</button>
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
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="token in tokens" :key="token.tokenid">
                  <td>
                    <code>{{ formatTokenId(selectedUser?.userid, token.tokenid) }}</code>
                  </td>
                  <td>{{ token.comment || '—' }}</td>
                  <td class="text-sm">
                    <span v-if="token.expire && token.expire > 0"
                          :class="['expiry-badge', expiryClass(token.expire)]">
                      {{ formatExpiry(token.expire) }}
                    </span>
                    <span v-else class="text-muted">Never</span>
                  </td>
                  <td>
                    <span :class="['badge', token.privsep !== 0 ? 'badge-warning' : 'badge-success']">
                      {{ token.privsep !== 0 ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">
                    {{ token.ctime ? formatDate(token.ctime) : '—' }}
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button
                        @click="copyToClipboard(formatTokenId(selectedUser?.userid, token.tokenid))"
                        class="btn btn-outline btn-sm"
                        title="Copy Token ID"
                      >
                        Copy ID
                      </button>
                      <button @click="revokeToken(token.tokenid)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
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
        </div>
      </div>
    </div>

    <!-- Token Secret Modal (shown once after creation) -->
    <div v-if="showTokenSecretModal" class="modal" @click.self="showTokenSecretModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Token Created!</h3>
          <button @click="showTokenSecretModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="token-secret-alert">
            <p class="text-sm" style="margin-bottom: 1rem;">
              Copy your token secret — it will <strong>not</strong> be shown again:
            </p>
            <div class="token-secret-block">
              <code class="token-secret-value">{{ createdTokenValue }}</code>
              <button @click="copyToClipboard(createdTokenValue)" class="btn btn-outline btn-sm copy-secret-btn">
                Copy
              </button>
            </div>
          </div>
          <div class="flex gap-1 mt-2" style="justify-content: flex-end;">
            <button @click="showTokenSecretModal = false" class="btn btn-primary">Done</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Grant Permission Modal -->
    <div v-if="showGrantModal" class="modal" @click="showGrantModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Grant Permission</h3>
          <button @click="showGrantModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="grantAcl" class="modal-body">
          <div class="form-group">
            <label class="form-label">Path</label>
            <input
              v-model="newAcl.path"
              class="form-control"
              placeholder="/ or /nodes/pve or /vms/100"
              required
            />
            <p class="text-xs text-muted mt-1">Root path "/" grants access to everything.</p>
          </div>

          <div class="form-group">
            <label class="form-label">User / Token ID</label>
            <input
              v-model="newAcl.ugid"
              class="form-control"
              placeholder="user@pve or user@pve!token"
              required
            />
            <p class="text-xs text-muted mt-1">Use <code>user@realm</code> for a user or <code>user@realm!tokenid</code> for a token.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Role</label>
            <div v-if="loadingRoles" class="text-sm text-muted">Loading roles...</div>
            <select v-else v-model="newAcl.roles" class="form-control" required>
              <option value="" disabled>Select a role</option>
              <option v-for="role in roles" :key="role.roleid" :value="role.roleid">
                {{ role.roleid }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">
              <input type="checkbox" v-model="newAcl.propagate" :true-value="1" :false-value="0" />
              Propagate (apply to sub-paths)
            </label>
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingAcl">
              {{ savingAcl ? 'Granting...' : 'Grant Permission' }}
            </button>
            <button type="button" @click="showGrantModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- User Permissions Modal -->
    <div v-if="showPermissionsModal" class="modal" @click="showPermissionsModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Permissions — {{ permissionsUser?.userid }}</h3>
          <button @click="showPermissionsModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingPermissions" class="loading-spinner"></div>
          <div v-else-if="userPermissions.length === 0" class="text-muted text-sm" style="padding: 1rem 0;">
            No explicit permissions (inherits from group)
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Role</th>
                  <th>Propagate</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in userPermissions" :key="idx">
                  <td><code>{{ entry.path }}</code></td>
                  <td><span class="badge badge-info">{{ entry.roleid }}</span></td>
                  <td>
                    <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                      {{ entry.propagate ? 'Yes' : 'No' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Role Modal -->
    <div v-if="showRoleModal" class="modal" @click="showRoleModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>{{ editingRole ? 'Edit Role' : 'Create Role' }} — {{ editingRole ? editingRole.roleid : '' }}</h3>
          <button @click="showRoleModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveRole" class="modal-body">
          <div v-if="!editingRole" class="form-group">
            <label class="form-label">Role ID</label>
            <input v-model="roleForm.roleid" class="form-control" placeholder="MyRole" required />
          </div>
          <div class="form-group">
            <label class="form-label">Privileges</label>
            <p class="text-xs text-muted mb-1">Select the privileges this role grants:</p>
            <div class="priv-checkbox-grid">
              <label
                v-for="priv in allPrivileges"
                :key="priv"
                class="priv-checkbox-item"
              >
                <input type="checkbox" :value="priv" v-model="roleForm.privs" />
                <span class="priv-name">{{ priv }}</span>
              </label>
            </div>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingRole">
              {{ savingRole ? 'Saving...' : (editingRole ? 'Update Role' : 'Create Role') }}
            </button>
            <button type="button" @click="showRoleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Group Modal -->
    <div v-if="showCreateGroupModal" class="modal" @click="showCreateGroupModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Group</h3>
          <button @click="showCreateGroupModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createGroup" class="modal-body">
          <div class="form-group">
            <label class="form-label">Group ID</label>
            <input v-model="newGroup.groupid" class="form-control" placeholder="admins" required />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newGroup.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingGroup">
              {{ savingGroup ? 'Creating...' : 'Create Group' }}
            </button>
            <button type="button" @click="showCreateGroupModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
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

    const tabs = [
      { id: 'users', label: 'Users' },
      { id: 'acl', label: 'Access Control' },
      { id: 'roles', label: 'Roles' },
      { id: 'groups', label: 'Groups' }
    ]
    const activeTab = ref('users')

    // ── Users ──────────────────────────────────────────────────────────────
    const users = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)
    const showTokensModal = ref(false)
    const showTokenSecretModal = ref(false)
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
        const payload = {}
        if (newToken.value.comment) payload.comment = newToken.value.comment
        if (newToken.value.privsep !== undefined) payload.privsep = newToken.value.privsep
        const response = await api.pveNode.createUserToken(
          hostId.value,
          encodeURIComponent(selectedUser.value.userid),
          newToken.value.tokenid,
          payload
        )
        // PVE returns the secret inside response.data.value or response.data
        const secret = response.data?.value || response.data?.full_tokenid || JSON.stringify(response.data)
        createdTokenValue.value = secret
        newToken.value = { tokenid: '', comment: '', privsep: 0 }
        // Refresh token list (without closing tokens modal)
        loadingTokens.value = true
        try {
          const r2 = await api.pveNode.listUserTokens(hostId.value, encodeURIComponent(selectedUser.value.userid))
          tokens.value = r2.data || []
        } finally {
          loadingTokens.value = false
        }
        // Show secret modal on top
        showTokenSecretModal.value = true
      } catch (error) {
        console.error('Failed to create token:', error)
        toast.error('Failed to create token')
      } finally {
        savingToken.value = false
      }
    }

    const revokeToken = async (tokenid) => {
      if (!selectedUser.value) return
      if (!confirm(`Delete token "${tokenid}"?`)) return
      try {
        await api.pveNode.deleteUserToken(
          hostId.value,
          encodeURIComponent(selectedUser.value.userid),
          tokenid
        )
        toast.success('Token deleted')
        await openTokens(selectedUser.value)
      } catch (error) {
        console.error('Failed to revoke token:', error)
        toast.error('Failed to delete token')
      }
    }

    // ── User Permissions ───────────────────────────────────────────────────
    const showPermissionsModal = ref(false)
    const permissionsUser = ref(null)
    const userPermissions = ref([])
    const loadingPermissions = ref(false)

    const openPermissions = async (user) => {
      permissionsUser.value = user
      userPermissions.value = []
      showPermissionsModal.value = true
      loadingPermissions.value = true
      try {
        const response = await api.pveNode.listAcl(hostId.value)
        const all = response.data || []
        // Match entries where ugid equals this user's userid (user type entries)
        userPermissions.value = all.filter(
          e => e.type === 'user' && e.ugid === user.userid
        )
      } catch (error) {
        console.error('Failed to fetch ACL for user:', error)
        toast.error('Failed to load user permissions')
      } finally {
        loadingPermissions.value = false
      }
    }

    // ── ACL ────────────────────────────────────────────────────────────────
    const aclEntries = ref([])
    const loadingAcl = ref(false)
    const roles = ref([])
    const loadingRoles = ref(false)
    const showGrantModal = ref(false)
    const savingAcl = ref(false)

    const newAcl = ref({
      path: '/',
      ugid: '',
      roles: '',
      propagate: 1
    })

    const fetchAcl = async () => {
      loadingAcl.value = true
      try {
        const response = await api.pveNode.listAcl(hostId.value)
        aclEntries.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch ACL:', error)
        toast.error('Failed to load ACL entries')
      } finally {
        loadingAcl.value = false
      }
    }

    const fetchRoles = async () => {
      if (roles.value.length > 0) return
      loadingRoles.value = true
      try {
        const response = await api.pveNode.listRoles(hostId.value)
        roles.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch roles:', error)
        toast.error('Failed to load roles')
      } finally {
        loadingRoles.value = false
      }
    }

    const openGrantModal = async () => {
      newAcl.value = { path: '/', ugid: '', roles: '', propagate: 1 }
      showGrantModal.value = true
      await fetchRoles()
    }

    const grantAcl = async () => {
      savingAcl.value = true
      try {
        await api.pveNode.updateAcl(hostId.value, {
          path: newAcl.value.path,
          roles: newAcl.value.roles,
          ugid: newAcl.value.ugid,
          delete: 0,
          propagate: newAcl.value.propagate
        })
        toast.success('Permission granted')
        showGrantModal.value = false
        await fetchAcl()
      } catch (error) {
        console.error('Failed to grant ACL:', error)
        toast.error(error.response?.data?.detail || 'Failed to grant permission')
      } finally {
        savingAcl.value = false
      }
    }

    const deleteAclEntry = async (entry) => {
      if (!confirm(`Remove "${entry.roleid}" on "${entry.path}" for "${entry.ugid}"?`)) return
      try {
        await api.pveNode.updateAcl(hostId.value, {
          path: entry.path,
          roles: entry.roleid,
          ugid: entry.ugid,
          delete: 1,
          propagate: entry.propagate ? 1 : 0
        })
        toast.success('ACL entry removed')
        await fetchAcl()
      } catch (error) {
        console.error('Failed to delete ACL entry:', error)
        toast.error('Failed to remove ACL entry')
      }
    }

    // ── Groups ─────────────────────────────────────────────────────────────
    const groups = ref([])
    const loadingGroups = ref(false)
    const showCreateGroupModal = ref(false)
    const savingGroup = ref(false)

    const newGroup = ref({ groupid: '', comment: '' })

    const fetchGroups = async () => {
      loadingGroups.value = true
      try {
        const response = await api.pveNode.listGroups(hostId.value)
        groups.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch groups:', error)
        toast.error('Failed to load groups')
      } finally {
        loadingGroups.value = false
      }
    }

    const createGroup = async () => {
      savingGroup.value = true
      try {
        const payload = { groupid: newGroup.value.groupid }
        if (newGroup.value.comment) payload.comment = newGroup.value.comment
        await api.pveNode.createGroup(hostId.value, payload)
        toast.success('Group created')
        showCreateGroupModal.value = false
        newGroup.value = { groupid: '', comment: '' }
        await fetchGroups()
      } catch (error) {
        console.error('Failed to create group:', error)
        toast.error(error.response?.data?.detail || 'Failed to create group')
      } finally {
        savingGroup.value = false
      }
    }

    const deleteGroup = async (groupid) => {
      if (!confirm(`Delete group "${groupid}"? This cannot be undone.`)) return
      try {
        await api.pveNode.deleteGroup(hostId.value, groupid)
        toast.success('Group deleted')
        await fetchGroups()
      } catch (error) {
        console.error('Failed to delete group:', error)
        toast.error('Failed to delete group')
      }
    }

    // ── Roles Management ──────────────────────────────────────────────────────
    const rolesList = ref([])
    const loadingRolesList = ref(false)
    const expandedRoles = ref(new Set())
    const showRoleModal = ref(false)
    const editingRole = ref(null)
    const savingRole = ref(false)
    const roleForm = ref({ roleid: '', privs: [] })

    // All available Proxmox privileges
    const allPrivileges = [
      'VM.Allocate', 'VM.Audit', 'VM.Backup', 'VM.Clone', 'VM.Config.CDROM',
      'VM.Config.CPU', 'VM.Config.Cloudinit', 'VM.Config.Disk', 'VM.Config.HWType',
      'VM.Config.Memory', 'VM.Config.MoveConfig', 'VM.Config.Net', 'VM.Config.Options',
      'VM.Console', 'VM.Migrate', 'VM.Monitor', 'VM.PowerMgmt', 'VM.Snapshot',
      'VM.Snapshot.Rollback',
      'Datastore.Allocate', 'Datastore.AllocateSpace', 'Datastore.AllocateTemplate',
      'Datastore.Audit',
      'Sys.Audit', 'Sys.Console', 'Sys.Incoming', 'Sys.Modify', 'Sys.PowerMgmt',
      'Sys.Syslog',
      'Permissions.Modify',
      'Pool.Allocate', 'Pool.Audit',
      'SDN.Allocate', 'SDN.Audit', 'SDN.Use',
      'Realm.AllocateUser',
    ].sort()

    const fetchRolesList = async () => {
      loadingRolesList.value = true
      try {
        const response = await api.pveNode.listRoles(hostId.value)
        rolesList.value = response.data || []
        roles.value = rolesList.value
      } catch (error) {
        console.error('Failed to fetch roles:', error)
        toast.error('Failed to load roles')
      } finally {
        loadingRolesList.value = false
      }
    }

    const toggleRoleExpand = (roleid) => {
      const s = new Set(expandedRoles.value)
      if (s.has(roleid)) s.delete(roleid)
      else s.add(roleid)
      expandedRoles.value = s
    }

    const countPrivileges = (role) => getPrivileges(role).length

    const getPrivileges = (role) => {
      if (!role.privs) return []
      if (Array.isArray(role.privs)) return role.privs
      return role.privs.split(',').map(p => p.trim()).filter(Boolean)
    }

    const openCreateRoleModal = () => {
      editingRole.value = null
      roleForm.value = { roleid: '', privs: [] }
      showRoleModal.value = true
    }

    const openEditRoleModal = (role) => {
      editingRole.value = role
      roleForm.value = { roleid: role.roleid, privs: getPrivileges(role) }
      showRoleModal.value = true
    }

    const saveRole = async () => {
      savingRole.value = true
      try {
        const privString = roleForm.value.privs.join(',')
        if (editingRole.value) {
          await api.pveNode.updateRole(hostId.value, editingRole.value.roleid, { privs: privString })
          toast.success('Role updated')
        } else {
          await api.pveNode.createRole(hostId.value, { roleid: roleForm.value.roleid, privs: privString })
          toast.success('Role created')
        }
        showRoleModal.value = false
        await fetchRolesList()
      } catch (error) {
        console.error('Failed to save role:', error)
        toast.error(error.response?.data?.detail || 'Failed to save role')
      } finally {
        savingRole.value = false
      }
    }

    const deleteRole = async (roleid) => {
      if (!confirm(`Delete role "${roleid}"? This cannot be undone.`)) return
      try {
        await api.pveNode.deleteRole(hostId.value, roleid)
        toast.success('Role deleted')
        await fetchRolesList()
      } catch (error) {
        console.error('Failed to delete role:', error)
        toast.error(error.response?.data?.detail || 'Failed to delete role')
      }
    }

    // ── Tab switching ──────────────────────────────────────────────────────
    const switchTab = (tabId) => {
      activeTab.value = tabId
      if (tabId === 'acl') {
        fetchAcl()
        fetchRoles()
      } else if (tabId === 'groups') {
        fetchGroups()
      } else if (tabId === 'roles') {
        fetchRolesList()
      }
    }

    // ── Helpers ────────────────────────────────────────────────────────────
    const extractRealm = (userid) => {
      if (!userid) return '—'
      const parts = userid.split('@')
      return parts.length > 1 ? parts[parts.length - 1] : 'unknown'
    }

    const formatTokenId = (userid, tokenid) => {
      if (!userid || !tokenid) return tokenid || ''
      return `${userid}!${tokenid}`
    }

    const formatExpiry = (epoch) => {
      if (!epoch) return 'Never'
      return new Date(epoch * 1000).toLocaleDateString()
    }

    const formatDate = (epoch) => {
      if (!epoch) return '—'
      return new Date(epoch * 1000).toLocaleDateString()
    }

    const expiryClass = (epoch) => {
      if (!epoch || epoch === 0) return 'expiry-never'
      const now = Math.floor(Date.now() / 1000)
      const diff = epoch - now
      if (diff < 0) return 'expiry-expired'
      if (diff < 30 * 24 * 3600) return 'expiry-soon'
      return 'expiry-ok'
    }

    const copyToClipboard = async (text) => {
      try {
        await navigator.clipboard.writeText(text)
        toast.success('Copied to clipboard')
      } catch {
        toast.error('Failed to copy')
      }
    }

    onMounted(() => {
      fetchUsers()
    })

    return {
      hostId,
      tabs,
      activeTab,
      switchTab,
      // users
      users,
      loading,
      saving,
      showAddModal,
      showTokensModal,
      showTokenSecretModal,
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
      // permissions
      showPermissionsModal,
      permissionsUser,
      userPermissions,
      loadingPermissions,
      openPermissions,
      // acl
      aclEntries,
      loadingAcl,
      roles,
      loadingRoles,
      showGrantModal,
      savingAcl,
      newAcl,
      openGrantModal,
      grantAcl,
      deleteAclEntry,
      // groups
      groups,
      loadingGroups,
      showCreateGroupModal,
      savingGroup,
      newGroup,
      createGroup,
      deleteGroup,
      // roles
      rolesList,
      loadingRolesList,
      expandedRoles,
      showRoleModal,
      editingRole,
      savingRole,
      roleForm,
      allPrivileges,
      fetchRolesList,
      toggleRoleExpand,
      countPrivileges,
      getPrivileges,
      openCreateRoleModal,
      openEditRoleModal,
      saveRole,
      deleteRole,
      // helpers
      extractRealm,
      formatTokenId,
      formatExpiry,
      formatDate,
      expiryClass,
      copyToClipboard
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

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.625rem 1.25rem;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--primary, #3b82f6);
  border-bottom-color: var(--primary, #3b82f6);
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
  background: var(--card-bg, #fff);
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

/* Token secret modal */
.token-secret-alert {
  padding: 1rem;
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 0.5rem;
  color: #78350f;
}

.token-secret-block {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.token-secret-value {
  display: block;
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: #1c1917;
  color: #fef3c7;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  word-break: break-all;
  white-space: pre-wrap;
}

.copy-secret-btn {
  flex-shrink: 0;
  align-self: center;
}

/* Expiry color coding */
.expiry-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
  font-weight: 500;
}

.expiry-expired {
  background: #fee2e2;
  color: #991b1b;
}

.expiry-soon {
  background: #fef9c3;
  color: #854d0e;
}

.expiry-ok {
  background: #dcfce7;
  color: #166534;
}

.badge-secondary {
  background: var(--background, #f3f4f6);
  color: var(--text-secondary, #6b7280);
}

/* Roles tab */
.privilege-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.25rem 0;
}

.priv-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  font-family: monospace;
}

.priv-checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.4rem;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem;
}

.priv-checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  padding: 0.2rem 0.25rem;
  border-radius: 0.25rem;
  transition: background 0.1s;
}

.priv-checkbox-item:hover {
  background: var(--background, #f3f4f6);
}

.priv-name {
  font-size: 0.8125rem;
  font-family: monospace;
  color: var(--text-primary);
}
</style>
