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
                <input v-model="passwordForm.current_password" type="password" class="form-control" required />
              </div>

              <div class="form-group">
                <label class="form-label">New Password</label>
                <input v-model="passwordForm.new_password" type="password" class="form-control" required />
              </div>

              <div class="form-group">
                <label class="form-label">Confirm New Password</label>
                <input v-model="passwordForm.confirm_password" type="password" class="form-control" required />
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
          <p><strong>Latest Version:</strong> {{ updateInfo.latest_version }}</p>
          <p v-if="updateInfo.update_available" class="text-success">
            ✨ Update available!
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
          <button @click="checkForUpdates" class="btn btn-outline" :disabled="checkingUpdates">
            {{ checkingUpdates ? 'Checking...' : '🔍 Check for Updates' }}
          </button>
          <button
            v-if="updateInfo && updateInfo.update_available"
            @click="applyUpdate"
            class="btn btn-success"
            :disabled="applyingUpdate"
          >
            {{ applyingUpdate ? 'Updating...' : '⬇️ Install Update' }}
          </button>
        </div>

        <div v-if="updateError" class="error-message" style="margin-top: 1rem;">
          {{ updateError }}
        </div>

        <div v-if="updateSuccess" class="success-message" style="margin-top: 1rem;">
          {{ updateSuccess }}
        </div>
      </div>
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
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Settings',
  setup() {
    const toast = useToast()
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

    const profileForm = ref({
      username: '',
      email: ''
    })

    const passwordForm = ref({
      current_password: '',
      new_password: '',
      confirm_password: ''
    })

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

    const applyUpdate = async () => {
      if (!confirm('This will update Depl0y and restart the service. Continue?')) {
        return
      }

      applyingUpdate.value = true
      updateError.value = null
      updateSuccess.value = null

      try {
        const response = await api.systemUpdates.apply()
        updateSuccess.value = response.data.message
        toast.success('Update started! Service will restart shortly.')

        setTimeout(() => {
          toast.info('Reloading page in 20 seconds...')
          setTimeout(() => {
            window.location.reload()
          }, 20000)
        }, 5000)

      } catch (error) {
        console.error('Failed to apply update:', error)
        updateError.value = error.response?.data?.detail || 'Failed to apply update'
        toast.error('Failed to apply update')
      } finally {
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

    onMounted(() => {
      fetchUser()
      fetchSystemInfo()
      checkSSHStatus()
      checkClusterSSHStatus()
      checkForUpdates()
      checkHAStatus()
    })

    return {
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
      manageHAGroups
    }
  }
}
</script>

<style scoped>
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
</style>
