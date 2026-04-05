<template>
  <div class="pve-users-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header-main">
        <h2>Proxmox Users &amp; Permissions</h2>
        <p class="text-muted">Manage users, groups, roles and ACL entries across your Proxmox hosts</p>
      </div>
      <!-- Host selector -->
      <div class="host-selector-wrap">
        <label class="form-label" style="margin-bottom: 0.25rem;">Host</label>
        <select v-model="selectedHostId" class="form-control host-select" @change="onHostChange">
          <option value="" disabled>Select a host...</option>
          <option v-for="h in hosts" :key="h.id" :value="h.id">
            {{ h.name || h.hostname }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="!selectedHostId" class="empty-state">
      <p>Select a Proxmox host above to manage its users and permissions.</p>
    </div>

    <template v-else>
      <!-- Tab Bar -->
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['tab-btn', { active: activeTab === tab.id }]"
          @click="switchTab(tab.id)"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          {{ tab.label }}
          <span v-if="tab.id === 'users' && users.length" class="tab-count">{{ users.length }}</span>
          <span v-if="tab.id === 'groups' && groups.length" class="tab-count">{{ groups.length }}</span>
          <span v-if="tab.id === 'acl' && aclEntries.length" class="tab-count">{{ aclEntries.length }}</span>
        </button>
      </div>

      <!-- ═══════════════════════════════════════════ USERS TAB ═══════════════ -->
      <div v-if="activeTab === 'users'" class="card">
        <div class="card-header">
          <h3>Users</h3>
          <button @click="openAddUserModal" class="btn btn-primary">+ Add User</button>
        </div>

        <div v-if="loading" class="loading-spinner"></div>

        <div v-else-if="users.length === 0" class="empty-card">
          <p>No users found on this host.</p>
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
                <th>Expires</th>
                <th>2FA</th>
                <th>Enabled</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.userid">
                <td><strong>{{ user.userid }}</strong></td>
                <td>{{ [user.firstname, user.lastname].filter(Boolean).join(' ') || '—' }}</td>
                <td class="text-sm">{{ user.email || '—' }}</td>
                <td>
                  <span :class="['badge', user.userid.endsWith('@pam') ? 'badge-warning' : 'badge-info']">
                    {{ extractRealm(user.userid) }}
                  </span>
                </td>
                <td class="text-sm">{{ user.groups || '—' }}</td>
                <td class="text-sm">
                  <span v-if="user.expire && user.expire > 0" :class="['expiry-badge', expiryClass(user.expire)]">
                    {{ formatExpiry(user.expire) }}
                  </span>
                  <span v-else class="text-muted">Never</span>
                </td>
                <td>
                  <span v-if="user.keys" class="badge badge-success" title="TOTP/Keys configured">2FA</span>
                  <span v-else class="text-muted text-sm">—</span>
                </td>
                <td>
                  <span :class="['badge', isEnabled(user) ? 'badge-success' : 'badge-danger']">
                    {{ isEnabled(user) ? 'Enabled' : 'Disabled' }}
                  </span>
                </td>
                <td>
                  <div class="action-btns">
                    <button @click="openEditUserModal(user)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="openTokens(user)" class="btn btn-outline btn-sm">Tokens</button>
                    <button @click="openUserPermissions(user)" class="btn btn-outline btn-sm">ACL</button>
                    <button
                      v-if="!isRootUser(user.userid)"
                      @click="deleteUser(user.userid)"
                      class="btn btn-danger btn-sm"
                    >Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ══════════════════════════════════════════ GROUPS TAB ══════════════ -->
      <div v-if="activeTab === 'groups'" class="card">
        <div class="card-header">
          <h3>Groups</h3>
          <button @click="openCreateGroupModal" class="btn btn-primary">+ Create Group</button>
        </div>

        <div v-if="loadingGroups" class="loading-spinner"></div>

        <div v-else-if="groups.length === 0" class="empty-card">
          <p>No groups found on this host.</p>
        </div>

        <div v-else>
          <div class="table-container">
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
                <template v-for="group in groups" :key="group.groupid">
                  <tr>
                    <td><strong>{{ group.groupid }}</strong></td>
                    <td class="text-sm">{{ group.comment || '—' }}</td>
                    <td>
                      <button
                        @click="toggleGroupExpand(group.groupid)"
                        class="btn btn-outline btn-sm"
                      >
                        {{ expandedGroups.has(group.groupid) ? 'Hide' : 'Show' }}
                        ({{ group.members ? group.members.length : 0 }})
                      </button>
                    </td>
                    <td>
                      <div class="action-btns">
                        <button @click="openAddMemberModal(group)" class="btn btn-outline btn-sm">+ Member</button>
                        <button @click="deleteGroup(group.groupid)" class="btn btn-danger btn-sm">Delete</button>
                      </div>
                    </td>
                  </tr>
                  <!-- Expanded members row -->
                  <tr v-if="expandedGroups.has(group.groupid)">
                    <td colspan="4" class="members-row">
                      <div v-if="group.members && group.members.length > 0" class="members-list">
                        <div v-for="member in group.members" :key="member" class="member-chip">
                          <span>{{ member }}</span>
                          <button
                            @click="removeMemberFromGroup(group, member)"
                            class="member-remove-btn"
                            title="Remove from group"
                          >×</button>
                        </div>
                      </div>
                      <p v-else class="text-muted text-sm" style="margin: 0;">No members in this group.</p>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════ ROLES TAB ══════════════ -->
      <div v-if="activeTab === 'roles'" class="card">
        <div class="card-header">
          <h3>Roles</h3>
          <button @click="openCreateRoleModal" class="btn btn-primary">+ Create Role</button>
        </div>

        <div v-if="loadingRolesList" class="loading-spinner"></div>

        <div v-else-if="rolesList.length === 0" class="empty-card">
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
                  <td><strong>{{ role.roleid }}</strong></td>
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
                      {{ countPrivileges(role) }} privs
                    </button>
                  </td>
                  <td>
                    <div class="action-btns">
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
                <tr v-if="expandedRoles.has(role.roleid)">
                  <td colspan="4" class="privs-row">
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

      <!-- ═══════════════════════════════════════════ ACL TAB ════════════════ -->
      <div v-if="activeTab === 'acl'" class="card">
        <div class="card-header">
          <h3>Access Control List</h3>
          <button @click="openGrantModal" class="btn btn-primary">+ Grant Permission</button>
        </div>

        <div v-if="loadingAcl" class="loading-spinner"></div>

        <div v-else-if="aclEntries.length === 0" class="empty-card">
          <p>No ACL entries found.</p>
        </div>

        <div v-else>
          <!-- Filter bar -->
          <div class="acl-filter-bar">
            <input
              v-model="aclFilter"
              class="form-control acl-filter-input"
              placeholder="Filter by path, user, group or role..."
            />
            <select v-model="aclTypeFilter" class="form-control acl-type-filter">
              <option value="">All types</option>
              <option value="user">Users</option>
              <option value="group">Groups</option>
              <option value="token">Tokens</option>
            </select>
          </div>

          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Principal</th>
                  <th>Role</th>
                  <th>Propagate</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, idx) in filteredAcl" :key="idx">
                  <td><code class="path-code">{{ entry.path }}</code></td>
                  <td>
                    <span v-if="entry.type === 'group'" class="badge badge-warning acl-type-badge">group</span>
                    <span v-else-if="entry.type === 'token'" class="badge badge-info acl-type-badge">token</span>
                    <span v-else class="badge badge-secondary acl-type-badge">user</span>
                    {{ entry.ugid }}
                  </td>
                  <td><span class="badge badge-info">{{ entry.roleid }}</span></td>
                  <td>
                    <span :class="['badge', entry.propagate ? 'badge-success' : 'badge-secondary']">
                      {{ entry.propagate ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td>
                    <button @click="deleteAclEntry(entry)" class="btn btn-danger btn-sm">Remove</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="text-sm text-muted" style="padding: 0.5rem 1rem;">
            Showing {{ filteredAcl.length }} of {{ aclEntries.length }} entries
          </p>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════ MODALS ═══════════════════════════ -->

    <!-- Add / Edit User Modal -->
    <div v-if="showUserModal" class="modal" @click.self="showUserModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingUser ? 'Edit User' : 'Add Proxmox User' }}</h3>
          <button @click="showUserModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveUser" class="modal-body">
          <div class="form-group">
            <label class="form-label">
              User ID <span class="text-muted text-sm">(user@realm)</span>
            </label>
            <input
              v-model="userForm.userid"
              class="form-control"
              placeholder="admin@pve"
              :disabled="!!editingUser"
              required
            />
          </div>

          <div v-if="!editingUser" class="form-group">
            <label class="form-label">Password</label>
            <input
              v-model="userForm.password"
              type="password"
              autocomplete="new-password"
              class="form-control"
              :required="!editingUser"
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">First Name</label>
              <input v-model="userForm.firstname" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Last Name</label>
              <input v-model="userForm.lastname" class="form-control" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Email</label>
            <input v-model="userForm.email" type="email" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="userForm.comment" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Groups <span class="text-muted text-sm">(comma-separated)</span></label>
            <input v-model="userForm.groups" class="form-control" placeholder="admins,users" />
          </div>

          <div class="form-group">
            <label class="form-label">Expire</label>
            <input v-model="userForm.expireDate" type="date" class="form-control" />
            <p class="text-xs text-muted mt-1">Leave empty for never.</p>
          </div>

          <div class="form-check">
            <input type="checkbox" id="user-enabled" v-model="userForm.enableBool" />
            <label for="user-enabled" class="form-label" style="margin: 0;">Account Enabled</label>
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingUser">
              {{ savingUser ? 'Saving...' : (editingUser ? 'Update User' : 'Add User') }}
            </button>
            <button type="button" @click="showUserModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Tokens Modal -->
    <div v-if="showTokensModal" class="modal" @click.self="showTokensModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>API Tokens — {{ selectedUser?.userid }}</h3>
          <button @click="showTokensModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <h4 class="section-heading">Existing Tokens</h4>
          <div v-if="loadingTokens" class="loading-spinner"></div>
          <div v-else-if="tokens.length === 0" class="text-muted text-sm" style="margin-bottom: 1.5rem;">
            No API tokens for this user.
          </div>
          <div v-else class="table-container" style="margin-bottom: 1.5rem;">
            <table class="table">
              <thead>
                <tr>
                  <th>Full Token ID</th>
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
                    <code>{{ selectedUser?.userid }}!{{ token.tokenid }}</code>
                  </td>
                  <td class="text-sm">{{ token.comment || '—' }}</td>
                  <td class="text-sm">
                    <span v-if="token.expire && token.expire > 0" :class="['expiry-badge', expiryClass(token.expire)]">
                      {{ formatExpiry(token.expire) }}
                    </span>
                    <span v-else class="text-muted">Never</span>
                  </td>
                  <td>
                    <span :class="['badge', token.privsep !== 0 ? 'badge-warning' : 'badge-success']">
                      {{ token.privsep !== 0 ? 'Yes' : 'No' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ token.ctime ? formatDate(token.ctime) : '—' }}</td>
                  <td>
                    <div class="action-btns">
                      <button
                        @click="copyText(selectedUser?.userid + '!' + token.tokenid)"
                        class="btn btn-outline btn-sm"
                      >Copy ID</button>
                      <button @click="revokeToken(token.tokenid)" class="btn btn-danger btn-sm">Revoke</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <h4 class="section-heading">Create New Token</h4>
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
            <div class="form-check">
              <input type="checkbox" id="privsep" v-model="newToken.privsepBool" />
              <label for="privsep" class="form-label" style="margin:0;">
                Privilege Separation (limit to user's own permissions)
              </label>
            </div>
            <button type="submit" class="btn btn-primary mt-2" :disabled="savingToken">
              {{ savingToken ? 'Creating...' : 'Create Token' }}
            </button>
          </form>
        </div>
      </div>
    </div>

    <!-- Token Secret Display Modal -->
    <div v-if="showTokenSecretModal" class="modal" @click.self="showTokenSecretModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Token Created</h3>
          <button @click="showTokenSecretModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div class="token-secret-alert">
            <p class="text-sm" style="margin-bottom: 1rem;">
              Save this secret now — it will <strong>not</strong> be shown again:
            </p>
            <div class="token-secret-block">
              <code class="token-secret-value">{{ createdTokenValue }}</code>
              <button @click="copyText(createdTokenValue)" class="btn btn-outline btn-sm">Copy</button>
            </div>
          </div>
          <div style="display:flex; justify-content:flex-end; margin-top:1rem;">
            <button @click="showTokenSecretModal = false" class="btn btn-primary">Done</button>
          </div>
        </div>
      </div>
    </div>

    <!-- User Permissions Modal (read-only ACL view for a specific user) -->
    <div v-if="showPermissionsModal" class="modal" @click.self="showPermissionsModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>ACL Entries — {{ permissionsUser?.userid }}</h3>
          <button @click="showPermissionsModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingPermissions" class="loading-spinner"></div>
          <div v-else-if="userPermissions.length === 0" class="text-muted text-sm">
            No explicit ACL entries for this user.
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
                <tr v-for="(e, i) in userPermissions" :key="i">
                  <td><code class="path-code">{{ e.path }}</code></td>
                  <td><span class="badge badge-info">{{ e.roleid }}</span></td>
                  <td>
                    <span :class="['badge', e.propagate ? 'badge-success' : 'badge-secondary']">
                      {{ e.propagate ? 'Yes' : 'No' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Grant Permission Modal -->
    <div v-if="showGrantModal" class="modal" @click.self="showGrantModal = false">
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
              placeholder="/ or /vms/100 or /nodes/pve"
              required
            />
            <p class="text-xs text-muted mt-1">Use <code>/</code> to grant access to everything.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Principal (user / token / group)</label>
            <input
              v-model="newAcl.ugid"
              class="form-control"
              placeholder="user@pve  or  @groupname  or  user@pve!token"
              required
            />
            <p class="text-xs text-muted mt-1">
              Users: <code>user@realm</code> — Groups: <code>@groupname</code> — Tokens: <code>user@realm!tokenid</code>
            </p>
          </div>

          <div class="form-group">
            <label class="form-label">Role</label>
            <div v-if="loadingRoles" class="text-sm text-muted">Loading roles...</div>
            <select v-else v-model="newAcl.roles" class="form-control" required>
              <option value="" disabled>Select a role</option>
              <option v-for="r in roles" :key="r.roleid" :value="r.roleid">{{ r.roleid }}</option>
            </select>
          </div>

          <div class="form-check">
            <input type="checkbox" id="propagate" v-model="newAcl.propagateBool" />
            <label for="propagate" class="form-label" style="margin:0;">Propagate to sub-paths</label>
          </div>

          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingAcl">
              {{ savingAcl ? 'Granting...' : 'Grant Permission' }}
            </button>
            <button type="button" @click="showGrantModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Role Modal -->
    <div v-if="showRoleModal" class="modal" @click.self="showRoleModal = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>{{ editingRole ? `Edit Role — ${editingRole.roleid}` : 'Create Role' }}</h3>
          <button @click="showRoleModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="saveRole" class="modal-body">
          <div v-if="!editingRole" class="form-group">
            <label class="form-label">Role ID</label>
            <input v-model="roleForm.roleid" class="form-control" placeholder="MyCustomRole" required />
          </div>
          <div class="form-group">
            <label class="form-label">Privileges</label>
            <p class="text-xs text-muted" style="margin-bottom:0.5rem;">
              Select the privileges this role grants:
            </p>
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
          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingRole">
              {{ savingRole ? 'Saving...' : (editingRole ? 'Update Role' : 'Create Role') }}
            </button>
            <button type="button" @click="showRoleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Group Modal -->
    <div v-if="showCreateGroupModal" class="modal" @click.self="showCreateGroupModal = false">
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
          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingGroup">
              {{ savingGroup ? 'Creating...' : 'Create Group' }}
            </button>
            <button type="button" @click="showCreateGroupModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add Member to Group Modal -->
    <div v-if="showAddMemberModal" class="modal" @click.self="showAddMemberModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Member to "{{ addMemberGroup?.groupid }}"</h3>
          <button @click="showAddMemberModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addMemberToGroup" class="modal-body">
          <div class="form-group">
            <label class="form-label">User</label>
            <select v-model="addMemberUserId" class="form-control" required>
              <option value="" disabled>Select a user...</option>
              <option
                v-for="u in usersNotInGroup"
                :key="u.userid"
                :value="u.userid"
              >{{ u.userid }}</option>
            </select>
          </div>
          <div class="modal-actions">
            <button type="submit" class="btn btn-primary" :disabled="savingMember">
              {{ savingMember ? 'Adding...' : 'Add Member' }}
            </button>
            <button type="button" @click="showAddMemberModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'PVEUsers',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    // ── Host selection ────────────────────────────────────────────────────
    const hosts = ref([])
    const selectedHostId = ref(route.query.hostId ? Number(route.query.hostId) : '')

    const fetchHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = (res.data || []).filter(h => h.is_active !== false)
        // Auto-select first host if only one and none was provided
        if (!selectedHostId.value && hosts.value.length === 1) {
          selectedHostId.value = hosts.value[0].id
          loadTabData(activeTab.value)
        }
      } catch (e) {
        console.error('Failed to fetch hosts:', e)
      }
    }

    const onHostChange = () => {
      // Reset all data when host changes
      users.value = []
      groups.value = []
      rolesList.value = []
      aclEntries.value = []
      loadTabData(activeTab.value)
    }

    // ── Tabs ──────────────────────────────────────────────────────────────
    const tabs = [
      { id: 'users',  label: 'Users',        icon: '👤' },
      { id: 'groups', label: 'Groups',       icon: '👥' },
      { id: 'roles',  label: 'Roles',        icon: '🛡️' },
      { id: 'acl',    label: 'Permissions',  icon: '🔑' },
    ]
    const activeTab = ref('users')

    const switchTab = (tabId) => {
      activeTab.value = tabId
      loadTabData(tabId)
    }

    const loadTabData = (tabId) => {
      if (!selectedHostId.value) return
      if (tabId === 'users')  fetchUsers()
      if (tabId === 'groups') fetchGroups()
      if (tabId === 'roles')  fetchRolesList()
      if (tabId === 'acl')   { fetchAcl(); fetchRoles() }
    }

    // ── Users ─────────────────────────────────────────────────────────────
    const users = ref([])
    const loading = ref(false)
    const showUserModal = ref(false)
    const editingUser = ref(null)
    const savingUser = ref(false)

    const userForm = ref({
      userid: '', password: '', firstname: '', lastname: '',
      email: '', comment: '', groups: '', expireDate: '', enableBool: true,
    })

    const fetchUsers = async () => {
      if (!selectedHostId.value) return
      loading.value = true
      try {
        const res = await api.pveNode.listUsers(selectedHostId.value)
        users.value = res.data || []
      } catch (e) {
        toast.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const openAddUserModal = () => {
      editingUser.value = null
      userForm.value = { userid: '', password: '', firstname: '', lastname: '', email: '', comment: '', groups: '', expireDate: '', enableBool: true }
      showUserModal.value = true
    }

    const openEditUserModal = (user) => {
      editingUser.value = user
      const expDate = (user.expire && user.expire > 0)
        ? new Date(user.expire * 1000).toISOString().slice(0, 10)
        : ''
      userForm.value = {
        userid: user.userid,
        password: '',
        firstname: user.firstname || '',
        lastname: user.lastname || '',
        email: user.email || '',
        comment: user.comment || '',
        groups: user.groups || '',
        expireDate: expDate,
        enableBool: isEnabled(user),
      }
      showUserModal.value = true
    }

    const saveUser = async () => {
      savingUser.value = true
      try {
        const payload = {}
        if (userForm.value.firstname) payload.firstname = userForm.value.firstname
        if (userForm.value.lastname)  payload.lastname  = userForm.value.lastname
        if (userForm.value.email)     payload.email     = userForm.value.email
        if (userForm.value.comment)   payload.comment   = userForm.value.comment
        if (userForm.value.groups)    payload.groups    = userForm.value.groups
        payload.enable = userForm.value.enableBool ? 1 : 0
        if (userForm.value.expireDate) {
          payload.expire = Math.floor(new Date(userForm.value.expireDate).getTime() / 1000)
        } else {
          payload.expire = 0
        }

        if (editingUser.value) {
          await api.pveNode.updateUser(selectedHostId.value, encodeURIComponent(editingUser.value.userid), payload)
          toast.success('User updated')
        } else {
          payload.userid   = userForm.value.userid
          payload.password = userForm.value.password
          await api.pveNode.createUser(selectedHostId.value, payload)
          toast.success('User created')
        }
        showUserModal.value = false
        await fetchUsers()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save user')
      } finally {
        savingUser.value = false
      }
    }

    const deleteUser = async (userid) => {
      if (!confirm(`Delete user "${userid}"? This cannot be undone.`)) return
      try {
        await api.pveNode.deleteUser(selectedHostId.value, encodeURIComponent(userid))
        toast.success('User deleted')
        await fetchUsers()
      } catch (e) {
        toast.error('Failed to delete user')
      }
    }

    // ── Tokens ────────────────────────────────────────────────────────────
    const showTokensModal = ref(false)
    const showTokenSecretModal = ref(false)
    const selectedUser = ref(null)
    const tokens = ref([])
    const loadingTokens = ref(false)
    const savingToken = ref(false)
    const createdTokenValue = ref('')
    const newToken = ref({ tokenid: '', comment: '', privsepBool: false })

    const openTokens = async (user) => {
      selectedUser.value = user
      tokens.value = []
      newToken.value = { tokenid: '', comment: '', privsepBool: false }
      createdTokenValue.value = ''
      showTokensModal.value = true
      loadingTokens.value = true
      try {
        const res = await api.pveNode.listUserTokens(selectedHostId.value, encodeURIComponent(user.userid))
        tokens.value = res.data || []
      } catch (e) {
        console.error('Failed to load tokens', e)
      } finally {
        loadingTokens.value = false
      }
    }

    const createToken = async () => {
      if (!selectedUser.value) return
      savingToken.value = true
      try {
        const payload = {}
        if (newToken.value.comment) payload.comment = newToken.value.comment
        payload.privsep = newToken.value.privsepBool ? 1 : 0
        const res = await api.pveNode.createUserToken(
          selectedHostId.value,
          encodeURIComponent(selectedUser.value.userid),
          newToken.value.tokenid,
          payload,
        )
        const secret = res.data?.value || JSON.stringify(res.data)
        createdTokenValue.value = secret
        newToken.value = { tokenid: '', comment: '', privsepBool: false }
        // Refresh token list
        const r2 = await api.pveNode.listUserTokens(selectedHostId.value, encodeURIComponent(selectedUser.value.userid))
        tokens.value = r2.data || []
        showTokenSecretModal.value = true
      } catch (e) {
        toast.error('Failed to create token')
      } finally {
        savingToken.value = false
      }
    }

    const revokeToken = async (tokenid) => {
      if (!selectedUser.value || !confirm(`Revoke token "${tokenid}"?`)) return
      try {
        await api.pveNode.deleteUserToken(selectedHostId.value, encodeURIComponent(selectedUser.value.userid), tokenid)
        toast.success('Token revoked')
        await openTokens(selectedUser.value)
      } catch (e) {
        toast.error('Failed to revoke token')
      }
    }

    // ── User Permissions Modal ─────────────────────────────────────────────
    const showPermissionsModal = ref(false)
    const permissionsUser = ref(null)
    const userPermissions = ref([])
    const loadingPermissions = ref(false)

    const openUserPermissions = async (user) => {
      permissionsUser.value = user
      userPermissions.value = []
      showPermissionsModal.value = true
      loadingPermissions.value = true
      try {
        const res = await api.pveNode.listAcl(selectedHostId.value)
        const all = res.data || []
        userPermissions.value = all.filter(e => e.type === 'user' && e.ugid === user.userid)
      } catch (e) {
        toast.error('Failed to load permissions')
      } finally {
        loadingPermissions.value = false
      }
    }

    // ── Groups ────────────────────────────────────────────────────────────
    const groups = ref([])
    const loadingGroups = ref(false)
    const showCreateGroupModal = ref(false)
    const savingGroup = ref(false)
    const expandedGroups = ref(new Set())
    const newGroup = ref({ groupid: '', comment: '' })

    // Add member
    const showAddMemberModal = ref(false)
    const addMemberGroup = ref(null)
    const addMemberUserId = ref('')
    const savingMember = ref(false)

    const usersNotInGroup = computed(() => {
      if (!addMemberGroup.value) return users.value
      const members = addMemberGroup.value.members || []
      return users.value.filter(u => !members.includes(u.userid))
    })

    const fetchGroups = async () => {
      if (!selectedHostId.value) return
      loadingGroups.value = true
      try {
        const res = await api.pveNode.listGroups(selectedHostId.value)
        // Fetch full details (with member list) for each group
        const basicGroups = res.data || []
        // Try to get member lists by fetching ACL — fall back to basic list
        groups.value = basicGroups
        // Enrich each group with member list if possible via individual GET
        const enriched = await Promise.all(
          basicGroups.map(async (g) => {
            try {
              const detail = await api.pveNode.listGroups(selectedHostId.value)
              // Note: basic list may include members array directly from PVE
              return g
            } catch {
              return g
            }
          })
        )
        groups.value = enriched
      } catch (e) {
        toast.error('Failed to load groups')
      } finally {
        loadingGroups.value = false
      }
    }

    const toggleGroupExpand = (groupid) => {
      const s = new Set(expandedGroups.value)
      s.has(groupid) ? s.delete(groupid) : s.add(groupid)
      expandedGroups.value = s
    }

    const openCreateGroupModal = () => {
      newGroup.value = { groupid: '', comment: '' }
      showCreateGroupModal.value = true
    }

    const createGroup = async () => {
      savingGroup.value = true
      try {
        const payload = { groupid: newGroup.value.groupid }
        if (newGroup.value.comment) payload.comment = newGroup.value.comment
        await api.pveNode.createGroup(selectedHostId.value, payload)
        toast.success('Group created')
        showCreateGroupModal.value = false
        await fetchGroups()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to create group')
      } finally {
        savingGroup.value = false
      }
    }

    const deleteGroup = async (groupid) => {
      if (!confirm(`Delete group "${groupid}"?`)) return
      try {
        await api.pveNode.deleteGroup(selectedHostId.value, groupid)
        toast.success('Group deleted')
        await fetchGroups()
      } catch (e) {
        toast.error('Failed to delete group')
      }
    }

    const openAddMemberModal = (group) => {
      addMemberGroup.value = group
      addMemberUserId.value = ''
      showAddMemberModal.value = true
      // Ensure users list is loaded
      if (users.value.length === 0) fetchUsers()
    }

    const addMemberToGroup = async () => {
      if (!addMemberGroup.value || !addMemberUserId.value) return
      savingMember.value = true
      try {
        // Proxmox uses PUT /access/groups/{groupid} with members param
        // members is a comma-separated list of all members (replace full set)
        const group = addMemberGroup.value
        const currentMembers = group.members ? [...group.members] : []
        if (!currentMembers.includes(addMemberUserId.value)) {
          currentMembers.push(addMemberUserId.value)
        }
        await api.pveNode.updateGroup(selectedHostId.value, group.groupid, {
          members: currentMembers.join(',')
        })
        toast.success(`Added ${addMemberUserId.value} to ${group.groupid}`)
        showAddMemberModal.value = false
        await fetchGroups()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to add member')
      } finally {
        savingMember.value = false
      }
    }

    const removeMemberFromGroup = async (group, userid) => {
      if (!confirm(`Remove ${userid} from group ${group.groupid}?`)) return
      try {
        const newMembers = (group.members || []).filter(m => m !== userid)
        await api.pveNode.updateGroup(selectedHostId.value, group.groupid, {
          members: newMembers.join(',')
        })
        toast.success(`Removed ${userid} from ${group.groupid}`)
        await fetchGroups()
      } catch (e) {
        toast.error('Failed to remove member')
      }
    }

    // ── Roles ─────────────────────────────────────────────────────────────
    const rolesList = ref([])
    const loadingRolesList = ref(false)
    const roles = ref([])
    const loadingRoles = ref(false)
    const expandedRoles = ref(new Set())
    const showRoleModal = ref(false)
    const editingRole = ref(null)
    const savingRole = ref(false)
    const roleForm = ref({ roleid: '', privs: [] })

    const allPrivileges = [
      'Datastore.Allocate', 'Datastore.AllocateSpace', 'Datastore.AllocateTemplate', 'Datastore.Audit',
      'Permissions.Modify',
      'Pool.Allocate', 'Pool.Audit',
      'Realm.AllocateUser',
      'SDN.Allocate', 'SDN.Audit', 'SDN.Use',
      'Sys.Audit', 'Sys.Console', 'Sys.Incoming', 'Sys.Modify', 'Sys.PowerMgmt', 'Sys.Syslog',
      'VM.Allocate', 'VM.Audit', 'VM.Backup', 'VM.Clone',
      'VM.Config.CDROM', 'VM.Config.CPU', 'VM.Config.Cloudinit', 'VM.Config.Disk',
      'VM.Config.HWType', 'VM.Config.Memory', 'VM.Config.MoveConfig', 'VM.Config.Net', 'VM.Config.Options',
      'VM.Console', 'VM.Migrate', 'VM.Monitor', 'VM.PowerMgmt', 'VM.Snapshot', 'VM.Snapshot.Rollback',
    ].sort()

    const fetchRolesList = async () => {
      if (!selectedHostId.value) return
      loadingRolesList.value = true
      try {
        const res = await api.pveNode.listRoles(selectedHostId.value)
        rolesList.value = res.data || []
        roles.value = rolesList.value
      } catch (e) {
        toast.error('Failed to load roles')
      } finally {
        loadingRolesList.value = false
      }
    }

    const fetchRoles = async () => {
      if (roles.value.length > 0) return
      loadingRoles.value = true
      try {
        const res = await api.pveNode.listRoles(selectedHostId.value)
        roles.value = res.data || []
      } catch (e) {
        console.error('Failed to load roles for ACL modal', e)
      } finally {
        loadingRoles.value = false
      }
    }

    const toggleRoleExpand = (roleid) => {
      const s = new Set(expandedRoles.value)
      s.has(roleid) ? s.delete(roleid) : s.add(roleid)
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
          await api.pveNode.updateRole(selectedHostId.value, editingRole.value.roleid, { privs: privString })
          toast.success('Role updated')
        } else {
          await api.pveNode.createRole(selectedHostId.value, { roleid: roleForm.value.roleid, privs: privString })
          toast.success('Role created')
        }
        showRoleModal.value = false
        await fetchRolesList()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save role')
      } finally {
        savingRole.value = false
      }
    }

    const deleteRole = async (roleid) => {
      if (!confirm(`Delete role "${roleid}"?`)) return
      try {
        await api.pveNode.deleteRole(selectedHostId.value, roleid)
        toast.success('Role deleted')
        await fetchRolesList()
      } catch (e) {
        toast.error('Failed to delete role')
      }
    }

    // ── ACL ───────────────────────────────────────────────────────────────
    const aclEntries = ref([])
    const loadingAcl = ref(false)
    const showGrantModal = ref(false)
    const savingAcl = ref(false)
    const aclFilter = ref('')
    const aclTypeFilter = ref('')

    const newAcl = ref({ path: '/', ugid: '', roles: '', propagateBool: true })

    const filteredAcl = computed(() => {
      let list = aclEntries.value
      if (aclTypeFilter.value) {
        list = list.filter(e => e.type === aclTypeFilter.value)
      }
      if (aclFilter.value.trim()) {
        const q = aclFilter.value.toLowerCase()
        list = list.filter(e =>
          e.path?.toLowerCase().includes(q) ||
          e.ugid?.toLowerCase().includes(q) ||
          e.roleid?.toLowerCase().includes(q)
        )
      }
      return list
    })

    const fetchAcl = async () => {
      if (!selectedHostId.value) return
      loadingAcl.value = true
      try {
        const res = await api.pveNode.listAcl(selectedHostId.value)
        aclEntries.value = res.data || []
      } catch (e) {
        toast.error('Failed to load ACL')
      } finally {
        loadingAcl.value = false
      }
    }

    const openGrantModal = async () => {
      newAcl.value = { path: '/', ugid: '', roles: '', propagateBool: true }
      showGrantModal.value = true
      await fetchRoles()
    }

    const grantAcl = async () => {
      savingAcl.value = true
      try {
        // Proxmox API: ugid prefixed with @ for groups
        const ugid = newAcl.value.ugid
        await api.pveNode.updateAcl(selectedHostId.value, {
          path: newAcl.value.path,
          roles: newAcl.value.roles,
          ugid: ugid,
          delete: 0,
          propagate: newAcl.value.propagateBool ? 1 : 0,
        })
        toast.success('Permission granted')
        showGrantModal.value = false
        await fetchAcl()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to grant permission')
      } finally {
        savingAcl.value = false
      }
    }

    const deleteAclEntry = async (entry) => {
      if (!confirm(`Remove role "${entry.roleid}" on "${entry.path}" for "${entry.ugid}"?`)) return
      try {
        await api.pveNode.updateAcl(selectedHostId.value, {
          path: entry.path,
          roles: entry.roleid,
          ugid: entry.ugid,
          delete: 1,
          propagate: entry.propagate ? 1 : 0,
        })
        toast.success('ACL entry removed')
        await fetchAcl()
      } catch (e) {
        toast.error('Failed to remove ACL entry')
      }
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    const extractRealm = (userid) => {
      if (!userid) return '?'
      const parts = userid.split('@')
      return parts.length > 1 ? parts[parts.length - 1] : 'unknown'
    }

    const isEnabled = (user) => user.enable !== false && user.enable !== 0

    const isRootUser = (userid) => userid === 'root@pam'

    const formatExpiry = (epoch) => new Date(epoch * 1000).toLocaleDateString()

    const formatDate = (epoch) => new Date(epoch * 1000).toLocaleDateString()

    const expiryClass = (epoch) => {
      if (!epoch || epoch === 0) return 'expiry-never'
      const diff = epoch - Math.floor(Date.now() / 1000)
      if (diff < 0) return 'expiry-expired'
      if (diff < 30 * 86400) return 'expiry-soon'
      return 'expiry-ok'
    }

    const copyText = async (text) => {
      try {
        await navigator.clipboard.writeText(text)
        toast.success('Copied to clipboard')
      } catch {
        toast.error('Failed to copy')
      }
    }

    onMounted(() => {
      fetchHosts()
      if (selectedHostId.value) fetchUsers()
    })

    return {
      // host
      hosts, selectedHostId, onHostChange,
      // tabs
      tabs, activeTab, switchTab,
      // users
      users, loading, showUserModal, editingUser, savingUser, userForm,
      openAddUserModal, openEditUserModal, saveUser, deleteUser,
      isEnabled, isRootUser, extractRealm,
      // tokens
      showTokensModal, showTokenSecretModal, selectedUser, tokens,
      loadingTokens, savingToken, createdTokenValue, newToken,
      openTokens, createToken, revokeToken,
      // permissions
      showPermissionsModal, permissionsUser, userPermissions, loadingPermissions,
      openUserPermissions,
      // groups
      groups, loadingGroups, showCreateGroupModal, savingGroup, newGroup, expandedGroups,
      openCreateGroupModal, createGroup, deleteGroup, toggleGroupExpand,
      showAddMemberModal, addMemberGroup, addMemberUserId, savingMember, usersNotInGroup,
      openAddMemberModal, addMemberToGroup, removeMemberFromGroup,
      // roles
      rolesList, loadingRolesList, roles, loadingRoles, expandedRoles,
      showRoleModal, editingRole, savingRole, roleForm, allPrivileges,
      toggleRoleExpand, countPrivileges, getPrivileges,
      openCreateRoleModal, openEditRoleModal, saveRole, deleteRole,
      // acl
      aclEntries, loadingAcl, showGrantModal, savingAcl, newAcl,
      filteredAcl, aclFilter, aclTypeFilter,
      openGrantModal, grantAcl, deleteAclEntry,
      // helpers
      formatExpiry, formatDate, expiryClass, copyText,
    }
  }
}
</script>

<style scoped>
/* ── Page header ────────────────────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.page-header-main h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.host-selector-wrap {
  display: flex;
  flex-direction: column;
  min-width: 220px;
}

.host-select {
  min-width: 220px;
}

/* ── Empty state ────────────────────────────────────────────────────────── */
.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
  background: var(--card-bg, #fff);
  border-radius: 0.5rem;
  border: 1px dashed var(--border-color);
}

.empty-card {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
}

/* ── Tab bar ────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
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

.tab-btn:hover { color: var(--text-primary); }

.tab-btn.active {
  color: var(--primary, #3b82f6);
  border-bottom-color: var(--primary, #3b82f6);
}

.tab-icon { font-size: 1rem; }

.tab-count {
  background: var(--primary, #3b82f6);
  color: #fff;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  min-width: 1.4rem;
  text-align: center;
}

/* ── Card ───────────────────────────────────────────────────────────────── */
.card {
  background: var(--card-bg, #fff);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 { margin: 0; font-size: 1.1rem; font-weight: 600; }

/* ── Action buttons ─────────────────────────────────────────────────────── */
.action-btns {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

/* ── Members row ────────────────────────────────────────────────────────── */
.members-row {
  background: var(--background, #f9fafb);
  padding: 0.75rem 1.5rem 1rem;
}

.members-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.member-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 0.15rem 0.5rem 0.15rem 0.6rem;
  font-size: 0.8125rem;
  font-weight: 500;
}

.member-remove-btn {
  background: none;
  border: none;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0;
  opacity: 0.6;
  transition: opacity 0.1s;
}

.member-remove-btn:hover { opacity: 1; }

/* ── Privileges ─────────────────────────────────────────────────────────── */
.privs-row {
  background: var(--background, #f9fafb);
  padding: 0.5rem 1.5rem 1rem;
}

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
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.4rem;
  max-height: 380px;
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

.priv-checkbox-item:hover { background: var(--background, #f3f4f6); }

.priv-name {
  font-size: 0.8125rem;
  font-family: monospace;
  color: var(--text-primary);
}

/* ── ACL filter bar ─────────────────────────────────────────────────────── */
.acl-filter-bar {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.5rem 0;
}

.acl-filter-input { flex: 1; }
.acl-type-filter { width: 140px; }

.path-code {
  font-family: monospace;
  font-size: 0.8125rem;
  background: var(--background, #f3f4f6);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
}

.acl-type-badge { margin-right: 0.35rem; }

/* ── Modals ─────────────────────────────────────────────────────────────── */
.modal {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: var(--card-bg, white);
  border-radius: 0.5rem;
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}

.modal-content.modal-large { max-width: 820px; }

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 { margin: 0; font-size: 1.1rem; font-weight: 600; }

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body { padding: 1.5rem; }

.modal-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.section-heading {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.75rem 0;
  color: var(--text-primary);
}

/* ── Form helpers ────────────────────────────────────────────────────────── */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.mt-2 { margin-top: 0.75rem; }

/* ── Token secret ────────────────────────────────────────────────────────── */
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
  font-size: 0.8125rem;
  word-break: break-all;
  white-space: pre-wrap;
}

/* ── Expiry badges ───────────────────────────────────────────────────────── */
.expiry-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.8125rem;
  font-weight: 500;
}

.expiry-expired { background: #fee2e2; color: #991b1b; }
.expiry-soon    { background: #fef9c3; color: #854d0e; }
.expiry-ok      { background: #dcfce7; color: #166534; }

.badge-secondary {
  background: var(--background, #f3f4f6);
  color: var(--text-secondary, #6b7280);
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8125rem;
}

@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .form-row { grid-template-columns: 1fr; }
  .acl-filter-bar { flex-direction: column; }
  .acl-type-filter { width: 100%; }
}
</style>
