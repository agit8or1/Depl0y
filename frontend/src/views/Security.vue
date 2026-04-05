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
            <div class="flex gap-1">
              <select v-model="historyFilter" class="form-control" style="width:130px">
                <option value="all">All</option>
                <option value="success">Successes</option>
                <option value="failure">Failures</option>
              </select>
              <button @click="loadLoginHistory" class="btn btn-outline btn-sm">Refresh</button>
            </div>
          </div>
          <div v-if="loginHistory.length === 0" class="empty-state">No login history available.</div>
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
                <tr v-for="item in filteredHistory" :key="item.id">
                  <td class="text-sm text-muted">{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.username_attempted }}</strong></td>
                  <td><code>{{ item.ip_address }}</code></td>
                  <td>
                    <span :class="['badge', item.success ? 'badge-success' : 'badge-danger']">
                      {{ item.success ? 'Success' : 'Failed' }}
                    </span>
                  </td>
                  <td class="text-sm text-muted">{{ item.failure_reason || '—' }}</td>
                  <td class="text-sm text-muted ua-cell">{{ item.user_agent || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Password Policy ─────────────────────────────────── -->
      <div v-if="activeTab === 'policy'">
        <div class="card">
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
      </div>

      <!-- ── 2FA Overview ────────────────────────────────────── -->
      <div v-if="activeTab === '2fa'">
        <div class="card">
          <div class="card-header">
            <h3>2FA Status Overview</h3>
            <button @click="load2faOverview" class="btn btn-outline btn-sm">Refresh</button>
          </div>
          <div v-if="twoFaList.length === 0" class="empty-state">No users found.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Account Status</th>
                  <th>2FA Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in twoFaList" :key="u.id">
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
import { ref, computed, onMounted } from 'vue'
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
    const activeTab = ref('brute')
    const historyFilter = ref('all')

    const tabs = [
      { key: 'brute',    label: 'Brute Force' },
      { key: 'lockouts', label: 'Lockouts' },
      { key: 'iplist',   label: 'IP Access' },
      { key: 'geoip',    label: 'GeoIP' },
      { key: 'sessions', label: 'Sessions' },
      { key: 'history',  label: 'Login History' },
      { key: 'policy',   label: 'Password Policy' },
      { key: '2fa',      label: '2FA Overview' },
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

    // Filtered login history
    const filteredHistory = computed(() => {
      if (historyFilter.value === 'all') return loginHistory.value
      const success = historyFilter.value === 'success'
      return loginHistory.value.filter(h => h.success === success)
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

    onMounted(loadAll)

    return {
      loading, savingSettings, savingIP, savingGeoIP, savingPolicy, invalidatingAll,
      showIPModal, showGeoIPModal, activeTab, tabs,
      settings, passwordPolicy,
      lockouts, failedLogins, ipList, geoipRules, loginHistory, userList, twoFaList,
      newIP, newGeoIP,
      historyFilter, filteredHistory,
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
</style>
