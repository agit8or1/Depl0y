<template>
  <div class="api-explorer">
    <div class="page-header">
      <div>
        <h1>API Explorer</h1>
        <p class="text-muted">Browse, test and copy Depl0y API endpoints</p>
      </div>
      <div class="header-actions">
        <input
          v-model="search"
          class="search-input"
          placeholder="Search endpoints..."
          type="text"
        />
        <a
          href="/docs"
          target="_blank"
          rel="noopener"
          class="btn btn-outline btn-sm"
        >Swagger UI</a>
        <a
          href="/redoc"
          target="_blank"
          rel="noopener"
          class="btn btn-outline btn-sm"
        >ReDoc</a>
      </div>
    </div>

    <div class="explorer-layout">
      <!-- Sidebar: endpoint list -->
      <aside class="endpoint-sidebar">
        <div
          v-for="group in filteredGroups"
          :key="group.tag"
          class="endpoint-group"
        >
          <div class="group-label" @click="toggleGroup(group.tag)">
            <span>{{ group.tag }}</span>
            <span class="group-count">{{ group.endpoints.length }}</span>
            <span class="group-chevron">{{ collapsedGroups.has(group.tag) ? '▶' : '▼' }}</span>
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
          No endpoints match "{{ search }}"
        </div>
      </aside>

      <!-- Main panel -->
      <main class="endpoint-detail" v-if="selectedEndpoint">
        <div class="ep-header">
          <span :class="['method-badge-lg', 'badge-' + selectedEndpoint.method.toLowerCase()]">
            {{ selectedEndpoint.method }}
          </span>
          <code class="ep-full-path">{{ selectedEndpoint.path }}</code>
          <button class="btn btn-sm btn-outline" @click="copyCurl" title="Copy as cURL">
            {{ curlCopied ? 'Copied!' : 'Copy cURL' }}
          </button>
        </div>

        <p v-if="selectedEndpoint.description" class="ep-description">
          {{ selectedEndpoint.description }}
        </p>
        <p v-else-if="selectedEndpoint.summary" class="ep-description text-muted">
          {{ selectedEndpoint.summary }}
        </p>

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
                    :placeholder="param.name"
                    type="text"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Query parameters (for GET) -->
        <div v-if="selectedEndpoint.method === 'GET'" class="ep-section">
          <h4 class="section-title">Query Parameters <span class="text-muted" style="font-weight:400;font-size:0.8rem;">(optional)</span></h4>
          <div class="query-params-area">
            <div v-for="(val, key) in tryItQuery" :key="key" class="query-param-row">
              <input v-model="queryKeys[key]" class="param-input param-key" placeholder="key" @input="renameQueryKey(key, queryKeys[key])" />
              <input v-model="tryItQuery[key]" class="param-input param-val" placeholder="value" />
              <button class="btn btn-sm btn-danger-soft" @click="removeQueryParam(key)">✕</button>
            </div>
            <button class="btn btn-sm btn-outline" @click="addQueryParam">+ Add param</button>
          </div>
        </div>

        <!-- Request body (for POST/PUT/PATCH) -->
        <div v-if="['POST','PUT','PATCH'].includes(selectedEndpoint.method)" class="ep-section">
          <h4 class="section-title">Request Body <span class="text-muted" style="font-weight:400;font-size:0.8rem;">(JSON)</span></h4>
          <textarea
            v-model="requestBody"
            class="body-editor"
            placeholder="{}"
            rows="6"
            spellcheck="false"
          ></textarea>
          <p v-if="bodyError" class="field-error">{{ bodyError }}</p>
        </div>

        <!-- Try It button -->
        <div class="ep-section try-section">
          <button
            class="btn btn-primary"
            :disabled="executing"
            @click="execute"
          >
            {{ executing ? 'Sending...' : 'Send Request' }}
          </button>
          <span v-if="lastResponse" class="response-status" :class="statusClass">
            {{ lastResponse.status }} {{ lastResponse.statusText }}
          </span>
        </div>

        <!-- Response -->
        <div v-if="lastResponse" class="ep-section">
          <h4 class="section-title">Response</h4>
          <div class="response-meta">
            <span class="resp-time text-muted">{{ lastResponse.time }}ms</span>
          </div>
          <pre class="response-body"><code v-html="highlightedResponse"></code></pre>
        </div>
      </main>

      <main class="endpoint-detail empty-state" v-else>
        <div class="empty-content">
          <div class="empty-icon">⚡</div>
          <h3>Select an endpoint</h3>
          <p class="text-muted">Choose an API endpoint from the left panel to view details and test it.</p>
          <p class="text-muted" style="margin-top:0.5rem;">
            Or browse the full Swagger UI at
            <a href="/docs" target="_blank">/docs</a>.
          </p>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue'
