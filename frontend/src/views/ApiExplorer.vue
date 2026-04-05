<template>
  <div class="api-explorer">
    <div class="page-header">
      <div>
        <h1>API Explorer</h1>
        <p class="text-muted">Browse, test and copy Depl0y API endpoints interactively</p>
      </div>
      <div class="header-actions">
        <div class="search-wrap">
          <span class="search-icon">&#128269;</span>
          <input
            v-model="search"
            class="search-input"
            placeholder="Search endpoints..."
            type="text"
          />
          <button v-if="search" class="search-clear" @click="search = ''">&#215;</button>
        </div>
        <button class="btn btn-sm btn-outline" @click="fetchFromOpenApi" :disabled="loadingOpenApi" title="Reload endpoint list from /api/v1/openapi-summary">
          {{ loadingOpenApi ? 'Loading...' : 'Sync API' }}
        </button>
        <a href="/docs" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Swagger UI</a>
        <a href="/redoc" target="_blank" rel="noopener" class="btn btn-outline btn-sm">ReDoc</a>
      </div>
    </div>

    <!-- Auth info banner -->
    <div class="auth-banner">
      <span class="auth-icon">&#128274;</span>
      <span>
        <strong>Authentication:</strong>
        Your current session JWT is attached automatically to all requests.
        For scripts, use an API key (<code>Authorization: Bearer dpl0y_...</code>) — create one in
        <router-link to="/profile">Profile &rarr; API Keys</router-link>.
      </span>
      <span v-if="tokenPresent" class="token-badge token-ok">Token active</span>
      <span v-else class="token-badge token-missing">Not logged in</span>
    </div>

    <div class="explorer-layout">
      <!-- Sidebar: endpoint list -->
      <aside class="endpoint-sidebar">
        <div class="sidebar-stats">
          <span class="stat-pill">{{ totalEndpoints }} endpoints</span>
          <span class="stat-pill">{{ filteredTotalEndpoints }} shown</span>
        </div>

        <div
          v-for="group in filteredGroups"
          :key="group.tag"
          class="endpoint-group"
        >
          <div class="group-label" @click="toggleGroup(group.tag)">
            <span class="group-name">{{ group.tag }}</span>
            <span class="group-count">{{ group.endpoints.length }}</span>
            <span class="group-chevron">{{ collapsedGroups.has(group.tag) ? '&#9654;' : '&#9660;' }}</span>
          </div>
          <div v-if="!collapsedGroups.has(group.tag)" class="group-endpoints">
            <button
              v-for="ep in group.endpoints"
              :key="ep.method + ep.path"
              :class="['endpoint-item', { active: selectedEndpoint === ep }]"
              @click="selectEndpoint(ep)"
            >
              <span :class="['method-badge', 'badge-' + ep.method.toLowerCase()]">
                {{ ep.method }}
              </span>
              <span class="ep-path">{{ ep.shortPath }}</span>
            </button>
          </div>
        </div>

        <div v-if="filteredGroups.length === 0" class="no-results text-muted">
          No endpoints match "<em>{{ search }}</em>"
        </div>
      </aside>

      <!-- Main panel: endpoint detail -->
      <main class="endpoint-detail" v-if="selectedEndpoint">
        <div class="ep-header">
          <span :class="['method-badge-lg', 'badge-' + selectedEndpoint.method.toLowerCase()]">
            {{ selectedEndpoint.method }}
          </span>
          <code class="ep-full-path">{{ selectedEndpoint.path }}</code>
          <div class="ep-header-actions">
            <button class="btn btn-sm btn-outline" @click="copyCurl" title="Copy as cURL">
              {{ curlCopied ? 'Copied!' : 'Copy cURL' }}
            </button>
            <button class="btn btn-sm btn-outline" @click="copyPath" title="Copy path">
              {{ pathCopied ? 'Copied!' : 'Copy path' }}
            </button>
          </div>
        </div>

        <p v-if="selectedEndpoint.description" class="ep-description">
          {{ selectedEndpoint.description }}
        </p>
        <p v-else-if="selectedEndpoint.summary" class="ep-description text-muted">
          {{ selectedEndpoint.summary }}
        </p>

        <!-- Auth note -->
        <div class="auth-note">
          <span class="auth-note-icon">&#128274;</span>
          <span>
            <strong>Authentication required.</strong>
            Your JWT token is attached automatically. For external scripts, pass
            <code>Authorization: Bearer &lt;token_or_api_key&gt;</code>.
          </span>
        </div>

        <!-- Path parameters -->
        <div v-if="pathParams.length > 0" class="ep-section">
          <h4 class="section-title">Path Parameters</h4>
          <table class="param-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Required</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="param in pathParams" :key="param.name">
                <td><code>{{ param.name }}</code></td>
                <td class="text-muted">string</td>
                <td><span class="badge badge-danger-soft">required</span></td>
                <td>
                  <input
                    v-model="tryItParams[param.name]"
                    class="param-input"
                    :placeholder="'Enter ' + param.name"
                    type="text"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Query parameters (for GET/DELETE) -->
        <div v-if="['GET','DELETE'].includes(selectedEndpoint.method)" class="ep-section">
          <h4 class="section-title">
            Query Parameters
            <span class="text-muted section-subtitle">(optional)</span>
          </h4>
          <div class="query-params-area">
            <div v-for="(val, key) in tryItQuery" :key="key" class="query-param-row">
              <input
                v-model="queryKeys[key]"
                class="param-input param-key"
                placeholder="key"
                @input="renameQueryKey(key, queryKeys[key])"
              />
              <input v-model="tryItQuery[key]" class="param-input param-val" placeholder="value" />
              <button class="btn btn-sm btn-danger-soft" @click="removeQueryParam(key)" title="Remove">&#215;</button>
            </div>
            <button class="btn btn-sm btn-outline add-param-btn" @click="addQueryParam">+ Add parameter</button>
          </div>
        </div>

        <!-- Request body (for POST/PUT/PATCH) -->
        <div v-if="['POST','PUT','PATCH'].includes(selectedEndpoint.method)" class="ep-section">
          <div class="section-title-row">
            <h4 class="section-title">
              Request Body
              <span class="text-muted section-subtitle">(JSON)</span>
            </h4>
            <button class="btn btn-sm btn-outline" @click="formatBody" title="Format JSON">Format</button>
          </div>
          <textarea
            v-model="requestBody"
            class="body-editor"
            placeholder="{}"
            rows="8"
            spellcheck="false"
          ></textarea>
          <p v-if="bodyError" class="field-error">{{ bodyError }}</p>
        </div>

        <!-- Send Request -->
        <div class="ep-section try-section">
          <button
            class="btn btn-primary send-btn"
            :disabled="executing"
            @click="execute"
          >
            <span v-if="executing" class="spinner"></span>
            {{ executing ? 'Sending...' : 'Send Request' }}
          </button>
          <span v-if="lastResponse" class="response-status" :class="statusClass">
            {{ lastResponse.status }} {{ lastResponse.statusText }}
          </span>
          <span v-if="lastResponse" class="resp-time text-muted">
            {{ lastResponse.time }}ms
          </span>
        </div>

        <!-- Response -->
        <div v-if="lastResponse" class="ep-section response-section">
          <div class="response-header">
            <h4 class="section-title">Response</h4>
            <div class="response-header-actions">
              <button class="btn btn-sm btn-outline" @click="copyResponse" title="Copy response JSON">
                {{ responseCopied ? 'Copied!' : 'Copy' }}
              </button>
              <button class="btn btn-sm btn-outline" @click="lastResponse = null" title="Clear response">Clear</button>
            </div>
          </div>
          <pre class="response-body"><code v-html="highlightedResponse"></code></pre>
        </div>
      </main>

      <!-- Empty state -->
      <main class="endpoint-detail empty-state" v-else>
        <div class="empty-content">
          <div class="empty-icon">&#9889;</div>
          <h3>Select an endpoint</h3>
          <p class="text-muted">Choose an API endpoint from the sidebar to view details and test it interactively.</p>
          <div class="empty-links">
            <a href="/docs" target="_blank" class="btn btn-outline btn-sm">Swagger UI</a>
            <a href="/redoc" target="_blank" class="btn btn-outline btn-sm">ReDoc</a>
            <a href="/api/v1/openapi.json" target="_blank" class="btn btn-outline btn-sm">OpenAPI JSON</a>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'

