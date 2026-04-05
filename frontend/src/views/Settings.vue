<template>
  <div class="settings-page">
    <!-- User Profile Section -->
    <div class="card">
      <div class="card-header">
        <h3>User Profile</h3>
      </div>
      <div class="profile-content">
        <div v-if="user" class="profile-section">
          <div class="profile-header">
            <div class="profile-avatar">{{ user.username.charAt(0).toUpperCase() }}</div>
            <div>
              <h4>{{ user.username }}</h4>
              <p class="text-sm text-muted">{{ user.email }}</p>
              <span :class="['badge', 'badge-' + getRoleBadge(user.role)]">{{ user.role }}</span>
            </div>
          </div>

          <div class="profile-details">
            <h5 class="subsection-title">Account Information</h5>
            <form @submit.prevent="updateProfile" class="profile-form">
              <div class="form-group">
                <label class="form-label">Username</label>
                <input v-model="profileForm.username" class="form-control" disabled />
                <p class="text-xs text-muted">Username cannot be changed</p>
              </div>

              <div class="form-group">
                <label class="form-label">Email Address</label>
                <input v-model="profileForm.email" type="email" class="form-control" required />
              </div>

              <button type="submit" class="btn btn-primary" :disabled="updatingProfile">
                {{ updatingProfile ? 'Updating...' : 'Update Profile' }}
              </button>
            </form>

            <h5 class="subsection-title" style="margin-top: 2rem;">Change Password</h5>
            <form @submit.prevent="changePassword" class="password-form">
              <div class="form-group">
                <label class="form-label">Current Password</label>
                <input v-model="passwordForm.current_password" type="password" autocomplete="current-password" class="form-control" required />
              </div>

              <div class="form-group">
                <label class="form-label">New Password</label>
                <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" class="form-control" required />
              </div>

              <div class="form-group">
                <label class="form-label">Confirm New Password</label>
                <input v-model="passwordForm.confirm_password" type="password" autocomplete="new-password" class="form-control" required />
              </div>

              <button type="submit" class="btn btn-primary" :disabled="changingPassword">
                {{ changingPassword ? 'Changing...' : 'Change Password' }}
              </button>
            </form>

            <h5 class="subsection-title" style="margin-top: 2rem;">Two-Factor Authentication (2FA)</h5>
            <div class="totp-section">
              <div v-if="user.totp_enabled" class="totp-enabled">
                <div class="flex gap-2 align-center">
                  <span class="badge badge-success">✓ Enabled</span>
                  <p class="text-sm">2FA is currently enabled for your account</p>
                </div>
                <button @click="disableTOTP" class="btn btn-danger" :disabled="totp_loading">
                  {{ totp_loading ? 'Disabling...' : 'Disable 2FA' }}
                </button>
              </div>
              <div v-else class="totp-disabled">
                <div class="flex gap-2 align-center">
                  <span class="badge badge-warning">⚠ Disabled</span>
                  <p class="text-sm">Enable 2FA for enhanced account security</p>
                </div>
                <button @click="setupTOTP" class="btn btn-primary" :disabled="totp_loading">
                  {{ totp_loading ? 'Setting up...' : 'Enable 2FA' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Cloud Image Setup Section -->
    <div class="card">
      <div class="card-header">
        <h3>Cloud Image Setup</h3>
      </div>
      <div class="cloud-setup-content">
        <div class="info-box">
          <h4>🚀 Enable Automatic Cloud Image Deployments</h4>
          <p>Cloud images allow you to deploy VMs with the OS pre-installed in seconds!</p>
          <p class="text-sm text-muted">
            This one-time setup configures SSH access to your Proxmox server, enabling:
          </p>
          <ul class="feature-list">
            <li>✅ Automatic OS installation (Ubuntu, Debian, etc.)</li>
            <li>✅ Pre-configured credentials</li>
            <li>✅ 30-second deployments (after initial template creation)</li>
            <li>✅ No manual installation needed</li>
          </ul>
        </div>

        <div v-if="sshStatus === null" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Checking SSH configuration...</p>
        </div>

        <div v-else-if="sshStatus === true" class="success-box">
          <div class="status-icon">✅</div>
          <div>
            <h4>Cloud Images Enabled!</h4>
            <p>SSH access is configured. You can now deploy VMs from cloud images.</p>
            <p class="text-sm text-muted">First deployment per image takes ~5-10 minutes. All subsequent deployments take ~30 seconds.</p>
          </div>
        </div>

        <div v-else class="warning-box">
          <div class="status-icon">⚠️</div>
          <div>
            <h4>Setup Required</h4>
            <p><strong>Quick Setup:</strong> Click the button below to enable cloud images automatically!</p>
            <div class="action-buttons">
              <button @click="showPasswordPrompt = true" class="btn btn-success btn-lg">
                🚀 Enable Cloud Images Now
              </button>
              <button @click="checkSSHStatus" class="btn btn-outline" :disabled="checkingSSH">
                {{ checkingSSH ? 'Checking...' : 'Re-check Status' }}
              </button>
            </div>

            <div class="or-divider">
              <span>OR</span>
            </div>

            <p class="text-sm text-muted"><strong>Manual Setup:</strong> Run this command on your server:</p>
            <div class="command-box">
              <code>sudo /tmp/enable_cloud_images.sh</code>
              <button @click="copyCommand" class="btn btn-sm btn-outline">
                {{ commandCopied ? '✓ Copied' : 'Copy' }}
              </button>
            </div>
            <div class="action-buttons">
              <button @click="showSetupInstructions = true" class="btn btn-sm btn-outline">
                📖 View Full Instructions
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Appearance Section -->
    <div class="card">
      <div class="card-header">
        <h3>Appearance</h3>
        <p>Customise how Depl0y looks</p>
      </div>
      <div class="card-body">
        <div class="settings-group">
          <h5 class="subsection-title">Theme</h5>
          <p class="text-sm text-muted">Choose between light, dark, or system preference.</p>
          <div class="theme-options" style="margin-top: 0.75rem;">
            <button
              v-for="opt in themeOptions"
              :key="opt.value"
              :class="['theme-option-btn', currentTheme === opt.value ? 'theme-option-btn--active' : '']"
              @click="setTheme(opt.value)"
            >
              <span class="theme-option-icon">{{ opt.icon }}</span>
              <span class="theme-option-label">{{ opt.label }}</span>
            </button>
          </div>
          <p class="text-xs text-muted" style="margin-top: 0.5rem;">
            Current: <strong>{{ themeOptions.find(t => t.value === currentTheme)?.label }}</strong>
          </p>
        </div>

        <!-- Language Selector -->
        <div class="settings-group" style="margin-top: 1.75rem;">
          <h5 class="subsection-title">Language</h5>
          <p class="text-sm text-muted">Select the language for the Depl0y interface. Takes effect immediately.</p>
          <div class="form-group" style="max-width: 300px; margin-top: 0.75rem;">
            <label class="form-label">Interface Language</label>
            <select
              v-model="currentLocale"
              @change="handleLocaleChange"
              class="form-control"
            >
              <option value="en">English (EN)</option>
              <option value="de">Deutsch (DE)</option>
              <option value="fr">Français (FR)</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Proxmox Integration Section -->
    <div class="card">
      <div class="card-header">
        <h3>Proxmox Integration</h3>
        <p>Client-side preferences for Proxmox operations</p>
      </div>
      <div class="card-body">

        <!-- Default Host Selector -->
        <div class="settings-group">
          <h5 class="subsection-title">Default Proxmox Host</h5>
          <p class="text-sm text-muted">The host used by default for operations that require a host selection.</p>
          <div class="form-group" style="max-width: 400px; margin-top: 0.75rem;">
            <label class="form-label">Default host</label>
            <div v-if="loadingHosts" class="loading-message" style="padding: 0.5rem 0;">
              <div class="loading-spinner"></div>
              <p>Loading hosts...</p>
            </div>
            <select
              v-else
              v-model="defaultHost"
              @change="saveDefaultHost"
              class="form-control"
            >
              <option value="">— None (always prompt) —</option>
              <option v-for="host in proxmoxHosts" :key="host.id" :value="String(host.id)">
                {{ host.name }} ({{ host.host }})
              </option>
            </select>
            <p v-if="hostsError" class="text-sm" style="color: #ef4444; margin-top: 0.25rem;">{{ hostsError }}</p>
          </div>
        </div>

        <!-- Console Settings -->
        <div class="settings-group" style="margin-top: 1.75rem;">
          <h5 class="subsection-title">Console Settings</h5>
          <div class="toggle-row">
            <div>
              <strong>Open console in new tab</strong>
              <p class="text-sm text-muted">Launch VM/node consoles in a new browser tab instead of the current one</p>
            </div>
            <label class="toggle-switch">
              <input
                type="checkbox"
                v-model="consoleNewTab"
                @change="saveConsoleSetting('depl0y_console_new_tab', consoleNewTab)"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="toggle-row">
            <div>
              <strong>Scale viewport to fit</strong>
              <p class="text-sm text-muted">Automatically scale the console display to fit your browser window</p>
            </div>
            <label class="toggle-switch">
              <input
                type="checkbox"
                v-model="consoleScale"
                @change="saveConsoleSetting('depl0y_console_scale', consoleScale)"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>

        <!-- Auto-Refresh Interval -->
        <div class="settings-group" style="margin-top: 1.75rem;">
          <h5 class="subsection-title">Auto-Refresh Interval</h5>
          <p class="text-sm text-muted">How often the dashboard and VM list automatically refresh (in seconds).</p>
          <div class="refresh-interval-row" style="margin-top: 0.75rem;">
            <input
              v-model.number="refreshInterval"
              type="number"
              min="10"
              max="300"
              step="5"
              class="form-control"
              style="width: 120px; display: inline-block;"
              @change="saveRefreshInterval"
            />
            <span class="text-sm text-muted" style="margin-left: 0.5rem;">seconds (min 10, max 300)</span>
          </div>
        </div>

      </div>
    </div>

    <!-- Proxmox Cluster Inter-Node SSH Section -->
    <div class="card">
      <div class="card-header">
        <h3>🔗 Proxmox Cluster Inter-Node SSH</h3>
        <p>Required for multi-node clusters to create templates on specific nodes</p>
      </div>
      <div class="card-body">
        <div class="info-box">
          <p><strong>Why needed?</strong> When deploying to different nodes in your cluster, the system needs to create cloud image templates on each specific node. This requires SSH access between cluster nodes.</p>
          <p class="text-sm text-muted">Single-node setups don't need this.</p>
        </div>

        <div v-if="clusterSSHStatus === null" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Checking inter-node SSH configuration...</p>
        </div>

        <div v-else-if="clusterSSHStatus === true" class="success-box">
          <div class="status-icon">✅</div>
          <div>
            <h4>Inter-Node SSH Enabled!</h4>
            <p>SSH keys are configured between cluster nodes.</p>
            <p class="text-sm text-muted">Cloud image templates can be created on any node in your cluster.</p>
          </div>
        </div>

        <div v-else class="warning-box">
          <div class="status-icon">⚠️</div>
          <div>
            <h4>Setup Required</h4>
            <p>Inter-node SSH is not configured yet.</p>
          </div>
        </div>

        <div class="action-buttons" style="margin-top: 1rem;">
          <button
            v-if="clusterSSHStatus !== true"
            @click="showClusterSSHPrompt = true"
            class="btn btn-primary"
          >
            🔐 Enable Inter-Node SSH
          </button>
          <button
            v-else
            @click="checkClusterSSHStatus"
            class="btn btn-outline"
            :disabled="checkingClusterSSH"
          >
            {{ checkingClusterSSH ? 'Checking...' : '🔄 Re-check Status' }}
          </button>
        </div>
      </div>
    </div>

    <!-- High Availability / Failover Section -->
    <div class="card">
      <div class="card-header">
        <h3>🔒 High Availability (HA) & Failover</h3>
        <p>Automatically restart VMs on other nodes if a node fails</p>
      </div>
      <div class="card-body">
        <div class="info-box">
          <p><strong>What is HA?</strong> High Availability ensures your critical VMs automatically restart on another node if the current node fails or goes offline.</p>
          <p class="text-sm text-muted">
            <strong>Requirements:</strong> Multi-node Proxmox cluster with shared storage
          </p>
          <ul class="feature-list text-sm">
            <li>✅ Automatic VM migration on node failure</li>
            <li>✅ Configurable restart priorities</li>
            <li>✅ Minimal downtime for critical services</li>
            <li>✅ Health monitoring and alerting</li>
          </ul>
        </div>

        <div v-if="haStatus === null" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Checking HA status...</p>
        </div>

        <div v-else-if="haStatus && haStatus.enabled" class="success-box">
          <div class="status-icon">✅</div>
          <div>
            <h4>HA Enabled</h4>
            <p>High Availability is configured and active on your cluster.</p>
            <p class="text-sm text-muted">Protected VMs: {{ haStatus.protected_vms || 0 }}</p>
          </div>
        </div>

        <div v-else class="warning-box">
          <div class="status-icon">⚠️</div>
          <div>
            <h4>HA Not Configured</h4>
            <p>Enable High Availability to protect your VMs from node failures.</p>
          </div>
        </div>

        <div class="action-buttons" style="margin-top: 1rem;">
          <button @click="checkHAStatus" class="btn btn-outline" :disabled="checkingHA">
            {{ checkingHA ? 'Checking...' : '🔍 Check HA Status' }}
          </button>
          <button
            v-if="haStatus && !haStatus.enabled"
            @click="showHAPrompt = true"
            class="btn btn-success"
          >
            🔒 Enable High Availability
          </button>
          <!-- HA Groups now managed via dedicated HA Management menu item -->
        </div>

        <div v-if="haError" class="error-message" style="margin-top: 1rem;">
          {{ haError }}
        </div>
      </div>
    </div>

    <!-- System Updates Section -->
    <div class="card">
      <div class="card-header">
        <h3>🔄 System Updates</h3>
        <p>Keep Depl0y up to date from GitHub (github.com/agit8or1/Depl0y)</p>
      </div>
      <div class="card-body">
        <div v-if="checkingUpdates && !updateInfo" class="info-box">
          <p class="text-muted">⏳ Checking for updates...</p>
        </div>

        <div v-else-if="updateError && !updateInfo" class="info-box alert-danger">
          <p><strong>Error:</strong> {{ updateError }}</p>
          <p class="text-muted">Click "Check for Updates" to try again</p>
        </div>

        <div v-else-if="updateInfo" class="info-box">
          <p><strong>Current Version:</strong> {{ updateInfo.current_version }}</p>
          <p><strong>Latest Release:</strong> {{ updateInfo.latest_version }}</p>
          <p v-if="updateInfo.update_available" class="text-success">
            ✨ Update available!
          </p>
          <p v-else-if="isNewerThanLatest(updateInfo.current_version, updateInfo.latest_version)" class="text-muted">
            ✅ You're running a pre-release version (newer than {{ updateInfo.latest_version }})
          </p>
          <p v-else class="text-muted">
            ✅ You're running the latest version
          </p>
        </div>

        <div v-if="updateInfo && updateInfo.release_notes" class="release-notes">
          <h4>Release Notes:</h4>
          <pre>{{ updateInfo.release_notes }}</pre>
        </div>

        <div class="action-buttons" style="margin-top: 1rem;">
          <button @click="checkForUpdates" class="btn btn-outline" :disabled="checkingUpdates || applyingUpdate">
            {{ checkingUpdates ? 'Checking...' : '🔍 Check for Updates' }}
          </button>
          <button
            v-if="updateInfo && updateInfo.update_available && !applyingUpdate && !updateDone"
            @click="applyUpdate"
            class="btn btn-success"
          >
            ⬇️ Install Update
          </button>
        </div>

        <!-- Live progress terminal -->
        <div v-if="applyingUpdate || updateLog.length > 0" class="update-terminal" ref="terminalEl">
          <div class="update-terminal__header">
            <span v-if="applyingUpdate && !updateDone && !updateFailed">
              <span class="terminal-spinner"></span> Update in progress…
            </span>
            <span v-else-if="updateDone" style="color:#4ade80">✅ Upgrade complete — reloading in {{ reloadCountdown }}s</span>
            <span v-else-if="updateFailed" style="color:#f87171">❌ Update failed</span>
            <span v-else>Update log</span>
          </div>
          <pre class="update-terminal__body" ref="logBodyEl">{{ updateLog.join('\n') }}</pre>
        </div>

        <div v-if="updateError" class="error-message" style="margin-top: 1rem;">
          {{ updateError }}
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         GENERAL SETTINGS (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>General Settings</h3>
        <div class="flex gap-2">
          <button @click="resetGeneralDefaults" class="btn btn-outline btn-sm">Reset Defaults</button>
          <button @click="saveGeneralSettings" class="btn btn-primary" :disabled="savingGeneral">
            {{ savingGeneral ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="generalLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading settings...</p>
        </div>
        <div v-else>
          <div class="settings-group">
            <h5 class="subsection-title">Application</h5>
            <div class="settings-form-grid">
              <div class="form-group">
                <label class="form-label">Application Name</label>
                <input v-model="generalForm.app_name" class="form-control" placeholder="Depl0y" @input="markDirty('general')" />
                <p class="text-xs text-muted">Displayed in the browser title and header</p>
              </div>
              <div class="form-group">
                <label class="form-label">Application URL</label>
                <input v-model="generalForm.app_url" class="form-control" placeholder="https://depl0y.example.com" @input="markDirty('general')" />
                <p class="text-xs text-muted">The public URL of this instance — used in email links and webhook callback URLs</p>
              </div>
              <div class="form-group">
                <label class="form-label">Default Language</label>
                <select v-model="generalForm.default_language" class="form-control" @change="markDirty('general')">
                  <option value="en">English</option>
                  <option value="de">German (coming soon)</option>
                  <option value="fr">French (coming soon)</option>
                </select>
                <p class="text-xs text-muted">Interface language for all users</p>
              </div>
              <div class="form-group">
                <label class="form-label">Default Timezone</label>
                <select v-model="generalForm.default_timezone" class="form-control" @change="markDirty('general')">
                  <option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
                </select>
                <p class="text-xs text-muted">Used when displaying timestamps in reports and logs</p>
              </div>
            </div>
          </div>

          <div class="settings-group" style="margin-top:1.75rem;">
            <h5 class="subsection-title">Session &amp; Security</h5>
            <p class="text-sm text-muted" style="margin-bottom:1rem;">These settings are enforced server-side on every login. Changes take effect on the next login.</p>
            <div class="settings-form-grid">
              <div class="form-group">
                <label class="form-label">Session Timeout (minutes)</label>
                <input v-model.number="generalForm.session_timeout_minutes" type="number" min="5" max="10080" class="form-control" @input="markDirty('general')" />
                <p class="text-xs text-muted">JWT expiry duration set at login. Min 5 min, max 10080 min (7 days). Default: 480 min (8 hours).</p>
                <p v-if="generalValidationErrors.session_timeout_minutes" class="text-xs" style="color:#ef4444; margin-top:0.2rem;">{{ generalValidationErrors.session_timeout_minutes }}</p>
              </div>
              <div class="form-group">
                <label class="form-label">Max Login Attempts Before Lockout</label>
                <input v-model.number="generalForm.max_login_attempts" type="number" min="1" max="100" class="form-control" @input="markDirty('general')" />
                <p class="text-xs text-muted">Consecutive failed logins before the account is temporarily locked. Prevents brute-force attacks.</p>
                <p v-if="generalValidationErrors.max_login_attempts" class="text-xs" style="color:#ef4444; margin-top:0.2rem;">{{ generalValidationErrors.max_login_attempts }}</p>
              </div>
              <div class="form-group">
                <label class="form-label">Lockout Duration (minutes)</label>
                <input v-model.number="generalForm.lockout_duration_minutes" type="number" min="1" max="1440" class="form-control" @input="markDirty('general')" />
                <p class="text-xs text-muted">How long the lockout lasts before new attempts are allowed. Locked accounts are automatically released after this period.</p>
              </div>
              <div class="form-group">
                <label class="form-label">IP Allowlist (CIDR, comma-separated)</label>
                <input v-model="generalForm.ip_allowlist" class="form-control" placeholder="e.g. 192.168.1.0/24, 10.0.0.1/32" @input="markDirty('general')" />
                <p class="text-xs text-muted">If set, only these IP ranges may log in. Leave blank to allow all IPs. Example: <code>192.168.0.0/16, 10.0.0.1/32</code></p>
                <p v-if="generalValidationErrors.ip_allowlist" class="text-xs" style="color:#ef4444; margin-top:0.2rem;">{{ generalValidationErrors.ip_allowlist }}</p>
              </div>
              <div class="form-group">
                <label class="form-label">Password Policy (comma-separated rules)</label>
                <input v-model="generalForm.password_policy" class="form-control" placeholder="e.g. min_length:12, uppercase, numbers, symbols" @input="markDirty('general')" />
                <p class="text-xs text-muted">Rules enforced on new passwords. Options: <code>min_length:N</code>, <code>uppercase</code>, <code>numbers</code>, <code>symbols</code>. Leave blank for no policy beyond the 8-character minimum.</p>
              </div>
            </div>
          </div>
        </div>
        <div v-if="generalError" class="error-message" style="margin-top:1rem;">{{ generalError }}</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         EMAIL / SMTP SETTINGS (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Email / SMTP Configuration</h3>
        <div class="flex gap-2">
          <button @click="resetSmtpDefaults" class="btn btn-outline btn-sm">Reset Defaults</button>
          <button @click="sendTestEmail" class="btn btn-outline" :disabled="testingEmail || savingSmtp">
            {{ testingEmail ? 'Sending...' : 'Test Email' }}
          </button>
          <button @click="saveSmtpSettings" class="btn btn-primary" :disabled="savingSmtp">
            {{ savingSmtp ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="smtpLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading SMTP settings...</p>
        </div>
        <div v-else class="settings-form-grid">
          <div class="form-group">
            <label class="form-label">SMTP Host</label>
            <input v-model="smtpForm.smtp_host" class="form-control" placeholder="smtp.example.com" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">Hostname of your outgoing mail server</p>
          </div>
          <div class="form-group">
            <label class="form-label">SMTP Port</label>
            <input v-model.number="smtpForm.smtp_port" type="number" class="form-control" placeholder="587" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">587 (STARTTLS, recommended) or 465 (SSL/TLS) or 25 (unencrypted)</p>
            <p v-if="smtpValidationErrors.smtp_port" class="text-xs" style="color:#ef4444; margin-top:0.2rem;">{{ smtpValidationErrors.smtp_port }}</p>
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="smtpForm.smtp_username" class="form-control" placeholder="user@example.com" autocomplete="off" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">SMTP authentication username (usually an email address)</p>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input v-model="smtpForm.smtp_password" type="password" class="form-control" autocomplete="new-password" placeholder="••••••••" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">Leave blank to keep the existing password unchanged</p>
          </div>
          <div class="form-group">
            <label class="form-label">From Address</label>
            <input v-model="smtpForm.smtp_from" class="form-control" placeholder="noreply@example.com" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">The sender address shown in outgoing emails</p>
          </div>
          <div class="form-group">
            <label class="form-label">From Name</label>
            <input v-model="smtpForm.smtp_from_name" class="form-control" placeholder="Depl0y" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">Display name shown alongside the from address</p>
          </div>
          <div class="form-group">
            <label class="form-label">Notification Recipient</label>
            <input v-model="smtpForm.smtp_to" class="form-control" placeholder="admin@example.com" @input="markDirty('smtp')" />
            <p class="text-xs text-muted">Where to send system notifications and test emails</p>
          </div>
          <div class="form-group">
            <label class="form-label">Use TLS/SSL</label>
            <div class="toggle-row" style="border:none; padding:0; margin-top:0.5rem;">
              <div>
                <p class="text-sm text-muted">Enable STARTTLS (port 587) or SSL (port 465). Strongly recommended for security.</p>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" v-model="smtpFormTls" @change="markDirty('smtp')" />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </div>
        <div v-if="testEmailResult" :class="['info-box', testEmailError ? 'alert-danger' : 'alert-success']" style="margin-top:1rem;">
          {{ testEmailResult }}
        </div>
        <div v-if="smtpError" class="error-message" style="margin-top:1rem;">{{ smtpError }}</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         PROXMOX VM DEFAULTS (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Proxmox VM Defaults</h3>
        <button @click="savePveDefaults" class="btn btn-primary" :disabled="savingPveDefaults">
          {{ savingPveDefaults ? 'Saving...' : 'Save' }}
        </button>
      </div>
      <div class="card-body">
        <div v-if="pveDefaultsLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading defaults...</p>
        </div>
        <div v-else>
          <p class="text-sm text-muted" style="margin-bottom:1.25rem;">These values pre-fill the Create VM form for every new virtual machine.</p>
          <div class="settings-form-grid">
            <div class="form-group">
              <label class="form-label">Default CPU Type</label>
              <select v-model="pveDefaultsForm.pve_default_cpu_type" class="form-control">
                <option value="host">host (best performance)</option>
                <option value="kvm64">kvm64 (max compatibility)</option>
                <option value="qemu64">qemu64</option>
                <option value="x86-64-v2-AES">x86-64-v2-AES</option>
                <option value="x86-64-v3">x86-64-v3</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Default Network Bridge</label>
              <input v-model="pveDefaultsForm.pve_default_bridge" class="form-control" placeholder="vmbr0" />
            </div>
            <div class="form-group">
              <label class="form-label">Default VM Storage</label>
              <input v-model="pveDefaultsForm.pve_default_storage" class="form-control" placeholder="local-lvm" />
              <p class="text-xs text-muted">Storage pool for VM disks</p>
            </div>
            <div class="form-group">
              <label class="form-label">Default ISO Storage</label>
              <input v-model="pveDefaultsForm.pve_default_iso_storage" class="form-control" placeholder="local" />
              <p class="text-xs text-muted">Storage pool where ISO images are kept</p>
            </div>
            <div class="form-group">
              <label class="form-label">Template VM ID</label>
              <input v-model.number="pveDefaultsForm.pve_template_vmid" type="number" class="form-control" placeholder="9000" />
              <p class="text-xs text-muted">Base template VMID used for linked clones</p>
            </div>
            <div class="form-group">
              <label class="form-label">Proxmox Web Console URL Pattern</label>
              <input v-model="pveDefaultsForm.pve_console_url_pattern" class="form-control" placeholder="https://{host}:8006/#v1:0:18:4::::::::" />
              <p class="text-xs text-muted">Use {host} as a placeholder for the Proxmox hostname</p>
            </div>
          </div>
        </div>
        <div v-if="pveDefaultsError" class="error-message" style="margin-top:1rem;">{{ pveDefaultsError }}</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         BACKUP DEFAULTS (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Backup Defaults</h3>
        <button @click="saveBackupDefaults" class="btn btn-primary" :disabled="savingBackupDefaults">
          {{ savingBackupDefaults ? 'Saving...' : 'Save' }}
        </button>
      </div>
      <div class="card-body">
        <div v-if="backupDefaultsLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading backup defaults...</p>
        </div>
        <div v-else>
          <p class="text-sm text-muted" style="margin-bottom:1.25rem;">Default values used when creating new backup jobs.</p>
          <div class="settings-form-grid">
            <div class="form-group">
              <label class="form-label">Default Backup Storage</label>
              <input v-model="backupDefaultsForm.backup_default_storage" class="form-control" placeholder="local" />
            </div>
            <div class="form-group">
              <label class="form-label">Default Backup Schedule (cron)</label>
              <input v-model="backupDefaultsForm.backup_default_schedule" class="form-control" placeholder="0 2 * * *" />
              <p class="text-xs text-muted">Cron expression, e.g. <code>0 2 * * *</code> = daily at 2am</p>
            </div>
            <div class="form-group">
              <label class="form-label">Keep Last N Backups</label>
              <input v-model.number="backupDefaultsForm.backup_keep_last" type="number" min="1" max="365" class="form-control" placeholder="7" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Daily Backups</label>
              <input v-model.number="backupDefaultsForm.backup_keep_daily" type="number" min="0" max="365" class="form-control" placeholder="7" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Weekly Backups</label>
              <input v-model.number="backupDefaultsForm.backup_keep_weekly" type="number" min="0" max="52" class="form-control" placeholder="4" />
            </div>
            <div class="form-group">
              <label class="form-label">Keep Monthly Backups</label>
              <input v-model.number="backupDefaultsForm.backup_keep_monthly" type="number" min="0" max="24" class="form-control" placeholder="3" />
            </div>
            <div class="form-group">
              <label class="form-label">Email Notification</label>
              <select v-model="backupDefaultsForm.backup_email_notification" class="form-control">
                <option value="never">Never</option>
                <option value="failure">On failure only</option>
                <option value="always">Always</option>
              </select>
            </div>
          </div>
        </div>
        <div v-if="backupDefaultsError" class="error-message" style="margin-top:1rem;">{{ backupDefaultsError }}</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         MAINTENANCE (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Maintenance</h3>
      </div>
      <div class="card-body">

        <!-- Database -->
        <div class="settings-group">
          <h5 class="subsection-title">Database Maintenance</h5>
          <p class="text-sm text-muted" style="margin-bottom:0.75rem;">Run database utilities to optimise performance and verify integrity.</p>
          <div class="action-buttons">
            <button @click="runDbVacuum" class="btn btn-outline" :disabled="runningVacuum">
              {{ runningVacuum ? 'Running...' : 'VACUUM (Reclaim Space)' }}
            </button>
            <button @click="runDbCheck" class="btn btn-outline" :disabled="runningDbCheck">
              {{ runningDbCheck ? 'Checking...' : 'Integrity Check' }}
            </button>
          </div>
          <div v-if="vacuumResult" :class="['info-box', vacuumResult.success ? 'alert-success' : 'alert-danger']" style="margin-top:0.75rem;">
            <span v-if="vacuumResult.success">
              VACUUM complete. Freed {{ formatBytes(vacuumResult.freed_bytes) }}
              ({{ formatBytes(vacuumResult.size_before_bytes) }} → {{ formatBytes(vacuumResult.size_after_bytes) }})
            </span>
            <span v-else>{{ vacuumResult.message }}</span>
          </div>
          <div v-if="dbCheckResult" :class="['info-box', dbCheckResult.ok ? 'alert-success' : 'alert-danger']" style="margin-top:0.75rem;">
            Integrity check: <strong>{{ dbCheckResult.ok ? 'OK' : 'FAILED' }}</strong>
            <span v-if="!dbCheckResult.ok"> — {{ dbCheckResult.results.join(', ') }}</span>
          </div>
        </div>

        <!-- Cache -->
        <div class="settings-group" style="margin-top:1.75rem;">
          <h5 class="subsection-title">Cache Management</h5>
          <p class="text-sm text-muted" style="margin-bottom:0.75rem;">The PVE TTL cache stores recent Proxmox API responses. Clearing it forces fresh data on next request.</p>
          <div class="action-buttons">
            <button @click="fetchCacheStats" class="btn btn-outline" :disabled="loadingCacheStats">
              {{ loadingCacheStats ? 'Loading...' : 'View Cache Stats' }}
            </button>
            <button @click="clearCache" class="btn btn-outline" :disabled="clearingCache">
              {{ clearingCache ? 'Clearing...' : 'Clear PVE Cache' }}
            </button>
          </div>
          <div v-if="cacheStats" class="info-box" style="margin-top:0.75rem;">
            <div class="cache-stats-grid">
              <div class="info-item">
                <span class="info-label">Live Keys</span>
                <span class="info-value">{{ cacheStats.size }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Total Entries</span>
                <span class="info-value">{{ cacheStats.total_entries }}</span>
              </div>
            </div>
            <div v-if="cacheStats.keys && cacheStats.keys.length > 0" style="margin-top:0.75rem;">
              <p class="text-xs text-muted" style="margin-bottom:0.25rem;">Cached keys:</p>
              <div class="cache-keys-list">
                <code v-for="k in cacheStats.keys.slice(0, 20)" :key="k" class="cache-key-tag">{{ k }}</code>
                <span v-if="cacheStats.keys.length > 20" class="text-xs text-muted">... and {{ cacheStats.keys.length - 20 }} more</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Log Level -->
        <div class="settings-group" style="margin-top:1.75rem;">
          <h5 class="subsection-title">Log Level</h5>
          <p class="text-sm text-muted" style="margin-bottom:0.75rem;">Change the verbosity of the backend application log. Stored in system settings — takes effect after the next restart.</p>
          <div class="form-group" style="max-width:250px;">
            <select v-model="logLevelSetting" class="form-control">
              <option value="DEBUG">DEBUG (most verbose)</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR (least verbose)</option>
            </select>
          </div>
          <div class="action-buttons" style="margin-top:0.5rem;">
            <button @click="saveLogLevel" class="btn btn-primary" :disabled="savingLogLevel">
              {{ savingLogLevel ? 'Saving...' : 'Save Log Level' }}
            </button>
          </div>
        </div>

        <!-- System Restart -->
        <div class="settings-group" style="margin-top:1.75rem;">
          <h5 class="subsection-title">System Restart</h5>
          <div class="warning-box" style="margin-bottom:1rem;">
            <div class="status-icon">⚠</div>
            <div>
              <p><strong>Restart Backend Service</strong></p>
              <p class="text-sm">This will restart the Depl0y backend process. The UI will be temporarily unavailable for a few seconds.</p>
            </div>
          </div>
          <div v-if="!showRestartConfirm">
            <button @click="showRestartConfirm = true" class="btn btn-danger">Restart Backend</button>
          </div>
          <div v-else class="restart-confirm-box">
            <p class="text-sm" style="margin-bottom:0.75rem;"><strong>Are you sure?</strong> The service will restart in 3 seconds after you confirm.</p>
            <div class="action-buttons">
              <button @click="showRestartConfirm = false" class="btn btn-outline">Cancel</button>
              <button @click="restartBackend" class="btn btn-danger" :disabled="restarting">
                {{ restarting ? `Restarting... (${restartCountdown}s)` : 'Confirm Restart' }}
              </button>
            </div>
          </div>
          <div v-if="restartError" class="error-message" style="margin-top:0.75rem;">{{ restartError }}</div>
        </div>

      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════
         SYSTEM HEALTH (admin only)
         ═══════════════════════════════════════════════════════════════════ -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>System Health</h3>
        <button @click="fetchSystemHealth" class="btn btn-outline" :disabled="loadingHealth">
          {{ loadingHealth ? 'Checking...' : 'Refresh' }}
        </button>
      </div>
      <div class="card-body">
        <div v-if="loadingHealth && !healthData" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Running health checks...</p>
        </div>
        <div v-else-if="healthData" class="health-checks-grid">
          <div class="health-check-item" :class="healthData.checks.db === 'ok' ? 'health-ok' : 'health-fail'">
            <div class="health-check-icon">{{ healthData.checks.db === 'ok' ? '✓' : '✗' }}</div>
            <div>
              <strong>Database</strong>
              <p class="text-xs text-muted">{{ healthData.checks.db === 'ok' ? 'Connected and responding' : 'Connection failed' }}</p>
            </div>
          </div>
          <div class="health-check-item" :class="healthData.checks.smtp === 'configured' ? 'health-ok' : 'health-warn'">
            <div class="health-check-icon">{{ healthData.checks.smtp === 'configured' ? '✓' : '!' }}</div>
            <div>
              <strong>SMTP Email</strong>
              <p class="text-xs text-muted">{{ healthData.checks.smtp === 'configured' ? 'SMTP host is configured' : 'Not configured — email sending is disabled' }}</p>
            </div>
          </div>
          <div class="health-check-item" :class="healthData.checks.hosts > 0 ? 'health-ok' : 'health-warn'">
            <div class="health-check-icon">{{ healthData.checks.hosts > 0 ? '✓' : '!' }}</div>
            <div>
              <strong>Proxmox Hosts</strong>
              <p class="text-xs text-muted">{{ healthData.checks.hosts }} host{{ healthData.checks.hosts !== 1 ? 's' : '' }} configured</p>
            </div>
          </div>
          <div class="health-check-item" :class="healthData.checks.encryption === 'ok' ? 'health-ok' : 'health-fail'">
            <div class="health-check-icon">{{ healthData.checks.encryption === 'ok' ? '✓' : '✗' }}</div>
            <div>
              <strong>Encryption Key</strong>
              <p class="text-xs text-muted">{{ healthData.checks.encryption === 'ok' ? 'Encryption key is set' : 'Encryption key missing — credentials cannot be decrypted' }}</p>
            </div>
          </div>
          <div class="health-check-item" :class="(healthData.checks.disk_free_gb !== null && healthData.checks.disk_free_gb > 1) ? 'health-ok' : 'health-warn'">
            <div class="health-check-icon">{{ (healthData.checks.disk_free_gb !== null && healthData.checks.disk_free_gb > 1) ? '✓' : '!' }}</div>
            <div>
              <strong>Disk Space</strong>
              <p class="text-xs text-muted">
                <span v-if="healthData.checks.disk_free_gb !== null">{{ healthData.checks.disk_free_gb }} GB free at DB location</span>
                <span v-else>Unable to determine disk space</span>
              </p>
            </div>
          </div>
        </div>
        <div v-else>
          <p class="text-sm text-muted">Click Refresh to run health checks.</p>
        </div>
      </div>
    </div>

    <!-- Unsaved changes warning banner -->
    <div v-if="hasDirtySection" class="unsaved-changes-banner">
      <span>You have unsaved changes in: {{ dirtySections.join(', ') }}</span>
    </div>

    <!-- Setup Instructions Modal -->
    <div v-if="showSetupInstructions" class="modal" @click="showSetupInstructions = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>Cloud Image Setup Instructions</h3>
          <button @click="showSetupInstructions = false" class="btn-close">×</button>
        </div>
        <div class="modal-body setup-instructions">
          <h4>Step 1: Run the Setup Script</h4>
          <p>SSH into your Depl0y server and run:</p>
          <div class="command-box">
            <code>sudo /tmp/enable_cloud_images.sh</code>
          </div>

          <h4>Step 2: Enter Proxmox Password</h4>
          <p>The script will prompt for your Proxmox root password to configure SSH access.</p>

          <h4>Step 3: Verify</h4>
          <p>Click "Re-check Status" above to verify the setup completed successfully.</p>

          <h4>Step 4: Deploy VMs!</h4>
          <p>Go to Create VM → Select "Cloud Image (Fast)" → Choose any cloud image.</p>

          <div class="info-box">
            <h5>What Happens Next?</h5>
            <ul>
              <li><strong>First time per cloud image:</strong> System downloads and creates a template (~5-10 min)</li>
              <li><strong>All subsequent VMs:</strong> Instant cloning from template (~30 seconds)</li>
              <li><strong>Result:</strong> VM boots with OS fully installed and your credentials configured!</li>
            </ul>
          </div>

          <div class="warning-box">
            <h5>Security Note</h5>
            <p>This setup uses SSH key authentication (no passwords stored). The Depl0y server's public key is added to your Proxmox server's authorized_keys file.</p>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showSetupInstructions = false" class="btn btn-primary">
            Got It!
          </button>
        </div>
      </div>
    </div>

    <!-- Password Prompt Modal -->
    <div v-if="showPasswordPrompt" class="modal" @click="showPasswordPrompt = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>🚀 Enable Cloud Images</h3>
          <button @click="showPasswordPrompt = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p>To enable cloud images, we need to configure SSH access to your Proxmox server.</p>
          <p class="text-sm text-muted">This is a one-time setup that takes about 30 seconds.</p>

          <div class="form-group">
            <label for="proxmox-password">Proxmox Root Password</label>
            <input
              type="password"
              id="proxmox-password"
              v-model="proxmoxPassword"
              class="form-control"
              placeholder="Enter Proxmox root password"
              :disabled="enablingCloudImages"
              @keyup.enter="enableCloudImages"
            />
            <p class="text-sm text-muted mt-2">
              🔒 Your password is only used once to copy the SSH key and is not stored anywhere.
            </p>
          </div>

          <div v-if="setupError" class="error-message">
            {{ setupError }}
          </div>

          <div v-if="setupSuccess" class="success-message">
            ✅ {{ setupSuccess }}
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showPasswordPrompt = false" class="btn btn-outline" :disabled="enablingCloudImages">
            Cancel
          </button>
          <button @click="enableCloudImages" class="btn btn-success" :disabled="!proxmoxPassword || enablingCloudImages">
            {{ enablingCloudImages ? 'Setting up...' : 'Enable Cloud Images' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 2FA Setup Modal -->
    <div v-if="showTOTPModal" class="modal" @click="showTOTPModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Setup Two-Factor Authentication</h3>
          <button @click="showTOTPModal = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <div v-if="totpSetup" class="totp-setup">
            <p>Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)</p>
            <div class="qr-code">
              <img :src="totpSetup.qr_code" alt="QR Code" />
            </div>
            <p class="text-sm text-muted">Or enter this code manually:</p>
            <code class="secret-code">{{ totpSetup.secret }}</code>

            <form @submit.prevent="verifyTOTP" class="totp-verify-form">
              <div class="form-group">
                <label class="form-label">Enter 6-digit code from your app:</label>
                <input v-model="totpCode" type="text" class="form-control" maxlength="6" pattern="[0-9]{6}" required />
              </div>
              <button type="submit" class="btn btn-primary">
                Verify & Enable
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>

    <!-- Linux VM Agent Section (Admin Only) -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Linux VM Security Agent</h3>
        <p>Install a lightweight push agent on managed Linux VMs to run automated security scans</p>
      </div>
      <div class="card-body">
        <div class="info-box">
          <p><strong>What does it do?</strong> The agent runs on each VM, performs OS update checks, security hardening scans, and dependency audits, then POSTs results back to Depl0y.</p>
          <ul class="feature-list text-sm">
            <li>OS package update detection</li>
            <li>Open port and failed login checks</li>
            <li>Python dependency audit</li>
            <li>Runs every 12 hours via systemd timer</li>
          </ul>
        </div>

        <div v-if="linuxAgentLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading settings...</p>
        </div>

        <div v-else class="linux-agent-settings">
          <div class="toggle-row">
            <div>
              <strong>Enable Linux VM Agent</strong>
              <p class="text-sm text-muted">Allow VMs to register agents and report scan results</p>
            </div>
            <label class="toggle-switch">
              <input
                type="checkbox"
                v-model="linuxAgentEnabled"
                @change="saveLinuxAgentSettings"
                :disabled="savingLinuxAgent"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div v-if="linuxAgentEnabled" class="agent-stats">
            <div class="info-item">
              <span class="info-label">Registered Agents</span>
              <span class="info-value">{{ agentCount }}</span>
            </div>
            <div style="margin-top: 1rem;">
              <router-link to="/linux-vms" class="btn btn-primary">
                Manage Agents
              </router-link>
            </div>
          </div>
        </div>

        <div v-if="linuxAgentError" class="error-message" style="margin-top: 1rem;">
          {{ linuxAgentError }}
        </div>
      </div>
    </div>

    <!-- Notification Rules & In-App Test (Admin Only) -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Notification Rules</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted" style="margin-bottom: 1rem;">Choose which events create in-app notifications for all users.</p>

        <div v-if="notifRulesLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading...</p>
        </div>

        <div v-else class="notif-rules-grid">
          <div class="toggle-row">
            <div>
              <strong>VM Start</strong>
              <p class="text-sm text-muted">Notify when a VM is started</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="notifRules.notify_vm_start" @change="saveNotifRules" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="toggle-row">
            <div>
              <strong>VM Stop</strong>
              <p class="text-sm text-muted">Notify when a VM is stopped</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="notifRules.notify_vm_stop" @change="saveNotifRules" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="toggle-row">
            <div>
              <strong>Task Failure</strong>
              <p class="text-sm text-muted">Notify when a background task fails</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="notifRules.notify_task_failure" @change="saveNotifRules" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="toggle-row">
            <div>
              <strong>User Login</strong>
              <p class="text-sm text-muted">Notify admins when any user logs in</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="notifRules.notify_user_login" @change="saveNotifRules" />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>

        <div style="margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid rgba(255,255,255,0.07);">
          <h5 class="subsection-title">In-App Notification Test</h5>
          <p class="text-sm text-muted" style="margin-bottom: 0.75rem;">Send yourself a test notification to verify the notification center is working.</p>
          <div class="action-buttons">
            <button
              @click="sendTestNotification"
              class="btn btn-primary"
              :disabled="sendingTestNotif"
            >
              {{ sendingTestNotif ? 'Sending...' : 'Send Test Notification' }}
            </button>
          </div>
          <div v-if="testNotifResult" class="info-box alert-success" style="margin-top: 0.75rem;">
            {{ testNotifResult }}
          </div>
        </div>
      </div>
    </div>

    <!-- Email Notifications Section (Admin Only) -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Email Notifications</h3>
      </div>
      <div class="card-body">
        <div class="info-box">
          <p><strong>SMTP Configuration</strong> — set the following keys via the database or environment to enable email notifications:</p>
          <ul class="feature-list text-sm">
            <li><code>smtp_host</code> — SMTP server hostname</li>
            <li><code>smtp_port</code> — Port (default 587)</li>
            <li><code>smtp_username</code> — SMTP login username</li>
            <li><code>smtp_password</code> — SMTP login password</li>
            <li><code>smtp_from</code> — Sender address</li>
            <li><code>smtp_to</code> — Recipient address for notifications</li>
            <li><code>smtp_tls</code> — true/false (default true, STARTTLS on port 587, SSL on 465)</li>
          </ul>
        </div>

        <div class="action-buttons" style="margin-top: 1rem;">
          <button
            @click="sendTestEmail"
            class="btn btn-primary"
            :disabled="testingEmail"
          >
            {{ testingEmail ? 'Sending...' : 'Send Test Email' }}
          </button>
        </div>

        <div v-if="testEmailResult" :class="['info-box', testEmailError ? 'alert-danger' : 'alert-success']" style="margin-top:1rem;">
          {{ testEmailResult }}
        </div>
      </div>
    </div>

    <!-- Webhook Notifications Section (Admin Only) -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Webhook Notifications</h3>
        <button @click="showAddWebhookModal = true" class="btn btn-primary">
          + Add Webhook
        </button>
      </div>
      <div class="card-body">
        <div class="info-box">
          <p><strong>What are webhooks?</strong> Webhooks send HTTP POST requests to external URLs when VM events occur, allowing integration with Slack, Teams, custom scripts, and more.</p>
          <p class="text-sm text-muted">Supported events: vm.start, vm.stop, vm.create, vm.delete, vm.error, task.failed, user.login, backup.complete</p>
        </div>

        <div v-if="webhooksLoading" class="loading-message">
          <div class="loading-spinner"></div>
          <p>Loading webhooks...</p>
        </div>

        <div v-else-if="webhooks.length === 0" class="logs-empty" style="margin-top: 1rem;">
          <p>No webhooks configured. Click "Add Webhook" to create one.</p>
        </div>

        <div v-else class="webhooks-list">
          <div v-for="hook in webhooks" :key="hook.id" class="webhook-card">
            <!-- Webhook header -->
            <div class="webhook-row">
              <div class="webhook-info">
                <div class="webhook-header-row">
                  <strong class="webhook-name">{{ hook.name }}</strong>
                  <span :class="['badge', hook.enabled ? 'badge-success' : 'badge-secondary']">
                    {{ hook.enabled ? 'Enabled' : 'Disabled' }}
                  </span>
                </div>
                <p class="webhook-url text-sm text-muted">{{ hook.url }}</p>
                <div class="webhook-events">
                  <span v-for="evt in hook.events" :key="evt" class="event-badge">{{ evt }}</span>
                </div>
              </div>
              <div class="webhook-actions">
                <button
                  @click="triggerTestWebhook(hook.id)"
                  class="btn btn-sm btn-outline"
                  :disabled="testingWebhook === hook.id"
                >
                  {{ testingWebhook === hook.id ? 'Sending...' : 'Test' }}
                </button>
                <button
                  @click="deleteWebhookById(hook.id, hook.name)"
                  class="btn btn-sm btn-danger"
                  :disabled="deletingWebhook === hook.id"
                >
                  {{ deletingWebhook === hook.id ? 'Deleting...' : 'Delete' }}
                </button>
              </div>
            </div>

            <!-- Delivery Log -->
            <div v-if="hook.delivery_log && hook.delivery_log.length > 0" class="webhook-delivery-log">
              <p class="delivery-log-title">Last {{ hook.delivery_log.length }} deliveries</p>
              <div class="delivery-log-table">
                <div class="delivery-log-row delivery-log-header">
                  <span>Event</span>
                  <span>Status</span>
                  <span>Time</span>
                </div>
                <div
                  v-for="d in hook.delivery_log"
                  :key="d.id"
                  class="delivery-log-row"
                  :class="d.success ? 'delivery-ok' : 'delivery-fail'"
                >
                  <span class="delivery-event">{{ d.event }}</span>
                  <span class="delivery-status">
                    <span :class="['delivery-badge', d.success ? 'badge-ok' : 'badge-fail']">
                      {{ d.status_code || 'ERR' }}
                    </span>
                  </span>
                  <span class="delivery-time">{{ deliveryTimeAgo(d.created_at) }}</span>
                </div>
              </div>
            </div>
            <div v-else-if="hook.delivery_log && hook.delivery_log.length === 0" class="webhook-delivery-log">
              <p class="text-sm text-muted" style="margin: 0; padding: 0.35rem 0;">No delivery attempts yet — click "Test" to send one.</p>
            </div>
          </div>
        </div>

        <div v-if="webhooksError" class="error-message" style="margin-top: 1rem;">
          {{ webhooksError }}
        </div>
      </div>
    </div>

    <!-- Add Webhook Modal -->
    <div v-if="showAddWebhookModal" class="modal" @click="closeAddWebhookModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Webhook</h3>
          <button @click="closeAddWebhookModal" class="btn-close">x</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Webhook Name <span style="color:#ef4444">*</span></label>
            <input
              v-model="webhookForm.name"
              class="form-control"
              placeholder="e.g. Slack Alerts"
              :disabled="savingWebhook"
            />
          </div>

          <div class="form-group">
            <label class="form-label">URL <span style="color:#ef4444">*</span></label>
            <input
              v-model="webhookForm.url"
              class="form-control"
              placeholder="https://hooks.example.com/..."
              type="url"
              :disabled="savingWebhook"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Secret (optional)</label>
            <input
              v-model="webhookForm.secret"
              class="form-control"
              placeholder="Used to sign payloads with HMAC-SHA256"
              type="password"
              :disabled="savingWebhook"
            />
            <p class="text-xs text-muted" style="margin-top:0.25rem;">If set, a X-Depl0y-Signature header will be included with each request.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Events <span style="color:#ef4444">*</span></label>
            <div class="events-checkboxes">
              <label v-for="evt in availableEvents" :key="evt.value" class="event-checkbox-label">
                <input
                  type="checkbox"
                  :value="evt.value"
                  v-model="webhookForm.events"
                  :disabled="savingWebhook"
                />
                <span>{{ evt.label }}</span>
              </label>
            </div>
          </div>

          <div class="form-group">
            <div class="toggle-row" style="border:none; padding:0;">
              <div>
                <strong>Enabled</strong>
                <p class="text-sm text-muted">Enable or disable this webhook without deleting it</p>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" v-model="webhookForm.enabled" :disabled="savingWebhook" />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>

          <div v-if="webhookFormError" class="error-message">
            {{ webhookFormError }}
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeAddWebhookModal" class="btn btn-outline" :disabled="savingWebhook">
            Cancel
          </button>
          <button
            @click="saveWebhook"
            class="btn btn-primary"
            :disabled="savingWebhook || !webhookForm.name || !webhookForm.url || webhookForm.events.length === 0"
          >
            {{ savingWebhook ? 'Saving...' : 'Add Webhook' }}
          </button>
        </div>
      </div>
    </div>

    <!-- About Section -->
    <div class="card">
      <div class="card-header">
        <h3>About Depl0y</h3>
      </div>
      <div class="about-content">
        <div class="logo-section">
          <h1 class="about-logo">Depl<span class="logo-zero">0</span>y</h1>
          <p class="tagline">VM Deployment Panel for Proxmox VE</p>
        </div>

        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">Version</span>
            <span class="info-value">{{ updateInfo?.current_version || 'Loading...' }}</span>
          </div>

          <div class="info-item">
            <span class="info-label">Status</span>
            <span class="badge badge-success">Running</span>
          </div>

          <div class="info-item">
            <span class="info-label">Backend</span>
            <span class="info-value">FastAPI (Python)</span>
          </div>

          <div class="info-item">
            <span class="info-label">Frontend</span>
            <span class="info-value">Vue.js 3</span>
          </div>

          <div class="info-item">
            <span class="info-label">Database</span>
            <span class="info-value">SQLite</span>
          </div>

          <div class="info-item">
            <span class="info-label">License</span>
            <span class="info-value">Open Source</span>
          </div>
        </div>

        <div class="builder-section">
          <div class="builder-card">
            <div class="builder-icon">🚀</div>
            <div class="builder-info">
              <h4>Built by</h4>
              <a href="https://www.agit8or.net" target="_blank" rel="noopener noreferrer" class="builder-link">
                <strong>Agit8or</strong>
              </a>
              <p class="builder-url">www.agit8or.net</p>
            </div>
          </div>
        </div>

        <div class="features-section">
          <h4 class="section-title">Features</h4>
          <div class="features-grid">
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Automated VM Deployment</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Cloud-init Support</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>ISO Management</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Multi-user Authentication</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>2FA Support (TOTP)</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Update Management</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Resource Monitoring</span>
            </div>
            <div class="feature-item">
              <span class="feature-icon">✓</span>
              <span>Proxmox API Integration</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- System Information -->
    <div class="card" v-if="systemInfo">
      <div class="card-header">
        <h3>System Information</h3>
      </div>
      <div class="system-info">
        <div class="info-row">
          <span class="info-label">Total VMs</span>
          <span class="info-value">{{ systemInfo.total_vms }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Active Proxmox Hosts</span>
          <span class="info-value">{{ systemInfo.datacenters }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">ISO Images</span>
          <span class="info-value">{{ systemInfo.total_isos }}</span>
        </div>
      </div>
    </div>

    <!-- Backend Logs (Admin Only) -->
    <div class="card" v-if="user && user.role === 'admin'">
      <div class="card-header">
        <h3>Backend Logs</h3>
        <button @click="refreshLogs" class="btn btn-primary" :disabled="loadingLogs">
          {{ loadingLogs ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
      <div class="logs-content">
        <div class="logs-controls">
          <label class="form-label">
            Show last
            <select v-model="logLines" @change="refreshLogs" class="log-lines-select">
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
              <option :value="500">500</option>
            </select>
            lines
          </label>
        </div>
        <div v-if="backendLogs" class="logs-viewer">
          <pre class="logs-text">{{ backendLogs }}</pre>
        </div>
        <div v-else class="logs-empty">
          <p>Click "Refresh" to load logs</p>
        </div>
      </div>
    </div>

    <!-- Cluster SSH Password Prompt Modal -->
    <div v-if="showClusterSSHPrompt" class="modal" @click="showClusterSSHPrompt = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>🔐 Enable Inter-Node SSH</h3>
          <button @click="showClusterSSHPrompt = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p>To enable inter-node SSH, we need to configure SSH keys between your Proxmox cluster nodes.</p>
          <p class="text-sm text-muted">This is a one-time setup that takes about 30 seconds.</p>

          <div class="form-group">
            <label for="cluster-password">Proxmox Root Password</label>
            <input
              type="password"
              id="cluster-password"
              v-model="clusterPassword"
              class="form-control"
              placeholder="Enter Proxmox root password"
              :disabled="enablingClusterSSH"
              @keyup.enter="enableClusterSSH"
            />
            <p class="text-sm text-muted mt-2">
              🔒 Your password is only used once to set up SSH keys and is not stored anywhere.
            </p>
          </div>

          <div v-if="clusterSSHError" class="error-message">
            {{ clusterSSHError }}
          </div>

          <div v-if="clusterSSHSuccess" class="success-message">
            ✅ {{ clusterSSHSuccess }}
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showClusterSSHPrompt = false" class="btn btn-outline" :disabled="enablingClusterSSH">
            Cancel
          </button>
          <button @click="enableClusterSSH" class="btn btn-primary" :disabled="!clusterPassword || enablingClusterSSH">
            {{ enablingClusterSSH ? 'Setting up...' : 'Enable Inter-Node SSH' }}
          </button>
        </div>
      </div>
    </div>

    <!-- High Availability Setup Modal -->
    <div v-if="showHAPrompt" class="modal" @click="showHAPrompt = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>🔒 Enable High Availability</h3>
          <button @click="showHAPrompt = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p>High Availability will be enabled on your Proxmox cluster, allowing automatic failover of VMs.</p>
          <p class="text-sm text-muted">This requires:</p>
          <ul class="text-sm">
            <li>Multi-node Proxmox cluster</li>
            <li>Shared storage accessible by all nodes</li>
            <li>Proxmox root access</li>
          </ul>

          <div class="form-group" style="margin-top: 1rem;">
            <label for="ha-password">Proxmox Root Password</label>
            <input
              type="password"
              id="ha-password"
              v-model="haPassword"
              class="form-control"
              placeholder="Enter Proxmox root password"
              :disabled="enablingHA"
              @keyup.enter="enableHA"
            />
            <p class="text-sm text-muted mt-2">
              🔒 Your password is only used once to configure HA and is not stored.
            </p>
          </div>

          <div v-if="haSetupError" class="error-message">
            {{ haSetupError }}
          </div>

          <div v-if="haSetupSuccess" class="success-message">
            ✅ {{ haSetupSuccess }}
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showHAPrompt = false" class="btn btn-outline" :disabled="enablingHA">
            Cancel
          </button>
          <button @click="enableHA" class="btn btn-success" :disabled="!haPassword || enablingHA">
            {{ enablingHA ? 'Enabling HA...' : '🔒 Enable High Availability' }}
          </button>
        </div>
      </div>
    </div>

    <!-- HA Groups Management Modal -->
    <div v-if="showHAManagement" class="modal" @click="showHAManagement = false">
      <div class="modal-content modal-large" @click.stop>
        <div class="modal-header">
          <h3>⚙️ Manage HA Groups</h3>
          <button @click="showHAManagement = false" class="btn-close">×</button>
        </div>
        <div class="modal-body">
          <p>Configure which VMs are protected by High Availability and their restart priorities.</p>

          <div class="info-box" style="margin-bottom: 1rem;">
            <p class="text-sm"><strong>Priority Levels:</strong></p>
            <ul class="text-sm">
              <li><strong>1-10:</strong> Critical services (restarted first)</li>
              <li><strong>11-50:</strong> Important services</li>
              <li><strong>51-100:</strong> Standard services</li>
            </ul>
          </div>

          <p class="text-center text-muted">HA Group management coming soon! For now, use the Proxmox web interface to manage HA groups.</p>
          <p class="text-sm text-center text-muted">Datacenter → HA → Groups/Resources</p>
        </div>
        <div class="modal-footer">
          <button @click="showHAManagement = false" class="btn btn-primary">
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, nextTick, computed } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'
import { setLocale, getCurrentLocale } from '@/i18n/index.js'

export default {
  name: 'Settings',

  setup() {
    const toast = useToast()

    // ── Dirty tracking for unsaved-changes warning ─────────────────────────
    const _dirty = ref({})  // { section: true/false }

    const markDirty = (section) => {
      _dirty.value = { ..._dirty.value, [section]: true }
    }
    const clearDirty = (section) => {
      const d = { ..._dirty.value }
      delete d[section]
      _dirty.value = d
    }
    const dirtySections = computed(() =>
      Object.entries(_dirty.value)
        .filter(([, v]) => v)
        .map(([k]) => k)
    )
    const hasDirtySection = computed(() => dirtySections.value.length > 0)

    // Warn when navigating away with unsaved changes
    onBeforeRouteLeave((to, from, next) => {
      if (hasDirtySection.value) {
        const confirmed = window.confirm(
          `You have unsaved changes in: ${dirtySections.value.join(', ')}.\n\nLeave without saving?`
        )
        if (!confirmed) {
          next(false)
          return
        }
      }
      next()
    })

    // ── Theme ──────────────────────────────────────────────────────────────
    const themeOptions = [
      { value: 'light', label: 'Light', icon: '☀️' },
      { value: 'dark', label: 'Dark', icon: '🌙' },
      { value: 'system', label: 'System', icon: '💻' },
    ]
    const currentTheme = ref(localStorage.getItem('depl0y_theme') || 'light')

    const setTheme = (theme) => {
      currentTheme.value = theme
      localStorage.setItem('depl0y_theme', theme)
      const root = document.documentElement
      if (theme === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
      } else {
        root.setAttribute('data-theme', theme)
      }
    }

    // ── Language / i18n ─────────────────────────────────────────────────────
    const currentLocale = ref(getCurrentLocale())

    const handleLocaleChange = () => {
      setLocale(currentLocale.value)
      // Reload the page so all components pick up the new locale immediately
      window.location.reload()
    }

    const systemInfo = ref(null)
    const user = ref(null)
    const updatingProfile = ref(false)
    const changingPassword = ref(false)
    const totp_loading = ref(false)
    const showTOTPModal = ref(false)
    const totpSetup = ref(null)
    const totpCode = ref('')
    const backendLogs = ref(null)
    const loadingLogs = ref(false)
    const logLines = ref(100)

    // Cloud Image Setup
    const sshStatus = ref(null)
    const checkingSSH = ref(false)
    const commandCopied = ref(false)
    const showSetupInstructions = ref(false)
    const showPasswordPrompt = ref(false)
    const proxmoxPassword = ref('')
    const enablingCloudImages = ref(false)
    const setupError = ref(null)
    const setupSuccess = ref(null)

    // Cluster SSH Setup
    const clusterSSHStatus = ref(null)
    const checkingClusterSSH = ref(false)
    const showClusterSSHPrompt = ref(false)
    const clusterPassword = ref('')
    const enablingClusterSSH = ref(false)
    const clusterSSHError = ref(null)
    const clusterSSHSuccess = ref(null)

    // System Updates
    const updateInfo = ref(null)
    const checkingUpdates = ref(false)
    const applyingUpdate = ref(false)
    const updateError = ref(null)
    const updateSuccess = ref(null)
    const updateLog = ref([])
    const updateDone = ref(false)
    const updateFailed = ref(false)
    const reloadCountdown = ref(15)
    const terminalEl = ref(null)
    const logBodyEl = ref(null)
    let _logPollTimer = null
    let _reloadTimer = null

    // Linux VM Agent
    const linuxAgentEnabled = ref(false)
    const linuxAgentLoading = ref(false)
    const savingLinuxAgent = ref(false)
    const linuxAgentError = ref(null)
    const agentCount = ref(0)

    // High Availability
    const haStatus = ref(null)
    const checkingHA = ref(false)
    const showHAPrompt = ref(false)
    const haPassword = ref('')
    const enablingHA = ref(false)
    const haSetupError = ref(null)
    const haSetupSuccess = ref(null)
    const haError = ref(null)
    const showHAManagement = ref(false)

    // Notification Rules (admin)
    const notifRules = ref({
      notify_vm_start: false,
      notify_vm_stop: false,
      notify_task_failure: true,
      notify_user_login: false,
    })
    const notifRulesLoading = ref(false)
    const sendingTestNotif = ref(false)
    const testNotifResult = ref(null)

    const fetchNotifRules = async () => {
      notifRulesLoading.value = true
      try {
        const res = await api.notifications.getSettings()
        notifRules.value = res.data
      } catch {
        // Non-admin or not configured — silently ignore
      } finally {
        notifRulesLoading.value = false
      }
    }

    const saveNotifRules = async () => {
      try {
        await api.notifications.updateSettings(notifRules.value)
        toast.success('Notification rules saved')
      } catch (error) {
        toast.error('Failed to save notification rules')
      }
    }

    const sendTestNotification = async () => {
      sendingTestNotif.value = true
      testNotifResult.value = null
      try {
        await api.notifications.sendTest()
        testNotifResult.value = 'Test notification created! Check the bell icon in the header.'
        toast.success('Test notification sent!')
        setTimeout(() => { testNotifResult.value = null }, 5000)
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to send test notification')
      } finally {
        sendingTestNotif.value = false
      }
    }

    // Email Notifications
    const testingEmail = ref(false)
    const testEmailResult = ref(null)
    const testEmailError = ref(false)

    const sendTestEmail = async () => {
      testingEmail.value = true
      testEmailResult.value = null
      testEmailError.value = false
      try {
        const res = await api.system.testEmail()
        testEmailResult.value = res.data.message || 'Test email sent successfully'
        toast.success('Test email sent!')
      } catch (error) {
        testEmailError.value = true
        testEmailResult.value = error.response?.data?.detail || 'Failed to send test email'
        toast.error(testEmailResult.value)
      } finally {
        testingEmail.value = false
      }
    }

    // Webhook Notifications
    const webhooks = ref([])
    const webhooksLoading = ref(false)
    const webhooksError = ref(null)
    const showAddWebhookModal = ref(false)
    const savingWebhook = ref(false)
    const testingWebhook = ref(null)
    const deletingWebhook = ref(null)
    const webhookFormError = ref(null)
    const webhookForm = ref({
      name: '',
      url: '',
      secret: '',
      events: [],
      enabled: true
    })
    const availableEvents = [
      { value: 'vm.start', label: 'VM Start' },
      { value: 'vm.stop', label: 'VM Stop' },
      { value: 'vm.create', label: 'VM Create' },
      { value: 'vm.delete', label: 'VM Delete' },
      { value: 'vm.error', label: 'VM Error' },
      { value: 'task.failed', label: 'Task Failed' },
      { value: 'user.login', label: 'User Login' },
      { value: 'backup.complete', label: 'Backup Complete' },
    ]

    const deliveryTimeAgo = (isoStr) => {
      if (!isoStr) return ''
      const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
      if (diff < 60) return 'just now'
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return `${Math.floor(diff / 86400)}d ago`
    }

    const fetchWebhooks = async () => {
      webhooksLoading.value = true
      webhooksError.value = null
      try {
        const res = await api.notifications.listWebhooks()
        webhooks.value = res.data.webhooks || []
      } catch (error) {
        // Non-admin or not yet configured — silently ignore
      } finally {
        webhooksLoading.value = false
      }
    }

    const closeAddWebhookModal = () => {
      showAddWebhookModal.value = false
      webhookForm.value = { name: '', url: '', secret: '', events: [], enabled: true }
      webhookFormError.value = null
    }

    const saveWebhook = async () => {
      webhookFormError.value = null
      if (!webhookForm.value.name.trim()) {
        webhookFormError.value = 'Webhook name is required'
        return
      }
      if (!webhookForm.value.url.trim()) {
        webhookFormError.value = 'Webhook URL is required'
        return
      }
      if (webhookForm.value.events.length === 0) {
        webhookFormError.value = 'Select at least one event'
        return
      }
      savingWebhook.value = true
      try {
        const payload = {
          name: webhookForm.value.name.trim(),
          url: webhookForm.value.url.trim(),
          secret: webhookForm.value.secret || null,
          events: webhookForm.value.events,
          enabled: webhookForm.value.enabled
        }
        await api.notifications.createWebhook(payload)
        toast.success('Webhook added successfully')
        closeAddWebhookModal()
        await fetchWebhooks()
      } catch (error) {
        webhookFormError.value = error.response?.data?.detail || 'Failed to save webhook'
        toast.error('Failed to add webhook')
      } finally {
        savingWebhook.value = false
      }
    }

    const triggerTestWebhook = async (hookId) => {
      testingWebhook.value = hookId
      try {
        const res = await api.notifications.testWebhook(hookId)
        toast.success(`Test sent — received HTTP ${res.data.response_code}`)
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to send test webhook')
      } finally {
        testingWebhook.value = null
      }
    }

    const deleteWebhookById = async (hookId, hookName) => {
      if (!confirm(`Delete webhook "${hookName}"?`)) return
      deletingWebhook.value = hookId
      try {
        await api.notifications.deleteWebhook(hookId)
        toast.success('Webhook deleted')
        await fetchWebhooks()
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to delete webhook')
      } finally {
        deletingWebhook.value = null
      }
    }

    // Proxmox Integration preferences (localStorage-backed)
    const proxmoxHosts = ref([])
    const loadingHosts = ref(false)
    const hostsError = ref(null)
    const defaultHost = ref(localStorage.getItem('depl0y_default_host') || '')
    const consoleNewTab = ref(localStorage.getItem('depl0y_console_new_tab') !== 'false')
    const consoleScale = ref(localStorage.getItem('depl0y_console_scale') !== 'false')
    const refreshInterval = ref(Number(localStorage.getItem('depl0y_refresh_interval')) || 30)

    const profileForm = ref({
      username: '',
      email: ''
    })

    const passwordForm = ref({
      current_password: '',
      new_password: '',
      confirm_password: ''
    })

    const fetchProxmoxHosts = async () => {
      loadingHosts.value = true
      hostsError.value = null
      try {
        const response = await api.proxmox.listHosts()
        proxmoxHosts.value = response.data
        // Validate stored default still exists
        if (defaultHost.value && !response.data.find(h => String(h.id) === defaultHost.value)) {
          defaultHost.value = ''
          localStorage.removeItem('depl0y_default_host')
        }
      } catch (error) {
        console.error('Failed to fetch Proxmox hosts:', error)
        hostsError.value = 'Could not load hosts'
      } finally {
        loadingHosts.value = false
      }
    }

    const saveDefaultHost = () => {
      if (defaultHost.value) {
        localStorage.setItem('depl0y_default_host', defaultHost.value)
        const host = proxmoxHosts.value.find(h => String(h.id) === defaultHost.value)
        toast.success(`Default host set to ${host ? host.name : defaultHost.value}`)
      } else {
        localStorage.removeItem('depl0y_default_host')
        toast.success('Default host cleared')
      }
    }

    const saveConsoleSetting = (key, value) => {
      localStorage.setItem(key, String(value))
      toast.success('Console preference saved')
    }

    const saveRefreshInterval = () => {
      const val = Math.min(300, Math.max(10, refreshInterval.value || 30))
      refreshInterval.value = val
      localStorage.setItem('depl0y_refresh_interval', String(val))
      toast.success(`Auto-refresh interval set to ${val}s`)
    }

    const fetchUser = async () => {
      try {
        const response = await api.auth.getMe()
        user.value = response.data
        profileForm.value.username = user.value.username
        profileForm.value.email = user.value.email
      } catch (error) {
        console.error('Failed to fetch user:', error)
      }
    }

    const fetchSystemInfo = async () => {
      try {
        const response = await api.dashboard.getStats()
        systemInfo.value = response.data
      } catch (error) {
        console.error('Failed to fetch system info:', error)
      }
    }

    const updateProfile = async () => {
      updatingProfile.value = true
      try {
        await api.users.update(user.value.id, { email: profileForm.value.email })
        toast.success('Profile updated successfully')
        await fetchUser()
      } catch (error) {
        console.error('Failed to update profile:', error)
      } finally {
        updatingProfile.value = false
      }
    }

    const changePassword = async () => {
      if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
        toast.error('New passwords do not match')
        return
      }

      changingPassword.value = true
      try {
        await api.users.changePassword({
          current_password: passwordForm.value.current_password,
          new_password: passwordForm.value.new_password
        })
        toast.success('Password changed successfully')
        passwordForm.value = {
          current_password: '',
          new_password: '',
          confirm_password: ''
        }
      } catch (error) {
        console.error('Failed to change password:', error)
      } finally {
        changingPassword.value = false
      }
    }

    const setupTOTP = async () => {
      totp_loading.value = true
      try {
        const response = await api.auth.setupTOTP()
        totpSetup.value = response.data
        showTOTPModal.value = true
      } catch (error) {
        console.error('Failed to setup TOTP:', error)
      } finally {
        totp_loading.value = false
      }
    }

    const verifyTOTP = async () => {
      try {
        await api.auth.verifyTOTP(totpCode.value)
        toast.success('2FA enabled successfully')
        showTOTPModal.value = false
        totpCode.value = ''
        await fetchUser()
      } catch (error) {
        toast.error('Invalid code. Please try again.')
        console.error('Failed to verify TOTP:', error)
      }
    }

    const disableTOTP = async () => {
      const code = prompt('Enter your 6-digit 2FA code to disable:')
      if (!code) return

      totp_loading.value = true
      try {
        await api.auth.disableTOTP(code)
        toast.success('2FA disabled successfully')
        await fetchUser()
      } catch (error) {
        toast.error('Failed to disable 2FA. Check your code.')
        console.error('Failed to disable TOTP:', error)
      } finally {
        totp_loading.value = false
      }
    }

    const getRoleBadge = (role) => {
      const badges = {
        admin: 'danger',
        operator: 'warning',
        viewer: 'info'
      }
      return badges[role] || 'info'
    }

    const refreshLogs = async () => {
      loadingLogs.value = true
      try {
        const response = await api.logs.getBackendLogs(logLines.value)
        backendLogs.value = response.data.logs
      } catch (error) {
        console.error('Failed to fetch logs:', error)
        toast.error('Failed to load backend logs')
      } finally {
        loadingLogs.value = false
      }
    }

    const checkSSHStatus = async () => {
      checkingSSH.value = true
      try {
        const response = await api.cloudImages.checkSSHStatus()
        sshStatus.value = response.data.configured
        if (sshStatus.value) {
          toast.success('SSH access is configured!')
        } else {
          toast.warning('SSH access not configured')
        }
      } catch (error) {
        console.error('Failed to check SSH status:', error)
        sshStatus.value = false
      } finally {
        checkingSSH.value = false
      }
    }

    const copyCommand = () => {
      navigator.clipboard.writeText('sudo /tmp/enable_cloud_images.sh')
      commandCopied.value = true
      toast.success('Command copied to clipboard!')
      setTimeout(() => {
        commandCopied.value = false
      }, 2000)
    }

    const enableCloudImages = async () => {
      if (!proxmoxPassword.value) {
        toast.error('Please enter your Proxmox password')
        return
      }

      enablingCloudImages.value = true
      setupError.value = null
      setupSuccess.value = null

      try {
        const response = await api.setup.enableCloudImages(proxmoxPassword.value)

        if (response.data.already_configured) {
          setupSuccess.value = response.data.message
          toast.success('Cloud images already enabled!')
        } else {
          setupSuccess.value = response.data.message
          toast.success('Cloud images enabled successfully!')
        }

        // Clear password
        proxmoxPassword.value = ''

        // Refresh SSH status
        setTimeout(async () => {
          await checkSSHStatus()
          showPasswordPrompt.value = false
          setupSuccess.value = null
        }, 2000)

      } catch (error) {
        console.error('Failed to enable cloud images:', error)
        setupError.value = error.response?.data?.detail || 'Failed to enable cloud images. Please check your password and try again.'
        toast.error('Setup failed: ' + setupError.value)
      } finally {
        enablingCloudImages.value = false
      }
    }

    const checkClusterSSHStatus = async () => {
      checkingClusterSSH.value = true
      try {
        const response = await api.cloudImages.checkSSHStatus()
        // Cluster SSH uses the same SSH keys as cloud images
        clusterSSHStatus.value = response.data.configured
      } catch (error) {
        console.error('Failed to check cluster SSH status:', error)
        clusterSSHStatus.value = false
      } finally {
        checkingClusterSSH.value = false
      }
    }

    const enableClusterSSH = async () => {
      if (!clusterPassword.value) {
        toast.error('Please enter your Proxmox password')
        return
      }

      enablingClusterSSH.value = true
      clusterSSHError.value = null
      clusterSSHSuccess.value = null

      try {
        const response = await api.setup.enableClusterSSH(clusterPassword.value)

        if (response.data.already_configured) {
          clusterSSHSuccess.value = response.data.message
          toast.success('Inter-node SSH already enabled!')
        } else {
          clusterSSHSuccess.value = response.data.message
          toast.success('Inter-node SSH enabled successfully!')
        }

        // Clear password
        clusterPassword.value = ''

        // Close modal after success and refresh status
        setTimeout(() => {
          showClusterSSHPrompt.value = false
          clusterSSHSuccess.value = null
          checkClusterSSHStatus()
        }, 2000)

      } catch (error) {
        console.error('Failed to enable inter-node SSH:', error)
        clusterSSHError.value = error.response?.data?.detail || 'Failed to enable inter-node SSH. Please check your password and try again.'
        toast.error('Setup failed: ' + clusterSSHError.value)
      } finally {
        enablingClusterSSH.value = false
      }
    }

    const isNewerThanLatest = (current, latest) => {
      try {
        const parse = v => (v || '').replace(/^v/, '').split('.').map(Number)
        const c = parse(current)
        const l = parse(latest)
        for (let i = 0; i < 3; i++) {
          if ((c[i] || 0) > (l[i] || 0)) return true
          if ((c[i] || 0) < (l[i] || 0)) return false
        }
        return false
      } catch { return false }
    }

    const checkForUpdates = async () => {
      checkingUpdates.value = true
      updateError.value = null

      try {
        const response = await api.systemUpdates.check()
        updateInfo.value = response.data

        if (response.data.update_available) {
          toast.info('Update available!')
        } else {
          toast.success('You\'re up to date!')
        }
      } catch (error) {
        console.error('Failed to check for updates:', error)
        updateError.value = error.response?.data?.detail || 'Failed to check for updates'
        toast.error('Failed to check for updates')
      } finally {
        checkingUpdates.value = false
      }
    }

    const _scrollLog = () => {
      nextTick(() => {
        if (logBodyEl.value) logBodyEl.value.scrollTop = logBodyEl.value.scrollHeight
      })
    }

    const _startLogPoll = () => {
      if (_logPollTimer) return
      _logPollTimer = setInterval(async () => {
        try {
          const res = await api.systemUpdates.log()
          updateLog.value = res.data.lines || []
          _scrollLog()
          if (res.data.done && !updateDone.value) {
            updateDone.value = true
            applyingUpdate.value = false
            clearInterval(_logPollTimer)
            _logPollTimer = null
            // Countdown then reload
            reloadCountdown.value = 15
            _reloadTimer = setInterval(() => {
              reloadCountdown.value--
              if (reloadCountdown.value <= 0) {
                clearInterval(_reloadTimer)
                window.location.reload()
              }
            }, 1000)
          } else if (res.data.failed && !updateFailed.value) {
            updateFailed.value = true
            applyingUpdate.value = false
            clearInterval(_logPollTimer)
            _logPollTimer = null
          }
        } catch {
          // Backend restarted — keep polling until it comes back
        }
      }, 2000)
    }

    const applyUpdate = async () => {
      if (!confirm('This will update Depl0y and restart the service. Continue?')) return

      applyingUpdate.value = true
      updateError.value = null
      updateSuccess.value = null
      updateLog.value = []
      updateDone.value = false
      updateFailed.value = false
      if (_logPollTimer) { clearInterval(_logPollTimer); _logPollTimer = null }
      if (_reloadTimer) { clearInterval(_reloadTimer); _reloadTimer = null }

      try {
        await api.systemUpdates.apply()
        toast.success('Update started — watch the progress log below.')
        _startLogPoll()
      } catch (error) {
        console.error('Failed to apply update:', error)
        updateError.value = error.response?.data?.detail || 'Failed to apply update'
        toast.error('Failed to apply update')
        applyingUpdate.value = false
      }
    }

    const checkHAStatus = async () => {
      checkingHA.value = true
      haError.value = null
      try {
        const response = await api.ha.checkStatus()
        haStatus.value = response.data
      } catch (error) {
        console.error('Failed to check HA status:', error)
        haError.value = error.response?.data?.detail || 'Failed to check HA status'
        haStatus.value = { enabled: false, protected_vms: 0 }
      } finally {
        checkingHA.value = false
      }
    }

    const enableHA = async () => {
      enablingHA.value = true
      haSetupError.value = null
      haSetupSuccess.value = null
      try {
        const response = await api.ha.enable({ proxmox_password: haPassword.value })
        haSetupSuccess.value = response.data.message || 'High Availability enabled successfully!'
        toast.success('High Availability enabled!')
        setTimeout(() => {
          showHAPrompt.value = false
          haPassword.value = ''
          checkHAStatus()
        }, 2000)
      } catch (error) {
        console.error('Failed to enable HA:', error)
        haSetupError.value = error.response?.data?.detail || 'Failed to enable HA'
        toast.error('Failed to enable High Availability')
      } finally {
        enablingHA.value = false
      }
    }

    const manageHAGroups = () => {
      showHAManagement.value = true
    }

    const fetchLinuxAgentSettings = async () => {
      linuxAgentLoading.value = true
      try {
        const [settingsRes, agentsRes] = await Promise.all([
          api.vmAgent.getSettings(),
          api.vmAgent.list()
        ])
        linuxAgentEnabled.value = settingsRes.data.enabled
        agentCount.value = agentsRes.data.length
      } catch (error) {
        // Non-admin or feature not yet configured — silently ignore
      } finally {
        linuxAgentLoading.value = false
      }
    }

    const saveLinuxAgentSettings = async () => {
      savingLinuxAgent.value = true
      linuxAgentError.value = null
      try {
        await api.vmAgent.updateSettings({ enabled: linuxAgentEnabled.value, ai_enabled: false })
        toast.success(`Linux VM Agent ${linuxAgentEnabled.value ? 'enabled' : 'disabled'}`)
      } catch (error) {
        linuxAgentError.value = error.response?.data?.detail || 'Failed to save settings'
        toast.error('Failed to save Linux Agent settings')
      } finally {
        savingLinuxAgent.value = false
      }
    }

    // ── General Settings ────────────────────────────────────────────────────
    const generalLoading = ref(false)
    const savingGeneral = ref(false)
    const generalError = ref(null)
    const generalValidationErrors = ref({})
    const smtpValidationErrors = ref({})
    const generalForm = ref({
      app_name: 'Depl0y',
      app_url: '',
      default_language: 'en',
      default_timezone: 'UTC',
      session_timeout_minutes: 480,
      max_login_attempts: 5,
      lockout_duration_minutes: 15,
      ip_allowlist: '',
      password_policy: '',
    })

    const _GENERAL_DEFAULTS = {
      app_name: 'Depl0y',
      app_url: '',
      default_language: 'en',
      default_timezone: 'UTC',
      session_timeout_minutes: 480,
      max_login_attempts: 5,
      lockout_duration_minutes: 15,
      ip_allowlist: '',
      password_policy: '',
    }

    const resetGeneralDefaults = () => {
      if (!confirm('Reset all General Settings to their default values?')) return
      Object.assign(generalForm.value, _GENERAL_DEFAULTS)
      generalValidationErrors.value = {}
      toast.info('General settings reset to defaults — click Save to apply')
      markDirty('general')
    }

    const _validateGeneralForm = () => {
      const errors = {}
      const timeout = Number(generalForm.value.session_timeout_minutes)
      if (!timeout || timeout < 5 || timeout > 10080) {
        errors.session_timeout_minutes = 'Must be between 5 and 10080 minutes'
      }
      const attempts = Number(generalForm.value.max_login_attempts)
      if (!attempts || attempts < 1 || attempts > 100) {
        errors.max_login_attempts = 'Must be between 1 and 100'
      }
      const allowlist = (generalForm.value.ip_allowlist || '').trim()
      if (allowlist) {
        const bad = []
        allowlist.split(',').forEach(raw => {
          const entry = raw.trim()
          if (!entry) return
          // Basic CIDR format check
          const cidrRe = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(?:\/\d{1,3})?$/
          if (!cidrRe.test(entry)) bad.push(entry)
        })
        if (bad.length > 0) {
          errors.ip_allowlist = `Invalid CIDR: ${bad.join(', ')}`
        }
      }
      generalValidationErrors.value = errors
      return Object.keys(errors).length === 0
    }

    const _validateSmtpForm = () => {
      const errors = {}
      const port = Number(smtpForm.value.smtp_port)
      if (smtpForm.value.smtp_port !== '' && (!Number.isInteger(port) || port < 1 || port > 65535)) {
        errors.smtp_port = 'Port must be between 1 and 65535'
      }
      smtpValidationErrors.value = errors
      return Object.keys(errors).length === 0
    }

    // ── System Health ────────────────────────────────────────────────────────
    const healthData = ref(null)
    const loadingHealth = ref(false)

    const fetchSystemHealth = async () => {
      loadingHealth.value = true
      try {
        const res = await api.system.health()
        healthData.value = res.data
      } catch (error) {
        toast.error('Failed to load health data')
      } finally {
        loadingHealth.value = false
      }
    }

    // ── SMTP Reset Defaults ──────────────────────────────────────────────────
    const resetSmtpDefaults = () => {
      if (!confirm('Reset SMTP settings to defaults? This will clear all SMTP configuration.')) return
      smtpForm.value = {
        smtp_host: '',
        smtp_port: 587,
        smtp_username: '',
        smtp_password: '',
        smtp_from: '',
        smtp_from_name: '',
        smtp_to: '',
      }
      smtpFormTls.value = true
      smtpValidationErrors.value = {}
      toast.info('SMTP settings reset — click Save to apply')
      markDirty('smtp')
    }

    const timezoneOptions = [
      { value: 'UTC', label: 'UTC' },
      { value: 'America/New_York', label: 'America/New_York (EST/EDT)' },
      { value: 'America/Chicago', label: 'America/Chicago (CST/CDT)' },
      { value: 'America/Denver', label: 'America/Denver (MST/MDT)' },
      { value: 'America/Los_Angeles', label: 'America/Los_Angeles (PST/PDT)' },
      { value: 'America/Sao_Paulo', label: 'America/Sao_Paulo (BRT)' },
      { value: 'Europe/London', label: 'Europe/London (GMT/BST)' },
      { value: 'Europe/Paris', label: 'Europe/Paris (CET/CEST)' },
      { value: 'Europe/Berlin', label: 'Europe/Berlin (CET/CEST)' },
      { value: 'Europe/Moscow', label: 'Europe/Moscow (MSK)' },
      { value: 'Asia/Dubai', label: 'Asia/Dubai (GST)' },
      { value: 'Asia/Kolkata', label: 'Asia/Kolkata (IST)' },
      { value: 'Asia/Singapore', label: 'Asia/Singapore (SGT)' },
      { value: 'Asia/Tokyo', label: 'Asia/Tokyo (JST)' },
      { value: 'Asia/Shanghai', label: 'Asia/Shanghai (CST)' },
      { value: 'Australia/Sydney', label: 'Australia/Sydney (AEST/AEDT)' },
      { value: 'Pacific/Auckland', label: 'Pacific/Auckland (NZST/NZDT)' },
    ]

    const fetchGeneralSettings = async () => {
      generalLoading.value = true
      try {
        const res = await api.system.getSettings()
        const s = res.data
        generalForm.value.app_name = s.app_name || 'Depl0y'
        generalForm.value.app_url = s.app_url || ''
        generalForm.value.default_language = s.default_language || 'en'
        generalForm.value.default_timezone = s.default_timezone || 'UTC'
        generalForm.value.session_timeout_minutes = parseInt(s.session_timeout_minutes) || 480
        generalForm.value.max_login_attempts = parseInt(s.max_login_attempts) || 5
        generalForm.value.lockout_duration_minutes = parseInt(s.lockout_duration_minutes) || 15
        generalForm.value.ip_allowlist = s.ip_allowlist || ''
        generalForm.value.password_policy = s.password_policy || ''
        // Also seed SMTP form from loaded settings
        smtpForm.value.smtp_host = s.smtp_host || ''
        smtpForm.value.smtp_port = parseInt(s.smtp_port) || 587
        smtpForm.value.smtp_username = s.smtp_username || ''
        smtpForm.value.smtp_password = s.smtp_password || ''
        smtpForm.value.smtp_from = s.smtp_from || ''
        smtpForm.value.smtp_from_name = s.smtp_from_name || ''
        smtpForm.value.smtp_to = s.smtp_to || ''
        smtpFormTls.value = (s.smtp_tls || 'true').toLowerCase() !== 'false'
        // Proxmox defaults
        pveDefaultsForm.value.pve_default_cpu_type = s.pve_default_cpu_type || 'host'
        pveDefaultsForm.value.pve_default_bridge = s.pve_default_bridge || 'vmbr0'
        pveDefaultsForm.value.pve_default_storage = s.pve_default_storage || 'local-lvm'
        pveDefaultsForm.value.pve_default_iso_storage = s.pve_default_iso_storage || 'local'
        pveDefaultsForm.value.pve_template_vmid = parseInt(s.pve_template_vmid) || 9000
        pveDefaultsForm.value.pve_console_url_pattern = s.pve_console_url_pattern || ''
        // Backup defaults
        backupDefaultsForm.value.backup_default_storage = s.backup_default_storage || ''
        backupDefaultsForm.value.backup_default_schedule = s.backup_default_schedule || '0 2 * * *'
        backupDefaultsForm.value.backup_keep_last = parseInt(s.backup_keep_last) || 7
        backupDefaultsForm.value.backup_keep_daily = parseInt(s.backup_keep_daily) || 7
        backupDefaultsForm.value.backup_keep_weekly = parseInt(s.backup_keep_weekly) || 4
        backupDefaultsForm.value.backup_keep_monthly = parseInt(s.backup_keep_monthly) || 3
        backupDefaultsForm.value.backup_email_notification = s.backup_email_notification || 'failure'
        // Log level
        logLevelSetting.value = s.log_level || 'INFO'
      } catch {
        // Non-admin — silently ignore
      } finally {
        generalLoading.value = false
      }
    }

    const saveGeneralSettings = async () => {
      if (!_validateGeneralForm()) {
        toast.error('Please fix validation errors before saving')
        return
      }
      savingGeneral.value = true
      generalError.value = null
      try {
        await api.system.updateSettings({
          app_name: generalForm.value.app_name,
          app_url: generalForm.value.app_url,
          default_language: generalForm.value.default_language,
          default_timezone: generalForm.value.default_timezone,
          session_timeout_minutes: String(generalForm.value.session_timeout_minutes),
          max_login_attempts: String(generalForm.value.max_login_attempts),
          lockout_duration_minutes: String(generalForm.value.lockout_duration_minutes),
          ip_allowlist: generalForm.value.ip_allowlist || '',
          password_policy: generalForm.value.password_policy || '',
        })
        toast.success('General settings saved')
        clearDirty('general')
      } catch (error) {
        generalError.value = error.response?.data?.detail || 'Failed to save general settings'
        toast.error('Failed to save general settings')
      } finally {
        savingGeneral.value = false
      }
    }

    // ── SMTP Settings ────────────────────────────────────────────────────────
    const smtpLoading = ref(false)
    const savingSmtp = ref(false)
    const smtpError = ref(null)
    const smtpFormTls = ref(true)
    const smtpForm = ref({
      smtp_host: '',
      smtp_port: 587,
      smtp_username: '',
      smtp_password: '',
      smtp_from: '',
      smtp_from_name: '',
      smtp_to: '',
    })

    const saveSmtpSettings = async () => {
      if (!_validateSmtpForm()) {
        toast.error('Please fix validation errors before saving')
        return
      }
      savingSmtp.value = true
      smtpError.value = null
      try {
        const payload = { ...smtpForm.value }
        payload.smtp_port = String(payload.smtp_port)
        payload.smtp_tls = smtpFormTls.value ? 'true' : 'false'
        // Don't store empty passwords — skip if blank
        if (!payload.smtp_password) delete payload.smtp_password
        await api.system.updateSettings(payload)
        toast.success('SMTP settings saved')
        clearDirty('smtp')
      } catch (error) {
        smtpError.value = error.response?.data?.detail || 'Failed to save SMTP settings'
        toast.error('Failed to save SMTP settings')
      } finally {
        savingSmtp.value = false
      }
    }

    // ── Proxmox VM Defaults ──────────────────────────────────────────────────
    const pveDefaultsLoading = ref(false)
    const savingPveDefaults = ref(false)
    const pveDefaultsError = ref(null)
    const pveDefaultsForm = ref({
      pve_default_cpu_type: 'host',
      pve_default_bridge: 'vmbr0',
      pve_default_storage: 'local-lvm',
      pve_default_iso_storage: 'local',
      pve_template_vmid: 9000,
      pve_console_url_pattern: '',
    })

    const savePveDefaults = async () => {
      savingPveDefaults.value = true
      pveDefaultsError.value = null
      try {
        const payload = { ...pveDefaultsForm.value }
        payload.pve_template_vmid = String(payload.pve_template_vmid)
        await api.system.updateSettings(payload)
        toast.success('Proxmox VM defaults saved')
      } catch (error) {
        pveDefaultsError.value = error.response?.data?.detail || 'Failed to save Proxmox defaults'
        toast.error('Failed to save Proxmox VM defaults')
      } finally {
        savingPveDefaults.value = false
      }
    }

    // ── Backup Defaults ──────────────────────────────────────────────────────
    const backupDefaultsLoading = ref(false)
    const savingBackupDefaults = ref(false)
    const backupDefaultsError = ref(null)
    const backupDefaultsForm = ref({
      backup_default_storage: '',
      backup_default_schedule: '0 2 * * *',
      backup_keep_last: 7,
      backup_keep_daily: 7,
      backup_keep_weekly: 4,
      backup_keep_monthly: 3,
      backup_email_notification: 'failure',
    })

    const saveBackupDefaults = async () => {
      savingBackupDefaults.value = true
      backupDefaultsError.value = null
      try {
        const payload = {}
        for (const [k, v] of Object.entries(backupDefaultsForm.value)) {
          payload[k] = String(v)
        }
        await api.system.updateSettings(payload)
        toast.success('Backup defaults saved')
      } catch (error) {
        backupDefaultsError.value = error.response?.data?.detail || 'Failed to save backup defaults'
        toast.error('Failed to save backup defaults')
      } finally {
        savingBackupDefaults.value = false
      }
    }

    // ── Maintenance ─────────────────────────────────────────────────────────
    const runningVacuum = ref(false)
    const vacuumResult = ref(null)
    const runningDbCheck = ref(false)
    const dbCheckResult = ref(null)
    const loadingCacheStats = ref(false)
    const cacheStats = ref(null)
    const clearingCache = ref(false)
    const logLevelSetting = ref('INFO')
    const savingLogLevel = ref(false)
    const showRestartConfirm = ref(false)
    const restarting = ref(false)
    const restartCountdown = ref(5)
    const restartError = ref(null)
    let _restartTimer = null

    const formatBytes = (bytes) => {
      if (!bytes) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    }

    const runDbVacuum = async () => {
      runningVacuum.value = true
      vacuumResult.value = null
      try {
        const res = await api.system.dbVacuum()
        vacuumResult.value = res.data
        toast.success('VACUUM completed successfully')
      } catch (error) {
        vacuumResult.value = { success: false, message: error.response?.data?.detail || 'VACUUM failed' }
        toast.error('VACUUM failed')
      } finally {
        runningVacuum.value = false
      }
    }

    const runDbCheck = async () => {
      runningDbCheck.value = true
      dbCheckResult.value = null
      try {
        const res = await api.system.dbCheck()
        dbCheckResult.value = res.data
        toast.success(res.data.ok ? 'Integrity check passed' : 'Integrity check FAILED')
      } catch (error) {
        toast.error('Integrity check failed')
      } finally {
        runningDbCheck.value = false
      }
    }

    const fetchCacheStats = async () => {
      loadingCacheStats.value = true
      try {
        const res = await api.system.getCacheStats()
        cacheStats.value = res.data
      } catch (error) {
        toast.error('Failed to load cache stats')
      } finally {
        loadingCacheStats.value = false
      }
    }

    const clearCache = async () => {
      clearingCache.value = true
      try {
        await api.system.clearCache()
        toast.success('PVE cache cleared')
        cacheStats.value = null
      } catch (error) {
        toast.error('Failed to clear cache')
      } finally {
        clearingCache.value = false
      }
    }

    const saveLogLevel = async () => {
      savingLogLevel.value = true
      try {
        await api.system.updateSettings({ log_level: logLevelSetting.value })
        toast.success(`Log level set to ${logLevelSetting.value}. Restart backend to apply.`)
      } catch (error) {
        toast.error('Failed to save log level')
      } finally {
        savingLogLevel.value = false
      }
    }

    const restartBackend = async () => {
      restarting.value = true
      restartError.value = null
      restartCountdown.value = 5
      try {
        await api.system.restartBackend()
        toast.warning('Backend is restarting…')
        // Countdown then reload
        _restartTimer = setInterval(() => {
          restartCountdown.value--
          if (restartCountdown.value <= 0) {
            clearInterval(_restartTimer)
            window.location.reload()
          }
        }, 1000)
      } catch (error) {
        restartError.value = error.response?.data?.detail || 'Failed to trigger restart'
        toast.error('Failed to restart backend')
        restarting.value = false
        showRestartConfirm.value = false
      }
    }

    onMounted(() => {
      fetchUser()
      fetchSystemInfo()
      fetchProxmoxHosts()
      checkSSHStatus()
      checkClusterSSHStatus()
      checkForUpdates()
      checkHAStatus()
      fetchLinuxAgentSettings()
      fetchWebhooks()
      fetchNotifRules()
      fetchGeneralSettings()
      fetchSystemHealth()
    })

    return {
      // Theme
      themeOptions,
      currentTheme,
      setTheme,
      // Language
      currentLocale,
      handleLocaleChange,
      isNewerThanLatest,
      systemInfo,
      user,
      profileForm,
      passwordForm,
      updatingProfile,
      changingPassword,
      totp_loading,
      showTOTPModal,
      totpSetup,
      totpCode,
      backendLogs,
      loadingLogs,
      logLines,
      sshStatus,
      checkingSSH,
      commandCopied,
      showSetupInstructions,
      showPasswordPrompt,
      proxmoxPassword,
      enablingCloudImages,
      setupError,
      setupSuccess,
      clusterSSHStatus,
      checkingClusterSSH,
      showClusterSSHPrompt,
      clusterPassword,
      enablingClusterSSH,
      clusterSSHError,
      clusterSSHSuccess,
      checkClusterSSHStatus,
      updateProfile,
      changePassword,
      setupTOTP,
      verifyTOTP,
      disableTOTP,
      getRoleBadge,
      refreshLogs,
      checkSSHStatus,
      copyCommand,
      enableCloudImages,
      enableClusterSSH,
      updateInfo,
      checkingUpdates,
      applyingUpdate,
      updateError,
      updateSuccess,
      updateLog,
      updateDone,
      updateFailed,
      reloadCountdown,
      terminalEl,
      logBodyEl,
      checkForUpdates,
      applyUpdate,
      haStatus,
      checkingHA,
      showHAPrompt,
      haPassword,
      enablingHA,
      haSetupError,
      haSetupSuccess,
      haError,
      showHAManagement,
      checkHAStatus,
      enableHA,
      manageHAGroups,
      linuxAgentEnabled,
      linuxAgentLoading,
      savingLinuxAgent,
      linuxAgentError,
      agentCount,
      saveLinuxAgentSettings,
      proxmoxHosts,
      loadingHosts,
      hostsError,
      defaultHost,
      consoleNewTab,
      consoleScale,
      refreshInterval,
      fetchProxmoxHosts,
      saveDefaultHost,
      saveConsoleSetting,
      saveRefreshInterval,
      // Notification Rules
      notifRules,
      notifRulesLoading,
      sendingTestNotif,
      testNotifResult,
      saveNotifRules,
      sendTestNotification,
      // Email
      testingEmail,
      testEmailResult,
      testEmailError,
      sendTestEmail,
      // Webhooks
      webhooks,
      webhooksLoading,
      webhooksError,
      showAddWebhookModal,
      savingWebhook,
      testingWebhook,
      deletingWebhook,
      webhookFormError,
      webhookForm,
      availableEvents,
      fetchWebhooks,
      closeAddWebhookModal,
      saveWebhook,
      triggerTestWebhook,
      deleteWebhookById,
      deliveryTimeAgo,
      // Dirty tracking / unsaved changes
      markDirty,
      clearDirty,
      dirtySections,
      hasDirtySection,
      // General Settings
      generalLoading,
      savingGeneral,
      generalError,
      generalValidationErrors,
      generalForm,
      timezoneOptions,
      saveGeneralSettings,
      resetGeneralDefaults,
      // SMTP
      smtpLoading,
      savingSmtp,
      smtpError,
      smtpValidationErrors,
      smtpForm,
      smtpFormTls,
      saveSmtpSettings,
      resetSmtpDefaults,
      // System Health
      healthData,
      loadingHealth,
      fetchSystemHealth,
      // Proxmox VM Defaults
      pveDefaultsLoading,
      savingPveDefaults,
      pveDefaultsError,
      pveDefaultsForm,
      savePveDefaults,
      // Backup Defaults
      backupDefaultsLoading,
      savingBackupDefaults,
      backupDefaultsError,
      backupDefaultsForm,
      saveBackupDefaults,
      // Maintenance
      runningVacuum,
      vacuumResult,
      runningDbCheck,
      dbCheckResult,
      loadingCacheStats,
      cacheStats,
      clearingCache,
      logLevelSetting,
      savingLogLevel,
      showRestartConfirm,
      restarting,
      restartCountdown,
      restartError,
      formatBytes,
      runDbVacuum,
      runDbCheck,
      fetchCacheStats,
      clearCache,
      saveLogLevel,
      restartBackend,
    }
  }
}
</script>

<style scoped>
/* ── Theme toggle ─────────────────────────────────────────────────────────── */
.theme-options {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.theme-option-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: border-color 0.15s, background 0.15s;
}

.theme-option-btn:hover {
  border-color: var(--primary-color);
  background: var(--background);
}

.theme-option-btn--active {
  border-color: var(--primary-color);
  background: rgba(37, 99, 235, 0.08);
  color: var(--primary-color);
}

.theme-option-icon {
  font-size: 1rem;
}

.theme-option-label {
  font-size: 0.875rem;
}

/* ── Profile ──────────────────────────────────────────────────────────────── */
.profile-content {
  padding: 2rem;
}

.profile-section {
  max-width: 800px;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding-bottom: 2rem;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 2rem;
}

.profile-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 2rem;
  font-weight: 700;
}

.profile-header h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
}

.subsection-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.profile-details {
  margin-top: 2rem;
}

.profile-form,
.password-form {
  max-width: 500px;
}

.totp-section {
  padding: 1.5rem;
  background-color: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  max-width: 500px;
}

.totp-enabled,
.totp-disabled {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.totp-setup {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.qr-code {
  padding: 1rem;
  background: white;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.qr-code img {
  display: block;
  max-width: 250px;
}

.secret-code {
  padding: 0.75rem 1rem;
  background-color: var(--background);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-family: monospace;
  font-size: 1rem;
  display: block;
  text-align: center;
  letter-spacing: 0.1em;
}

.totp-verify-form {
  width: 100%;
  max-width: 400px;
  margin-top: 1rem;
}

.modal {
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
  background: white;
  border-radius: 0.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
}

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

.about-content {
  padding: 2rem;
}

.logo-section {
  text-align: center;
  padding: 2rem 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 2rem;
}

.about-logo {
  font-size: 4rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -2px;
  color: var(--text-primary);
}

.logo-zero {
  color: #3b82f6;
}

.tagline {
  font-size: 1.25rem;
  color: var(--text-secondary);
  margin-top: 0.5rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  background-color: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.info-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.info-value {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.builder-section {
  margin: 2rem 0;
  padding: 2rem 0;
  border-top: 2px solid var(--border-color);
  border-bottom: 2px solid var(--border-color);
}

.builder-card {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1d4ed8 100%);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-lg);
}

.builder-icon {
  font-size: 3rem;
  filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3));
}

.builder-info {
  color: white;
}

.builder-info h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.9;
}

.builder-link {
  color: white;
  text-decoration: none;
  font-size: 1.75rem;
  display: inline-block;
  transition: transform 0.2s;
}

.builder-link:hover {
  transform: translateX(5px);
  text-decoration: underline;
}

.builder-url {
  margin: 0.25rem 0 0 0;
  font-size: 1rem;
  opacity: 0.8;
  font-family: monospace;
}

.features-section {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background-color: var(--background);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  transition: all 0.2s;
}

.feature-item:hover {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.feature-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  background-color: var(--secondary-color);
  color: white;
  border-radius: 50%;
  font-size: 0.875rem;
  font-weight: bold;
  flex-shrink: 0;
}

.system-info {
  padding: 1.5rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
}

.info-row:last-child {
  border-bottom: none;
}

.logs-content {
  padding: 1.5rem;
}

.logs-controls {
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.log-lines-select {
  margin: 0 0.5rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: white;
  cursor: pointer;
}

.logs-viewer {
  background-color: #1e1e1e;
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid var(--border-color);
  max-height: 600px;
  overflow-y: auto;
}

.logs-text {
  margin: 0;
  padding: 1rem;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.logs-empty {
  padding: 3rem;
  text-align: center;
  color: var(--text-secondary);
  border: 2px dashed var(--border-color);
  border-radius: 0.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Cloud Image Setup Styles */
.cloud-setup-content {
  padding: 2rem;
}

.info-box {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(147, 51, 234, 0.1));
  border: 1px solid var(--primary-color);
  border-radius: 0.5rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.info-box h4 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feature-list li {
  padding: 0.5rem 0;
  color: var(--text-secondary);
}

.success-box {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  padding: 1.5rem;
  background: #d1fae5;
  border: 2px solid #10b981;
  border-radius: 0.5rem;
  color: #065f46;
}

.warning-box {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  padding: 1.5rem;
  background: #fef3c7;
  border: 2px solid #f59e0b;
  border-radius: 0.5rem;
  color: #92400e;
}

.status-icon {
  font-size: 2rem;
  line-height: 1;
}

.success-box h4,
.warning-box h4 {
  margin: 0 0 0.5rem 0;
}

.success-box p,
.warning-box p {
  margin: 0 0 0.5rem 0;
}

.command-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #1e293b;
  padding: 1rem;
  border-radius: 0.375rem;
  margin: 1rem 0;
}

.command-box code {
  flex: 1;
  color: #10b981;
  font-family: monospace;
  font-size: 0.95rem;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}

.setup-instructions-modal {
  max-width: 900px;
}

.setup-instructions-modal .modal-body {
  max-height: 70vh;
  overflow-y: auto;
}

.setup-instructions-modal h4 {
  margin-top: 1.5rem;
  color: var(--primary-color);
}

.setup-instructions-modal h4:first-child {
  margin-top: 0;
}

.setup-instructions-modal ul,
.setup-instructions-modal ol {
  margin: 0.5rem 0 1rem 1.5rem;
}

.setup-instructions-modal code {
  background: #1e293b;
  color: #10b981;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.9rem;
}

.setup-instructions-modal pre {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.or-divider {
  text-align: center;
  margin: 1.5rem 0;
  position: relative;
}

.or-divider::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  border-top: 1px solid var(--border-color);
  z-index: 0;
}

.or-divider span {
  background: white;
  padding: 0 1rem;
  position: relative;
  z-index: 1;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 600;
}

.btn-lg {
  padding: 0.875rem 1.75rem;
  font-size: 1.125rem;
  font-weight: 600;
}

.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 52px;
  height: 28px;
  flex-shrink: 0;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: #cbd5e1;
  border-radius: 28px;
  transition: 0.2s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 4px;
  bottom: 4px;
  background-color: white;
  border-radius: 50%;
  transition: 0.2s;
}

.toggle-switch input:checked + .toggle-slider {
  background-color: #3b82f6;
}

.toggle-switch input:checked + .toggle-slider:before {
  transform: translateX(24px);
}

.linux-agent-settings {
  margin-top: 1rem;
}

.agent-stats {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.update-terminal {
  margin-top: 1.25rem;
  border: 1px solid #334155;
  border-radius: 0.5rem;
  overflow: hidden;
  font-family: 'Fira Mono', 'Consolas', monospace;
  font-size: 0.8rem;
}
.update-terminal__header {
  background: #1e293b;
  color: #94a3b8;
  padding: 0.4rem 0.75rem;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid #334155;
}
.update-terminal__body {
  background: #0f172a;
  color: #e2e8f0;
  margin: 0;
  padding: 0.75rem;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}
@keyframes spin { to { transform: rotate(360deg); } }
.terminal-spinner {
  display: inline-block;
  width: 0.8rem;
  height: 0.8rem;
  border: 2px solid #475569;
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
}

.error-message {
  background: #fee2e2;
  border: 1px solid #ef4444;
  color: #991b1b;
  padding: 1rem;
  border-radius: 0.375rem;
  margin-top: 1rem;
}

.success-message {
  background: #d1fae5;
  border: 1px solid #10b981;
  color: #065f46;
  padding: 1rem;
  border-radius: 0.375rem;
  margin-top: 1rem;
}

.mt-2 {
  margin-top: 0.5rem;
}

.text-sm {
  font-size: 0.875rem;
}

.text-muted {
  color: var(--text-secondary);
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .about-logo {
    font-size: 3rem;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .features-grid {
    grid-template-columns: 1fr;
  }

  .card-header {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons button {
    width: 100%;
  }
}

/* Webhook Styles */
.webhooks-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.webhook-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--background);
  transition: border-color 0.2s;
}

.webhook-row:hover {
  border-color: var(--primary-color);
}

.webhook-info {
  flex: 1;
  min-width: 0;
}

.webhook-header-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}

.webhook-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.webhook-url {
  margin: 0.25rem 0 0.5rem 0;
  word-break: break-all;
  font-family: monospace;
  font-size: 0.8rem;
}

.webhook-events {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.event-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  background: rgba(37, 99, 235, 0.1);
  color: var(--primary-color);
  border: 1px solid rgba(37, 99, 235, 0.3);
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.webhook-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
  align-items: flex-start;
}

.events-checkboxes {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.event-checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: border-color 0.15s, background 0.15s;
  user-select: none;
}

.event-checkbox-label:hover {
  border-color: var(--primary-color);
  background: rgba(37, 99, 235, 0.05);
}

.event-checkbox-label input[type="checkbox"] {
  accent-color: var(--primary-color);
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.badge-secondary {
  background-color: #6b7280;
  color: white;
  padding: 0.2em 0.6em;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.text-xs {
  font-size: 0.75rem;
}

/* ── Notification Rules ── */
.notif-rules-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── Webhook card / delivery log ── */
.webhook-card {
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.webhook-card .webhook-row {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.webhook-delivery-log {
  padding: 0.6rem 1rem 0.75rem;
  background: rgba(0, 0, 0, 0.12);
}

.delivery-log-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.65);
  margin: 0 0 0.4rem 0;
}

.delivery-log-table {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.delivery-log-row {
  display: grid;
  grid-template-columns: 1fr 80px 90px;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.73rem;
  padding: 3px 0;
}

.delivery-log-header {
  color: rgba(255, 255, 255, 0.65);
  font-weight: 600;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 4px;
  margin-bottom: 2px;
}

.delivery-event {
  color: rgba(255, 255, 255, 0.85);
  font-family: monospace;
  font-size: 0.72rem;
}

.delivery-status {
  display: flex;
  align-items: center;
}

.delivery-badge {
  font-size: 0.67rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 10px;
}

.badge-ok {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.badge-fail {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.delivery-time {
  color: rgba(255, 255, 255, 0.65);
  font-size: 0.68rem;
  text-align: right;
}

/* ── Settings sections shared styles ──────────────────────────────────────── */
.settings-group {
  padding-bottom: 0.5rem;
}

.settings-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}

.card-body {
  padding: 1.5rem 2rem;
}

/* ── Cache stats ──────────────────────────────────────────────────────────── */
.cache-stats-grid {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.cache-keys-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.cache-key-tag {
  background: rgba(37, 99, 235, 0.1);
  border: 1px solid rgba(37, 99, 235, 0.25);
  color: var(--primary-color);
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.72rem;
  font-family: monospace;
}

/* ── Restart confirm ──────────────────────────────────────────────────────── */
.restart-confirm-box {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
}

/* ── Info-box variants ────────────────────────────────────────────────────── */
.info-box.alert-success {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
  color: var(--text-primary);
}

.info-box.alert-danger {
  background: rgba(239, 68, 68, 0.08);
  border-color: #ef4444;
  color: var(--text-primary);
}

/* ── Flex utility ─────────────────────────────────────────────────────────── */
.flex {
  display: flex;
}

.gap-2 {
  gap: 0.5rem;
}

/* ── System Health checks ──────────────────────────────────────────────────── */
.health-checks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.health-check-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  background: var(--background);
}

.health-check-icon {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
}

.health-ok .health-check-icon {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.health-fail .health-check-icon {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

.health-warn .health-check-icon {
  background: rgba(234, 179, 8, 0.15);
  color: #ca8a04;
}

/* ── Unsaved changes banner ────────────────────────────────────────────────── */
.unsaved-changes-banner {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: #f59e0b;
  color: #1c1917;
  padding: 0.75rem 1.25rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 999;
  animation: slideIn 0.2s ease-out;
}

@keyframes slideIn {
  from { transform: translateY(1rem); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* ── btn-sm ────────────────────────────────────────────────────────────────── */
.btn-sm {
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
}
</style>