import api from '@/services/api'

// Full hardcoded endpoint list grouped by tag
const ALL_ENDPOINTS = [
  // Authentication
  { method: 'POST', path: '/api/v1/auth/login', tag: 'Authentication', summary: 'Login and obtain JWT tokens', description: 'Authenticate with username, password, and optional TOTP code. Returns access_token and refresh_token.' },
  { method: 'POST', path: '/api/v1/auth/refresh', tag: 'Authentication', summary: 'Refresh access token', description: 'Exchange a valid refresh_token for new access and refresh tokens.' },
  { method: 'GET',  path: '/api/v1/auth/me', tag: 'Authentication', summary: 'Get current user info' },
  { method: 'PATCH', path: '/api/v1/auth/me/password', tag: 'Authentication', summary: 'Change current user password' },
  { method: 'POST', path: '/api/v1/auth/totp/setup', tag: 'Authentication', summary: 'Setup TOTP 2FA' },
  { method: 'POST', path: '/api/v1/auth/totp/verify', tag: 'Authentication', summary: 'Verify and enable TOTP 2FA' },
  { method: 'POST', path: '/api/v1/auth/totp/disable', tag: 'Authentication', summary: 'Disable TOTP 2FA' },
  { method: 'GET',  path: '/api/v1/auth/api-keys', tag: 'Authentication', summary: 'List API keys' },
  { method: 'POST', path: '/api/v1/auth/api-keys', tag: 'Authentication', summary: 'Create API key' },
  { method: 'DELETE', path: '/api/v1/auth/api-keys/{key_id}', tag: 'Authentication', summary: 'Revoke API key' },

  // Users
  { method: 'GET',    path: '/api/v1/users/', tag: 'Users', summary: 'List users (admin only)' },
  { method: 'POST',   path: '/api/v1/users/', tag: 'Users', summary: 'Create user (admin only)' },
  { method: 'GET',    path: '/api/v1/users/{id}', tag: 'Users', summary: 'Get user by ID' },
  { method: 'PUT',    path: '/api/v1/users/{id}', tag: 'Users', summary: 'Update user' },
  { method: 'PATCH',  path: '/api/v1/users/{id}', tag: 'Users', summary: 'Partially update user' },
  { method: 'DELETE', path: '/api/v1/users/{id}', tag: 'Users', summary: 'Delete user' },
  { method: 'PATCH',  path: '/api/v1/users/{id}/status', tag: 'Users', summary: 'Set user active/inactive' },
  { method: 'POST',   path: '/api/v1/users/{id}/reset-password', tag: 'Users', summary: 'Reset user password (admin)' },
  { method: 'POST',   path: '/api/v1/users/{id}/disable-totp', tag: 'Users', summary: 'Disable user TOTP (admin)' },
  { method: 'POST',   path: '/api/v1/users/invalidate-sessions/{id}', tag: 'Users', summary: 'Invalidate user sessions' },
  { method: 'POST',   path: '/api/v1/users/invalidate-sessions-all', tag: 'Users', summary: 'Invalidate all sessions (admin)' },

  // Proxmox Hosts
  { method: 'GET',    path: '/api/v1/proxmox/', tag: 'Proxmox Hosts', summary: 'List Proxmox hosts' },
  { method: 'POST',   path: '/api/v1/proxmox/', tag: 'Proxmox Hosts', summary: 'Add Proxmox host' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}', tag: 'Proxmox Hosts', summary: 'Get Proxmox host' },
  { method: 'PUT',    path: '/api/v1/proxmox/{id}', tag: 'Proxmox Hosts', summary: 'Update Proxmox host' },
  { method: 'DELETE', path: '/api/v1/proxmox/{id}', tag: 'Proxmox Hosts', summary: 'Delete Proxmox host' },
  { method: 'POST',   path: '/api/v1/proxmox/{id}/test', tag: 'Proxmox Hosts', summary: 'Test host connection' },
  { method: 'POST',   path: '/api/v1/proxmox/{id}/poll', tag: 'Proxmox Hosts', summary: 'Poll host for current state' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}/nodes', tag: 'Proxmox Hosts', summary: 'List nodes for host' },
  { method: 'GET',    path: '/api/v1/proxmox/{id}/stats', tag: 'Proxmox Hosts', summary: 'Get host statistics' },
  { method: 'GET',    path: '/api/v1/proxmox/nodes/{nodeId}', tag: 'Proxmox Hosts', summary: 'Get node by ID' },
  { method: 'GET',    path: '/api/v1/proxmox/nodes/{nodeId}/storage', tag: 'Proxmox Hosts', summary: 'Get node storage' },
  { method: 'GET',    path: '/api/v1/proxmox/nodes/{nodeId}/network', tag: 'Proxmox Hosts', summary: 'Get node network' },

  // Virtual Machines
  { method: 'GET',    path: '/api/v1/vms/', tag: 'Virtual Machines', summary: 'List managed VMs' },
  { method: 'POST',   path: '/api/v1/vms/', tag: 'Virtual Machines', summary: 'Create/deploy VM' },
  { method: 'GET',    path: '/api/v1/vms/managed', tag: 'Virtual Machines', summary: 'List managed VMs (alternate)' },
  { method: 'GET',    path: '/api/v1/vms/{id}', tag: 'Virtual Machines', summary: 'Get VM by ID' },
  { method: 'PUT',    path: '/api/v1/vms/{id}', tag: 'Virtual Machines', summary: 'Update VM record' },
  { method: 'DELETE', path: '/api/v1/vms/{id}', tag: 'Virtual Machines', summary: 'Delete VM record' },
  { method: 'POST',   path: '/api/v1/vms/{id}/start', tag: 'Virtual Machines', summary: 'Start VM' },
  { method: 'POST',   path: '/api/v1/vms/{id}/stop', tag: 'Virtual Machines', summary: 'Stop VM' },
  { method: 'GET',    path: '/api/v1/vms/{id}/status', tag: 'Virtual Machines', summary: 'Get VM status' },
  { method: 'GET',    path: '/api/v1/vms/{id}/progress', tag: 'Virtual Machines', summary: 'Get VM deployment progress' },
  { method: 'POST',   path: '/api/v1/vms/adopt', tag: 'Virtual Machines', summary: 'Adopt existing PVE VM into Depl0y' },

  // PVE VM Control
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/config', tag: 'PVE VM Control', summary: 'Get VM configuration' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/config', tag: 'PVE VM Control', summary: 'Update VM configuration' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/status', tag: 'PVE VM Control', summary: 'Get VM runtime status' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/start', tag: 'PVE VM Control', summary: 'Start VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/stop', tag: 'PVE VM Control', summary: 'Stop VM (immediate)' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/shutdown', tag: 'PVE VM Control', summary: 'Graceful shutdown' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/reboot', tag: 'PVE VM Control', summary: 'Reboot VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/reset', tag: 'PVE VM Control', summary: 'Hard reset VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/suspend', tag: 'PVE VM Control', summary: 'Suspend VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/resume', tag: 'PVE VM Control', summary: 'Resume VM' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots', tag: 'PVE VM Control', summary: 'List snapshots' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots', tag: 'PVE VM Control', summary: 'Create snapshot' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots/{snap}', tag: 'PVE VM Control', summary: 'Delete snapshot' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/snapshots/{snap}/rollback', tag: 'PVE VM Control', summary: 'Rollback to snapshot' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/clone', tag: 'PVE VM Control', summary: 'Clone VM' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/migrate', tag: 'PVE VM Control', summary: 'Migrate VM to another node' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/template', tag: 'PVE VM Control', summary: 'Convert VM to template' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}', tag: 'PVE VM Control', summary: 'Delete VM permanently' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk', tag: 'PVE VM Control', summary: 'Add disk to VM' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk/{disk}/resize', tag: 'PVE VM Control', summary: 'Resize VM disk' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/disk/{disk}', tag: 'PVE VM Control', summary: 'Delete/detach VM disk' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/network', tag: 'PVE VM Control', summary: 'Add NIC to VM' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/network/{nic}', tag: 'PVE VM Control', summary: 'Remove NIC from VM' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/rrddata', tag: 'PVE VM Control', summary: 'Get VM performance data' },
  { method: 'GET',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules', tag: 'PVE VM Control', summary: 'Get VM firewall rules' },
  { method: 'POST',   path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules', tag: 'PVE VM Control', summary: 'Add VM firewall rule' },
  { method: 'PUT',    path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules/{pos}', tag: 'PVE VM Control', summary: 'Update VM firewall rule' },
  { method: 'DELETE', path: '/api/v1/pve-vm/{host_id}/{node}/{vmid}/firewall/rules/{pos}', tag: 'PVE VM Control', summary: 'Delete VM firewall rule' },

  // PVE Node/Cluster
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/status', tag: 'PVE Node/Cluster', summary: 'Get cluster status' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/nextid', tag: 'PVE Node/Cluster', summary: 'Get next available VM ID' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/status', tag: 'PVE Node/Cluster', summary: 'Get node status' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/rrddata', tag: 'PVE Node/Cluster', summary: 'Get node performance data' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/vms', tag: 'PVE Node/Cluster', summary: 'List VMs on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/tasks', tag: 'PVE Node/Cluster', summary: 'List node tasks' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/storage', tag: 'PVE Node/Cluster', summary: 'List node storage' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network', tag: 'PVE Node/Cluster', summary: 'List node network interfaces' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc', tag: 'PVE Node/Cluster', summary: 'List LXC containers on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/disks/list', tag: 'PVE Node/Cluster', summary: 'List physical disks on node' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/disks/{disk}/smart', tag: 'PVE Node/Cluster', summary: 'Get SMART data for disk' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/services', tag: 'PVE Node/Cluster', summary: 'List node services' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/services/{service}/{cmd}', tag: 'PVE Node/Cluster', summary: 'Control node service' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/access/users', tag: 'PVE Node/Cluster', summary: 'List PVE users' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/pools', tag: 'PVE Node/Cluster', summary: 'List resource pools' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/pools', tag: 'PVE Node/Cluster', summary: 'Create resource pool' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/backup', tag: 'PVE Node/Cluster', summary: 'List backup schedules' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/backup', tag: 'PVE Node/Cluster', summary: 'Create backup schedule' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/vzdump', tag: 'PVE Node/Cluster', summary: 'Run backup (vzdump)' },

  // LXC
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/config', tag: 'LXC', summary: 'Get container config' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/config', tag: 'LXC', summary: 'Update container config' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/status', tag: 'LXC', summary: 'Get container status' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/start', tag: 'LXC', summary: 'Start container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/stop', tag: 'LXC', summary: 'Stop container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/shutdown', tag: 'LXC', summary: 'Shutdown container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/reboot', tag: 'LXC', summary: 'Reboot container' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots', tag: 'LXC', summary: 'List container snapshots' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots', tag: 'LXC', summary: 'Create container snapshot' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/snapshots/{snap}/rollback', tag: 'LXC', summary: 'Rollback container snapshot' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}', tag: 'LXC', summary: 'Delete container' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/clone', tag: 'LXC', summary: 'Clone container' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/rrddata', tag: 'LXC', summary: 'Container performance data' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc/{vmid}/resize', tag: 'LXC', summary: 'Resize container disk' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/lxc', tag: 'LXC', summary: 'Create LXC container' },

  // PBS
  { method: 'GET',    path: '/api/v1/pbs/', tag: 'PBS', summary: 'List PBS servers' },
  { method: 'POST',   path: '/api/v1/pbs/', tag: 'PBS', summary: 'Add PBS server' },
  { method: 'GET',    path: '/api/v1/pbs/{id}', tag: 'PBS', summary: 'Get PBS server' },
  { method: 'PUT',    path: '/api/v1/pbs/{id}', tag: 'PBS', summary: 'Update PBS server' },
  { method: 'DELETE', path: '/api/v1/pbs/{id}', tag: 'PBS', summary: 'Delete PBS server' },

  // PBS Management
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/test', tag: 'PBS Management', summary: 'Test PBS connection' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/datastores', tag: 'PBS Management', summary: 'List PBS datastores' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/groups', tag: 'PBS Management', summary: 'List backup groups in datastore' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/snapshots', tag: 'PBS Management', summary: 'List snapshots in datastore' },
  { method: 'POST',   path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/verify', tag: 'PBS Management', summary: 'Verify backup snapshot' },
  { method: 'DELETE', path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/snapshots', tag: 'PBS Management', summary: 'Delete backup snapshot' },
  { method: 'POST',   path: '/api/v1/pbs-mgmt/{id}/datastores/{ds}/prune', tag: 'PBS Management', summary: 'Prune backup group' },
  { method: 'GET',    path: '/api/v1/pbs-mgmt/{id}/tasks', tag: 'PBS Management', summary: 'List PBS tasks' },

  // Cluster Operations
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/tasks', tag: 'Cluster Operations', summary: 'List cluster-wide tasks' },
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/replication', tag: 'Cluster Operations', summary: 'List replication jobs' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/replication', tag: 'Cluster Operations', summary: 'Create replication job' },
  { method: 'PUT',    path: '/api/v1/cluster/{host_id}/replication/{jobId}', tag: 'Cluster Operations', summary: 'Update replication job' },
  { method: 'DELETE', path: '/api/v1/cluster/{host_id}/replication/{jobId}', tag: 'Cluster Operations', summary: 'Delete replication job' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/replication/{jobId}/schedule_now', tag: 'Cluster Operations', summary: 'Force replication job now' },
  { method: 'POST',   path: '/api/v1/cluster/{host_id}/nodes/{node}/evacuate', tag: 'Cluster Operations', summary: 'Evacuate node (migrate all VMs off)' },
  { method: 'GET',    path: '/api/v1/cluster/{host_id}/log', tag: 'Cluster Operations', summary: 'Get cluster event log' },

  // PVE Firewall
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/ipsets', tag: 'PVE Firewall', summary: 'List IPSets' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/ipsets', tag: 'PVE Firewall', summary: 'Create IPSet' },
  { method: 'DELETE', path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}', tag: 'PVE Firewall', summary: 'Delete IPSet' },
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}', tag: 'PVE Firewall', summary: 'List IPSet entries' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}', tag: 'PVE Firewall', summary: 'Add IPSet entry' },
  { method: 'DELETE', path: '/api/v1/pve-firewall/{host_id}/ipsets/{name}/{cidr}', tag: 'PVE Firewall', summary: 'Remove IPSet entry' },
  { method: 'GET',    path: '/api/v1/pve-firewall/{host_id}/aliases', tag: 'PVE Firewall', summary: 'List firewall aliases' },
  { method: 'POST',   path: '/api/v1/pve-firewall/{host_id}/aliases', tag: 'PVE Firewall', summary: 'Create firewall alias' },
  { method: 'PUT',    path: '/api/v1/pve-firewall/{host_id}/aliases/{name}', tag: 'PVE Firewall', summary: 'Update firewall alias' },
  { method: 'DELETE', path: '/api/v1/pve-firewall/{host_id}/aliases/{name}', tag: 'PVE Firewall', summary: 'Delete firewall alias' },
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules', tag: 'PVE Firewall', summary: 'List cluster firewall rules' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules', tag: 'PVE Firewall', summary: 'Add cluster firewall rule' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/cluster/firewall/rules/{pos}', tag: 'PVE Firewall', summary: 'Delete cluster firewall rule' },
  { method: 'PUT',    path: '/api/v1/pve-firewall/{host_id}/cluster/firewall/rules/{pos}', tag: 'PVE Firewall', summary: 'Update cluster firewall rule' },

  // Network
  { method: 'GET',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network', tag: 'Network', summary: 'List node network interfaces' },
  { method: 'POST',   path: '/api/v1/pve-node/{host_id}/nodes/{node}/network', tag: 'Network', summary: 'Create network interface' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network/{iface}', tag: 'Network', summary: 'Update network interface' },
  { method: 'DELETE', path: '/api/v1/pve-node/{host_id}/nodes/{node}/network/{iface}', tag: 'Network', summary: 'Delete network interface' },
  { method: 'PUT',    path: '/api/v1/pve-node/{host_id}/nodes/{node}/network', tag: 'Network', summary: 'Apply pending network config' },

  // Notifications
  { method: 'GET',    path: '/api/v1/notifications/in-app', tag: 'Notifications', summary: 'List in-app notifications' },
  { method: 'POST',   path: '/api/v1/notifications/in-app/mark-read', tag: 'Notifications', summary: 'Mark notifications as read' },
  { method: 'DELETE', path: '/api/v1/notifications/in-app/{id}', tag: 'Notifications', summary: 'Delete notification' },
  { method: 'DELETE', path: '/api/v1/notifications/in-app', tag: 'Notifications', summary: 'Delete all notifications' },
  { method: 'GET',    path: '/api/v1/notifications/settings', tag: 'Notifications', summary: 'Get notification settings' },
  { method: 'PUT',    path: '/api/v1/notifications/settings', tag: 'Notifications', summary: 'Update notification settings' },
  { method: 'GET',    path: '/api/v1/notifications/webhooks', tag: 'Notifications', summary: 'List webhooks' },
  { method: 'POST',   path: '/api/v1/notifications/webhooks', tag: 'Notifications', summary: 'Create webhook' },
  { method: 'PUT',    path: '/api/v1/notifications/webhooks/{id}', tag: 'Notifications', summary: 'Update webhook' },
  { method: 'DELETE', path: '/api/v1/notifications/webhooks/{id}', tag: 'Notifications', summary: 'Delete webhook' },
  { method: 'POST',   path: '/api/v1/notifications/webhooks/{id}/test', tag: 'Notifications', summary: 'Test webhook' },
  { method: 'GET',    path: '/api/v1/notifications/webhooks/{id}/deliveries', tag: 'Notifications', summary: 'Get webhook delivery history' },

  // Security
  { method: 'GET',    path: '/api/v1/security/settings', tag: 'Security', summary: 'Get security settings' },
  { method: 'PUT',    path: '/api/v1/security/settings', tag: 'Security', summary: 'Update security settings' },
  { method: 'GET',    path: '/api/v1/security/lockouts', tag: 'Security', summary: 'List locked accounts' },
  { method: 'DELETE', path: '/api/v1/security/lockouts/{username}', tag: 'Security', summary: 'Unlock account' },
  { method: 'GET',    path: '/api/v1/security/failed-logins', tag: 'Security', summary: 'List failed login attempts' },
  { method: 'GET',    path: '/api/v1/security/ip-list', tag: 'Security', summary: 'List IP allow/block list' },
  { method: 'POST',   path: '/api/v1/security/ip-list', tag: 'Security', summary: 'Add IP list entry' },
  { method: 'DELETE', path: '/api/v1/security/ip-list/{id}', tag: 'Security', summary: 'Delete IP list entry' },
  { method: 'PATCH',  path: '/api/v1/security/ip-list/{id}/toggle', tag: 'Security', summary: 'Toggle IP list entry' },
  { method: 'GET',    path: '/api/v1/security/geoip', tag: 'Security', summary: 'List GeoIP rules' },
  { method: 'POST',   path: '/api/v1/security/geoip', tag: 'Security', summary: 'Add GeoIP rule' },
  { method: 'DELETE', path: '/api/v1/security/geoip/{id}', tag: 'Security', summary: 'Delete GeoIP rule' },
  { method: 'GET',    path: '/api/v1/security/events', tag: 'Security', summary: 'List security events' },
  { method: 'GET',    path: '/api/v1/security/login-history', tag: 'Security', summary: 'Get login history' },

  // System
  { method: 'GET',    path: '/api/v1/system/info', tag: 'System', summary: 'Get system information and version' },
  { method: 'GET',    path: '/api/v1/system/health', tag: 'System', summary: 'System health check' },
  { method: 'GET',    path: '/api/v1/system/diagnostics', tag: 'System', summary: 'Full diagnostic bundle (admin)' },
  { method: 'POST',   path: '/api/v1/system/db-check', tag: 'System', summary: 'SQLite integrity check (admin)' },
  { method: 'POST',   path: '/api/v1/system/test-email', tag: 'System', summary: 'Send test email (admin)' },
  { method: 'GET',    path: '/api/v1/system/metrics', tag: 'System', summary: 'Get system metrics (admin)', description: 'Returns request counts, user totals, API key totals, and uptime.' },

  // Audit
  { method: 'GET',    path: '/api/v1/audit/', tag: 'Audit Log', summary: 'List audit log entries (admin)' },

  // Dashboard
  { method: 'GET',    path: '/api/v1/dashboard/stats', tag: 'Dashboard', summary: 'Get dashboard statistics' },
  { method: 'GET',    path: '/api/v1/dashboard/resources', tag: 'Dashboard', summary: 'Get resource overview' },
  { method: 'GET',    path: '/api/v1/dashboard/activity', tag: 'Dashboard', summary: 'Get recent activity' },

  // Developer Tools
  { method: 'GET',    path: '/api/v1/openapi-summary', tag: 'Developer Tools', summary: 'List all API routes (simplified OpenAPI)', description: 'Returns all registered routes with method, path, tag, and summary.' },
]

// Add shortPath to each endpoint
ALL_ENDPOINTS.forEach(ep => {
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
    let queryCounter = 0

    // Group endpoints by tag
    const grouped = computed(() => {
      const map = {}
      ALL_ENDPOINTS.forEach(ep => {
        if (!map[ep.tag]) map[ep.tag] = []
        map[ep.tag].push(ep)
      })
      return Object.entries(map).map(([tag, endpoints]) => ({ tag, endpoints }))
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
            g.tag.toLowerCase().includes(q)
          )
        }))
        .filter(g => g.endpoints.length > 0)
    })

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
      // Pre-fill path params
      pathParams.value.forEach(p => {
        tryItParams.value[p.name] = ''
      })
    }

    const toggleGroup = (tag) => {
      if (collapsedGroups.value.has(tag)) {
        collapsedGroups.value.delete(tag)
      } else {
        collapsedGroups.value.add(tag)
      }
      // Force reactivity
      collapsedGroups.value = new Set(collapsedGroups.value)
    }

    const addQueryParam = () => {
      const k = `param_${queryCounter++}`
      tryItQuery.value[k] = ''
      queryKeys.value[k] = ''
    }

    const removeQueryParam = (key) => {
      delete tryItQuery.value[key]
      delete queryKeys.value[key]
      tryItQuery.value = { ...tryItQuery.value }
    }

    const renameQueryKey = (oldKey, newKey) => {
      if (newKey === oldKey) return
      const val = tryItQuery.value[oldKey]
      delete tryItQuery.value[oldKey]
      tryItQuery.value[newKey] = val
    }

    const buildUrl = () => {
      if (!selectedEndpoint.value) return ''
      let path = selectedEndpoint.value.path
      // Replace path params
      Object.entries(tryItParams.value).forEach(([k, v]) => {
        path = path.replace(`{${k}}`, v || `{${k}}`)
      })
      // Add query params
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

      // Build relative URL (strip /api/v1 prefix since axios baseURL is /api/v1)
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

      let body = null
      if (['POST', 'PUT', 'PATCH'].includes(ep.method)) {
        try {
          body = requestBody.value.trim() ? JSON.parse(requestBody.value) : undefined
        } catch (e) {
          bodyError.value = 'Invalid JSON: ' + e.message
          executing.value = false
          return
        }
      }

      const start = Date.now()
      try {
        const axiosInst = (await import('@/services/api')).default
        // axiosInst is the named export default, but it's a methods object — use raw axios
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
          validateStatus: () => true, // don't throw on non-2xx
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
      return ''
    })

    const highlightedResponse = computed(() => {
      if (!lastResponse.value) return ''
      try {
        const json = JSON.stringify(lastResponse.value.data, null, 2)
        return json
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, (match) => {
            let cls = 'json-num'
            if (/^"/.test(match)) {
              if (/:$/.test(match)) {
                cls = 'json-key'
              } else {
                cls = 'json-str'
              }
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
        const body = requestBody.value.trim() || '{}'
        curl += ` \\\n  -d '${body}'`
      }
      navigator.clipboard.writeText(curl).then(() => {
        curlCopied.value = true
        setTimeout(() => { curlCopied.value = false }, 2000)
      })
    }

    return {
      search,
      selectedEndpoint,
      collapsedGroups,
      filteredGroups,
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
      selectEndpoint,
      toggleGroup,
      addQueryParam,
      removeQueryParam,
      renameQueryKey,
      execute,
      copyCurl,
    }
  }
}
</script>

<style scoped>
.api-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1.25rem;
  gap: 1rem;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h1 {
  margin: 0 0 0.2rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.search-input {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.35rem;
  padding: 0.4rem 0.75rem;
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

.explorer-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  flex: 1;
  min-height: 0;
  height: calc(100vh - 180px);
}

/* Sidebar */
.endpoint-sidebar {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 0.5rem;
  overflow-y: auto;
}

.endpoint-group {
  border-bottom: 1px solid var(--border-color, #f3f4f6);
}

.group-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #6b7280);
  cursor: pointer;
  user-select: none;
  background: var(--surface, #f9fafb);
}

.group-label:hover {
  background: var(--border-color, #f3f4f6);
}

.group-count {
  margin-left: auto;
  background: var(--border-color, #e5e7eb);
  border-radius: 999px;
  font-size: 0.68rem;
  padding: 0.05rem 0.4rem;
  color: var(--text-muted, #6b7280);
}

.group-chevron {
  font-size: 0.6rem;
  opacity: 0.6;
}

.group-endpoints {
  display: flex;
  flex-direction: column;
}

.endpoint-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--text, #374151);
  border-left: 2px solid transparent;
  transition: background 0.15s;
  width: 100%;
}

.endpoint-item:hover {
  background: var(--surface, #f9fafb);
}

.endpoint-item.active {
  background: rgba(59,130,246,0.08);
  border-left-color: #3b82f6;
  color: #1d4ed8;
}

.ep-path {
  font-family: monospace;
  font-size: 0.74rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-results {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.875rem;
}

/* Main panel */
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

.empty-content {
  text-align: center;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-content h3 {
  margin: 0 0 0.5rem;
}

.ep-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.ep-full-path {
  font-family: monospace;
  font-size: 1rem;
  flex: 1;
  color: var(--text, #111);
  word-break: break-all;
}

.ep-description {
  font-size: 0.9rem;
  margin: 0 0 1.25rem;
  line-height: 1.5;
}

/* Method badges */
.method-badge,
.method-badge-lg {
  border-radius: 4px;
  padding: 0.15rem 0.4rem;
  font-size: 0.68rem;
  font-weight: 700;
  font-family: monospace;
  text-transform: uppercase;
  flex-shrink: 0;
  white-space: nowrap;
}

.method-badge-lg {
  font-size: 0.85rem;
  padding: 0.25rem 0.6rem;
  border-radius: 5px;
}

.badge-get     { background: #dbeafe; color: #1d4ed8; }
.badge-post    { background: #d1fae5; color: #065f46; }
.badge-put     { background: #fef3c7; color: #92400e; }
.badge-patch   { background: #ede9fe; color: #5b21b6; }
.badge-delete  { background: #fee2e2; color: #991b1b; }

/* Sections */
.ep-section {
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #6b7280);
  margin: 0 0 0.6rem;
}

/* Param table */
.param-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.param-table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  font-size: 0.72rem;
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
  gap: 1rem;
}

.response-status {
  font-family: monospace;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
}

.status-ok   { background: #d1fae5; color: #065f46; }
.status-warn { background: #fef3c7; color: #92400e; }
.status-err  { background: #fee2e2; color: #991b1b; }

.response-meta {
  margin-bottom: 0.4rem;
  font-size: 0.8rem;
}

.resp-time {
  font-family: monospace;
}

/* Response body */
.response-body {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 0.4rem;
  padding: 1rem;
  overflow-x: auto;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}

.response-body code {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
}

/* JSON highlighting */
:deep(.json-key)  { color: #93c5fd; }
:deep(.json-str)  { color: #86efac; }
:deep(.json-num)  { color: #fcd34d; }
:deep(.json-bool) { color: #f9a8d4; }
:deep(.json-null) { color: #94a3b8; }

/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.45rem 0.9rem; border-radius: 0.35rem; border: none; font-size: 0.875rem; font-weight: 500; cursor: pointer; text-decoration: none; transition: all 0.15s; }
.btn-sm { padding: 0.3rem 0.65rem; font-size: 0.8rem; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid var(--border-color, #e5e7eb); color: var(--text, #374151); }
.btn-outline:hover { background: var(--surface, #f9fafb); }
.btn-danger-soft { background: #fee2e2; color: #991b1b; border: none; }
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
}
</style>
