<template>
  <div class="users-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h2>User Management</h2>
        <p class="text-muted">Create, edit, and manage platform user accounts</p>
      </div>
      <button @click="openCreateModal" class="btn btn-primary">+ Add User</button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar card mb-2">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control search-input"
        placeholder="Search by username or email…"
      />
      <div class="filter-group">
        <span class="filter-label">Role:</span>
        <button
          v-for="r in ['all', 'admin', 'operator', 'viewer']"
          :key="r"
          :class="['btn btn-sm', roleFilter === r ? 'btn-primary' : 'btn-outline']"
          @click="roleFilter = r"
        >{{ r === 'all' ? 'All' : formatRole(r) }}</button>
      </div>
      <div class="filter-group">
        <span class="filter-label">2FA:</span>
        <button
          v-for="t in [{ val: 'all', label: 'All' }, { val: 'enabled', label: 'Enabled' }, { val: 'disabled', label: 'Disabled' }]"
          :key="t.val"
          :class="['btn btn-sm', twoFaFilter === t.val ? 'btn-primary' : 'btn-outline']"
          @click="twoFaFilter = t.val"
        >{{ t.label }}</button>
      </div>
      <div class="filter-group">
        <span class="filter-label">Status:</span>
        <button
          v-for="s in [{ val: 'all', label: 'All' }, { val: 'active', label: 'Active' }, { val: 'disabled', label: 'Disabled' }]"
          :key="s.val"
          :class="['btn btn-sm', statusFilter === s.val ? 'btn-primary' : 'btn-outline']"
          @click="statusFilter = s.val"
        >{{ s.label }}</button>
      </div>
      <span class="text-muted text-sm ml-auto">
        {{ selectedIds.size > 0 ? `${selectedIds.size} selected · ` : '' }}{{ filteredUsers.length }} user{{ filteredUsers.length !== 1 ? 's' : '' }}
      </span>
    </div>

    <!-- Bulk Actions Bar -->
    <div v-if="selectedIds.size > 0" class="bulk-bar card mb-2">
      <span class="text-sm"><strong>{{ selectedIds.size }}</strong> selected</span>
      <button @click="bulkEnable" class="btn btn-outline btn-sm">Enable Selected</button>
      <button @click="bulkDisable" class="btn btn-warning btn-sm">Disable Selected</button>
      <button @click="confirmBulkDelete" class="btn btn-danger btn-sm">Delete Selected</button>
      <button @click="selectedIds.clear()" class="btn btn-outline btn-sm">Clear</button>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-else-if="filteredUsers.length === 0" class="card empty-state">
      <p>No users found matching the current filters.</p>
    </div>

    <div v-else class="card table-container">
      <table class="table">
        <thead>
          <tr>
            <th class="th-check">
              <input
                type="checkbox"
                :checked="allSelected"
                :indeterminate.prop="someSelected"
                @change="toggleSelectAll"
              />
            </th>
            <th class="th-avatar"></th>
            <th @click="setSort('username')" class="sortable">
              Username <span class="sort-icon">{{ sortIcon('username') }}</span>
            </th>
            <th @click="setSort('email')" class="sortable">
              Email <span class="sort-icon">{{ sortIcon('email') }}</span>
            </th>
            <th @click="setSort('role')" class="sortable">
              Role <span class="sort-icon">{{ sortIcon('role') }}</span>
            </th>
            <th @click="setSort('totp_enabled')" class="sortable">
              2FA <span class="sort-icon">{{ sortIcon('totp_enabled') }}</span>
            </th>
            <th @click="setSort('last_login')" class="sortable">
              Last Login <span class="sort-icon">{{ sortIcon('last_login') }}</span>
            </th>
            <th @click="setSort('is_active')" class="sortable">
              Status <span class="sort-icon">{{ sortIcon('is_active') }}</span>
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="user in sortedUsers"
            :key="user.id"
            :class="{ 'row-disabled': !user.is_active, 'row-selected': selectedIds.has(user.id) }"
          >
            <td class="td-check">
              <input
                type="checkbox"
                :checked="selectedIds.has(user.id)"
                @change="toggleSelect(user.id)"
              />
            </td>
            <td class="td-avatar">
              <div :class="['avatar-badge', `avatar-${getAvatarColor(user.username)}`]">
                {{ getInitials(user.username) }}
              </div>
            </td>
            <td>
              <button class="username-btn" @click="openDrawer(user)">
                <strong>{{ user.username }}</strong>
              </button>
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
            <td class="text-sm text-muted">{{ formatDate(user.last_login) }}</td>
            <td>
              <span :class="['badge', user.is_active ? 'badge-success' : 'badge-danger']">
                {{ user.is_active ? 'Active' : 'Disabled' }}
              </span>
            </td>
            <td>
              <div class="action-btns">
                <button @click="openEditModal(user)" class="btn btn-outline btn-sm">Edit</button>
                <button
                  @click="toggleStatus(user)"
                  :class="['btn btn-sm', user.is_active ? 'btn-warning' : 'btn-outline']"
                >{{ user.is_active ? 'Disable' : 'Enable' }}</button>
                <button @click="confirmDelete(user)" class="btn btn-danger btn-sm">Delete</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Create User Modal ──────────────────────────────── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content modal-lg">
        <div class="modal-header">
          <h3>Create New User</h3>
          <button @click="showCreateModal = false" class="modal-close">×</button>
        </div>
        <form @submit.prevent="createUser" class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Username *</label>
              <input v-model="createForm.username" type="text" class="form-control" required autocomplete="off" />
            </div>
            <div class="form-group">
              <label class="form-label">Email *</label>
              <input v-model="createForm.email" type="email" class="form-control" required autocomplete="off" />
            </div>
          </div>

          <div class="form-row">
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
              <label class="form-label">Confirm Password *</label>
              <input
                v-model="createForm.confirmPassword"
                :type="showCreatePassword ? 'text' : 'password'"
                class="form-control"
                required
                autocomplete="new-password"
                :class="{ 'input-error': createForm.confirmPassword && createForm.password !== createForm.confirmPassword }"
              />
              <p v-if="createForm.confirmPassword && createForm.password !== createForm.confirmPassword" class="form-hint form-error">Passwords do not match</p>
            </div>
          </div>

          <!-- Role selector -->
          <div class="form-group">
            <label class="form-label">Role *</label>
            <div class="role-selector">
              <label
                v-for="role in roleOptions"
                :key="role.value"
                :class="['role-option', createForm.role === role.value ? 'role-option-selected' : '']"
              >
                <input type="radio" v-model="createForm.role" :value="role.value" class="role-radio" />
                <div class="role-option-content">
                  <span :class="['badge', role.badgeClass]">{{ role.label }}</span>
                  <span class="role-desc">{{ role.description }}</span>
                </div>
              </label>
            </div>
          </div>

          <!-- Host access -->
          <div class="form-group">
            <label class="form-label">Host Access</label>
            <p class="form-hint mb-1">
              Admin users always have access to all hosts. For operator/viewer, select which hosts to grant access.
            </p>
            <div v-if="loadingHosts" class="text-muted text-sm">Loading hosts…</div>
            <div v-else-if="allHosts.length === 0" class="text-muted text-sm">No Proxmox hosts configured.</div>
            <div v-else class="host-checkboxes">
              <label
                v-for="host in allHosts"
                :key="host.id"
                class="host-checkbox-item"
              >
                <input
                  type="checkbox"
                  :value="host.id"
                  v-model="createForm.selectedHosts"
                  :disabled="createForm.role === 'admin'"
                />
                <span>
                  <strong>{{ host.name }}</strong>
                  <span class="text-muted text-sm"> — {{ host.hostname }}</span>
                </span>
              </label>
            </div>
            <p v-if="createForm.role === 'admin'" class="form-hint">Admin users inherit access to all hosts automatically.</p>
          </div>

          <div class="modal-footer">
            <button type="button" @click="showCreateModal = false" class="btn btn-outline">Cancel</button>
            <button
              type="submit"
              class="btn btn-primary"
              :disabled="creating || (createForm.confirmPassword && createForm.password !== createForm.confirmPassword)"
            >
              {{ creating ? 'Creating…' : 'Create User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Edit User Modal ────────────────────────────────── -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content modal-lg">
        <div class="modal-header">
          <h3>Edit User — {{ editForm.username }}</h3>
          <button @click="showEditModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <!-- Basic Info -->
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Username</label>
              <input :value="editForm.username" type="text" class="form-control" disabled />
            </div>
            <div class="form-group">
              <label class="form-label">Email *</label>
              <input v-model="editForm.email" type="email" class="form-control" required />
            </div>
          </div>

          <!-- Role -->
          <div class="form-group">
            <label class="form-label">Role</label>
            <div class="role-selector">
              <label
                v-for="role in roleOptions"
                :key="role.value"
                :class="['role-option', editForm.role === role.value ? 'role-option-selected' : '']"
              >
                <input type="radio" v-model="editForm.role" :value="role.value" class="role-radio" />
                <div class="role-option-content">
                  <span :class="['badge', role.badgeClass]">{{ role.label }}</span>
                  <span class="role-desc">{{ role.description }}</span>
                </div>
              </label>
            </div>
          </div>

          <!-- Status toggle -->
          <div class="form-group">
            <label class="toggle-label">
              <input v-model="editForm.is_active" type="checkbox" />
              <span>Account Active</span>
            </label>
          </div>

          <!-- Reset Password section -->
          <div class="section-divider">
            <span>Reset Password</span>
          </div>
          <div v-if="!editResetMode" class="form-group">
            <button type="button" @click="editResetMode = true" class="btn btn-outline btn-sm">
              Set New Password
            </button>
          </div>
          <div v-else class="form-row">
            <div class="form-group">
              <label class="form-label">New Password</label>
              <div class="input-with-btn">
                <input
                  v-model="editForm.newPassword"
                  :type="showEditPassword ? 'text' : 'password'"
                  class="form-control"
                  minlength="8"
                  autocomplete="new-password"
                  placeholder="Leave blank to keep current"
                />
                <button type="button" @click="showEditPassword = !showEditPassword" class="btn btn-outline btn-sm">
                  {{ showEditPassword ? 'Hide' : 'Show' }}
                </button>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input
                v-model="editForm.confirmNewPassword"
                :type="showEditPassword ? 'text' : 'password'"
                class="form-control"
                autocomplete="new-password"
                :class="{ 'input-error': editForm.confirmNewPassword && editForm.newPassword !== editForm.confirmNewPassword }"
              />
              <p v-if="editForm.confirmNewPassword && editForm.newPassword !== editForm.confirmNewPassword" class="form-hint form-error">Passwords do not match</p>
            </div>
          </div>

          <!-- 2FA section -->
          <div class="section-divider">
            <span>Two-Factor Authentication</span>
          </div>
          <div class="form-group two-fa-row">
            <span :class="['badge', editForm.totp_enabled ? 'badge-success' : 'badge-secondary']">
              {{ editForm.totp_enabled ? '2FA Enabled' : '2FA Disabled' }}
            </span>
            <button
              v-if="editForm.totp_enabled"
              type="button"
              @click="disableTotp(editForm)"
              class="btn btn-warning btn-sm"
            >
              Disable 2FA
            </button>
          </div>

          <!-- Session management -->
          <div class="section-divider">
            <span>Sessions</span>
          </div>
          <div class="form-group">
            <p class="form-hint mb-1">Invalidate all active sessions for this user. They will be forced to log in again.</p>
            <button
              type="button"
              @click="invalidateSessions(editForm.id)"
              class="btn btn-outline btn-sm"
              :disabled="invalidatingSession"
            >
              {{ invalidatingSession ? 'Invalidating…' : 'Invalidate All Sessions' }}
            </button>
          </div>

          <!-- Host Access -->
          <div class="section-divider">
            <span>Host Access</span>
          </div>
          <div class="form-group">
            <p class="form-hint mb-1">
              Admin users always have access to all hosts. For operator/viewer, configure access below.
            </p>
            <div v-if="loadingEditHostPerms" class="text-muted text-sm">Loading host permissions…</div>
            <div v-else-if="allHosts.length === 0" class="text-muted text-sm">No Proxmox hosts configured.</div>
            <div v-else class="host-checkboxes">
              <label
                v-for="host in allHosts"
                :key="host.id"
                class="host-checkbox-item"
              >
                <input
                  type="checkbox"
                  :value="host.id"
                  v-model="editForm.selectedHosts"
                  :disabled="editForm.role === 'admin' || savingEditHostPerms"
                />
                <span>
                  <strong>{{ host.name }}</strong>
                  <span class="text-muted text-sm"> — {{ host.hostname }}</span>
                </span>
              </label>
            </div>
            <p v-if="editForm.role === 'admin'" class="form-hint">Admin users inherit access to all hosts automatically.</p>
          </div>

          <div class="modal-footer">
            <button type="button" @click="showEditModal = false" class="btn btn-outline">Cancel</button>
            <button
              type="button"
              @click="updateUser"
              class="btn btn-primary"
              :disabled="updating || (editForm.confirmNewPassword && editForm.newPassword !== editForm.confirmNewPassword)"
            >
              {{ updating ? 'Saving…' : 'Save Changes' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Delete Confirm Modal ───────────────────────────── -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="showDeleteModal = false">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h3>{{ bulkDeleteMode ? 'Delete Users' : 'Delete User' }}</h3>
          <button @click="showDeleteModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <p v-if="bulkDeleteMode">
            Are you sure you want to permanently delete <strong>{{ selectedIds.size }}</strong> user(s)?
          </p>
          <p v-else>
            Are you sure you want to permanently delete <strong>{{ deleteTarget?.username }}</strong>?
          </p>
          <p class="text-muted text-sm">This action cannot be undone.</p>
          <div class="modal-footer">
            <button @click="showDeleteModal = false" class="btn btn-outline">Cancel</button>
            <button @click="doDelete" class="btn btn-danger" :disabled="deleting">
              {{ deleting ? 'Deleting…' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── User Detail Drawer ──────────────────────────────── -->
    <div v-if="showDrawer" class="drawer-overlay" @click.self="closeDrawer">
      <div class="drawer">
        <div class="drawer-header">
          <div class="drawer-title-row">
            <div :class="['avatar-badge avatar-lg', `avatar-${getAvatarColor(drawerUser?.username || '')}`]">
              {{ getInitials(drawerUser?.username || '') }}
            </div>
            <div>
              <h3>{{ drawerUser?.username }}</h3>
              <p class="text-muted text-sm">{{ drawerUser?.email }}</p>
            </div>
          </div>
          <button @click="closeDrawer" class="modal-close">×</button>
        </div>

        <div class="drawer-body">
          <!-- Profile info -->
          <div class="drawer-section">
            <h4 class="drawer-section-title">Profile</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">Role</span>
                <span :class="['badge', getRoleBadgeClass(drawerUser?.role)]">{{ formatRole(drawerUser?.role) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Status</span>
                <span :class="['badge', drawerUser?.is_active ? 'badge-success' : 'badge-danger']">
                  {{ drawerUser?.is_active ? 'Active' : 'Disabled' }}
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">2FA</span>
                <span :class="['badge', drawerUser?.totp_enabled ? 'badge-success' : 'badge-secondary']">
                  {{ drawerUser?.totp_enabled ? 'Enabled' : 'Disabled' }}
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">Last Login</span>
                <span class="text-sm">{{ formatDate(drawerUser?.last_login) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Member Since</span>
                <span class="text-sm">{{ formatDateShort(drawerUser?.created_at) }}</span>
              </div>
            </div>
          </div>

          <!-- Host Permissions -->
          <div class="drawer-section">
            <h4 class="drawer-section-title">Host Access</h4>
            <div v-if="loadingDrawerData" class="text-muted text-sm">Loading…</div>
            <div v-else-if="drawerUser?.role === 'admin'" class="text-sm text-muted">
              Admin — access to all hosts.
            </div>
            <div v-else-if="drawerHostPerms.length === 0" class="text-sm text-muted">
              No host access granted.
            </div>
            <div v-else class="host-perm-list">
              <div v-for="perm in drawerHostPerms" :key="perm.id" class="host-perm-item">
                <span class="host-perm-name">{{ perm.host_name }}</span>
                <div class="host-perm-badges">
                  <span v-if="perm.can_view" class="badge badge-info badge-xs">View</span>
                  <span v-if="perm.can_manage" class="badge badge-warning badge-xs">Manage</span>
                  <span v-if="perm.can_admin" class="badge badge-danger badge-xs">Admin</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent Login History -->
          <div class="drawer-section">
            <h4 class="drawer-section-title">Recent Logins</h4>
            <div v-if="loadingDrawerData" class="text-muted text-sm">Loading…</div>
            <div v-else-if="drawerLoginHistory.length === 0" class="text-muted text-sm">No login history.</div>
            <div v-else class="login-history-list">
              <div v-for="attempt in drawerLoginHistory" :key="attempt.id" class="login-history-item">
                <span :class="['login-dot', attempt.success ? 'login-dot-success' : 'login-dot-fail']"></span>
                <div class="login-history-detail">
                  <span class="text-sm">{{ attempt.ip_address }}</span>
                  <span class="text-muted text-xs">{{ formatDateRelative(attempt.timestamp) }}</span>
                </div>
                <span :class="['badge badge-xs', attempt.success ? 'badge-success' : 'badge-danger']">
                  {{ attempt.success ? 'OK' : 'Failed' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Drawer Quick Actions -->
        <div class="drawer-footer">
          <button @click="openEditModal(drawerUser); closeDrawer()" class="btn btn-primary btn-sm">Edit</button>
          <button
            @click="toggleStatus(drawerUser)"
            :class="['btn btn-sm', drawerUser?.is_active ? 'btn-warning' : 'btn-outline']"
          >{{ drawerUser?.is_active ? 'Disable' : 'Enable' }}</button>
          <button @click="confirmDelete(drawerUser); closeDrawer()" class="btn btn-danger btn-sm">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

const AVATAR_COLORS = ['blue', 'green', 'purple', 'orange', 'teal', 'pink', 'indigo', 'amber']

function hashUsername(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

export default {
  name: 'Users',
  setup() {
    const toast = useToast()

    // ── Data ──────────────────────────────────────────────────────────────────
    const users = ref([])
    const allHosts = ref([])
    const loading = ref(false)
    const loadingHosts = ref(false)
    const creating = ref(false)
    const updating = ref(false)
    const deleting = ref(false)
    const invalidatingSession = ref(false)

    // ── Filters & Sort ────────────────────────────────────────────────────────
    const searchQuery = ref('')
    const roleFilter = ref('all')
    const twoFaFilter = ref('all')
    const statusFilter = ref('all')
    const sortKey = ref('username')
    const sortDir = ref(1)

    // ── Selection ─────────────────────────────────────────────────────────────
    const selectedIds = ref(new Set())

    // ── Modals ────────────────────────────────────────────────────────────────
    const showCreateModal = ref(false)
    const showEditModal = ref(false)
    const showDeleteModal = ref(false)
    const showCreatePassword = ref(false)
    const showEditPassword = ref(false)
    const editResetMode = ref(false)
    const bulkDeleteMode = ref(false)
    const deleteTarget = ref(null)

    // ── Create form ───────────────────────────────────────────────────────────
    const createForm = ref({
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
      role: 'viewer',
      selectedHosts: [],
    })

    // ── Edit form ─────────────────────────────────────────────────────────────
    const editForm = ref({
      id: null,
      username: '',
      email: '',
      role: '',
      is_active: true,
      totp_enabled: false,
      newPassword: '',
      confirmNewPassword: '',
      selectedHosts: [],
    })
    const loadingEditHostPerms = ref(false)
    const savingEditHostPerms = ref(false)
    const originalEditHostIds = ref([])

    // ── Drawer ────────────────────────────────────────────────────────────────
    const showDrawer = ref(false)
    const drawerUser = ref(null)
    const drawerHostPerms = ref([])
    const drawerLoginHistory = ref([])
    const loadingDrawerData = ref(false)

    // ── Role Options ──────────────────────────────────────────────────────────
    const roleOptions = [
      { value: 'admin', label: 'Admin', description: 'Full access to all resources and settings', badgeClass: 'badge-danger' },
      { value: 'operator', label: 'Operator', description: 'Can manage VMs and hosts, no user administration', badgeClass: 'badge-warning' },
      { value: 'viewer', label: 'Viewer', description: 'Read-only access to permitted hosts', badgeClass: 'badge-info' },
    ]

    // ── Computed ──────────────────────────────────────────────────────────────
    const filteredUsers = computed(() => {
      let list = users.value
      if (roleFilter.value !== 'all') {
        list = list.filter(u => u.role === roleFilter.value)
      }
      if (twoFaFilter.value === 'enabled') list = list.filter(u => u.totp_enabled)
      if (twoFaFilter.value === 'disabled') list = list.filter(u => !u.totp_enabled)
      if (statusFilter.value === 'active') list = list.filter(u => u.is_active)
      if (statusFilter.value === 'disabled') list = list.filter(u => !u.is_active)
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase().trim()
        list = list.filter(u =>
          u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
        )
      }
      return list
    })

    const sortedUsers = computed(() => {
      return [...filteredUsers.value].sort((a, b) => {
        let av = a[sortKey.value]
        let bv = b[sortKey.value]
        if (av === null || av === undefined) av = ''
        if (bv === null || bv === undefined) bv = ''
        if (typeof av === 'boolean') av = av ? 1 : 0
        if (typeof bv === 'boolean') bv = bv ? 1 : 0
        if (av < bv) return -sortDir.value
        if (av > bv) return sortDir.value
        return 0
      })
    })

    const allSelected = computed(() =>
      filteredUsers.value.length > 0 && filteredUsers.value.every(u => selectedIds.value.has(u.id))
    )
    const someSelected = computed(() =>
      filteredUsers.value.some(u => selectedIds.value.has(u.id)) && !allSelected.value
    )

    // ── Sort ──────────────────────────────────────────────────────────────────
    const setSort = (key) => {
      if (sortKey.value === key) sortDir.value *= -1
      else { sortKey.value = key; sortDir.value = 1 }
    }
    const sortIcon = (key) => {
      if (sortKey.value !== key) return '⇅'
      return sortDir.value === 1 ? '↑' : '↓'
    }

    // ── Selection ─────────────────────────────────────────────────────────────
    const toggleSelect = (id) => {
      const s = new Set(selectedIds.value)
      s.has(id) ? s.delete(id) : s.add(id)
      selectedIds.value = s
    }
    const toggleSelectAll = () => {
      if (allSelected.value) {
        const s = new Set(selectedIds.value)
        filteredUsers.value.forEach(u => s.delete(u.id))
        selectedIds.value = s
      } else {
        const s = new Set(selectedIds.value)
        filteredUsers.value.forEach(u => s.add(u.id))
        selectedIds.value = s
      }
    }

    // ── Fetch Data ────────────────────────────────────────────────────────────
    const fetchUsers = async () => {
      loading.value = true
      try {
        const response = await api.users.list()
        users.value = response.data
      } catch {
        toast.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const fetchHosts = async () => {
      loadingHosts.value = true
      try {
        const resp = await api.proxmox.listHosts()
        allHosts.value = resp.data || []
      } catch {
        // silently fail — hosts optional
      } finally {
        loadingHosts.value = false
      }
    }

    // ── Create User ───────────────────────────────────────────────────────────
    const openCreateModal = () => {
      createForm.value = { username: '', email: '', password: '', confirmPassword: '', role: 'viewer', selectedHosts: [] }
      showCreatePassword.value = false
      showCreateModal.value = true
      if (allHosts.value.length === 0) fetchHosts()
    }

    const createUser = async () => {
      if (createForm.value.password !== createForm.value.confirmPassword) {
        toast.error('Passwords do not match')
        return
      }
      creating.value = true
      try {
        const resp = await api.users.create({
          username: createForm.value.username,
          email: createForm.value.email,
          password: createForm.value.password,
          role: createForm.value.role,
        })
        const newUserId = resp.data.id
        // Grant host permissions (non-admin, if any selected)
        if (createForm.value.role !== 'admin' && createForm.value.selectedHosts.length > 0) {
          await Promise.allSettled(
            createForm.value.selectedHosts.map(hostId =>
              api.users.grantHostPermission(newUserId, { host_id: hostId, can_view: true, can_manage: false, can_admin: false })
            )
          )
        }
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

    // ── Edit User ─────────────────────────────────────────────────────────────
    const openEditModal = async (user) => {
      editForm.value = {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        is_active: user.is_active,
        totp_enabled: user.totp_enabled,
        newPassword: '',
        confirmNewPassword: '',
        selectedHosts: [],
      }
      editResetMode.value = false
      showEditPassword.value = false
      showEditModal.value = true

      // Load host perms and hosts in parallel
      loadingEditHostPerms.value = true
      if (allHosts.value.length === 0) fetchHosts()
      try {
        const permsResp = await api.users.listHostPermissions(user.id)
        const currentHostIds = (permsResp.data || []).map(p => p.host_id)
        editForm.value.selectedHosts = [...currentHostIds]
        originalEditHostIds.value = [...currentHostIds]
      } catch {
        // ignore
      } finally {
        loadingEditHostPerms.value = false
      }
    }

    const updateUser = async () => {
      if (editForm.value.newPassword && editForm.value.newPassword !== editForm.value.confirmNewPassword) {
        toast.error('Passwords do not match')
        return
      }
      updating.value = true
      try {
        // Update basic user fields
        const patchData = {
          email: editForm.value.email,
          role: editForm.value.role,
          is_active: editForm.value.is_active,
        }
        await api.users.patch(editForm.value.id, patchData)

        // Handle password reset if provided
        if (editForm.value.newPassword) {
          await api.users.setPassword(editForm.value.id, editForm.value.newPassword)
        }

        // Sync host permissions (diff approach)
        if (editForm.value.role !== 'admin') {
          savingEditHostPerms.value = true
          const newSelected = new Set(editForm.value.selectedHosts)
          const oldSelected = new Set(originalEditHostIds.value)
          const toGrant = [...newSelected].filter(id => !oldSelected.has(id))
          const toRevoke = [...oldSelected].filter(id => !newSelected.has(id))
          await Promise.allSettled([
            ...toGrant.map(hostId =>
              api.users.grantHostPermission(editForm.value.id, { host_id: hostId, can_view: true, can_manage: false, can_admin: false })
            ),
            ...toRevoke.map(hostId =>
              api.users.revokeHostPermission(editForm.value.id, hostId)
            ),
          ])
          savingEditHostPerms.value = false
        }

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

    // ── Toggle Status ─────────────────────────────────────────────────────────
    const toggleStatus = async (user) => {
      const action = user.is_active ? 'Disable' : 'Enable'
      if (!confirm(`${action} ${user.username}?`)) return
      try {
        await api.users.setStatus(user.id, !user.is_active)
        toast.success(`User ${action.toLowerCase()}d`)
        await fetchUsers()
        if (drawerUser.value?.id === user.id) {
          drawerUser.value = { ...drawerUser.value, is_active: !user.is_active }
        }
      } catch (error) {
        toast.error(error.response?.data?.detail || `Failed to ${action.toLowerCase()} user`)
      }
    }

    // ── Disable TOTP ──────────────────────────────────────────────────────────
    const disableTotp = async (user) => {
      if (!confirm(`Force-disable 2FA for ${user.username}? Use only for account recovery.`)) return
      try {
        await api.users.disableTotp(user.id)
        toast.success(`2FA disabled for ${user.username}`)
        editForm.value.totp_enabled = false
        await fetchUsers()
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to disable 2FA')
      }
    }

    // ── Invalidate Sessions ───────────────────────────────────────────────────
    const invalidateSessions = async (userId) => {
      if (!confirm('Invalidate all active sessions for this user?')) return
      invalidatingSession.value = true
      try {
        await api.users.invalidateSessions(userId)
        toast.success('All sessions invalidated')
      } catch (error) {
        toast.error('Failed to invalidate sessions')
      } finally {
        invalidatingSession.value = false
      }
    }

    // ── Delete ────────────────────────────────────────────────────────────────
    const confirmDelete = (user) => {
      deleteTarget.value = user
      bulkDeleteMode.value = false
      showDeleteModal.value = true
    }

    const confirmBulkDelete = () => {
      bulkDeleteMode.value = true
      showDeleteModal.value = true
    }

    const doDelete = async () => {
      deleting.value = true
      try {
        if (bulkDeleteMode.value) {
          const ids = [...selectedIds.value]
          await Promise.allSettled(ids.map(id => api.users.delete(id)))
          toast.success(`${ids.length} user(s) deleted`)
          selectedIds.value = new Set()
        } else {
          await api.users.delete(deleteTarget.value.id)
          toast.success('User deleted')
        }
        showDeleteModal.value = false
        await fetchUsers()
      } catch (error) {
        toast.error('Failed to delete user(s)')
      } finally {
        deleting.value = false
      }
    }

    // ── Bulk Actions ──────────────────────────────────────────────────────────
    const bulkSetStatus = async (isActive) => {
      const ids = [...selectedIds.value]
      const label = isActive ? 'enable' : 'disable'
      if (!confirm(`${label.charAt(0).toUpperCase() + label.slice(1)} ${ids.length} user(s)?`)) return
      try {
        await Promise.allSettled(ids.map(id => api.users.setStatus(id, isActive)))
        toast.success(`${ids.length} user(s) ${label}d`)
        selectedIds.value = new Set()
        await fetchUsers()
      } catch {
        toast.error(`Failed to ${label} some users`)
      }
    }
    const bulkEnable = () => bulkSetStatus(true)
    const bulkDisable = () => bulkSetStatus(false)

    // ── Drawer ────────────────────────────────────────────────────────────────
    const openDrawer = async (user) => {
      drawerUser.value = user
      drawerHostPerms.value = []
      drawerLoginHistory.value = []
      showDrawer.value = true
      loadingDrawerData.value = true
      try {
        const [permsResp, historyResp] = await Promise.allSettled([
          api.users.listHostPermissions(user.id),
          api.users.getLoginHistory(user.id, 5),
        ])
        if (permsResp.status === 'fulfilled') drawerHostPerms.value = permsResp.value.data || []
        if (historyResp.status === 'fulfilled') drawerLoginHistory.value = historyResp.value.data || []
      } finally {
        loadingDrawerData.value = false
      }
    }

    const closeDrawer = () => {
      showDrawer.value = false
      drawerUser.value = null
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    const getInitials = (name) => {
      if (!name) return '?'
      return name.slice(0, 2).toUpperCase()
    }

    const getAvatarColor = (name) => {
      if (!name) return AVATAR_COLORS[0]
      return AVATAR_COLORS[hashUsername(name) % AVATAR_COLORS.length]
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

    const formatDateRelative = (d) => {
      if (!d) return '—'
      const diff = Date.now() - new Date(d).getTime()
      const mins = Math.floor(diff / 60000)
      if (mins < 1) return 'just now'
      if (mins < 60) return `${mins}m ago`
      const hrs = Math.floor(mins / 60)
      if (hrs < 24) return `${hrs}h ago`
      const days = Math.floor(hrs / 24)
      if (days < 30) return `${days}d ago`
      return new Date(d).toLocaleDateString()
    }

    onMounted(() => {
      fetchUsers()
      fetchHosts()
    })

    return {
      users, allHosts, loading, loadingHosts,
      creating, updating, deleting, invalidatingSession,
      searchQuery, roleFilter, twoFaFilter, statusFilter,
      sortKey, sortDir, setSort, sortIcon,
      selectedIds, allSelected, someSelected, toggleSelect, toggleSelectAll,
      filteredUsers, sortedUsers,
      showCreateModal, showEditModal, showDeleteModal,
      showCreatePassword, showEditPassword, editResetMode,
      bulkDeleteMode, deleteTarget,
      createForm, editForm,
      loadingEditHostPerms, savingEditHostPerms,
      roleOptions,
      openCreateModal, createUser,
      openEditModal, updateUser,
      toggleStatus, disableTotp, invalidateSessions,
      confirmDelete, confirmBulkDelete, doDelete,
      bulkEnable, bulkDisable,
      showDrawer, drawerUser, drawerHostPerms, drawerLoginHistory, loadingDrawerData,
      openDrawer, closeDrawer,
      getInitials, getAvatarColor,
      formatRole, getRoleBadgeClass, formatDate, formatDateShort, formatDateRelative,
    }
  }
}
</script>

<style scoped>
/* ── Page ──────────────────────────────────────────────── */
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

/* ── Toolbar ────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  flex-wrap: wrap;
}

.search-input {
  width: 220px;
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.filter-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  margin-right: 0.1rem;
}

.ml-auto {
  margin-left: auto;
}

/* ── Bulk Bar ────────────────────────────────────────────── */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--primary-color, #3b82f6);
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary-color, #3b82f6) 30%, transparent);
  flex-wrap: wrap;
}

/* ── Table ──────────────────────────────────────────────── */
.table-container {
  padding: 0;
  overflow-x: auto;
}

.th-check, .td-check {
  width: 2rem;
  padding-left: 1rem;
}

.th-avatar {
  width: 2.5rem;
}

.sortable {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.sortable:hover {
  color: var(--primary-color);
}

.sort-icon {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.action-btns {
  display: flex;
  gap: 0.35rem;
  flex-wrap: nowrap;
}

.row-disabled td {
  opacity: 0.55;
}

.row-selected {
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 6%, transparent);
}

/* ── Avatar Badge ───────────────────────────────────────── */
.avatar-badge {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.avatar-badge.avatar-lg {
  width: 3rem;
  height: 3rem;
  font-size: 1rem;
}

.avatar-blue    { background: #3b82f6; }
.avatar-green   { background: #10b981; }
.avatar-purple  { background: #8b5cf6; }
.avatar-orange  { background: #f59e0b; }
.avatar-teal    { background: #14b8a6; }
.avatar-pink    { background: #ec4899; }
.avatar-indigo  { background: #6366f1; }
.avatar-amber   { background: #d97706; }

/* ── Username button ────────────────────────────────────── */
.username-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--primary-color, #3b82f6);
  text-decoration: underline;
  font-size: inherit;
}

.username-btn:hover {
  opacity: 0.8;
}

/* ── Empty state ────────────────────────────────────────── */
.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}

/* ── Modal ──────────────────────────────────────────────── */
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
  max-height: 92vh;
  overflow-y: auto;
}

.modal-sm { max-width: 360px; }
.modal-lg { max-width: 680px; }

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  background: var(--card-bg);
  z-index: 1;
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

.modal-body { padding: 1.5rem; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

/* ── Forms ──────────────────────────────────────────────── */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
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
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-control:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-control.input-error {
  border-color: var(--danger-color, #ef4444);
}

.form-hint {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  margin-bottom: 0;
}

.form-error {
  color: var(--danger-color, #ef4444);
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

/* ── Role Selector ──────────────────────────────────────── */
.role-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.role-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.role-option:hover {
  border-color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 5%, transparent);
}

.role-option-selected {
  border-color: var(--primary-color);
  background: color-mix(in srgb, var(--primary-color, #3b82f6) 8%, transparent);
}

.role-radio {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

.role-option-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.role-desc {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* ── Host Checkboxes ────────────────────────────────────── */
.host-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.host-checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.host-checkbox-item:hover {
  border-color: var(--primary-color);
}

/* ── Section Divider ────────────────────────────────────── */
.section-divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1.25rem 0 0.75rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.section-divider::before, .section-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color);
}

/* ── 2FA row in edit ────────────────────────────────────── */
.two-fa-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* ── Buttons ────────────────────────────────────────────── */
.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
}

.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }

/* ── Drawer ─────────────────────────────────────────────── */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.drawer {
  background: var(--card-bg);
  width: 400px;
  max-width: 95vw;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.2);
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.drawer-title-row {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.drawer-title-row h3 {
  margin: 0 0 0.1rem;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem;
}

.drawer-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 0.5rem;
}

.drawer-section {
  margin-bottom: 1.5rem;
}

.drawer-section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin: 0 0 0.75rem;
}

/* ── Info Grid ──────────────────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.info-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── Host Perm List ─────────────────────────────────────── */
.host-perm-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.host-perm-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.host-perm-name {
  font-weight: 500;
}

.host-perm-badges {
  display: flex;
  gap: 0.25rem;
}

.badge-xs {
  padding: 0.1rem 0.4rem;
  font-size: 0.7rem;
}

/* ── Login History ──────────────────────────────────────── */
.login-history-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.login-history-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0;
}

.login-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.login-dot-success { background: var(--success-color, #10b981); }
.login-dot-fail    { background: var(--danger-color, #ef4444); }

.login-history-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.text-xs { font-size: 0.75rem; }
</style>
