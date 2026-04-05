<template>
  <div class="security-page">
    <div class="page-header">
      <h2>Security</h2>
      <p class="text-muted">Brute force protection, IP access control, GeoIP filtering, session management and password policy</p>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-else>
      <!-- Tab nav -->
      <div class="tab-nav mb-2">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', activeTab === tab.key ? 'tab-active' : '']"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'lockouts' && lockouts.length" class="tab-badge">{{ lockouts.length }}</span>
        </button>
      </div>

      <!-- ── Overview ─────────────────────────────────────────── -->
      <div v-if="activeTab === 'overview'">
        <div class="overview-cards mb-2">
          <div class="overview-card">
            <div class="ov-icon ov-icon-blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <div class="ov-body">
              <div class="ov-value">{{ overviewStats.twofa_count }}</div>
              <div class="ov-label">Users with 2FA</div>
              <div class="ov-sub">of {{ overviewStats.total_users }} total users</div>
            </div>
          </div>
          <div class="overview-card">
            <div class="ov-icon ov-icon-green">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
            </div>
            <div class="ov-body">
              <div class="ov-value">{{ overviewStats.active_sessions }}</div>
              <div class="ov-label">Active Sessions</div>
              <div class="ov-sub">non-expired refresh tokens</div>
            </div>
          </div>
          <div class="overview-card">
            <div class="ov-icon ov-icon-red">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <div class="ov-body">
              <div class="ov-value">{{ overviewStats.failed_logins_24h }}</div>
              <div class="ov-label">Failed Logins (24h)</div>
              <div class="ov-sub">{{ overviewStats.success_rate_24h }}% success rate</div>
            </div>
          </div>
          <div class="overview-card">
            <div class="ov-icon ov-icon-yellow">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
            </div>
            <div class="ov-body">
              <div class="ov-value">{{ overviewStats.ip_entries }}</div>
              <div class="ov-label">IP List Entries</div>
              <div class="ov-sub">{{ overviewStats.lockouts_active }} active lockout{{ overviewStats.lockouts_active !== 1 ? 's' : '' }}</div>
            </div>
          </div>
        </div>

        <div class="card mb-2">
          <div class="card-header"><h3>Recent Activity</h3></div>
          <div v-if="recentActivity.length === 0" class="empty-state">No recent login activity.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>IP</th>
                  <th>Result</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recentActivity" :key="item.id">
                  <td class="text-sm text-muted">{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.username_attempted }}</strong></td>
                  <td><code>{{ item.ip_address }}</code></td>
                  <td>
                    <span :class="['badge', item.success ? 'badge-success' : 'badge-danger']">
                      {{ item.success ? 'Success' : 'Failed' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ item.failure_reason || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>Quick Actions</h3></div>
          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">View Login History</span>
                <span class="setting-desc">Review all authentication attempts with filters and export</span>
              </div>
              <button @click="activeTab = 'history'" class="btn btn-outline btn-sm">Open</button>
            </div>
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Manage IP Access Control</span>
                <span class="setting-desc">Add or modify IP ban/allow entries</span>
              </div>
              <button @click="activeTab = 'iplist'" class="btn btn-outline btn-sm">Open</button>
            </div>
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">2FA Status Overview</span>
                <span class="setting-desc">View and manage 2FA settings for all users</span>
              </div>
              <button @click="activeTab = '2fa'" class="btn btn-outline btn-sm">Open</button>
            </div>
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Compliance Report</span>
                <span class="setting-desc">View security score and recommendations</span>
              </div>
              <button @click="activeTab = 'compliance'" class="btn btn-outline btn-sm">Open</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Brute Force ─────────────────────────────────────── -->
      <div v-if="activeTab === 'brute'">
        <div class="card">
          <div class="card-header">
            <h3>Brute Force Protection</h3>
          </div>
          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Enable protection</span>
                <span class="setting-desc">Lock accounts after repeated failed login attempts</span>
              </div>
              <label class="toggle">
                <input type="checkbox" v-model="settings.brute_force_enabled" />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Max failed attempts</span>
                <span class="setting-desc">Lock the account after this many failures within the window</span>
              </div>
              <input
                v-model.number="settings.brute_force_max_attempts"
                type="number" min="1" max="100"
                class="form-control setting-input"
              />
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Lockout duration</span>
                <span class="setting-desc">How long (in minutes) a locked account stays locked</span>
              </div>
              <div class="input-suffix">
                <input
                  v-model.number="settings.brute_force_lockout_minutes"
                  type="number" min="1" max="1440"
                  class="form-control setting-input"
                />
                <span class="suffix-label">min</span>
              </div>
            </div>

            <div class="section-footer">
              <button @click="saveSettings" class="btn btn-primary" :disabled="savingSettings">
                {{ savingSettings ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Lockouts ────────────────────────────────────────── -->
      <div v-if="activeTab === 'lockouts'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Active Lockouts</h3>
            <button @click="loadLockouts" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="lockouts.length === 0" class="empty-state">
            No accounts are currently locked.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Failed Attempts</th>
                  <th>Locked At</th>
                  <th>Unlocks At</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="lockout in lockouts" :key="lockout.id">
                  <td><strong>{{ lockout.username }}</strong></td>
                  <td>{{ lockout.failed_attempts }}</td>
                  <td class="text-sm text-muted">{{ formatDate(lockout.locked_at) }}</td>
                  <td class="text-sm">{{ formatDate(lockout.locked_until) }}</td>
                  <td>
                    <button @click="unlockAccount(lockout.username)" class="btn btn-outline btn-sm">Unlock</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Recent Failed Logins</h3>
            <button @click="loadFailedLogins" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="failedLogins.length === 0" class="empty-state">
            No recent failed login attempts.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>IP Address</th>
                  <th>Time</th>
                  <th>User Agent</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="attempt in failedLogins" :key="attempt.id">
                  <td>{{ attempt.username }}</td>
                  <td>
                    <div class="flex gap-1" style="align-items:center">
                      <code>{{ attempt.ip_address }}</code>
                      <button
                        @click="quickBanIP(attempt.ip_address)"
                        class="btn btn-danger btn-sm"
                        title="Ban this IP"
                      >Ban</button>
                    </div>
                  </td>
                  <td class="text-sm text-muted">{{ formatDate(attempt.attempted_at) }}</td>
                  <td class="text-sm text-muted ua-cell">{{ attempt.user_agent }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── IP Access Control ───────────────────────────────── -->
      <div v-if="activeTab === 'iplist'">
        <div class="card">
          <div class="card-header">
            <h3>IP Access Control</h3>
            <button @click="showIPModal = true" class="btn btn-primary btn-sm">+ Add Entry</button>
          </div>

          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Mode</span>
                <span class="setting-desc">
                  <strong>Blacklist</strong> blocks listed IPs; all others are allowed.
                  <strong>Whitelist</strong> allows only listed IPs; all others are blocked.
                </span>
              </div>
              <select v-model="settings.ip_list_mode" class="form-control setting-input">
                <option value="blacklist">Blacklist</option>
                <option value="whitelist">Whitelist</option>
              </select>
            </div>
            <div class="section-footer">
              <button @click="saveSettings" class="btn btn-primary" :disabled="savingSettings">
                {{ savingSettings ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>

          <div v-if="ipList.length === 0" class="empty-state">
            No IP entries configured.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>IP / CIDR</th>
                  <th>Type</th>
                  <th>Reason</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in ipList" :key="entry.id">
                  <td><code>{{ entry.ip_address }}</code></td>
                  <td>
                    <span :class="['badge', entry.list_type === 'ban' ? 'badge-danger' : 'badge-success']">
                      {{ entry.list_type === 'ban' ? 'Block' : 'Allow' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ entry.reason || '—' }}</td>
                  <td class="text-sm">{{ entry.expires_at ? formatDate(entry.expires_at) : 'Permanent' }}</td>
                  <td>
                    <span :class="['badge', entry.is_active ? 'badge-success' : 'badge-secondary']">
                      {{ entry.is_active ? 'Active' : 'Disabled' }}
                    </span>
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="toggleIPEntry(entry)" class="btn btn-outline btn-sm">
                        {{ entry.is_active ? 'Disable' : 'Enable' }}
                      </button>
                      <button @click="deleteIPEntry(entry.id)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── GeoIP ───────────────────────────────────────────── -->
      <div v-if="activeTab === 'geoip'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>GeoIP Country Filtering</h3>
            <button @click="showGeoIPModal = true" class="btn btn-primary btn-sm">+ Add Country</button>
          </div>

          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Enable GeoIP filtering</span>
                <span class="setting-desc">Uses ip-api.com — no database file needed. Results are cached 24h per IP.</span>
              </div>
              <label class="toggle">
                <input type="checkbox" v-model="settings.geoip_enabled" />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Mode</span>
                <span class="setting-desc">
                  <strong>Blacklist</strong> blocks listed countries; all others allowed.
                  <strong>Whitelist</strong> allows only listed countries; all others blocked.
                </span>
              </div>
              <select v-model="settings.geoip_mode" class="form-control setting-input">
                <option value="blacklist">Blacklist</option>
                <option value="whitelist">Whitelist</option>
              </select>
            </div>

            <div class="section-footer">
              <button @click="saveSettings" class="btn btn-primary" :disabled="savingSettings">
                {{ savingSettings ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>

          <div v-if="geoipRules.length === 0" class="empty-state">
            No country rules configured.
          </div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr><th>Country</th><th>Code</th><th>Action</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="rule in geoipRules" :key="rule.id">
                  <td>{{ rule.country_name }}</td>
                  <td><code>{{ rule.country_code }}</code></td>
                  <td>
                    <span :class="['badge', rule.action === 'block' ? 'badge-danger' : 'badge-success']">
                      {{ rule.action === 'block' ? 'Block' : 'Allow' }}
                    </span>
                  </td>
                  <td>
                    <span :class="['badge', rule.is_active ? 'badge-success' : 'badge-secondary']">
                      {{ rule.is_active ? 'Active' : 'Disabled' }}
                    </span>
                  </td>
                  <td>
                    <div class="flex gap-1">
                      <button @click="toggleGeoIPRule(rule)" class="btn btn-outline btn-sm">{{ rule.is_active ? 'Disable' : 'Enable' }}</button>
                      <button @click="deleteGeoIPRule(rule.id)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- IP Lookup tool -->
        <div class="card">
          <div class="card-header"><h3>IP Lookup</h3></div>
          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Look up an IP address</span>
                <span class="setting-desc">Check what country any IP resolves to via ip-api.com</span>
              </div>
              <div class="lookup-row">
                <input v-model="lookupIP" class="form-control" placeholder="1.2.3.4" @keyup.enter="lookupIPCountry" />
                <button @click="lookupIPCountry" class="btn btn-outline btn-sm" :disabled="lookingUp">
                  {{ lookingUp ? 'Looking up…' : 'Lookup' }}
                </button>
              </div>
            </div>
            <div v-if="lookupResult" class="lookup-result">
              <div class="stat-list">
                <div class="stat-row"><span>IP</span><span>{{ lookupResult.ip }}</span></div>
                <div class="stat-row"><span>Country</span><span>{{ lookupResult.country || '—' }}</span></div>
                <div class="stat-row"><span>Code</span><span>{{ lookupResult.country_code || '—' }}</span></div>
                <div class="stat-row" v-if="lookupResult.city"><span>City</span><span>{{ lookupResult.city }}</span></div>
                <div class="stat-row" v-if="lookupResult.isp"><span>ISP</span><span>{{ lookupResult.isp }}</span></div>
                <div class="stat-row" v-if="lookupResult.org"><span>Org</span><span>{{ lookupResult.org }}</span></div>
              </div>
              <div class="flex gap-1 mt-1" v-if="lookupResult.country_code">
                <button @click="quickAddCountry(lookupResult, 'block')" class="btn btn-danger btn-sm">Block {{ lookupResult.country_code }}</button>
                <button @click="quickAddCountry(lookupResult, 'allow')" class="btn btn-outline btn-sm">Allow {{ lookupResult.country_code }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Sessions ────────────────────────────────────────── -->
      <div v-if="activeTab === 'sessions'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Session Management</h3>
          </div>
          <div class="section-body">
            <div class="info-box mb-2">
              <strong>How session invalidation works:</strong> Each user has a
              <code>token_version</code> counter. Bumping it immediately rejects any JWT
              with an older version number — effectively signing out that user on their next
              request. There is no live session list (stateless JWTs), but this provides
              forced logout capability without a token blacklist database.
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Invalidate all sessions — all users</span>
                <span class="setting-desc">Forces every user to re-authenticate on their next request</span>
              </div>
              <button @click="invalidateAllSessions" class="btn btn-danger btn-sm" :disabled="invalidatingAll">
                {{ invalidatingAll ? 'Invalidating…' : 'Invalidate All Sessions' }}
              </button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Per-User Session Invalidation</h3>
            <button @click="loadUserList" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="userList.length === 0" class="empty-state">No users found.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in userList" :key="u.id">
                  <td><strong>{{ u.username }}</strong></td>
                  <td>
                    <span :class="['badge', getRoleBadgeClass(u.role)]">{{ formatRole(u.role) }}</span>
                  </td>
                  <td>
                    <span :class="['badge', u.is_active ? 'badge-success' : 'badge-danger']">
                      {{ u.is_active ? 'Active' : 'Disabled' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ formatDate(u.last_login) }}</td>
                  <td>
                    <button @click="invalidateUserSessions(u)" class="btn btn-outline btn-sm">
                      Invalidate Sessions
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Login History ───────────────────────────────────── -->
      <div v-if="activeTab === 'history'">
        <div class="card">
          <div class="card-header">
            <h3>Login History</h3>
            <div class="flex gap-1" style="flex-wrap:wrap;align-items:center;">
              <button @click="exportHistoryCSV" class="btn btn-outline btn-sm">Export CSV</button>
              <button @click="loadLoginHistory" class="btn btn-outline btn-sm">Refresh</button>
            </div>
          </div>

          <!-- Filters bar -->
          <div class="filter-bar">
            <input
              v-model="historySearch"
              class="form-control filter-input"
              placeholder="Filter by username..."
              @input="historyPage = 1"
            />
            <select v-model="historyFilter" class="form-control" style="width:130px" @change="historyPage = 1">
              <option value="all">All</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
            </select>
            <input
              v-model="historyDateFrom"
              type="date"
              class="form-control"
              style="width:140px"
              @change="historyPage = 1"
              title="From date"
            />
            <input
              v-model="historyDateTo"
              type="date"
              class="form-control"
              style="width:140px"
              @change="historyPage = 1"
              title="To date"
            />
            <button @click="clearHistoryFilters" class="btn btn-outline btn-sm" v-if="historySearch || historyFilter !== 'all' || historyDateFrom || historyDateTo">
              Clear
            </button>
          </div>

          <div v-if="paginatedHistory.length === 0" class="empty-state">No login history matches your filters.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Username</th>
                  <th>IP Address</th>
                  <th>Result</th>
                  <th>Reason</th>
                  <th>User Agent</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in paginatedHistory" :key="item.id">
                  <td class="text-sm text-muted" style="white-space:nowrap;">{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.username_attempted }}</strong></td>
                  <td><code>{{ item.ip_address }}</code></td>
                  <td>
                    <span :class="['badge', item.success ? 'badge-success' : 'badge-danger']">
                      {{ item.success ? 'Success' : 'Failed' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ item.failure_reason || '—' }}</td>
                  <td class="text-sm text-muted ua-cell" :title="item.user_agent">{{ truncateUA(item.user_agent) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="filteredHistory.length > historyPageSize" class="pagination-bar">
            <span class="text-sm text-muted">
              {{ filteredHistory.length }} record{{ filteredHistory.length !== 1 ? 's' : '' }}
              &mdash; page {{ historyPage }} of {{ historyTotalPages }}
            </span>
            <div class="pagination-btns">
              <button @click="historyPage = 1" :disabled="historyPage === 1" class="btn btn-outline btn-sm">«</button>
              <button @click="historyPage--" :disabled="historyPage === 1" class="btn btn-outline btn-sm">‹</button>
              <button @click="historyPage++" :disabled="historyPage >= historyTotalPages" class="btn btn-outline btn-sm">›</button>
              <button @click="historyPage = historyTotalPages" :disabled="historyPage >= historyTotalPages" class="btn btn-outline btn-sm">»</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Password Policy ─────────────────────────────────── -->
      <div v-if="activeTab === 'policy'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Password Policy</h3>
          </div>
          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Minimum length</span>
                <span class="setting-desc">Minimum number of characters required for a password</span>
              </div>
              <div class="input-suffix">
                <input
                  v-model.number="passwordPolicy.min_length"
                  type="number" min="6" max="128"
                  class="form-control setting-input"
                />
                <span class="suffix-label">chars</span>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Require uppercase letters</span>
                <span class="setting-desc">Password must contain at least one uppercase letter (A–Z)</span>
              </div>
              <label class="toggle">
                <input type="checkbox" v-model="passwordPolicy.require_uppercase" />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Require numbers</span>
                <span class="setting-desc">Password must contain at least one numeric digit (0–9)</span>
              </div>
              <label class="toggle">
                <input type="checkbox" v-model="passwordPolicy.require_numbers" />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Require symbols</span>
                <span class="setting-desc">Password must contain at least one special character (!@#$%^&*…)</span>
              </div>
              <label class="toggle">
                <input type="checkbox" v-model="passwordPolicy.require_symbols" />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <div class="section-footer">
              <button @click="savePasswordPolicy" class="btn btn-primary" :disabled="savingPolicy">
                {{ savingPolicy ? 'Saving...' : 'Save Policy' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Visual strength indicator -->
        <div class="card">
          <div class="card-header"><h3>Current Policy Requirements</h3></div>
          <div class="section-body">
            <div class="policy-strength">
              <div class="strength-label">
                <span>Policy Strength</span>
                <span :class="['strength-level', policyStrength.cls]">{{ policyStrength.label }}</span>
              </div>
              <div class="strength-bar-wrap">
                <div
                  class="strength-bar-fill"
                  :class="policyStrength.cls"
                  :style="{ width: policyStrength.pct + '%' }"
                ></div>
              </div>
            </div>

            <div class="policy-checklist mt-1">
              <div class="policy-req" :class="passwordPolicy.min_length >= 8 ? 'req-met' : 'req-unmet'">
                <span class="req-icon">{{ passwordPolicy.min_length >= 8 ? '✓' : '✗' }}</span>
                Minimum {{ passwordPolicy.min_length }} characters
                <span class="text-muted text-xs">({{ passwordPolicy.min_length >= 12 ? 'Strong' : passwordPolicy.min_length >= 8 ? 'Acceptable' : 'Weak' }})</span>
              </div>
              <div class="policy-req" :class="passwordPolicy.require_uppercase ? 'req-met' : 'req-unmet'">
                <span class="req-icon">{{ passwordPolicy.require_uppercase ? '✓' : '✗' }}</span>
                Uppercase letters required
              </div>
              <div class="policy-req" :class="passwordPolicy.require_numbers ? 'req-met' : 'req-unmet'">
                <span class="req-icon">{{ passwordPolicy.require_numbers ? '✓' : '✗' }}</span>
                Numbers required
              </div>
              <div class="policy-req" :class="passwordPolicy.require_symbols ? 'req-met' : 'req-unmet'">
                <span class="req-icon">{{ passwordPolicy.require_symbols ? '✓' : '✗' }}</span>
                Symbols required
              </div>
            </div>

            <div class="info-box mt-1" style="margin-top:1rem;">
              <strong>Example compliant password:</strong>
              <code class="example-password">{{ policyExamplePassword }}</code>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Compliance ──────────────────────────────────────── -->
      <div v-if="activeTab === 'compliance'">
        <div class="card mb-2">
          <div class="card-header">
            <h3>Security Score</h3>
            <button @click="loadComplianceData" class="btn btn-outline btn-sm" :disabled="complianceLoading">
              {{ complianceLoading ? 'Loading...' : 'Refresh' }}
            </button>
          </div>
          <div class="section-body">
            <div v-if="complianceLoading" class="empty-state">Loading compliance data...</div>
            <div v-else>
              <div class="score-section">
                <div class="score-circle" :class="scoreClass">
                  <span class="score-number">{{ complianceScore }}</span>
                  <span class="score-label">/ 100</span>
                </div>
                <div class="score-breakdown">
                  <div class="score-item">
                    <span class="score-item-label">2FA Adoption</span>
                    <div class="score-bar-wrap">
                      <div class="score-bar" :style="{ width: complianceData.twofa_pct + '%' }"></div>
                    </div>
                    <span class="score-item-val">{{ complianceData.twofa_pct }}%</span>
                  </div>
                  <div class="score-item">
                    <span class="score-item-label">Admin 2FA</span>
                    <div class="score-bar-wrap">
                      <div class="score-bar" :class="complianceData.all_admins_2fa ? 'bar-green' : 'bar-red'" :style="{ width: complianceData.all_admins_2fa ? '100%' : '0%' }"></div>
                    </div>
                    <span class="score-item-val">{{ complianceData.all_admins_2fa ? '100%' : '0%' }}</span>
                  </div>
                  <div class="score-item">
                    <span class="score-item-label">Password Policy</span>
                    <div class="score-bar-wrap">
                      <div class="score-bar" :class="complianceData.password_policy_score >= 50 ? 'bar-green' : 'bar-red'" :style="{ width: complianceData.password_policy_score + '%' }"></div>
                    </div>
                    <span class="score-item-val">{{ complianceData.password_policy_score }}%</span>
                  </div>
                  <div class="score-item">
                    <span class="score-item-label">Failed Login Rate</span>
                    <div class="score-bar-wrap">
                      <div class="score-bar" :class="complianceData.login_success_rate >= 80 ? 'bar-green' : 'bar-red'" :style="{ width: complianceData.login_success_rate + '%' }"></div>
                    </div>
                    <span class="score-item-val">{{ complianceData.login_success_rate }}% success</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card mb-2">
          <div class="card-header"><h3>Compliance Checklist</h3></div>
          <div class="section-body">
            <div v-if="!complianceLoading" class="checklist">
              <div class="checklist-item" :class="complianceData.all_admins_2fa ? 'check-pass' : 'check-fail'">
                <span class="check-icon">{{ complianceData.all_admins_2fa ? '✓' : '✗' }}</span>
                <div class="check-info">
                  <span class="check-title">2FA enabled for all admins</span>
                  <span class="check-desc">{{ complianceData.all_admins_2fa ? 'All admin accounts have 2FA enabled.' : `${complianceData.admins_without_2fa} admin(s) do not have 2FA enabled.` }}</span>
                </div>
              </div>
              <div class="checklist-item" :class="complianceData.password_policy_configured ? 'check-pass' : 'check-fail'">
                <span class="check-icon">{{ complianceData.password_policy_configured ? '✓' : '✗' }}</span>
                <div class="check-info">
                  <span class="check-title">Password policy configured</span>
                  <span class="check-desc">{{ complianceData.password_policy_configured ? 'Password policy is active with complexity requirements.' : 'No password complexity requirements configured.' }}</span>
                </div>
              </div>
              <div class="checklist-item check-pass">
                <span class="check-icon">✓</span>
                <div class="check-info">
                  <span class="check-title">Audit logging active</span>
                  <span class="check-desc">All user actions are being recorded in the audit log.</span>
                </div>
              </div>
              <div class="checklist-item" :class="complianceData.api_keys_have_expiry ? 'check-pass' : 'check-warn'">
                <span class="check-icon">{{ complianceData.api_keys_have_expiry ? '✓' : '!' }}</span>
                <div class="check-info">
                  <span class="check-title">API keys have expiry dates</span>
                  <span class="check-desc">{{ complianceData.api_keys_have_expiry ? 'All active API keys have expiry dates set.' : `${complianceData.api_keys_no_expiry} API key(s) have no expiry date.` }}</span>
                </div>
              </div>
              <div class="checklist-item" :class="complianceData.no_inactive_users ? 'check-pass' : 'check-warn'">
                <span class="check-icon">{{ complianceData.no_inactive_users ? '✓' : '!' }}</span>
                <div class="check-info">
                  <span class="check-title">No users inactive > 90 days</span>
                  <span class="check-desc">{{ complianceData.no_inactive_users ? 'All users have been active within 90 days.' : `${complianceData.inactive_users_count} user(s) have not logged in within 90 days.` }}</span>
                </div>
              </div>
              <div class="checklist-item" :class="complianceData.brute_force_enabled ? 'check-pass' : 'check-fail'">
                <span class="check-icon">{{ complianceData.brute_force_enabled ? '✓' : '✗' }}</span>
                <div class="check-info">
                  <span class="check-title">Brute force protection enabled</span>
                  <span class="check-desc">{{ complianceData.brute_force_enabled ? 'Account lockout protection is active.' : 'Brute force protection is disabled.' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card mb-2">
          <div class="card-header"><h3>Recommendations</h3></div>
          <div class="section-body">
            <div v-if="!complianceLoading && recommendations.length === 0" class="empty-state">
              No issues found. Your security posture looks good.
            </div>
            <div v-else class="recommendations">
              <div v-for="rec in recommendations" :key="rec.title" class="rec-item" :class="'rec-' + rec.severity">
                <div class="rec-severity">{{ rec.severity.toUpperCase() }}</div>
                <div class="rec-body">
                  <div class="rec-title">{{ rec.title }}</div>
                  <div class="rec-desc">{{ rec.description }}</div>
                </div>
                <button v-if="rec.action" @click="rec.action()" class="btn btn-outline btn-sm">Fix</button>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>Export Compliance Report</h3></div>
          <div class="section-body">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-label">Generate a full compliance report</span>
                <span class="setting-desc">Opens the Audit Log report generator with compliance-relevant filters pre-applied</span>
              </div>
              <button @click="$router.push('/audit-log')" class="btn btn-primary btn-sm">Open Audit Log</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 2FA Overview ────────────────────────────────────── -->
      <div v-if="activeTab === '2fa'">
        <div class="card">
          <div class="card-header">
            <h3>2FA Status Overview</h3>
            <div class="flex gap-1" style="align-items:center;">
              <select v-model="twoFaFilter" class="form-control" style="width:150px">
                <option value="all">All Users</option>
                <option value="enabled">2FA Enabled</option>
                <option value="disabled">2FA Disabled</option>
              </select>
              <button @click="load2faOverview" class="btn btn-outline btn-sm">Refresh</button>
            </div>
          </div>

          <!-- Summary row -->
          <div class="twofa-summary">
            <div class="twofa-stat">
              <span class="twofa-stat-val">{{ twoFaList.filter(u => u.totp_enabled).length }}</span>
              <span class="twofa-stat-label">2FA Enabled</span>
            </div>
            <div class="twofa-stat">
              <span class="twofa-stat-val twofa-stat-warn">{{ twoFaList.filter(u => !u.totp_enabled && u.is_active).length }}</span>
              <span class="twofa-stat-label">Active without 2FA</span>
            </div>
            <div class="twofa-stat">
              <span class="twofa-stat-val twofa-stat-red">{{ twoFaList.filter(u => u.role === 'admin' && !u.totp_enabled).length }}</span>
              <span class="twofa-stat-label">Admins without 2FA</span>
            </div>
          </div>

          <div v-if="filtered2faList.length === 0" class="empty-state">No users match the current filter.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Account</th>
                  <th>2FA</th>
                  <th>Backup Codes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in filtered2faList" :key="u.id">
                  <td><strong>{{ u.username }}</strong></td>
                  <td class="text-sm text-muted">{{ u.email }}</td>
                  <td>
                    <span :class="['badge', getRoleBadgeClass(u.role)]">{{ formatRole(u.role) }}</span>
                  </td>
                  <td>
                    <span :class="['badge', u.is_active ? 'badge-success' : 'badge-danger']">
                      {{ u.is_active ? 'Active' : 'Disabled' }}
                    </span>
                  </td>
                  <td>
                    <span :class="['badge', u.totp_enabled ? 'badge-success' : 'badge-secondary']">
                      {{ u.totp_enabled ? 'Enabled' : 'Disabled' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">
                    <span v-if="u.totp_enabled">
                      {{ u.backup_codes_remaining !== undefined ? u.backup_codes_remaining + ' remaining' : '—' }}
                    </span>
                    <span v-else>—</span>
                  </td>
                  <td>
                    <button
                      v-if="u.totp_enabled"
                      @click="forceDisable2fa(u)"
                      class="btn btn-danger btn-sm"
                      title="Force-disable 2FA for account recovery"
                    >
                      Force Disable 2FA
                    </button>
                    <span v-else class="text-muted text-sm">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="section-body" style="border-top:1px solid var(--border-color); padding-top:1rem">
            <div class="info-box">
              <strong>Force Disable 2FA</strong> is for account recovery when a user has lost access to their
              authenticator app. After disabling, the user can log in with their password and set up 2FA again.
            </div>
          </div>
        </div>
      </div>

    </div><!-- end v-else (not loading) -->

    <!-- ── Add IP Modal ───────────────────────────────────────── -->
    <div v-if="showIPModal" class="modal-overlay" @click.self="showIPModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add IP Entry</h3>
          <button @click="showIPModal = false" class="modal-close">×</button>
        </div>
        <form @submit.prevent="addIPEntry" class="modal-body">
          <div class="form-group">
            <label class="form-label">IP Address or CIDR</label>
            <input v-model="newIP.ip_address" class="form-control" placeholder="203.0.113.5 or 10.0.0.0/8" required />
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <select v-model="newIP.list_type" class="form-control">
              <option value="ban">Block</option>
              <option value="allow">Allow</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Reason <span class="text-muted">(optional)</span></label>
            <input v-model="newIP.reason" class="form-control" placeholder="e.g. Repeated attack attempts" />
          </div>
          <div class="form-group">
            <label class="form-label">Expires <span class="text-muted">(leave blank for permanent)</span></label>
            <input v-model="newIP.expires_at" type="datetime-local" class="form-control" />
          </div>
          <div class="modal-footer">
            <button type="button" @click="showIPModal = false" class="btn btn-outline">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="savingIP">{{ savingIP ? 'Adding...' : 'Add Entry' }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Add GeoIP Modal (searchable country picker) ────────── -->
    <div v-if="showGeoIPModal" class="modal-overlay" @click.self="showGeoIPModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Add Country Rule</h3>
          <button @click="showGeoIPModal = false" class="modal-close">×</button>
        </div>
        <form @submit.prevent="addGeoIPRule" class="modal-body">
          <div class="form-group">
            <label class="form-label">Search Country</label>
            <input v-model="countrySearch" class="form-control" placeholder="Type country name or code…" @input="filterCountries" />
            <div v-if="filteredCountries.length && countrySearch" class="country-dropdown">
              <div
                v-for="c in filteredCountries.slice(0,10)" :key="c.code"
                class="country-option"
                @click="selectCountry(c)"
              >
                {{ c.name }} <span class="text-muted text-xs">({{ c.code }})</span>
              </div>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Selected Country</label>
            <div class="selected-country" v-if="newGeoIP.country_code">
              <code>{{ newGeoIP.country_code }}</code> — {{ newGeoIP.country_name }}
            </div>
            <p v-else class="text-muted text-sm">Search and click a country above</p>
          </div>
          <div class="form-group">
            <label class="form-label">Action</label>
            <select v-model="newGeoIP.action" class="form-control">
              <option value="block">Block</option>
              <option value="allow">Allow</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" @click="showGeoIPModal = false" class="btn btn-outline">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="savingGeoIP || !newGeoIP.country_code">
              {{ savingGeoIP ? 'Adding...' : 'Add Rule' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Security',
  setup() {
    const toast = useToast()
    const loading = ref(true)
    const savingSettings = ref(false)
    const savingIP = ref(false)
    const savingGeoIP = ref(false)
    const savingPolicy = ref(false)
    const invalidatingAll = ref(false)
    const showIPModal = ref(false)
    const showGeoIPModal = ref(false)
    const activeTab = ref('overview')
    const historyFilter = ref('all')
    const historySearch = ref('')
    const historyDateFrom = ref('')
    const historyDateTo = ref('')
    const historyPage = ref(1)
    const historyPageSize = 50
    const twoFaFilter = ref('all')

    const tabs = [
      { key: 'overview',   label: 'Overview' },
      { key: 'brute',      label: 'Brute Force' },
      { key: 'lockouts',   label: 'Lockouts' },
      { key: 'iplist',     label: 'IP Access' },
      { key: 'geoip',      label: 'GeoIP' },
      { key: 'sessions',   label: 'Sessions' },
      { key: 'history',    label: 'Login History' },
      { key: 'policy',     label: 'Password Policy' },
      { key: '2fa',        label: '2FA Overview' },
      { key: 'compliance', label: 'Compliance' },
    ]

    const settings = ref({
      brute_force_enabled: true,
      brute_force_max_attempts: 5,
      brute_force_lockout_minutes: 15,
      ip_list_mode: 'blacklist',
      geoip_enabled: false,
      geoip_mode: 'blacklist',
    })

    const passwordPolicy = ref({
      min_length: 8,
      require_uppercase: false,
      require_numbers: false,
      require_symbols: false,
    })

    const lockouts = ref([])
    const failedLogins = ref([])
    const ipList = ref([])
    const geoipRules = ref([])
    const loginHistory = ref([])
    const userList = ref([])
    const twoFaList = ref([])

    const newIP = ref({ ip_address: '', list_type: 'ban', reason: '', expires_at: '' })
    const newGeoIP = ref({ country_code: '', country_name: '', action: 'block' })

    // Compliance
    const complianceLoading = ref(false)
    const complianceData = ref({
      twofa_pct: 0,
      all_admins_2fa: false,
      admins_without_2fa: 0,
      password_policy_configured: false,
      password_policy_score: 0,
      login_success_rate: 100,
      api_keys_have_expiry: true,
      api_keys_no_expiry: 0,
      no_inactive_users: true,
      inactive_users_count: 0,
      brute_force_enabled: true,
    })

    const complianceScore = computed(() => {
      const d = complianceData.value
      let score = 0
      // 2FA adoption (max 25 pts)
      score += Math.round(d.twofa_pct * 0.25)
      // Admin 2FA (20 pts)
      if (d.all_admins_2fa) score += 20
      // Password policy (15 pts)
      score += Math.round(d.password_policy_score * 0.15)
      // Brute force (15 pts)
      if (d.brute_force_enabled) score += 15
      // Login success rate (15 pts)
      score += Math.round(Math.min(100, d.login_success_rate) * 0.15)
      // API keys with expiry (5 pts)
      if (d.api_keys_have_expiry) score += 5
      // No inactive users (5 pts)
      if (d.no_inactive_users) score += 5
      return Math.min(100, score)
    })

    const scoreClass = computed(() => {
      const s = complianceScore.value
      if (s >= 80) return 'score-good'
      if (s >= 50) return 'score-warn'
      return 'score-bad'
    })

    const recommendations = computed(() => {
      const d = complianceData.value
      const recs = []
      if (!d.all_admins_2fa) {
        recs.push({
          severity: 'high',
          title: 'Enable 2FA for all admin accounts',
          description: `${d.admins_without_2fa} admin account(s) do not have 2FA enabled. This is a critical security risk.`,
          action: () => { activeTab.value = '2fa' },
        })
      }
      if (!d.brute_force_enabled) {
        recs.push({
          severity: 'high',
          title: 'Enable brute force protection',
          description: 'Account lockout protection is disabled. Enable it to prevent password guessing attacks.',
          action: () => { activeTab.value = 'brute' },
        })
      }
      if (!d.password_policy_configured) {
        recs.push({
          severity: 'medium',
          title: 'Configure password policy',
          description: 'No password complexity requirements are set. Configure minimum length and complexity rules.',
          action: () => { activeTab.value = 'policy' },
        })
      }
      if (d.api_keys_no_expiry > 0) {
        recs.push({
          severity: 'medium',
          title: 'Set expiry dates on API keys',
          description: `${d.api_keys_no_expiry} API key(s) have no expiry date. Long-lived keys increase exposure risk.`,
          action: null,
        })
      }
      if (!d.no_inactive_users) {
        recs.push({
          severity: 'low',
          title: 'Review inactive user accounts',
          description: `${d.inactive_users_count} user(s) have not logged in within 90 days. Consider disabling unused accounts.`,
          action: null,
        })
      }
      if (d.login_success_rate < 80) {
        recs.push({
          severity: 'medium',
          title: 'High failed login rate',
          description: `Only ${d.login_success_rate}% of recent login attempts succeeded. Review the login history for potential attacks.`,
          action: () => { activeTab.value = 'history' },
        })
      }
      return recs
    })

    // Filtered login history
    const filteredHistory = computed(() => {
      let list = loginHistory.value
      if (historyFilter.value !== 'all') {
        const success = historyFilter.value === 'success'
        list = list.filter(h => h.success === success)
      }
      if (historySearch.value.trim()) {
        const q = historySearch.value.trim().toLowerCase()
        list = list.filter(h => (h.username_attempted || '').toLowerCase().includes(q) || (h.ip_address || '').toLowerCase().includes(q))
      }
      if (historyDateFrom.value) {
        const from = new Date(historyDateFrom.value)
        list = list.filter(h => new Date(h.timestamp) >= from)
      }
      if (historyDateTo.value) {
        const to = new Date(historyDateTo.value)
        to.setHours(23, 59, 59, 999)
        list = list.filter(h => new Date(h.timestamp) <= to)
      }
      return list
    })

    const historyTotalPages = computed(() => Math.max(1, Math.ceil(filteredHistory.value.length / historyPageSize)))

    const paginatedHistory = computed(() => {
      const start = (historyPage.value - 1) * historyPageSize
      return filteredHistory.value.slice(start, start + historyPageSize)
    })

    // 2FA filtered list
    const filtered2faList = computed(() => {
      if (twoFaFilter.value === 'enabled') return twoFaList.value.filter(u => u.totp_enabled)
      if (twoFaFilter.value === 'disabled') return twoFaList.value.filter(u => !u.totp_enabled)
      return twoFaList.value
    })

    // Overview stats (computed from loaded data)
    const overviewStats = computed(() => {
      const users = twoFaList.value
      const history24h = loginHistory.value.filter(h => {
        const ts = new Date(h.timestamp)
        return (Date.now() - ts.getTime()) < 86400000
      })
      const failed24h = history24h.filter(h => !h.success).length
      const total24h = history24h.length
      const successRate = total24h > 0 ? Math.round(((total24h - failed24h) / total24h) * 100) : 100

      return {
        twofa_count: users.filter(u => u.totp_enabled).length,
        total_users: users.length,
        active_sessions: 0, // Populated separately
        failed_logins_24h: failed24h,
        success_rate_24h: successRate,
        ip_entries: ipList.value.length,
        lockouts_active: lockouts.value.length,
      }
    })

    const recentActivity = computed(() => loginHistory.value.slice(0, 10))

    // Password policy strength
    const policyStrength = computed(() => {
      const p = passwordPolicy.value
      let score = 0
      if (p.min_length >= 8) score += 25
      if (p.min_length >= 12) score += 25
      if (p.require_uppercase) score += 15
      if (p.require_numbers) score += 15
      if (p.require_symbols) score += 20
      let label = 'Weak', cls = 'strength-weak'
      if (score >= 75) { label = 'Strong'; cls = 'strength-strong' }
      else if (score >= 40) { label = 'Moderate'; cls = 'strength-moderate' }
      return { pct: score, label, cls }
    })

    const policyExamplePassword = computed(() => {
      const p = passwordPolicy.value
      let pw = 'mysecret'
      if (p.require_uppercase) pw = 'MySecret'
      if (p.require_numbers) pw += '42'
      if (p.require_symbols) pw += '!'
      while (pw.length < p.min_length) pw += 'x'
      return pw
    })

    // ── Country picker ──
    const countrySearch = ref('')
    const filteredCountries = ref([])
    const COUNTRIES = [
      {code:'AF',name:'Afghanistan'},{code:'AL',name:'Albania'},{code:'DZ',name:'Algeria'},{code:'AD',name:'Andorra'},{code:'AO',name:'Angola'},
      {code:'AR',name:'Argentina'},{code:'AM',name:'Armenia'},{code:'AU',name:'Australia'},{code:'AT',name:'Austria'},{code:'AZ',name:'Azerbaijan'},
      {code:'BH',name:'Bahrain'},{code:'BD',name:'Bangladesh'},{code:'BY',name:'Belarus'},{code:'BE',name:'Belgium'},{code:'BJ',name:'Benin'},
      {code:'BO',name:'Bolivia'},{code:'BA',name:'Bosnia and Herzegovina'},{code:'BR',name:'Brazil'},{code:'BN',name:'Brunei'},{code:'BG',name:'Bulgaria'},
      {code:'BF',name:'Burkina Faso'},{code:'KH',name:'Cambodia'},{code:'CM',name:'Cameroon'},{code:'CA',name:'Canada'},{code:'TD',name:'Chad'},
      {code:'CL',name:'Chile'},{code:'CN',name:'China'},{code:'CO',name:'Colombia'},{code:'CD',name:'Congo (DRC)'},{code:'CG',name:'Congo (Republic)'},
      {code:'CR',name:'Costa Rica'},{code:'HR',name:'Croatia'},{code:'CU',name:'Cuba'},{code:'CY',name:'Cyprus'},{code:'CZ',name:'Czech Republic'},
      {code:'DK',name:'Denmark'},{code:'DO',name:'Dominican Republic'},{code:'EC',name:'Ecuador'},{code:'EG',name:'Egypt'},{code:'SV',name:'El Salvador'},
      {code:'ET',name:'Ethiopia'},{code:'FI',name:'Finland'},{code:'FR',name:'France'},{code:'GA',name:'Gabon'},{code:'GE',name:'Georgia'},
      {code:'DE',name:'Germany'},{code:'GH',name:'Ghana'},{code:'GR',name:'Greece'},{code:'GT',name:'Guatemala'},{code:'GN',name:'Guinea'},
      {code:'HT',name:'Haiti'},{code:'HN',name:'Honduras'},{code:'HK',name:'Hong Kong'},{code:'HU',name:'Hungary'},{code:'IN',name:'India'},
      {code:'ID',name:'Indonesia'},{code:'IR',name:'Iran'},{code:'IQ',name:'Iraq'},{code:'IE',name:'Ireland'},{code:'IL',name:'Israel'},
      {code:'IT',name:'Italy'},{code:'JM',name:'Jamaica'},{code:'JP',name:'Japan'},{code:'JO',name:'Jordan'},{code:'KZ',name:'Kazakhstan'},
      {code:'KE',name:'Kenya'},{code:'KP',name:'North Korea'},{code:'KR',name:'South Korea'},{code:'KW',name:'Kuwait'},{code:'KG',name:'Kyrgyzstan'},
      {code:'LA',name:'Laos'},{code:'LV',name:'Latvia'},{code:'LB',name:'Lebanon'},{code:'LY',name:'Libya'},{code:'LI',name:'Liechtenstein'},
      {code:'LT',name:'Lithuania'},{code:'LU',name:'Luxembourg'},{code:'MK',name:'North Macedonia'},{code:'MG',name:'Madagascar'},{code:'MY',name:'Malaysia'},
      {code:'MV',name:'Maldives'},{code:'ML',name:'Mali'},{code:'MT',name:'Malta'},{code:'MX',name:'Mexico'},{code:'MD',name:'Moldova'},
      {code:'MC',name:'Monaco'},{code:'MN',name:'Mongolia'},{code:'ME',name:'Montenegro'},{code:'MA',name:'Morocco'},{code:'MZ',name:'Mozambique'},
      {code:'MM',name:'Myanmar'},{code:'NA',name:'Namibia'},{code:'NP',name:'Nepal'},{code:'NL',name:'Netherlands'},{code:'NZ',name:'New Zealand'},
      {code:'NI',name:'Nicaragua'},{code:'NG',name:'Nigeria'},{code:'NO',name:'Norway'},{code:'OM',name:'Oman'},{code:'PK',name:'Pakistan'},
      {code:'PS',name:'Palestine'},{code:'PA',name:'Panama'},{code:'PY',name:'Paraguay'},{code:'PE',name:'Peru'},{code:'PH',name:'Philippines'},
      {code:'PL',name:'Poland'},{code:'PT',name:'Portugal'},{code:'QA',name:'Qatar'},{code:'RO',name:'Romania'},{code:'RU',name:'Russia'},
      {code:'RW',name:'Rwanda'},{code:'SA',name:'Saudi Arabia'},{code:'SN',name:'Senegal'},{code:'RS',name:'Serbia'},{code:'SL',name:'Sierra Leone'},
      {code:'SG',name:'Singapore'},{code:'SK',name:'Slovakia'},{code:'SI',name:'Slovenia'},{code:'SO',name:'Somalia'},{code:'ZA',name:'South Africa'},
      {code:'SS',name:'South Sudan'},{code:'ES',name:'Spain'},{code:'LK',name:'Sri Lanka'},{code:'SD',name:'Sudan'},{code:'SE',name:'Sweden'},
      {code:'CH',name:'Switzerland'},{code:'SY',name:'Syria'},{code:'TW',name:'Taiwan'},{code:'TJ',name:'Tajikistan'},{code:'TZ',name:'Tanzania'},
      {code:'TH',name:'Thailand'},{code:'TL',name:'Timor-Leste'},{code:'TG',name:'Togo'},{code:'TN',name:'Tunisia'},{code:'TR',name:'Turkey'},
      {code:'TM',name:'Turkmenistan'},{code:'UG',name:'Uganda'},{code:'UA',name:'Ukraine'},{code:'AE',name:'United Arab Emirates'},
      {code:'GB',name:'United Kingdom'},{code:'US',name:'United States'},{code:'UY',name:'Uruguay'},{code:'UZ',name:'Uzbekistan'},
      {code:'VE',name:'Venezuela'},{code:'VN',name:'Vietnam'},{code:'YE',name:'Yemen'},{code:'ZM',name:'Zambia'},{code:'ZW',name:'Zimbabwe'},
    ]
    const filterCountries = () => {
      const q = countrySearch.value.toLowerCase()
      filteredCountries.value = q ? COUNTRIES.filter(c => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q)) : []
    }
    const selectCountry = (c) => {
      newGeoIP.value.country_code = c.code
      newGeoIP.value.country_name = c.name
      countrySearch.value = c.name
      filteredCountries.value = []
    }

    // ── IP Lookup ──
    const lookupIP = ref('')
    const lookupResult = ref(null)
    const lookingUp = ref(false)
    const lookupIPCountry = async () => {
      if (!lookupIP.value) return
      lookingUp.value = true
      lookupResult.value = null
      try {
        const res = await api.security.lookupIP(lookupIP.value.trim())
        lookupResult.value = res.data
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Lookup failed')
      } finally {
        lookingUp.value = false
      }
    }
    const quickAddCountry = async (info, action) => {
      if (!info.country_code || !info.country) return
      try {
        await api.security.addGeoIPRule({ country_code: info.country_code, country_name: info.country, action })
        toast.success(`${action === 'block' ? 'Blocked' : 'Allowed'} ${info.country}`)
        await loadGeoIPRules()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to add rule')
      }
    }

    // ── Loaders ──
    const loadSettings     = async () => { const r = await api.security.getSettings();    settings.value     = r.data }
    const loadLockouts     = async () => { const r = await api.security.getLockouts();    lockouts.value     = r.data }
    const loadFailedLogins = async () => { const r = await api.security.getFailedLogins();failedLogins.value = r.data }
    const loadIPList       = async () => { const r = await api.security.getIPList();      ipList.value       = r.data }
    const loadGeoIPRules   = async () => { const r = await api.security.getGeoIPRules();  geoipRules.value   = r.data }
    const loadLoginHistory = async () => {
      try {
        const r = await api.security.getLoginHistory(200)
        loginHistory.value = r.data
      } catch (e) {
        loginHistory.value = []
      }
    }
    const loadPasswordPolicy = async () => {
      try {
        const r = await api.security.getPasswordPolicy()
        passwordPolicy.value = r.data
      } catch (e) {
        // defaults already set
      }
    }
    const loadUserList = async () => {
      try {
        const r = await api.users.list()
        userList.value = r.data
      } catch (e) {
        userList.value = []
      }
    }
    const load2faOverview = async () => {
      try {
        const r = await api.security.get2faOverview()
        twoFaList.value = r.data
      } catch (e) {
        twoFaList.value = []
      }
    }

    const loadComplianceData = async () => {
      complianceLoading.value = true
      try {
        // Gather data from multiple endpoints
        const [usersRes, policyRes, settingsRes, loginHistRes, twoFaRes] = await Promise.allSettled([
          api.users.list(),
          api.security.getPasswordPolicy(),
          api.security.getSettings(),
          api.security.getLoginHistory(200),
          api.security.get2faOverview(),
        ])

        const users = usersRes.status === 'fulfilled' ? usersRes.value.data : []
        const policy = policyRes.status === 'fulfilled' ? policyRes.value.data : {}
        const sec = settingsRes.status === 'fulfilled' ? settingsRes.value.data : {}
        const history = loginHistRes.status === 'fulfilled' ? loginHistRes.value.data : []
        const twoFaUsers = twoFaRes.status === 'fulfilled' ? twoFaRes.value.data : []

        // 2FA stats
        const activeUsers = (twoFaUsers.length ? twoFaUsers : users).filter(u => u.is_active)
        const totpEnabled = activeUsers.filter(u => u.totp_enabled).length
        const twofa_pct = activeUsers.length ? Math.round((totpEnabled / activeUsers.length) * 100) : 0

        const admins = activeUsers.filter(u => u.role === 'admin')
        const adminsWithout2fa = admins.filter(u => !u.totp_enabled).length
        const all_admins_2fa = admins.length > 0 && adminsWithout2fa === 0

        // Password policy score
        let ppScore = 0
        if (policy.min_length >= 8) ppScore += 25
        if (policy.min_length >= 12) ppScore += 25
        if (policy.require_uppercase) ppScore += 15
        if (policy.require_numbers) ppScore += 15
        if (policy.require_symbols) ppScore += 20
        const configured = ppScore > 0

        // Login success rate
        const totalLogins = history.length
        const successLogins = history.filter(h => h.success).length
        const loginSuccessRate = totalLogins > 0 ? Math.round((successLogins / totalLogins) * 100) : 100

        // API keys
        let apiKeysNoExpiry = 0
        try {
          const keysRes = await api.auth.listApiKeys()
          const keys = keysRes.data.api_keys || []
          apiKeysNoExpiry = keys.filter(k => k.is_active && !k.expires_at).length
        } catch (e) {
          apiKeysNoExpiry = 0
        }

        // Inactive users (>90 days)
        const ninetyDaysAgo = new Date()
        ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90)
        const inactiveCount = users.filter(u => u.is_active && (!u.last_login || new Date(u.last_login) < ninetyDaysAgo)).length

        complianceData.value = {
          twofa_pct,
          all_admins_2fa,
          admins_without_2fa: adminsWithout2fa,
          password_policy_configured: configured,
          password_policy_score: ppScore,
          login_success_rate: loginSuccessRate,
          api_keys_have_expiry: apiKeysNoExpiry === 0,
          api_keys_no_expiry: apiKeysNoExpiry,
          no_inactive_users: inactiveCount === 0,
          inactive_users_count: inactiveCount,
          brute_force_enabled: !!sec.brute_force_enabled,
        }
      } catch (e) {
        // non-critical
      } finally {
        complianceLoading.value = false
      }
    }

    const loadAll = async () => {
      loading.value = true
      try {
        await Promise.all([
          loadSettings(),
          loadLockouts(),
          loadFailedLogins(),
          loadIPList(),
          loadGeoIPRules(),
          loadLoginHistory(),
          loadPasswordPolicy(),
          loadUserList(),
          load2faOverview(),
        ])
      } finally {
        loading.value = false
      }
    }

    const saveSettings = async () => {
      savingSettings.value = true
      try {
        await api.security.updateSettings(settings.value)
        toast.success('Settings saved')
        await loadSettings()
      } finally {
        savingSettings.value = false
      }
    }

    const savePasswordPolicy = async () => {
      savingPolicy.value = true
      try {
        await api.security.updatePasswordPolicy(passwordPolicy.value)
        toast.success('Password policy saved')
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to save policy')
      } finally {
        savingPolicy.value = false
      }
    }

    const unlockAccount = async (username) => {
      if (!confirm(`Unlock account for ${username}?`)) return
      await api.security.unlockAccount(username)
      toast.success(`${username} unlocked`)
      await loadLockouts()
    }

    const quickBanIP = async (ip) => {
      if (!confirm(`Ban IP ${ip}?`)) return
      await api.security.addIPEntry({ ip_address: ip, list_type: 'ban', reason: 'Banned via failed login list' })
      toast.success(`${ip} banned`)
      activeTab.value = 'iplist'
      await loadIPList()
    }

    const addIPEntry = async () => {
      savingIP.value = true
      try {
        const data = { ...newIP.value }
        if (!data.expires_at) delete data.expires_at
        else data.expires_at = new Date(data.expires_at).toISOString()
        await api.security.addIPEntry(data)
        toast.success('Entry added')
        showIPModal.value = false
        newIP.value = { ip_address: '', list_type: 'ban', reason: '', expires_at: '' }
        await loadIPList()
      } finally {
        savingIP.value = false
      }
    }

    const deleteIPEntry = async (id) => {
      if (!confirm('Remove this entry?')) return
      await api.security.deleteIPEntry(id)
      toast.success('Entry removed')
      await loadIPList()
    }

    const toggleIPEntry = async (entry) => {
      await api.security.toggleIPEntry(entry.id)
      await loadIPList()
    }

    const addGeoIPRule = async () => {
      savingGeoIP.value = true
      try {
        await api.security.addGeoIPRule({
          ...newGeoIP.value,
          country_code: newGeoIP.value.country_code.toUpperCase()
        })
        toast.success('Rule added')
        showGeoIPModal.value = false
        newGeoIP.value = { country_code: '', country_name: '', action: 'block' }
        countrySearch.value = ''
        filteredCountries.value = []
        await loadGeoIPRules()
      } finally {
        savingGeoIP.value = false
      }
    }

    const deleteGeoIPRule = async (id) => {
      if (!confirm('Remove this rule?')) return
      await api.security.deleteGeoIPRule(id)
      toast.success('Rule removed')
      await loadGeoIPRules()
    }

    const toggleGeoIPRule = async (rule) => {
      await api.security.toggleGeoIPRule(rule.id)
      await loadGeoIPRules()
    }

    const invalidateAllSessions = async () => {
      if (!confirm('This will force ALL users to re-authenticate. Continue?')) return
      invalidatingAll.value = true
      try {
        await api.users.invalidateAllSessions()
        toast.success('All sessions invalidated')
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to invalidate sessions')
      } finally {
        invalidatingAll.value = false
      }
    }

    const invalidateUserSessions = async (u) => {
      if (!confirm(`Invalidate all sessions for ${u.username}?`)) return
      try {
        await api.users.invalidateSessions(u.id)
        toast.success(`Sessions invalidated for ${u.username}`)
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to invalidate sessions')
      }
    }

    const forceDisable2fa = async (u) => {
      if (!confirm(`Force-disable 2FA for ${u.username}? Use this only for account recovery.`)) return
      try {
        await api.users.disableTotp(u.id)
        toast.success(`2FA disabled for ${u.username}`)
        await load2faOverview()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to disable 2FA')
      }
    }

    const formatDate = (d) => d ? new Date(d).toLocaleString() : '—'

    const formatRole = (role) => ({ admin: 'Admin', operator: 'Operator', viewer: 'Viewer' }[role] || role)

    const getRoleBadgeClass = (role) => ({
      admin: 'badge-danger',
      operator: 'badge-warning',
      viewer: 'badge-info',
    }[role] || 'badge-secondary')

    const truncateUA = (ua) => {
      if (!ua) return '—'
      return ua.length > 60 ? ua.substring(0, 60) + '…' : ua
    }

    const clearHistoryFilters = () => {
      historySearch.value = ''
      historyFilter.value = 'all'
      historyDateFrom.value = ''
      historyDateTo.value = ''
      historyPage.value = 1
    }

    const exportHistoryCSV = () => {
      const rows = filteredHistory.value
      if (rows.length === 0) { toast.error('No data to export'); return }
      const headers = ['Timestamp', 'Username', 'IP Address', 'Result', 'Failure Reason', 'User Agent']
      const escape = (v) => '"' + String(v || '').replace(/"/g, '""') + '"'
      const lines = [headers.join(',')]
      for (const r of rows) {
        lines.push([
          escape(r.timestamp),
          escape(r.username_attempted),
          escape(r.ip_address),
          escape(r.success ? 'Success' : 'Failed'),
          escape(r.failure_reason || ''),
          escape(r.user_agent || ''),
        ].join(','))
      }
      const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `login-history-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${rows.length} records`)
    }

    onMounted(loadAll)

    watch(activeTab, (tab) => {
      if (tab === 'compliance') {
        loadComplianceData()
      }
    })

    watch(historyPage, () => {
      // ensure page stays in bounds when filters change
      if (historyPage.value > historyTotalPages.value) {
        historyPage.value = historyTotalPages.value
      }
    })

    return {
      loading, savingSettings, savingIP, savingGeoIP, savingPolicy, invalidatingAll,
      showIPModal, showGeoIPModal, activeTab, tabs,
      settings, passwordPolicy,
      lockouts, failedLogins, ipList, geoipRules, loginHistory, userList, twoFaList,
      newIP, newGeoIP,
      historyFilter, historySearch, historyDateFrom, historyDateTo,
      historyPage, historyPageSize, historyTotalPages, filteredHistory, paginatedHistory,
      twoFaFilter, filtered2faList,
      overviewStats, recentActivity,
      policyStrength, policyExamplePassword,
      countrySearch, filteredCountries, filterCountries, selectCountry,
      lookupIP, lookupResult, lookingUp, lookupIPCountry, quickAddCountry,
      saveSettings, savePasswordPolicy,
      unlockAccount, quickBanIP,
      addIPEntry, deleteIPEntry, toggleIPEntry,
      addGeoIPRule, deleteGeoIPRule, toggleGeoIPRule,
      loadLockouts, loadFailedLogins, loadLoginHistory, loadUserList, load2faOverview,
      invalidateAllSessions, invalidateUserSessions,
      forceDisable2fa,
      formatDate, formatRole, getRoleBadgeClass,
      truncateUA, clearHistoryFilters, exportHistoryCSV,
      // Compliance
      complianceLoading, complianceData, complianceScore, scoreClass,
      recommendations, loadComplianceData,
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}
.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Tabs */
.tab-nav {
  display: flex;
  gap: 0.25rem;
  border-bottom: 2px solid var(--border-color);
  flex-wrap: wrap;
}
.tab-btn {
  background: none;
  border: none;
  padding: 0.6rem 1.1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: color 0.15s;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}
.tab-badge {
  background: #ef4444;
  color: white;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  line-height: 1.4;
}

/* Settings rows */
.section-body {
  padding: 0 1.5rem;
}
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  padding: 1.1rem 0;
  border-bottom: 1px solid var(--border-color);
}
.setting-row:last-of-type {
  border-bottom: none;
}
.setting-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
}
.setting-label {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 0.9rem;
}
.setting-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
}
.setting-input {
  width: 100px;
  text-align: right;
  flex-shrink: 0;
}
.input-suffix {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.suffix-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
  white-space: nowrap;
}
.section-footer {
  padding: 1rem 0;
  display: flex;
  justify-content: flex-end;
}

/* Toggle switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--border-color);
  border-radius: 24px;
  cursor: pointer;
  transition: 0.2s;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  left: 3px;
  top: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}
.toggle input:checked + .toggle-slider { background: var(--primary-color, #3b82f6); }
.toggle input:checked + .toggle-slider::before { transform: translateX(20px); }

/* Empty state */
.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

/* Table tweaks */
.ua-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge-secondary {
  background-color: var(--text-secondary);
  color: white;
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
  max-width: 460px;
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
.modal-header h3 { margin: 0; color: var(--text-primary); }
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

.form-group { position: relative; margin-bottom: 1rem; }
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
}

.mb-2 { margin-bottom: 1rem; }
.mt-1 { margin-top: 0.5rem; }

/* IP Lookup */
.lookup-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-shrink: 0;
  width: 280px;
}
.lookup-result {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  margin-top: 0.75rem;
}
.stat-list { display: flex; flex-direction: column; gap: 0.2rem; }
.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  padding: 0.2rem 0;
  border-bottom: 1px solid var(--border-color);
}
.stat-row span:first-child { color: var(--text-secondary); }

/* Country picker dropdown */
.country-dropdown {
  position: absolute;
  z-index: 100;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-top: none;
  border-radius: 0 0 0.375rem 0.375rem;
  box-shadow: var(--shadow-lg);
  max-height: 220px;
  overflow-y: auto;
  width: 100%;
}
.country-option {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  cursor: pointer;
}
.country-option:hover { background: var(--background); }
.selected-country {
  padding: 0.5rem 0.75rem;
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

/* Info box */
.info-box {
  background: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.8rem;
}

/* Compliance Tab */
.score-section {
  display: flex;
  gap: 2rem;
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 0.5rem 0 1rem;
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  border: 4px solid;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.score-good {
  border-color: #22c55e;
  color: #4ade80;
}

.score-warn {
  border-color: #eab308;
  color: #facc15;
}

.score-bad {
  border-color: #ef4444;
  color: #f87171;
}

.score-number {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
}

.score-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  line-height: 1.2;
}

.score-breakdown {
  flex: 1;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.score-item-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  min-width: 140px;
  white-space: nowrap;
}

.score-bar-wrap {
  flex: 1;
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.score-bar {
  height: 100%;
  background: #3b82f6;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.bar-green { background: #22c55e; }
.bar-red   { background: #ef4444; }

.score-item-val {
  font-size: 0.75rem;
  color: var(--text-primary);
  min-width: 70px;
  text-align: right;
}

/* Checklist */
.checklist {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.checklist-item {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.8rem 0;
  border-bottom: 1px solid var(--border-color);
}

.checklist-item:last-child {
  border-bottom: none;
}

.check-icon {
  font-size: 1rem;
  font-weight: 700;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.75rem;
}

.check-pass .check-icon {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.check-fail .check-icon {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.check-warn .check-icon {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}

.check-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.check-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.check-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* Recommendations */
.recommendations {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.rec-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid;
}

.rec-high {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.rec-medium {
  border-color: rgba(234, 179, 8, 0.3);
  background: rgba(234, 179, 8, 0.05);
}

.rec-low {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.05);
}

.rec-severity {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.rec-high .rec-severity   { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.rec-medium .rec-severity { background: rgba(234, 179, 8, 0.2);  color: #facc15; }
.rec-low .rec-severity    { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }

.rec-body {
  flex: 1;
}

.rec-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.2rem;
}

.rec-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* ── Overview Tab ── */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.overview-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.25rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.ov-icon {
  width: 42px;
  height: 42px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ov-icon svg { width: 22px; height: 22px; }
.ov-icon-blue  { background: rgba(59,130,246,0.12); color: #3b82f6; }
.ov-icon-green { background: rgba(34,197,94,0.12);  color: #22c55e; }
.ov-icon-red   { background: rgba(239,68,68,0.12);  color: #ef4444; }
.ov-icon-yellow{ background: rgba(234,179,8,0.12);  color: #eab308; }

.ov-body { display: flex; flex-direction: column; gap: 0.1rem; }

.ov-value {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
  color: var(--text-primary);
}

.ov-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 0.25rem;
}

.ov-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* ── Filter bar (Login History) ── */
.filter-bar {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background);
}

.filter-input {
  min-width: 180px;
  flex: 1;
}

/* ── Pagination ── */
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  border-top: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 0.5rem;
}

.pagination-btns {
  display: flex;
  gap: 0.25rem;
}

/* ── Password Policy Strength ── */
.policy-strength {
  margin-bottom: 0.75rem;
}

.strength-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.strength-level {
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 99px;
}

.strength-weak     { background: rgba(239,68,68,0.15);   color: #ef4444; }
.strength-moderate { background: rgba(234,179,8,0.15);   color: #d97706; }
.strength-strong   { background: rgba(34,197,94,0.15);   color: #16a34a; }

.strength-bar-wrap {
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.strength-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.strength-bar-fill.strength-weak     { background: #ef4444; }
.strength-bar-fill.strength-moderate { background: #f59e0b; }
.strength-bar-fill.strength-strong   { background: #22c55e; }

.policy-checklist {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.policy-req {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--border-color);
}

.policy-req:last-child { border-bottom: none; }

.req-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}

.req-met .req-icon   { background: rgba(34,197,94,0.15); color: #16a34a; }
.req-unmet .req-icon { background: rgba(239,68,68,0.15); color: #dc2626; }
.req-met   { color: var(--text-primary); }
.req-unmet { color: var(--text-secondary); }

.example-password {
  display: inline-block;
  margin-left: 0.5rem;
  font-family: monospace;
  font-size: 0.85rem;
  background: var(--surface, #f3f4f6);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

/* ── 2FA Overview summary ── */
.twofa-summary {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color);
}

.twofa-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.85rem 0.5rem;
  border-right: 1px solid var(--border-color);
}

.twofa-stat:last-child { border-right: none; }

.twofa-stat-val {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.twofa-stat-warn { color: #d97706; }
.twofa-stat-red  { color: #dc2626; }

.twofa-stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-align: center;
  margin-top: 0.15rem;
}
</style>