// Full hardcoded endpoint list grouped by tag
const HARDCODED_ENDPOINTS = [
  // Authentication
  { method: 'POST',   path: '/api/v1/auth/login',              tag: 'Authentication', summary: 'Login — obtain JWT tokens', description: 'Authenticate with username, password, and optional TOTP code. Returns access_token and refresh_token.' },
  { method: 'POST',   path: '/api/v1/auth/refresh',            tag: 'Authentication', summary: 'Refresh access token', description: 'Exchange a valid refresh_token for new access and refresh tokens.' },
  { method: 'GET',    path: '/api/v1/auth/me',                 tag: 'Authentication', summary: 'Get current user info' },
  { method: 'PATCH',  path: '/api/v1/auth/me/password',        tag: 'Authentication', summary: 'Change current user password' },
  { method: 'POST',   path: '/api/v1/auth/logout',             tag: 'Authentication', summary: 'Logout (invalidate refresh token)' },
  { method: 'POST',   path: '/api/v1/auth/totp/setup',         tag: 'Authentication', summary: 'Setup TOTP 2FA' },
  { method: 'POST',   path: '/api/v1/auth/totp/verify',        tag: 'Authentication', summary: 'Verify and enable TOTP 2FA' },
  { method: 'POST',   path: '/api/v1/auth/totp/disable',       tag: 'Authentication', summary: 'Disable TOTP 2FA' },
  { method: 'GET',    path: '/api/v1/auth/api-keys',           tag: 'Authentication', summary: 'List API keys' },
  { method: 'POST',   path: '/api/v1/auth/api-keys',           tag: 'Authentication', summary: 'Create API key', description: 'Creates a long-lived API key prefixed with dpl0y_. The key value is shown only once.' },
  { method: 'DELETE', path: '/api/v1/auth/api-keys/{key_id}',  tag: 'Authentication', summary: 'Revoke API key' },

  // Users
  { method: 'GET',    path: '/api/v1/users/',                         tag: 'Users', summary: 'List users (admin only)' },
  { method: 'POST',   path: '/api/v1/users/',                         tag: 'Users', summary: 'Create user (admin only)' },
  { method: 'GET',    path: '/api/v1/users/{id}',                     tag: 'Users', summary: 'Get user by ID' },
  { method: 'PUT',    path: '/api/v1/users/{id}',                     tag: 'Users', summary: 'Update user' },
  { method: 'PATCH',  path: '/api/v1/users/{id}',                     tag: 'Users', summary: 'Partially update user' },
  { method: 'DELETE', path: '/api/v1/users/{id}',                     tag: 'Users', summary: 'Delete user' },
  { method: 'PATCH',  path: '/api/v1/users/{id}/status',              tag: 'Users', summary: 'Set user active/inactive' },
  { method: 'POST',   path: '/api/v1/users/{id}/reset-password',      tag: 'Users', summary: 'Reset user password (admin)' },
  { method: 'POST',   path: '/api/v1/users/{id}/disable-totp',        tag: 'Users', summary: 'Disable user TOTP (admin)' },
  { method: 'POST',   path: '/api/v1/users/invalidate-sessions/{id}', tag: 'Users', summary: 'Invalidate user sessions' },
  { method: 'POST',   path: '/api/v1/users/invalidate-sessions-all',  tag: 'Users', summary: 'Invalidate all sessions (admin)' },

  // Proxmox Hosts
  { method: 'GET',    path: '/api/v1/proxmox/',               tag: 'Proxmox Hosts', summary: 'List Proxmox hosts', description: 'Returns all registered Proxmox hosts with connection status and last-polled stats.' },
  { method: 'POST',   path: '/api/v1/proxmox/',               tag: 'Proxmox Hosts', summary: 'Add Proxmox host' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}',           tag: 'Proxmox Hosts', summary: 'Get Proxmox host' },
  { method: 'PUT',    path: '/api/v1/proxmox/{id}',           tag: 'Proxmox Hosts', summary: 'Update Proxmox host' },
  { method: 'DELETE', path: '/api/v1/proxmox/{id}',           tag: 'Proxmox Hosts', summary: 'Delete Proxmox host' },
  { method: 'POST',   path: '/api/v1/proxmox/{id}/test',      tag: 'Proxmox Hosts', summary: 'Test host connection' },
  { method: 'POST',   path: '/api/v1/proxmox/{id}/poll',      tag: 'Proxmox Hosts', summary: 'Poll host for current state', description: 'Synchronises all nodes, VMs, containers, and storage from the Proxmox API into the Depl0y database.' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}/nodes',     tag: 'Proxmox Hosts', summary: 'List nodes for host' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}/stats',     tag: 'Proxmox Hosts', summary: 'Get host statistics' },

  // Dashboard
  { method: 'GET',    path: '/api/v1/dashboard/stats',     tag: 'Dashboard', summary: 'Get dashboard statistics', description: 'Returns VM counts, host counts, and aggregate resource usage.' },
  { method: 'GET',    path: '/api/v1/dashboard/resources', tag: 'Dashboard', summary: 'Get resource overview' },
  { method: 'GET',    path: '/api/v1/dashboard/activity',  tag: 'Dashboard', summary: 'Get recent activity' },
  { method: 'GET',    path: '/api/v1/dashboard/summary',   tag: 'Dashboard', summary: 'Dashboard summary (compact)' },

  // Virtual Machines
  { method: 'GET',    path: '/api/v1/vms/',                tag: 'Virtual Machines', summary: 'List managed VMs' },
  { method: 'POST',   path: '/api/v1/vms/',                tag: 'Virtual Machines', summary: 'Create/deploy VM' },
  { method: 'GET',    path: '/api/v1/vms/{id}',            tag: 'Virtual Machines', summary: 'Get VM by ID' },
  { method: 'PUT',    path: '/api/v1/vms/{id}',            tag: 'Virtual Machines', summary: 'Update VM record' },
  { method: 'DELETE', path: '/api/v1/vms/{id}',            tag: 'Virtual Machines', summary: 'Delete VM record' },
  { method: 'POST',   path: '/api/v1/vms/{id}/start',      tag: 'Virtual Machines', summary: 'Start VM' },
  { method: 'POST',   path: '/api/v1/vms/{id}/stop',       tag: 'Virtual Machines', summary: 'Stop VM' },
  { method: 'GET',    path: '/api/v1/vms/{id}/status',     tag: 'Virtual Machines', summary: 'Get VM status' },
  { method: 'GET',    path: '/api/v1/vms/{id}/progress',   tag: 'Virtual Machines', summary: 'Get VM deployment progress' },
  { method: 'POST',   path: '/api/v1/vms/adopt',           tag: 'Virtual Machines', summary: 'Adopt existing PVE VM into Depl0y' },

  // PVE VM Control
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/config',                       tag: 'PVE VM Control', summary: 'Get VM configuration' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/config',                       tag: 'PVE VM Control', summary: 'Update VM configuration' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/status',                       tag: 'PVE VM Control', summary: 'Get VM runtime status' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/start',                        tag: 'PVE VM Control', summary: 'Start VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/stop',                        tag: 'PVE VM Control', summary: 'Stop VM (immediate)' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/shutdown',                    tag: 'PVE VM Control', summary: 'Graceful shutdown' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/reboot',                      tag: 'PVE VM Control', summary: 'Reboot VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/reset',                       tag: 'PVE VM Control', summary: 'Hard reset VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/suspend',                     tag: 'PVE VM Control', summary: 'Suspend VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/resume',                      tag: 'PVE VM Control', summary: 'Resume VM' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots',                   tag: 'PVE VM Control', summary: 'List snapshots' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots',                   tag: 'PVE VM Control', summary: 'Create snapshot' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots/{snap}',            tag: 'PVE VM Control', summary: 'Delete snapshot' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots/{snap}/rollback',   tag: 'PVE VM Control', summary: 'Rollback to snapshot' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/clone',                       tag: 'PVE VM Control', summary: 'Clone VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/migrate',                     tag: 'PVE VM Control', summary: 'Migrate VM to another node' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/template',                    tag: 'PVE VM Control', summary: 'Convert VM to template' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}',                             tag: 'PVE VM Control', summary: 'Delete VM permanently' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk',                        tag: 'PVE VM Control', summary: 'Add disk to VM' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk/{disk}/resize',          tag: 'PVE VM Control', summary: 'Resize VM disk' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk/{disk}',                 tag: 'PVE VM Control', summary: 'Delete/detach VM disk' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/network',                     tag: 'PVE VM Control', summary: 'Add NIC to VM' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/network/{nic}',               tag: 'PVE VM Control', summary: 'Remove NIC from VM' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/rrddata',                     tag: 'PVE VM Control', summary: 'Get VM performance data' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules',              tag: 'PVE VM Control', summary: 'Get VM firewall rules' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules',              tag: 'PVE VM Control', summary: 'Add VM firewall rule' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules/{pos}',        tag: 'PVE VM Control', summary: 'Update VM firewall rule' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules/{pos}',        tag: 'PVE VM Control', summary: 'Delete VM firewall rule' },

  // PVE Node/Cluster
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/status',                         tag: 'PVE Node/Cluster', summary: 'Get cluster status' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/nextid',                         tag: 'PVE Node/Cluster', summary: 'Get next available VM ID' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/status',                    tag: 'PVE Node/Cluster', summary: 'Get node status' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/rrddata',                   tag: 'PVE Node/Cluster', summary: 'Get node performance data' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/vms',                       tag: 'PVE Node/Cluster', summary: 'List VMs on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/tasks',                     tag: 'PVE Node/Cluster', summary: 'List node tasks' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/storage',                   tag: 'PVE Node/Cluster', summary: 'List node storage' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network',                   tag: 'PVE Node/Cluster', summary: 'List node network interfaces' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc',                       tag: 'PVE Node/Cluster', summary: 'List LXC containers on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/disks/list',                tag: 'PVE Node/Cluster', summary: 'List physical disks on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/services',                  tag: 'PVE Node/Cluster', summary: 'List node services' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/services/{service}/{cmd}',  tag: 'PVE Node/Cluster', summary: 'Control node service (start/stop/restart)' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/access/users',                           tag: 'PVE Node/Cluster', summary: 'List PVE users' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/pools',                                  tag: 'PVE Node/Cluster', summary: 'List resource pools' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/pools',                                  tag: 'PVE Node/Cluster', summary: 'Create resource pool' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/backup',                         tag: 'PVE Node/Cluster', summary: 'List backup schedules' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/backup',                         tag: 'PVE Node/Cluster', summary: 'Create backup schedule' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/vzdump',                    tag: 'PVE Node/Cluster', summary: 'Run backup (vzdump)' },

  // LXC Containers
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc',                              tag: 'LXC', summary: 'Create LXC container' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/config',                tag: 'LXC', summary: 'Get container config' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/config',                tag: 'LXC', summary: 'Update container config' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/status',               tag: 'LXC', summary: 'Get container status' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/start',                tag: 'LXC', summary: 'Start container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/stop',                 tag: 'LXC', summary: 'Stop container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/shutdown',             tag: 'LXC', summary: 'Shutdown container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/reboot',               tag: 'LXC', summary: 'Reboot container' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots',            tag: 'LXC', summary: 'List container snapshots' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots',            tag: 'LXC', summary: 'Create container snapshot' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots/{snap}/rollback', tag: 'LXC', summary: 'Rollback container snapshot' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}',                      tag: 'LXC', summary: 'Delete container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/clone',                tag: 'LXC', summary: 'Clone container' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/rrddata',              tag: 'LXC', summary: 'Container performance data' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/resize',               tag: 'LXC', summary: 'Resize container disk' },

  // Task Queue
  { method: 'GET',    path: '/api/v1/tasks/running',                           tag: 'Task Queue', summary: 'List currently running tasks', description: 'Returns all Proxmox tasks actively being tracked by Depl0y.' },
  { method: 'GET',    path: '/api/v1/tasks/history',                           tag: 'Task Queue', summary: 'Task history' },
  { method: 'GET',    path: '/api/v1/tasks/{host_id}/{node}/{upid}/status',    tag: 'Task Queue', summary: 'Get task status' },
  { method: 'GET',    path: '/api/v1/tasks/{host_id}/{node}/{upid}/log',       tag: 'Task Queue', summary: 'Get task log' },
  { method: 'DELETE', path: '/api/v1/tasks/{host_id}/{node}/{upid}',           tag: 'Task Queue', summary: 'Stop task' },

  // Alerts
  { method: 'GET',    path: '/api/v1/alerts/active',           tag: 'Alerts', summary: 'Get active alerts', description: 'Returns currently firing alert rules across all monitored resources.' },
  { method: 'POST',   path: '/api/v1/alerts/{id}/dismiss',     tag: 'Alerts', summary: 'Dismiss alert' },
  { method: 'POST',   path: '/api/v1/alerts/dismiss-all',      tag: 'Alerts', summary: 'Dismiss all alerts' },
  { method: 'GET',    path: '/api/v1/alerts/history',          tag: 'Alerts', summary: 'Alert history' },
  { method: 'GET',    path: '/api/v1/alerts/rules',            tag: 'Alerts', summary: 'List alert rules' },
  { method: 'POST',   path: '/api/v1/alerts/rules',            tag: 'Alerts', summary: 'Create alert rule' },
  { method: 'PUT',    path: '/api/v1/alerts/rules/{id}',       tag: 'Alerts', summary: 'Update alert rule' },
  { method: 'DELETE', path: '/api/v1/alerts/rules/{id}',       tag: 'Alerts', summary: 'Delete alert rule' },
  { method: 'POST',   path: '/api/v1/alerts/rules/{id}/toggle', tag: 'Alerts', summary: 'Toggle alert rule enabled/disabled' },
  { method: 'POST',   path: '/api/v1/alerts/evaluate',         tag: 'Alerts', summary: 'Trigger immediate alert evaluation' },

  // Cluster Operations
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/tasks',                              tag: 'Cluster Operations', summary: 'List cluster-wide tasks' },
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/replication',                        tag: 'Cluster Operations', summary: 'List replication jobs' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/replication',                        tag: 'Cluster Operations', summary: 'Create replication job' },
  { method: 'PUT',    path: '/api/v1/cluster/{host_id}/replication/{jobId}',                tag: 'Cluster Operations', summary: 'Update replication job' },
  { method: 'DELETE', path: '/api/v1/cluster/{host_id}/replication/{jobId}',                tag: 'Cluster Operations', summary: 'Delete replication job' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/replication/{jobId}/schedule_now',   tag: 'Cluster Operations', summary: 'Force replication job now' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/nodes/{node}/evacuate',              tag: 'Cluster Operations', summary: 'Evacuate node (migrate all VMs off)' },
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/log',                                tag: 'Cluster Operations', summary: 'Get cluster event log' },

  // High Availability
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/ha/resources',              tag: 'High Availability', summary: 'List HA resources' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/ha/resources',              tag: 'High Availability', summary: 'Add HA resource' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/cluster/ha/resources/{sid}',        tag: 'High Availability', summary: 'Update HA resource' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/cluster/ha/resources/{sid}',        tag: 'High Availability', summary: 'Remove HA resource' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/ha/groups',                 tag: 'High Availability', summary: 'List HA groups' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/ha/groups',                 tag: 'High Availability', summary: 'Create HA group' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/cluster/ha/groups/{groupid}',       tag: 'High Availability', summary: 'Update HA group' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/cluster/ha/groups/{groupid}',       tag: 'High Availability', summary: 'Delete HA group' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/ha/status',                 tag: 'High Availability', summary: 'Get HA status' },

  // Network / SDN
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network',              tag: 'Network', summary: 'List node network interfaces' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/network',              tag: 'Network', summary: 'Create network interface' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network/{iface}',      tag: 'Network', summary: 'Update network interface' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/nodes/{node}/network/{iface}',      tag: 'Network', summary: 'Delete network interface' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network',              tag: 'Network', summary: 'Apply pending network config' },
  { method: 'GET',    path: '/api/v1/sdn/{host_id}/vnets',                                  tag: 'Network', summary: 'List SDN VNets' },
  { method: 'POST',   path: '/api/v1/sdn/{host_id}/vnets',                                  tag: 'Network', summary: 'Create SDN VNet' },
  { method: 'DELETE', path: '/api/v1/sdn/{host_id}/vnets/{vnet}',                           tag: 'Network', summary: 'Delete SDN VNet' },
  { method: 'GET',    path: '/api/v1/sdn/{host_id}/zones',                                  tag: 'Network', summary: 'List SDN zones' },
  { method: 'POST',   path: '/api/v1/sdn/{host_id}/zones',                                  tag: 'Network', summary: 'Create SDN zone' },
  { method: 'POST',   path: '/api/v1/sdn/{host_id}/apply',                                  tag: 'Network', summary: 'Apply SDN configuration' },

  // Backup / PBS
  { method: 'GET',    path: '/api/v1/pbs/',                                         tag: 'Backup', summary: 'List PBS servers' },
  { method: 'POST',   path: '/api/v1/pbs/',                                         tag: 'Backup', summary: 'Add PBS server' },
  { method: 'GET',    path: '/api/v1/pbs/{id}',                                     tag: 'Backup', summary: 'Get PBS server' },
  { method: 'PUT',    path: '/api/v1/pbs/{id}',                                     tag: 'Backup', summary: 'Update PBS server' },
  { method: 'DELETE', path: '/api/v1/pbs/{id}',                                     tag: 'Backup', summary: 'Delete PBS server' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/test',                           tag: 'Backup', summary: 'Test PBS connection' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/datastores',                     tag: 'Backup', summary: 'List PBS datastores' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/snapshots',      tag: 'Backup', summary: 'List backup snapshots in datastore' },
  { method: 'POST',   path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/verify',         tag: 'Backup', summary: 'Verify backup snapshot' },
  { method: 'DELETE', path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/snapshots',      tag: 'Backup', summary: 'Delete backup snapshot' },
  { method: 'POST',   path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/prune',          tag: 'Backup', summary: 'Prune backup group' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/tasks',                          tag: 'Backup', summary: 'List PBS tasks' },

  // PVE Firewall
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/ipsets',                tag: 'PVE Firewall', summary: 'List IPSets' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/ipsets',                tag: 'PVE Firewall', summary: 'Create IPSet' },
  { method: 'DELETE', path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}',         tag: 'PVE Firewall', summary: 'Delete IPSet' },
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}',         tag: 'PVE Firewall', summary: 'List IPSet entries' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}',         tag: 'PVE Firewall', summary: 'Add IPSet entry' },
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/aliases',               tag: 'PVE Firewall', summary: 'List firewall aliases' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/aliases',               tag: 'PVE Firewall', summary: 'Create firewall alias' },
  { method: 'PUT',    path: '/api/v1/pve-firewall/{host_id}/aliases/{name}',        tag: 'PVE Firewall', summary: 'Update firewall alias' },
  { method: 'DELETE', path: '/api/v1/pve-firewall/{host_id}/aliases/{name}',        tag: 'PVE Firewall', summary: 'Delete firewall alias' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules',    tag: 'PVE Firewall', summary: 'List cluster firewall rules' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules',    tag: 'PVE Firewall', summary: 'Add cluster firewall rule' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules/{pos}', tag: 'PVE Firewall', summary: 'Delete cluster firewall rule' },

  // Security
  { method: 'GET',    path: '/api/v1/security/settings',            tag: 'Security', summary: 'Get security settings' },
  { method: 'PUT',    path: '/api/v1/security/settings',            tag: 'Security', summary: 'Update security settings' },
  { method: 'GET',    path: '/api/v1/security/lockouts',            tag: 'Security', summary: 'List locked accounts' },
  { method: 'DELETE', path: '/api/v1/security/lockouts/{username}', tag: 'Security', summary: 'Unlock account' },
  { method: 'GET',    path: '/api/v1/security/failed-logins',       tag: 'Security', summary: 'List failed login attempts' },
  { method: 'GET',    path: '/api/v1/security/ip-list',             tag: 'Security', summary: 'List IP allow/block list' },
  { method: 'POST',   path: '/api/v1/security/ip-list',             tag: 'Security', summary: 'Add IP list entry' },
  { method: 'DELETE', path: '/api/v1/security/ip-list/{id}',        tag: 'Security', summary: 'Delete IP list entry' },
  { method: 'PATCH',  path: '/api/v1/security/ip-list/{id}/toggle', tag: 'Security', summary: 'Toggle IP list entry' },
  { method: 'GET',    path: '/api/v1/security/geoip',               tag: 'Security', summary: 'List GeoIP rules' },
  { method: 'POST',   path: '/api/v1/security/geoip',               tag: 'Security', summary: 'Add GeoIP rule' },
  { method: 'DELETE', path: '/api/v1/security/geoip/{id}',          tag: 'Security', summary: 'Delete GeoIP rule' },
  { method: 'GET',    path: '/api/v1/security/events',              tag: 'Security', summary: 'List security events' },
  { method: 'GET',    path: '/api/v1/security/login-history',       tag: 'Security', summary: 'Get login history' },

  // System
  { method: 'GET',    path: '/api/v1/system/info',        tag: 'System', summary: 'Get system information and version' },
  { method: 'GET',    path: '/api/v1/system/health',      tag: 'System', summary: 'System health check', description: 'Returns the health status of the Depl0y backend and its components.' },
  { method: 'GET',    path: '/api/v1/system/diagnostics', tag: 'System', summary: 'Full diagnostic bundle (admin)' },
  { method: 'POST',   path: '/api/v1/system/db-check',    tag: 'System', summary: 'SQLite integrity check (admin)' },
  { method: 'POST',   path: '/api/v1/system/test-email',  tag: 'System', summary: 'Send test email (admin)' },
  { method: 'GET',    path: '/api/v1/system/metrics',     tag: 'System', summary: 'Get system metrics (admin)', description: 'Returns request counts, user totals, API key totals, and uptime.' },

  // Audit Log
  { method: 'GET',    path: '/api/v1/audit/', tag: 'Audit Log', summary: 'List audit log entries (admin)', description: 'Returns paginated audit log entries with user, action, resource, timestamp, and duration.' },

  // Notifications
  { method: 'GET',    path: '/api/v1/notifications/in-app',                     tag: 'Notifications', summary: 'List in-app notifications' },
  { method: 'POST',   path: '/api/v1/notifications/in-app/mark-read',           tag: 'Notifications', summary: 'Mark notifications as read' },
  { method: 'DELETE', path: '/api/v1/notifications/in-app/{id}',               tag: 'Notifications', summary: 'Delete notification' },
  { method: 'GET',    path: '/api/v1/notifications/settings',                   tag: 'Notifications', summary: 'Get notification settings' },
  { method: 'PUT',    path: '/api/v1/notifications/settings',                   tag: 'Notifications', summary: 'Update notification settings' },
  { method: 'GET',    path: '/api/v1/notifications/webhooks',                   tag: 'Notifications', summary: 'List webhooks' },
  { method: 'POST',   path: '/api/v1/notifications/webhooks',                   tag: 'Notifications', summary: 'Create webhook' },
  { method: 'PUT',    path: '/api/v1/notifications/webhooks/{id}',              tag: 'Notifications', summary: 'Update webhook' },
  { method: 'DELETE', path: '/api/v1/notifications/webhooks/{id}',              tag: 'Notifications', summary: 'Delete webhook' },
  { method: 'POST',   path: '/api/v1/notifications/webhooks/{id}/test',         tag: 'Notifications', summary: 'Test webhook delivery' },
  { method: 'GET',    path: '/api/v1/notifications/webhooks/{id}/deliveries',   tag: 'Notifications', summary: 'Get webhook delivery history' },

  // Developer Tools
  { method: 'GET',    path: '/api/v1/openapi-summary', tag: 'Developer Tools', summary: 'List all API routes (simplified OpenAPI)', description: 'Returns all registered routes with method, path, tag, and summary. Used to power the API Explorer sync.' },
]

