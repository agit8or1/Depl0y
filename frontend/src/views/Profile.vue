<template>
  <div class="profile-page">
    <div class="page-header">
      <h1>My Profile</h1>
      <p class="text-muted">Manage your account information and security settings</p>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading profile...</p>
    </div>

    <div v-else>
      <!-- Account Info Card (read-only) -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Account Information</h3>
        </div>
        <div class="card-body">
          <div class="profile-header mb-4">
            <div class="profile-avatar">{{ user ? user.username.charAt(0).toUpperCase() : '?' }}</div>
            <div>
              <h4>{{ user ? user.username : '' }}</h4>
              <p class="text-sm text-muted">{{ user ? user.email : '' }}</p>
              <span v-if="user" :class="['badge', 'badge-' + getRoleBadge(user.role)]">{{ user.role }}</span>
            </div>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Username</span>
              <span class="info-value">{{ user ? user.username : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Email</span>
              <span class="info-value">{{ user ? user.email : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Role</span>
              <span v-if="user" :class="['badge', 'badge-' + getRoleBadge(user.role)]">{{ user.role }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Member Since</span>
              <span class="info-value">{{ user ? formatDate(user.created_at) : '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Two-Factor Auth</span>
              <span v-if="user && user.totp_enabled" class="badge badge-success">Enabled</span>
              <span v-else class="badge badge-warning">Disabled</span>
            </div>
            <div class="info-item">
              <span class="info-label">Status</span>
              <span v-if="user && user.is_active" class="badge badge-success">Active</span>
              <span v-else class="badge badge-danger">Inactive</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Change Password Card -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Change Password</h3>
        </div>
        <div class="card-body">
          <form @submit.prevent="changePassword" class="password-form">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <input
                v-model="passwordForm.current_password"
                type="password"
                autocomplete="current-password"
                class="form-control"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">New Password</label>
              <input
                v-model="passwordForm.new_password"
                type="password"
                autocomplete="new-password"
                class="form-control"
                required
              />
              <p
                v-if="passwordForm.new_password && passwordForm.new_password.length < 8"
                class="field-hint field-error"
              >
                Password must be at least 8 characters
              </p>
            </div>

            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input
                v-model="passwordForm.confirm_password"
                type="password"
                autocomplete="new-password"
                class="form-control"
                required
              />
              <p
                v-if="passwordForm.confirm_password && passwordForm.new_password !== passwordForm.confirm_password"
                class="field-hint field-error"
              >
                Passwords do not match
              </p>
            </div>

            <div
              v-if="passwordMsg"
              :class="['alert', passwordMsgType === 'success' ? 'alert-success' : 'alert-danger']"
            >
              {{ passwordMsg }}
            </div>

            <button
              type="submit"
              class="btn btn-primary"
              :disabled="changingPassword || !passwordFormValid"
            >
              {{ changingPassword ? 'Changing...' : 'Change Password' }}
            </button>
          </form>
        </div>
      </div>

      <!-- Preferences Card -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Preferences</h3>
        </div>
        <div class="card-body">
          <p class="text-muted">
            Proxmox connection preferences and system options are managed in the Settings page.
          </p>
          <router-link to="/settings" class="btn btn-outline mt-3">
            Go to Settings
          </router-link>
        </div>
      </div>

      <!-- Developer Tools Card -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Developer Tools</h3>
        </div>
        <div class="card-body">
          <p class="text-muted" style="margin-bottom:1rem;">
            Use your API key to authenticate programmatic requests. The key grants the same access as your user account — keep it secret.
          </p>

          <!-- Current key hint -->
          <div v-if="apiKeys.length > 0" style="margin-bottom:1.25rem;">
            <label class="info-label">Active API Key</label>
            <div style="display:flex;align-items:center;gap:0.5rem;margin-top:0.25rem;">
              <code class="api-key-prefix" style="font-size:0.85rem;">{{ apiKeys[0].key_prefix }}...</code>
              <span class="text-muted text-sm">({{ apiKeys[0].name }})</span>
            </div>
            <p class="field-hint text-muted">
              Full key shown only at creation time. Create a new key below if you need it again.
            </p>
          </div>
          <div v-else class="text-muted" style="margin-bottom:1.25rem;font-size:0.875rem;">
            No active API keys. Create one in the API Keys section below, then return here for usage examples.
          </div>

          <!-- Code samples -->
          <div class="code-samples">
            <!-- cURL -->
            <div class="code-sample">
              <div class="code-sample-header">
                <span class="code-lang">cURL</span>
                <button class="btn btn-sm btn-outline" @click="copyCode('curl', apiKeys.length > 0 ? apiKeys[0].key_prefix + '...' : 'dk_YOUR_KEY_HERE')">
                  {{ copiedLang === 'curl' ? 'Copied!' : 'Copy' }}
                </button>
              </div>
              <pre class="code-block"><code>curl -H "X-API-Key: {{ apiKeys.length > 0 ? apiKeys[0].key_prefix + '...' : 'dk_YOUR_KEY_HERE' }}" \
  {{ window.location.origin }}/api/v1/cluster/resources</code></pre>
            </div>

            <!-- Python -->
            <div class="code-sample">
              <div class="code-sample-header">
                <span class="code-lang">Python</span>
                <button class="btn btn-sm btn-outline" @click="copyCode('python', apiKeys.length > 0 ? apiKeys[0].key_prefix + '...' : 'dk_YOUR_KEY_HERE')">
                  {{ copiedLang === 'python' ? 'Copied!' : 'Copy' }}
                </button>
              </div>
              <pre class="code-block"><code>import requests

headers = {"X-API-Key": "{{ apiKeys.length > 0 ? apiKeys[0].key_prefix + '...' : 'dk_YOUR_KEY_HERE' }}"}
r = requests.get(
    "{{ window.location.origin }}/api/v1/cluster/resources",
    headers=headers
)
print(r.json())</code></pre>
            </div>

            <!-- JavaScript -->
            <div class="code-sample">
              <div class="code-sample-header">
                <span class="code-lang">JavaScript</span>
                <button class="btn btn-sm btn-outline" @click="copyCode('js', apiKeys.length > 0 ? apiKeys[0].key_prefix + '...' : 'dk_YOUR_KEY_HERE')">
                  {{ copiedLang === 'js' ? 'Copied!' : 'Copy' }}
                </button>
              </div>
              <pre class="code-block"><code>const resp = await fetch('/api/v1/cluster/resources', {
  headers: { 'X-API-Key': '{{ apiKeys.length > 0 ? apiKeys[0].key_prefix + "..." : "dk_YOUR_KEY_HERE" }}' }
})
const data = await resp.json()</code></pre>
            </div>
          </div>

          <div style="margin-top:1.25rem;display:flex;gap:0.75rem;flex-wrap:wrap;">
            <router-link to="/api-explorer" class="btn btn-outline">
              Open API Explorer
            </router-link>
            <a href="/docs" target="_blank" rel="noopener" class="btn btn-outline">
              Swagger UI
            </a>
            <a href="/redoc" target="_blank" rel="noopener" class="btn btn-outline">
              ReDoc
            </a>
          </div>
        </div>
      </div>

      <!-- API Keys Card -->
      <div class="card">
        <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
          <h3>API Keys</h3>
          <button class="btn btn-primary" @click="showCreateKeyModal = true">+ Create API Key</button>
        </div>
        <div class="card-body">
          <p class="text-muted" style="margin-bottom:1rem;">
            API keys allow programmatic access to Depl0y. Keep keys secret — they grant full access as your user.
          </p>

          <div v-if="keysLoading" class="loading-state" style="padding:1rem 0;">
            <div class="spinner"></div>
            <p>Loading keys...</p>
          </div>

          <div v-else-if="apiKeys.length === 0" class="text-muted" style="padding:0.5rem 0;">
            No API keys yet. Create one to get started.
          </div>

          <div v-else class="api-keys-list">
            <div v-for="key in apiKeys" :key="key.id" class="api-key-row">
              <div class="api-key-info">
                <span class="api-key-name">{{ key.name }}</span>
                <code class="api-key-prefix">{{ key.key_prefix }}...</code>
                <span class="api-key-meta text-muted text-sm">
                  Created {{ formatDate(key.created_at) }}
                  <span v-if="key.last_used"> · Last used {{ formatDate(key.last_used) }}</span>
                  <span v-if="key.expires_at"> · Expires {{ formatDate(key.expires_at) }}</span>
                </span>
              </div>
              <button
                class="btn btn-sm btn-danger"
                :disabled="revokingKeyId === key.id"
                @click="revokeKey(key)"
              >
                {{ revokingKeyId === key.id ? 'Revoking...' : 'Revoke' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create API Key Modal -->
    <div v-if="showCreateKeyModal" class="modal-backdrop" @click.self="showCreateKeyModal = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Create API Key</h3>
          <button class="btn-close-x" @click="showCreateKeyModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Key Name <span style="color:#ef4444">*</span></label>
            <input
              v-model="newKeyForm.name"
              class="form-control"
              placeholder="e.g. CI/CD Pipeline, Automation Script"
              :disabled="creatingKey"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Expiry Date (optional)</label>
            <input
              v-model="newKeyForm.expires_at"
              type="date"
              class="form-control"
              :disabled="creatingKey"
            />
            <p class="field-hint text-muted">Leave blank for no expiry.</p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showCreateKeyModal = false" :disabled="creatingKey">Cancel</button>
          <button class="btn btn-primary" :disabled="!newKeyForm.name || creatingKey" @click="createKey">
            {{ creatingKey ? 'Creating...' : 'Create Key' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Show New Key Modal -->
    <div v-if="newKeyResult" class="modal-backdrop" @click.self="closeNewKeyResult">
      <div class="modal-box">
        <div class="modal-header">
          <h3>API Key Created</h3>
        </div>
        <div class="modal-body">
          <div class="alert alert-warning" style="margin-bottom:1rem;">
            This key will not be shown again. Copy it now and store it securely.
          </div>
          <label class="form-label">Your new API key:</label>
          <div class="key-display">
            <code class="key-value">{{ newKeyResult.key }}</code>
            <button class="btn btn-sm btn-outline" @click="copyKey(newKeyResult.key)">
              {{ keyCopied ? 'Copied!' : 'Copy' }}
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" @click="closeNewKeyResult">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useToast } from 'vue-toastification'
import api from '@/services/api'

export default {
  name: 'Profile',
  async setup() {
    const authStore = useAuthStore()
    const toast = useToast()

    const loading = ref(true)
    const user = ref(null)
    const changingPassword = ref(false)
    const passwordMsg = ref('')
    const passwordMsgType = ref('success')

    const passwordForm = ref({
      current_password: '',
      new_password: '',
      confirm_password: ''
    })

    // API Keys state
    const apiKeys = ref([])
    const keysLoading = ref(false)
    const showCreateKeyModal = ref(false)
    const creatingKey = ref(false)
    const newKeyForm = ref({ name: '', expires_at: '' })
    const newKeyResult = ref(null)
    const keyCopied = ref(false)
    const revokingKeyId = ref(null)

    // Developer Tools
    const copiedLang = ref('')
    const copyCode = (lang, keyHint) => {
      const origin = window.location.origin
      const samples = {
        curl: `curl -H "X-API-Key: ${keyHint}" \\\n  ${origin}/api/v1/cluster/resources`,
        python: `import requests\n\nheaders = {"X-API-Key": "${keyHint}"}\nr = requests.get(\n    "${origin}/api/v1/cluster/resources",\n    headers=headers\n)\nprint(r.json())`,
        js: `const resp = await fetch('/api/v1/cluster/resources', {\n  headers: { 'X-API-Key': '${keyHint}' }\n})\nconst data = await resp.json()`,
      }
      navigator.clipboard.writeText(samples[lang] || '').then(() => {
        copiedLang.value = lang
        setTimeout(() => { copiedLang.value = '' }, 2000)
      })
    }

    const passwordFormValid = computed(() => {
      const f = passwordForm.value
      return (
        f.current_password.length > 0 &&
        f.new_password.length >= 8 &&
        f.new_password === f.confirm_password
      )
    })

    const getRoleBadge = (role) => {
      const map = { admin: 'danger', operator: 'warning', viewer: 'info' }
      return map[role] || 'secondary'
    }

    const formatDate = (dateStr) => {
      if (!dateStr) return '—'
      return new Date(dateStr).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    }

    const loadProfile = async () => {
      loading.value = true
      try {
        const resp = await api.auth.getMe()
        user.value = resp.data
        authStore.user = resp.data
      } catch (e) {
        console.error('Failed to load profile', e)
      } finally {
        loading.value = false
      }
    }

    const loadApiKeys = async () => {
      keysLoading.value = true
      try {
        const resp = await api.auth.listApiKeys()
        apiKeys.value = resp.data.api_keys || []
      } catch (e) {
        console.error('Failed to load API keys', e)
      } finally {
        keysLoading.value = false
      }
    }

    const createKey = async () => {
      if (!newKeyForm.value.name.trim()) return
      creatingKey.value = true
      try {
        const payload = { name: newKeyForm.value.name.trim() }
        if (newKeyForm.value.expires_at) {
          payload.expires_at = new Date(newKeyForm.value.expires_at).toISOString()
        }
        const resp = await api.auth.createApiKey(payload)
        newKeyResult.value = resp.data
        showCreateKeyModal.value = false
        newKeyForm.value = { name: '', expires_at: '' }
        toast.success('API key created')
        await loadApiKeys()
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to create API key'
        toast.error(msg)
      } finally {
        creatingKey.value = false
      }
    }

    const closeNewKeyResult = () => {
      newKeyResult.value = null
      keyCopied.value = false
    }

    const copyKey = (key) => {
      navigator.clipboard.writeText(key).then(() => {
        keyCopied.value = true
        setTimeout(() => { keyCopied.value = false }, 2000)
      })
    }

    const revokeKey = async (key) => {
      if (!confirm(`Revoke API key "${key.name}"? This cannot be undone.`)) return
      revokingKeyId.value = key.id
      try {
        await api.auth.deleteApiKey(key.id)
        toast.success(`API key "${key.name}" revoked`)
        await loadApiKeys()
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to revoke key')
      } finally {
        revokingKeyId.value = null
      }
    }

    const changePassword = async () => {
      passwordMsg.value = ''
      if (!passwordFormValid.value) return
      changingPassword.value = true
      try {
        await api.auth.changePassword({
          current_password: passwordForm.value.current_password,
          new_password: passwordForm.value.new_password
        })
        toast.success('Password changed successfully')
        passwordMsg.value = 'Password changed successfully'
        passwordMsgType.value = 'success'
        passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
      } catch (e) {
        const msg = e.response?.data?.detail || 'Failed to change password'
        passwordMsg.value = msg
        passwordMsgType.value = 'error'
      } finally {
        changingPassword.value = false
      }
    }

    await loadProfile()
    await loadApiKeys()

    return {
      loading,
      user,
      passwordForm,
      passwordFormValid,
      changingPassword,
      passwordMsg,
      passwordMsgType,
      getRoleBadge,
      formatDate,
      changePassword,
      // API Keys
      apiKeys,
      keysLoading,
      showCreateKeyModal,
      creatingKey,
      newKeyForm,
      newKeyResult,
      keyCopied,
      revokingKeyId,
      createKey,
      closeNewKeyResult,
      copyKey,
      revokeKey,
      // Developer Tools
      copiedLang,
      copyCode,
      window,
    }
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 680px;
  margin: 0 auto;
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0 0 0.25rem;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.profile-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--primary, #3b82f6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  flex-shrink: 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.info-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: 0.55;
}

.info-value {
  font-size: 0.95rem;
}

.password-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 420px;
}

.field-hint {
  font-size: 0.8rem;
  margin: 0.3rem 0 0;
}

.field-error {
  color: #ef4444;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem;
  color: var(--text-muted, #6b7280);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-bottom: 0.75rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.mb-4 { margin-bottom: 1.25rem; }
.mt-3 { display: inline-block; margin-top: 0.75rem; }
.card-body { padding: 1.25rem; }
.text-muted { opacity: 0.65; }
.text-sm { font-size: 0.875rem; }

/* Developer Tools */
.code-samples {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.code-sample {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.4rem;
  overflow: hidden;
}

.code-sample-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.75rem;
  background: var(--surface, #f3f4f6);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.code-lang {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
}

.code-block {
  margin: 0;
  padding: 0.75rem;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.78rem;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  overflow-x: auto;
  line-height: 1.5;
}

.code-block code {
  font-family: inherit;
}

/* API Keys */
.api-keys-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.api-key-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.4rem;
  background: var(--background, #f9fafb);
}

.api-key-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.api-key-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.api-key-prefix {
  font-size: 0.78rem;
  font-family: monospace;
  background: var(--surface, #f3f4f6);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  width: fit-content;
}

.api-key-meta {
  font-size: 0.75rem;
}

/* Modals */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: var(--card-bg, #fff);
  border-radius: 0.6rem;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
}

.btn-close-x {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--text-muted, #6b7280);
  line-height: 1;
  padding: 0 0.25rem;
}

.modal-body {
  padding: 1.1rem 1.25rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 0.75rem 1.25rem 1rem;
  border-top: 1px solid var(--border-color, #e5e7eb);
}

.alert-warning {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fcd34d;
  border-radius: 0.4rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.875rem;
}

.key-display {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.4rem;
}

.key-value {
  flex: 1;
  font-family: monospace;
  font-size: 0.78rem;
  word-break: break-all;
  background: var(--surface, #f3f4f6);
  padding: 0.4rem 0.6rem;
  border-radius: 4px;
  border: 1px solid var(--border-color, #e5e7eb);
}
</style>