// Attach shortPath
HARDCODED_ENDPOINTS.forEach(ep => {
  ep.shortPath = ep.path.replace('/api/v1', '').replace(/\{([^}]+)\}/g, ':$1')
})

export default {
  name: 'ApiExplorer',
  setup() {
    const search = ref('')
    const selectedEndpoint = ref(null)
    const collapsedGroups = ref(new Set())
    const tryItParams = ref({})
    const tryItQuery = ref({})
    const queryKeys = ref({})
    const requestBody = ref('{}')
    const bodyError = ref('')
    const executing = ref(false)
    const lastResponse = ref(null)
    const curlCopied = ref(false)
    const pathCopied = ref(false)
    const responseCopied = ref(false)
    const loadingOpenApi = ref(false)
    const endpoints = ref([...HARDCODED_ENDPOINTS])
    let queryCounter = 0

    const tokenPresent = computed(() => !!localStorage.getItem('access_token'))

    // Group endpoints by tag
    const grouped = computed(() => {
      const map = {}
      endpoints.value.forEach(ep => {
        if (!map[ep.tag]) map[ep.tag] = []
        map[ep.tag].push(ep)
      })
      return Object.entries(map).map(([tag, epList]) => ({ tag, endpoints: epList }))
    })

    // Filter by search
    const filteredGroups = computed(() => {
      if (!search.value.trim()) return grouped.value
      const q = search.value.toLowerCase()
      return grouped.value
        .map(g => ({
          ...g,
          endpoints: g.endpoints.filter(ep =>
            ep.path.toLowerCase().includes(q) ||
            ep.method.toLowerCase().includes(q) ||
            (ep.summary || '').toLowerCase().includes(q) ||
            (ep.description || '').toLowerCase().includes(q) ||
            g.tag.toLowerCase().includes(q)
          )
        }))
        .filter(g => g.endpoints.length > 0)
    })

    const totalEndpoints = computed(() => endpoints.value.length)
    const filteredTotalEndpoints = computed(() =>
      filteredGroups.value.reduce((sum, g) => sum + g.endpoints.length, 0)
    )

    // Extract path parameters from the selected endpoint
    const pathParams = computed(() => {
      if (!selectedEndpoint.value) return []
      const matches = selectedEndpoint.value.path.matchAll(/\{([^}]+)\}/g)
      return Array.from(matches).map(m => ({ name: m[1] }))
    })

    const selectEndpoint = (ep) => {
      selectedEndpoint.value = ep
      tryItParams.value = {}
      tryItQuery.value = {}
      queryKeys.value = {}
      lastResponse.value = null
      bodyError.value = ''
      requestBody.value = '{}'
      queryCounter = 0
      pathParams.value.forEach(p => {
        tryItParams.value[p.name] = ''
      })
    }

    const toggleGroup = (tag) => {
      const s = new Set(collapsedGroups.value)
      if (s.has(tag)) s.delete(tag)
      else s.add(tag)
      collapsedGroups.value = s
    }

    const addQueryParam = () => {
      const k = `param_${queryCounter++}`
      tryItQuery.value = { ...tryItQuery.value, [k]: '' }
      queryKeys.value = { ...queryKeys.value, [k]: '' }
    }

    const removeQueryParam = (key) => {
      const q = { ...tryItQuery.value }
      const qk = { ...queryKeys.value }
      delete q[key]
      delete qk[key]
      tryItQuery.value = q
      queryKeys.value = qk
    }

    const renameQueryKey = (oldKey, newKey) => {
      if (newKey === oldKey) return
      const val = tryItQuery.value[oldKey]
      const q = { ...tryItQuery.value }
      delete q[oldKey]
      q[newKey] = val
      tryItQuery.value = q
    }

    const formatBody = () => {
      try {
        const parsed = JSON.parse(requestBody.value)
        requestBody.value = JSON.stringify(parsed, null, 2)
        bodyError.value = ''
      } catch (e) {
        bodyError.value = 'Invalid JSON: ' + e.message
      }
    }

    const buildUrl = () => {
      if (!selectedEndpoint.value) return ''
      let path = selectedEndpoint.value.path
      Object.entries(tryItParams.value).forEach(([k, v]) => {
        path = path.replace(`{${k}}`, v || `{${k}}`)
      })
      const queryParts = []
      Object.entries(tryItQuery.value).forEach(([k, v]) => {
        const key = queryKeys.value[k] || k
        if (key && v !== '') {
          queryParts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`)
        }
      })
      if (queryParts.length > 0) path += '?' + queryParts.join('&')
      return path
    }

    const execute = async () => {
      if (!selectedEndpoint.value) return
      bodyError.value = ''
      executing.value = true
      lastResponse.value = null

      const ep = selectedEndpoint.value
      const token = localStorage.getItem('access_token')

      let path = ep.path.replace('/api/v1', '')
      Object.entries(tryItParams.value).forEach(([k, v]) => {
        path = path.replace(`{${k}}`, v || `{${k}}`)
      })

      const queryParts = []
      Object.entries(tryItQuery.value).forEach(([k, v]) => {
        const key = queryKeys.value[k] || k
        if (key && v !== '') queryParts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`)
      })
      if (queryParts.length > 0) path += '?' + queryParts.join('&')

      let body = undefined
      if (['POST', 'PUT', 'PATCH'].includes(ep.method)) {
        try {
          const trimmed = requestBody.value.trim()
          body = trimmed && trimmed !== '{}' ? JSON.parse(trimmed) : undefined
        } catch (e) {
          bodyError.value = 'Invalid JSON: ' + e.message
          executing.value = false
          return
        }
      }

      const start = Date.now()
      try {
        const axiosLib = (await import('axios')).default
        const resp = await axiosLib({
          method: ep.method,
          url: path,
          baseURL: '/api/v1',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          data: body,
          validateStatus: () => true,
        })
        lastResponse.value = {
          status: resp.status,
          statusText: resp.statusText,
          data: resp.data,
          time: Date.now() - start,
        }
      } catch (e) {
        lastResponse.value = {
          status: 0,
          statusText: 'Network Error',
          data: { error: e.message },
          time: Date.now() - start,
        }
      } finally {
        executing.value = false
      }
    }

    const statusClass = computed(() => {
      if (!lastResponse.value) return ''
      const s = lastResponse.value.status
      if (s >= 200 && s < 300) return 'status-ok'
      if (s >= 400 && s < 500) return 'status-warn'
      if (s >= 500) return 'status-err'
      return 'status-muted'
    })

    const highlightedResponse = computed(() => {
      if (!lastResponse.value) return ''
      try {
        const json = JSON.stringify(lastResponse.value.data, null, 2)
        return json
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, (match) => {
            let cls = 'json-num'
            if (/^"/.test(match)) {
              cls = /:$/.test(match) ? 'json-key' : 'json-str'
            } else if (/true|false/.test(match)) {
              cls = 'json-bool'
            } else if (/null/.test(match)) {
              cls = 'json-null'
            }
            return `<span class="${cls}">${match}</span>`
          })
      } catch {
        return String(lastResponse.value.data)
      }
    })

    const copyCurl = () => {
      if (!selectedEndpoint.value) return
      const token = localStorage.getItem('access_token') || 'YOUR_TOKEN'
      const url = window.location.origin + buildUrl()
      const ep = selectedEndpoint.value
      let curl = `curl -X ${ep.method} '${url}' \\\n  -H 'Authorization: Bearer ${token}' \\\n  -H 'Content-Type: application/json'`
      if (['POST', 'PUT', 'PATCH'].includes(ep.method)) {
        const b = requestBody.value.trim() || '{}'
        curl += ` \\\n  -d '${b}'`
      }
      copyToClipboard(curl).then(() => {
        curlCopied.value = true
        setTimeout(() => { curlCopied.value = false }, 2000)
      })
    }

    const copyPath = () => {
      if (!selectedEndpoint.value) return
      copyToClipboard(window.location.origin + buildUrl()).then(() => {
        pathCopied.value = true
        setTimeout(() => { pathCopied.value = false }, 2000)
      })
    }

    const copyResponse = () => {
      if (!lastResponse.value) return
      copyToClipboard(JSON.stringify(lastResponse.value.data, null, 2)).then(() => {
        responseCopied.value = true
        setTimeout(() => { responseCopied.value = false }, 2000)
      })
    }

    const fetchFromOpenApi = async () => {
      loadingOpenApi.value = true
      try {
        const token = localStorage.getItem('access_token')
        const axiosLib = (await import('axios')).default
        const resp = await axiosLib.get('/api/v1/openapi-summary', {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          validateStatus: () => true,
        })
        if (resp.status === 200 && Array.isArray(resp.data)) {
          // Merge live data with hardcoded (prefer live descriptions)
          const liveMap = {}
          resp.data.forEach(item => {
            liveMap[item.method + item.path] = item
          })
          // Keep hardcoded as base, overlay live summaries/descriptions
          const merged = HARDCODED_ENDPOINTS.map(ep => {
            const live = liveMap[ep.method + ep.path]
            if (live) {
              return {
                ...ep,
                summary: live.summary || ep.summary,
                description: live.description || ep.description,
                tag: live.tag || ep.tag,
              }
            }
            return ep
          })
          // Add any endpoints from live that aren't hardcoded
          resp.data.forEach(item => {
            const key = item.method + item.path
            const exists = HARDCODED_ENDPOINTS.some(ep => ep.method + ep.path === key)
            if (!exists) {
              merged.push({
                method: item.method,
                path: item.path,
                tag: item.tag || 'Other',
                summary: item.summary || '',
                description: item.description || '',
                shortPath: item.path.replace('/api/v1', '').replace(/\{([^}]+)\}/g, ':$1'),
              })
            }
          })
          endpoints.value = merged
        }
      } catch (e) {
        // silently ignore — hardcoded list is still shown
      } finally {
        loadingOpenApi.value = false
      }
    }

    onMounted(() => {
      // Silently try to sync from live API on mount
      fetchFromOpenApi()
    })

    return {
      search,
      selectedEndpoint,
      collapsedGroups,
      filteredGroups,
      totalEndpoints,
      filteredTotalEndpoints,
      pathParams,
      tryItParams,
      tryItQuery,
      queryKeys,
      requestBody,
      bodyError,
      executing,
      lastResponse,
      statusClass,
      highlightedResponse,
      curlCopied,
      pathCopied,
      responseCopied,
      loadingOpenApi,
      tokenPresent,
      selectEndpoint,
      toggleGroup,
      addQueryParam,
      removeQueryParam,
      renameQueryKey,
      formatBody,
      execute,
      copyCurl,
      copyPath,
      copyResponse,
      fetchFromOpenApi,
    }
  }
}
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────── */
.api-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1.25rem;
  gap: 0.75rem;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h1 { margin: 0 0 0.2rem; }

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* Search */
.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.55rem;
  font-size: 0.8rem;
  opacity: 0.5;
  pointer-events: none;
}

.search-input {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.35rem;
  padding: 0.4rem 1.8rem 0.4rem 1.8rem;
  font-size: 0.875rem;
  background: var(--card-bg, #fff);
  color: var(--text, #111);
  width: 220px;
  outline: none;
}

.search-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15);
}

.search-clear {
  position: absolute;
  right: 0.4rem;
  background: none;
  border: none;
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0;
}

/* Auth banner */
.auth-banner {
  background: rgba(59,130,246,0.06);
  border: 1px solid rgba(59,130,246,0.2);
  border-radius: 0.4rem;
  padding: 0.6rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.82rem;
  color: var(--text, #374151);
  flex-wrap: wrap;
}

.auth-icon { font-size: 1rem; flex-shrink: 0; }

.auth-banner a {
  color: #3b82f6;
  text-decoration: underline;
}

.auth-banner code {
  background: rgba(0,0,0,0.07);
  border-radius: 3px;
  padding: 0.1rem 0.3rem;
  font-size: 0.8em;
}

.token-badge {
  margin-left: auto;
  border-radius: 999px;
  padding: 0.15rem 0.65rem;
  font-size: 0.72rem;
  font-weight: 600;
  flex-shrink: 0;
}

.token-ok      { background: #d1fae5; color: #065f46; }
.token-missing { background: #fee2e2; color: #991b1b; }

/* Explorer layout */
.explorer-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 1rem;
  flex: 1;
  min-height: 0;
  height: calc(100vh - 220px);
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.endpoint-sidebar {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.sidebar-stats {
  display: flex;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  background: var(--surface, #f9fafb);
}

.stat-pill {
  font-size: 0.7rem;
  background: var(--border-color, #e5e7eb);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  color: var(--text-muted, #6b7280);
}

.endpoint-group {
  border-bottom: 1px solid var(--border-color, #f3f4f6);
}

.group-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  user-select: none;
  background: var(--surface, #f9fafb);
}

.group-label:hover { background: var(--border-color, #f3f4f6); }

.group-name { flex: 1; }

.group-count {
  background: var(--border-color, #e5e7eb);
  border-radius: 999px;
  font-size: 0.68rem;
  padding: 0.05rem 0.4rem;
  color: var(--text-muted, #6b7280);
}

.group-chevron { font-size: 0.65rem; opacity: 0.55; }

.group-endpoints { display: flex; flex-direction: column; }

.endpoint-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.38rem 0.75rem;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  font-size: 0.76rem;
  color: var(--text, #374151);
  border-left: 2px solid transparent;
  transition: background 0.12s;
  width: 100%;
}

.endpoint-item:hover { background: var(--surface, #f9fafb); }

.endpoint-item.active {
  background: rgba(59,130,246,0.08);
  border-left-color: #3b82f6;
  color: #1d4ed8;
}

.ep-path {
  font-family: monospace;
  font-size: 0.73rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-results {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.875rem;
}

/* ── Main panel ──────────────────────────────────────────────────────────── */
.endpoint-detail {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  overflow-y: auto;
  padding: 1.5rem;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content { text-align: center; }

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.4;
}

.empty-content h3 { margin: 0 0 0.5rem; }

.empty-links {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 1rem;
}

/* Endpoint header */
.ep-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.ep-full-path {
  font-family: monospace;
  font-size: 0.95rem;
  flex: 1;
  color: var(--text, #111);
  word-break: break-all;
}

.ep-header-actions {
  display: flex;
  gap: 0.4rem;
}

.ep-description {
  font-size: 0.88rem;
  margin: 0 0 1rem;
  line-height: 1.55;
  color: var(--text, #374151);
}

/* Auth note */
.auth-note {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  background: rgba(59,130,246,0.05);
  border: 1px solid rgba(59,130,246,0.15);
  border-radius: 0.35rem;
  padding: 0.55rem 0.75rem;
  margin-bottom: 1.25rem;
  font-size: 0.8rem;
  color: var(--text, #374151);
}

.auth-note-icon { flex-shrink: 0; margin-top: 0.05rem; }

.auth-note code {
  background: rgba(0,0,0,0.07);
  border-radius: 3px;
  padding: 0.1rem 0.3rem;
  font-size: 0.82em;
}

/* Method badges */
.method-badge,
.method-badge-lg {
  border-radius: 4px;
  padding: 0.15rem 0.4rem;
  font-size: 0.66rem;
  font-weight: 700;
  font-family: monospace;
  text-transform: uppercase;
  flex-shrink: 0;
  white-space: nowrap;
}

.method-badge-lg {
  font-size: 0.82rem;
  padding: 0.25rem 0.65rem;
  border-radius: 5px;
}

.badge-get    { background: #dbeafe; color: #1d4ed8; }
.badge-post   { background: #d1fae5; color: #065f46; }
.badge-put    { background: #fef3c7; color: #92400e; }
.badge-patch  { background: #ede9fe; color: #5b21b6; }
.badge-delete { background: #fee2e2; color: #991b1b; }

/* Sections */
.ep-section { margin-bottom: 1.5rem; }

.section-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
  margin: 0 0 0.6rem;
}

.section-subtitle {
  font-weight: 400;
  font-size: 0.78rem;
  margin-left: 0.4rem;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.6rem;
}

.section-title-row .section-title { margin: 0; }

/* Param table */
.param-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.param-table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.param-table td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  vertical-align: middle;
}

.param-input {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.3rem;
  padding: 0.3rem 0.5rem;
  font-size: 0.8rem;
  width: 100%;
  background: var(--background, #f9fafb);
  color: var(--text, #111);
  font-family: monospace;
  box-sizing: border-box;
}

.param-input:focus {
  border-color: #3b82f6;
  outline: none;
}

.badge-danger-soft {
  background: #fee2e2;
  color: #991b1b;
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-size: 0.68rem;
  font-weight: 700;
}

/* Query params */
.query-params-area {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.query-param-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.param-key { width: 35%; }
.param-val { width: 55%; }

.add-param-btn { align-self: flex-start; }

/* Body editor */
.body-editor {
  width: 100%;
  font-family: monospace;
  font-size: 0.82rem;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.35rem;
  padding: 0.6rem;
  background: var(--surface, #f9fafb);
  color: var(--text, #111);
  resize: vertical;
  box-sizing: border-box;
  line-height: 1.5;
}

.body-editor:focus {
  border-color: #3b82f6;
  outline: none;
}

.field-error {
  color: #ef4444;
  font-size: 0.8rem;
  margin: 0.25rem 0 0;
}

/* Try section */
.try-section {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.send-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.response-status {
  font-family: monospace;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
}

.status-ok    { background: #d1fae5; color: #065f46; }
.status-warn  { background: #fef3c7; color: #92400e; }
.status-err   { background: #fee2e2; color: #991b1b; }
.status-muted { background: var(--border-color, #e5e7eb); color: var(--text-muted, #6b7280); }

.resp-time {
  font-family: monospace;
  font-size: 0.8rem;
}

/* Response */
.response-section {}

.response-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.response-header .section-title { margin: 0; }

.response-header-actions {
  display: flex;
  gap: 0.35rem;
}

.response-body {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 0.4rem;
  padding: 1rem;
  overflow-x: auto;
  font-size: 0.79rem;
  line-height: 1.55;
  max-height: 420px;
  overflow-y: auto;
  margin: 0;
}

.response-body code {
  font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
}

:deep(.json-key)  { color: #93c5fd; }
:deep(.json-str)  { color: #86efac; }
:deep(.json-num)  { color: #fcd34d; }
:deep(.json-bool) { color: #f9a8d4; }
:deep(.json-null) { color: #94a3b8; }

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.9rem;
  border-radius: 0.35rem;
  border: none;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-sm           { padding: 0.3rem 0.65rem; font-size: 0.8rem; }
.btn-primary      { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-outline      { background: transparent; border: 1px solid var(--border-color, #e5e7eb); color: var(--text, #374151); }
.btn-outline:hover { background: var(--surface, #f9fafb); }
.btn-danger-soft  { background: #fee2e2; color: #991b1b; border: none; }
.btn-danger-soft:hover { background: #fecaca; }

.text-muted { opacity: 0.65; }

@media (max-width: 900px) {
  .explorer-layout {
    grid-template-columns: 1fr;
    height: auto;
  }

  .endpoint-sidebar {
    max-height: 320px;
  }

  .auth-banner { font-size: 0.78rem; }

  .token-badge { margin-left: 0; }
}
</style>
