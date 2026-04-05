<template>
  <div class="doc-layout">
    <!-- Sidebar TOC -->
    <aside class="doc-sidebar" :class="{ 'sidebar-open': sidebarOpen }">
      <div class="sidebar-header">
        <span class="sidebar-title">Documentation</span>
        <button class="sidebar-close" @click="sidebarOpen = false">&#215;</button>
      </div>

      <!-- Search -->
      <div class="sidebar-search">
        <span class="search-icon">&#128269;</span>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Search docs..."
          @input="onSearch"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''; searchResults = []">&#215;</button>
      </div>

      <!-- Search results -->
      <div v-if="searchQuery && searchResults.length > 0" class="search-results">
        <div
          v-for="hit in searchResults"
          :key="hit.sectionId + '-' + hit.index"
          class="search-hit"
          @click="navigateToResult(hit)"
        >
          <span class="hit-section">{{ hit.sectionTitle }}</span>
          <span class="hit-snippet" v-html="hit.snippet"></span>
        </div>
      </div>
      <div v-else-if="searchQuery && searchResults.length === 0" class="search-no-results">
        No results for "{{ searchQuery }}"
      </div>

      <!-- TOC -->
      <nav v-if="!searchQuery" class="toc">
        <a
          v-for="section in sections"
          :key="section.id"
          :href="'#' + section.id"
          class="toc-item"
          :class="{ active: activeSection === section.id }"
          @click.prevent="scrollToSection(section.id)"
        >
          <span class="toc-icon">{{ section.icon }}</span>
          <span class="toc-label">{{ section.title }}</span>
        </a>
      </nav>

      <div class="sidebar-footer">
        <a href="/api/v1/docs" target="_blank" class="sidebar-link">Swagger UI</a>
        <router-link to="/support" class="sidebar-link">Support</router-link>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="doc-main" ref="mainRef">
      <!-- Top bar -->
      <div class="doc-topbar">
        <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">&#9776; Sections</button>
        <nav class="breadcrumb-nav">
          <router-link to="/" class="bc-link">Home</router-link>
          <span class="bc-sep">/</span>
          <span class="bc-current">Documentation</span>
          <template v-if="activeSection">
            <span class="bc-sep">/</span>
            <span class="bc-current">{{ activeSectionTitle }}</span>
          </template>
        </nav>
      </div>

      <!-- Page header -->
      <div class="doc-page-header">
        <h1>Documentation</h1>
        <p>Complete guide to installing, configuring, and using Depl0y — a Proxmox VE management platform.</p>
        <div class="doc-header-actions">
          <a href="/api/v1/docs" target="_blank" class="btn btn-outline btn-sm">Swagger API Docs</a>
          <router-link to="/support" class="btn btn-outline btn-sm">Support &amp; Changelog</router-link>
        </div>
      </div>

      <!-- Sections -->
      <section
        v-for="section in sections"
        :key="section.id"
        :id="section.id"
        class="doc-section"
        :ref="el => { if (el) sectionRefs[section.id] = el }"
      >
        <div class="section-title-row">
          <h2 class="section-title">
            <span class="section-icon">{{ section.icon }}</span>
            {{ section.title }}
          </h2>
          <a :href="'#' + section.id" class="anchor-link" title="Copy link to section">&#182;</a>
        </div>
        <div class="section-body" v-html="section.html"></div>
      </section>

      <!-- Legacy card grid for quick access -->
      <section class="doc-section" id="quick-links">
        <div class="section-title-row">
          <h2 class="section-title"><span class="section-icon">&#128279;</span> Quick Links</h2>
        </div>
        <div class="doc-grid">
          <div class="doc-card featured">
            <div class="doc-icon">&#9889;</div>
            <h3>Cloud Images Quick Start</h3>
            <p>Deploy VMs in 30 seconds using pre-built cloud images and cloud-init.</p>
            <div class="doc-actions">
              <button @click="showQuickStart = true" class="btn btn-primary btn-sm">Preview</button>
              <router-link to="/settings" class="btn btn-outline btn-sm">Settings</router-link>
            </div>
          </div>
          <div class="doc-card">
            <div class="doc-icon">&#128279;</div>
            <h3>API Documentation</h3>
            <p>Full OpenAPI docs for every endpoint — ideal for automation and integration.</p>
            <div class="doc-actions">
              <a href="/api/v1/docs" target="_blank" class="btn btn-primary btn-sm">Swagger UI</a>
              <a href="/api/v1/redoc" target="_blank" class="btn btn-outline btn-sm">ReDoc</a>
            </div>
          </div>
          <div class="doc-card">
            <div class="doc-icon">&#128229;</div>
            <h3>Download PDF</h3>
            <p>Get all documentation in a single PDF for offline reference.</p>
            <div class="doc-actions">
              <button class="btn btn-primary btn-sm" :disabled="downloadingPDF" @click="downloadPDF">
                {{ downloadingPDF ? 'Generating...' : 'Download PDF' }}
              </button>
            </div>
          </div>
          <div class="doc-card">
            <div class="doc-icon">&#128030;</div>
            <h3>Report a Bug</h3>
            <p>Found an issue? File a detailed bug report with logs and steps to reproduce.</p>
            <div class="doc-actions">
              <router-link to="/bug-report" class="btn btn-outline btn-sm">Bug Report Form</router-link>
              <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" class="btn btn-outline btn-sm">GitHub Issues</a>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- Cloud Quick Start Modal -->
    <div v-if="showQuickStart" class="modal" @click.self="showQuickStart = false">
      <div class="modal-content doc-modal">
        <div class="modal-header">
          <h3>&#9889; Cloud Images — Quick Start</h3>
          <button @click="showQuickStart = false" class="btn-close">&#215;</button>
        </div>
        <div class="modal-body">
          <h4>What Are Cloud Images?</h4>
          <p>Cloud images let you deploy VMs in <strong>30 seconds</strong> instead of 20 minutes. No manual OS installation needed!</p>
          <div class="step">
            <strong>Step 1: Check Status</strong>
            <p>Go to <router-link to="/settings" @click="showQuickStart = false">Settings</router-link> and look for the "Cloud Image Setup" section. A green box means already configured; yellow means setup is needed.</p>
          </div>
          <div class="step">
            <strong>Step 2: Run Setup Script</strong>
            <p>SSH to your Depl0y server and run:</p>
            <div class="code-block-wrap">
              <pre class="code-block">sudo /tmp/enable_cloud_images.sh</pre>
              <button class="copy-btn" @click="copyCode('sudo /tmp/enable_cloud_images.sh')">Copy</button>
            </div>
          </div>
          <div class="step">
            <strong>Step 3: Deploy</strong>
            <p>Go to <router-link to="/deploy" @click="showQuickStart = false">Deploy VM</router-link>, select Cloud Image, choose Ubuntu/Debian/etc., configure resources, and click Create.</p>
          </div>
          <div class="info-box">
            <strong>Deployment Times:</strong>
            <ul>
              <li><strong>First deploy:</strong> 5-10 minutes (creates template)</li>
              <li><strong>Subsequent deploys:</strong> ~30 seconds</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

// ── Section content definitions ─────────────────────────────────────────────
function codeBlock(code, label = '') {
  const id = 'cb-' + Math.random().toString(36).slice(2, 8)
  return `<div class="code-block-wrap"><pre class="code-block" id="${id}">${code}</pre><button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('${id}').innerText).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)})">Copy</button></div>`
}

function infoBox(text) {
  return `<div class="info-box">${text}</div>`
}

function warnBox(text) {
  return `<div class="warn-box">${text}</div>`
}

function step(num, title, body) {
  return `<div class="doc-step"><span class="step-num">${num}</span><div class="step-body"><strong>${title}</strong>${body}</div></div>`
}

const SECTIONS = [
  {
    id: 'getting-started',
    icon: '&#128640;',
    title: 'Getting Started',
    html: `
      <p>Depl0y is a self-hosted Proxmox VE management platform. It provides a clean web interface for managing virtual machines, LXC containers, storage, backups, and clusters across multiple Proxmox hosts — all from a single browser tab.</p>

      <h3>System Requirements</h3>
      <ul>
        <li><strong>OS:</strong> Ubuntu 22.04/24.04 or Debian 12 (server, not desktop)</li>
        <li><strong>RAM:</strong> 1 GB minimum (2 GB recommended)</li>
        <li><strong>Disk:</strong> 4 GB free space (more if storing ISOs)</li>
        <li><strong>Network:</strong> Must be able to reach Proxmox API on port 8006</li>
        <li><strong>Browser:</strong> Any modern browser (Chrome, Firefox, Edge, Safari)</li>
      </ul>

      <h3>One-Line Installation</h3>
      <p>Run this command on a fresh Ubuntu or Debian server to install Depl0y:</p>
      ${codeBlock('curl -sSL https://raw.githubusercontent.com/agit8or1/Depl0y/main/install.sh | sudo bash')}
      <p>The installer will:</p>
      <ol>
        <li>Install Python 3, Node.js, and system dependencies</li>
        <li>Create the <code>/var/lib/depl0y</code> data directory</li>
        <li>Set up a systemd service (<code>depl0y</code>) that starts on boot</li>
        <li>Build the Vue frontend and serve it via the FastAPI backend on port 8000</li>
        <li>Create an initial admin user (credentials shown at the end)</li>
      </ol>

      <h3>First Login</h3>
      ${step(1, 'Open your browser', '<p>Navigate to <code>http://&lt;server-ip&gt;:8000</code></p>')}
      ${step(2, 'Log in', '<p>Use the admin credentials shown at the end of the install script output.</p>')}
      ${step(3, 'Add a Proxmox Host', '<p>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Host</strong>. You will need a Proxmox API token (see the Proxmox Hosts Setup section).</p>')}
      ${step(4, 'Poll the host', '<p>Click <strong>Poll</strong> on the new host card to sync all nodes, VMs, and containers.</p>')}

      ${infoBox('<strong>Tip:</strong> After login, visit <strong>Settings</strong> to configure SMTP email notifications, set up cloud images, and adjust the auto-refresh interval.')}
    `
  },
  {
    id: 'proxmox-hosts',
    icon: '&#127970;',
    title: 'Proxmox Hosts Setup',
    html: `
      <p>Before managing VMs, you must register at least one Proxmox host. Depl0y communicates with Proxmox exclusively via its REST API using an API token — no root SSH is required.</p>

      <h3>Creating a Proxmox API Token</h3>
      ${step(1, 'Log into Proxmox Web UI', '<p>Navigate to <code>https://&lt;proxmox-ip&gt;:8006</code> and log in as root.</p>')}
      ${step(2, 'Create an API token', `<p>Go to <strong>Datacenter → Permissions → API Tokens → Add</strong>. Set:</p><ul><li><strong>User:</strong> root@pam (or a dedicated user)</li><li><strong>Token ID:</strong> e.g. <code>depl0y</code></li><li><strong>Privilege Separation:</strong> Leave unchecked for full root access</li></ul>`)}
      ${step(3, 'Copy the token secret', '<p>The secret is shown only once. Copy both the token ID and secret before closing the dialog.</p>')}

      <h3>Token Format</h3>
      <p>The token string you enter in Depl0y has this format:</p>
      ${codeBlock('PVEAPIToken=root@pam!depl0y=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')}

      <h3>Adding the Host in Depl0y</h3>
      <ol>
        <li>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Host</strong>.</li>
        <li>Enter the <strong>Host Address</strong> (e.g. <code>pve.example.com:8006</code> or just an IP).</li>
        <li>Paste the full <strong>API Token</strong> string.</li>
        <li>Give it a friendly <strong>Display Name</strong>.</li>
        <li>Click <strong>Save</strong>. Depl0y immediately tests the connection.</li>
      </ol>

      ${warnBox('<strong>Security:</strong> Depl0y stores API tokens encrypted at rest using Fernet symmetric encryption. Never share your <code>config.env</code> or database file.')}

      <h3>Polling and Sync</h3>
      <p>After adding a host, click <strong>Poll</strong> to fetch its current state (nodes, VMs, containers, storage). You can also configure auto-poll from Settings. The Dashboard shows the last-polled state; the PVE Live section uses live API calls.</p>

      <h3>Multiple Hosts</h3>
      <p>Depl0y supports any number of registered hosts. Each host is queried independently. The Dashboard aggregates stats across all active hosts. You can mark a host as inactive (toggle the Active switch) to exclude it from live queries without deleting its records.</p>
    `
  },
  {
    id: 'deploying-vms',
    icon: '&#9881;&#65039;',
    title: 'Deploying VMs',
    html: `
      <p>Depl0y offers two ways to create virtual machines: the native PVE VM wizard and the fast Cloud Image deploy path.</p>

      <h3>Method 1: Create VM (PVE Wizard)</h3>
      <p>Go to <strong>Create VM (PVE)</strong> for a guided 3-step form that creates a Proxmox-native VM:</p>

      <div class="tab-list">
        <div class="tab-item"><strong>Step 1 — Location</strong><span>Select target host and node. A VM ID is auto-generated (or set your own). Enter a VM name.</span></div>
        <div class="tab-item"><strong>Step 2 — Hardware</strong><span>CPU cores/sockets, RAM (MB), disk size and storage pool, network bridge and VLAN, ISO image or cloud image source, BIOS/UEFI, and machine type.</span></div>
        <div class="tab-item"><strong>Step 3 — Review</strong><span>Confirm all settings. Click Create VM to submit. A live task tracker shows Proxmox task progress.</span></div>
      </div>

      <h3>Method 2: Cloud Image Deploy (Fast)</h3>
      <p>Cloud images clone a pre-configured template, inject cloud-init, and boot in about 30 seconds. Ideal for bulk provisioning or quick dev environments.</p>

      ${step(1, 'Run one-time setup', `<p>SSH to your Depl0y host and run:</p>${codeBlock('sudo /tmp/enable_cloud_images.sh')}<p>This downloads Ubuntu/Debian cloud images to Proxmox and creates reusable templates.</p>`)}
      ${step(2, 'Go to Deploy', '<p>Navigate to <strong>Deploy VM</strong> and select <strong>Cloud Image (Fast)</strong>.</p>')}
      ${step(3, 'Configure', '<p>Choose image (Ubuntu 24.04, Debian 12, etc.), set CPU/RAM/disk, enter credentials (username + password or SSH key), and optionally add cloud-init user-data.</p>')}
      ${step(4, 'Deploy', '<p>Click Create. The VM is cloned and started within ~30 seconds on subsequent runs.</p>')}

      <h3>VM Controls</h3>
      <p>From the VM Detail page (Overview tab) you can:</p>
      <ul>
        <li><strong>Start / Stop / Reboot / Shutdown</strong> — power controls with confirmation</li>
        <li><strong>Force Stop</strong> — equivalent to pulling the power cord</li>
        <li><strong>View live stats</strong> — CPU%, RAM usage, disk I/O, network rx/tx</li>
        <li><strong>Open Console</strong> — noVNC in the browser</li>
      </ul>

      ${infoBox('<strong>Note:</strong> The QEMU guest agent must be installed and running inside the VM for accurate memory stats and guest IP detection. Install it with <code>apt install qemu-guest-agent && systemctl enable --now qemu-guest-agent</code>.')}
    `
  },
  {
    id: 'lxc-containers',
    icon: '&#128230;',
    title: 'LXC Containers',
    html: `
      <p>LXC containers are lightweight OS-level virtualization — faster to create than full VMs and share the host kernel. Depl0y provides full lifecycle management for LXC containers.</p>

      <h3>Creating an LXC Container</h3>
      <p>Go to <strong>Create LXC</strong> and fill in:</p>
      <div class="tab-list">
        <div class="tab-item"><strong>Host &amp; Node</strong><span>Which Proxmox host and node to create the container on.</span></div>
        <div class="tab-item"><strong>CT ID</strong><span>Container ID. Auto-generated by default; must be unique on the selected node.</span></div>
        <div class="tab-item"><strong>Hostname</strong><span>The container's hostname for DNS and display.</span></div>
        <div class="tab-item"><strong>Template</strong><span>LXC template image (Ubuntu 22.04, Debian 12, Alpine, etc.). Downloaded from the node's template storage. Click the storage browser to download new templates.</span></div>
        <div class="tab-item"><strong>Root Password</strong><span>Password set for the root account inside the container.</span></div>
        <div class="tab-item"><strong>CPU &amp; Memory</strong><span>CPU core limit and memory allocation in MB.</span></div>
        <div class="tab-item"><strong>Disk</strong><span>Root filesystem size and storage pool.</span></div>
        <div class="tab-item"><strong>Network</strong><span>Bridge, IP assignment (DHCP or static CIDR), and default gateway.</span></div>
        <div class="tab-item"><strong>DNS</strong><span>Optional DNS server and search domain overrides.</span></div>
        <div class="tab-item"><strong>Start on Create</strong><span>Automatically start the container immediately after creation.</span></div>
      </div>

      <h3>Container Management</h3>
      <p>From a container's detail page you can:</p>
      <ul>
        <li>Start, stop, restart, and destroy the container</li>
        <li>Open an interactive shell via the built-in xterm.js terminal</li>
        <li>View resource usage (CPU, memory, network)</li>
        <li>Edit configuration (memory, CPU, network interfaces)</li>
        <li>Create and restore snapshots</li>
        <li>View and manage backup archives</li>
      </ul>

      ${infoBox('<strong>Privileged vs Unprivileged:</strong> Depl0y creates unprivileged containers by default (UID mapping enabled, more secure). Set <code>unprivileged: false</code> in the config only if you need root device access inside the container.')}

      <h3>Downloading LXC Templates</h3>
      <p>Go to <strong>Proxmox Hosts → Node Detail → Storage Browser</strong> and navigate to your template storage (usually <code>local</code>). Click <strong>Download</strong> to fetch templates from the official Proxmox mirror directly onto the Proxmox node.</p>
    `
  },
  {
    id: 'templates-images',
    icon: '&#128448;',
    title: 'Templates &amp; Images',
    html: `
      <p>Depl0y provides several mechanisms for creating reusable VM templates and managing disk images.</p>

      <h3>Converting a VM to a Template</h3>
      <p>A VM template is a read-only base image used to clone new VMs quickly. The conversion is irreversible.</p>
      ${step(1, 'Prepare the VM', '<p>Boot the VM, install all desired software, run <code>cloud-init clean</code> (for cloud images) or sysprep (for Windows) to remove machine-specific state.</p>')}
      ${step(2, 'Shut it down', '<p>Stop the VM. You cannot convert a running VM.</p>')}
      ${step(3, 'Convert', '<p>From the VM Detail page or the <strong>Templates</strong> view, click <strong>Convert to Template</strong>. Proxmox marks the VM as a template and locks its disks.</p>')}

      <h3>Cloning from a Template</h3>
      <ol>
        <li>Go to <strong>Templates</strong> to see all templates across all registered hosts.</li>
        <li>Click <strong>Clone</strong> on the template you want to use.</li>
        <li>Enter a name and target node.</li>
        <li>Choose <strong>Full Clone</strong> (independent disk copy) or <strong>Linked Clone</strong> (shares base disk — faster but requires template to remain intact).</li>
        <li>Click <strong>Clone VM</strong>. A Proxmox task tracks progress.</li>
      </ol>

      ${infoBox('<strong>Best practice:</strong> Use Full Clones for production VMs. Linked Clones are excellent for dev/test environments where you want many short-lived copies.')}

      <h3>ISO Image Management</h3>
      <p>Go to <strong>ISO Images</strong> to upload or download ISO files for use when creating new VMs.</p>
      <ul>
        <li><strong>Upload:</strong> Select a local file. Progress is shown in real time.</li>
        <li><strong>URL Download:</strong> Paste a direct URL (e.g. Ubuntu ISO mirror). Depl0y downloads it to the server in the background.</li>
        <li><strong>Verify:</strong> Check SHA256 checksum after download to confirm integrity.</li>
      </ul>
      <p>Downloaded ISOs are stored in <code>/var/lib/depl0y/isos/</code> and are available when creating new VMs via the PVE wizard.</p>

      <h3>Cloud Image Management</h3>
      <p>Go to <strong>Cloud Images</strong> to see all configured cloud image profiles (Ubuntu 24.04, Debian 12, Rocky Linux, etc.). Each profile stores the download URL, expected checksum, and template VM ID. Click <strong>Fetch Latest</strong> to check for newer versions from the upstream mirror.</p>
    `
  },
  {
    id: 'backup-recovery',
    icon: '&#128190;',
    title: 'Backup &amp; Recovery',
    html: `
      <p>Depl0y integrates with Proxmox's native vzdump backup system and Proxmox Backup Server (PBS) for scheduled and on-demand VM/container backups.</p>

      <h3>Backup Jobs (vzdump)</h3>
      <p>Navigate to <strong>Proxmox Hosts → (select host) → Backup Manager</strong> to manage vzdump backup jobs:</p>
      <ul>
        <li><strong>Schedules tab:</strong> Lists all configured backup jobs with their cron schedule, included VMs, storage target, and retention policy.</li>
        <li><strong>Run Now:</strong> Trigger any backup job immediately without waiting for its schedule.</li>
        <li><strong>Retention:</strong> Configure keep-last, keep-daily, keep-weekly, and keep-monthly counts per job.</li>
      </ul>

      <h3>Manual VM Backup</h3>
      <p>From any VM's detail page, click <strong>Backup Now</strong> to create a one-off vzdump backup. Select the storage target and compression mode (zstd recommended).</p>

      <h3>Proxmox Backup Server (PBS)</h3>
      <p>If PBS is configured as a storage target on your Proxmox host, Depl0y's Backup Manager shows a <strong>Datastores</strong> tab with:</p>
      <ul>
        <li>Available datastores and their used/total capacity</li>
        <li>Individual backup snapshots with size and creation timestamp</li>
        <li><strong>Restore:</strong> One-click restore of any snapshot to a target node</li>
        <li><strong>Delete:</strong> Remove individual backup snapshots to reclaim space</li>
      </ul>

      ${infoBox('<strong>PBS deduplication:</strong> PBS deduplicates data across all backups automatically. Two VMs sharing the same OS blocks will store those blocks only once. This makes daily backups of many VMs extremely space-efficient.')}

      <h3>Restore Procedure</h3>
      ${step(1, 'Go to Backup Manager', '<p>Navigate via Proxmox Hosts → (host) → Backup Manager → Datastores.</p>')}
      ${step(2, 'Select the snapshot', '<p>Find the backup by VM name and date. Click <strong>Restore</strong>.</p>')}
      ${step(3, 'Configure restore options', '<p>Choose target node, storage pool, and whether to assign a new VM ID or restore to the original ID.</p>')}
      ${step(4, 'Confirm', '<p>Proxmox creates a task to restore the VM. Monitor progress in the Task list.</p>')}
    `
  },
  {
    id: 'user-management',
    icon: '&#128100;',
    title: 'User Management',
    html: `
      <p>Depl0y has its own user database, independent of Proxmox users. Three roles control what each user can do.</p>

      <h3>Roles</h3>
      <div class="tab-list">
        <div class="tab-item"><strong>Admin</strong><span>Full access. Can manage users, system settings, API tokens, diagnostics, security rules, and all Proxmox operations.</span></div>
        <div class="tab-item"><strong>Operator</strong><span>Can create, modify, start, stop, and delete VMs and containers. Cannot manage users or system settings.</span></div>
        <div class="tab-item"><strong>Viewer</strong><span>Read-only access. Can view VMs, containers, and stats but cannot make changes.</span></div>
      </div>

      <h3>Creating a User</h3>
      <p>Go to <strong>Users</strong> (admin only) and click <strong>Add User</strong>. Set a username, email, temporary password, and role. The user will be prompted to change their password on first login (if that setting is enabled).</p>

      <h3>Two-Factor Authentication (TOTP)</h3>
      <p>Users can enable TOTP 2FA from their <strong>Profile</strong> page:</p>
      ${step(1, 'Go to Profile', '<p>Click your username in the top-right corner.</p>')}
      ${step(2, 'Enable TOTP', '<p>Click <strong>Enable Two-Factor Auth</strong>. A QR code is shown.</p>')}
      ${step(3, 'Scan with authenticator app', '<p>Use Google Authenticator, Authy, or any TOTP app. Scan the QR code.</p>')}
      ${step(4, 'Verify', '<p>Enter the 6-digit code from the app to confirm setup. From now on, login requires both password and TOTP code.</p>')}

      <h3>API Keys</h3>
      <p>Users can generate API keys for programmatic access from their Profile page. API keys are prefixed with <code>dpl0y_</code> and grant the same permissions as the user's role. Keys can be revoked at any time. Use them in the <code>Authorization: Bearer &lt;key&gt;</code> header.</p>

      ${infoBox('<strong>Admin tip:</strong> Go to Settings → Security → 2FA Overview to see which users have 2FA enabled. You can enforce 2FA for all users from the same page.')}
    `
  },
  {
    id: 'api-keys',
    icon: '&#128273;',
    title: 'API Keys &amp; Integration',
    html: `
      <p>Depl0y exposes a full REST API that you can use for automation, CI/CD pipelines, and integrations with other tools.</p>

      <h3>Authentication Methods</h3>
      <div class="tab-list">
        <div class="tab-item"><strong>JWT Bearer Token</strong><span>Obtained via POST /api/v1/auth/login. Short-lived (30 min). Refresh using /api/v1/auth/refresh with the refresh token. Used by the web UI.</span></div>
        <div class="tab-item"><strong>API Key</strong><span>Long-lived token generated in your Profile. Prefixed with <code>dpl0y_</code>. Pass as <code>Authorization: Bearer dpl0y_xxxx</code>. Revoke from Profile at any time.</span></div>
      </div>

      <h3>Generating an API Key</h3>
      ${step(1, 'Open Profile', '<p>Click your username (top-right) → Profile → API Keys tab.</p>')}
      ${step(2, 'Create key', '<p>Click <strong>New API Key</strong>, enter a descriptive name (e.g. "Terraform automation"), and click Create.</p>')}
      ${step(3, 'Copy the key', '<p>The key is shown only once. Copy it immediately and store it securely.</p>')}

      <h3>Using the API</h3>
      <p>Example: start a VM using an API key:</p>
      ${codeBlock(`curl -X POST https://depl0y.example.com/api/v1/vms/123/start \\
  -H "Authorization: Bearer dpl0y_your_key_here"`)}

      <p>Example: list all Proxmox hosts:</p>
      ${codeBlock(`curl https://depl0y.example.com/api/v1/proxmox/ \\
  -H "Authorization: Bearer dpl0y_your_key_here"`)}

      <h3>API Reference</h3>
      <p>The full interactive API documentation is available at:</p>
      <ul>
        <li><a href="/api/v1/docs" target="_blank"><strong>Swagger UI</strong></a> — interactive, allows running API calls from the browser</li>
        <li><a href="/api/v1/redoc" target="_blank"><strong>ReDoc</strong></a> — clean, read-only reference format</li>
      </ul>

      ${infoBox('<strong>Rate limiting:</strong> The API is rate-limited to 100 requests/minute per IP by default. This can be adjusted in <code>/etc/depl0y/config.env</code> by setting <code>RATE_LIMIT_PER_MINUTE</code>.')}
    `
  },
  {
    id: 'security',
    icon: '&#128274;',
    title: 'Security Best Practices',
    html: `
      <p>Depl0y stores privileged credentials (Proxmox API tokens) and provides powerful management capabilities. Follow these recommendations to keep your deployment secure.</p>

      <h3>Network Security</h3>
      <ul>
        <li><strong>Do not expose port 8000 to the internet.</strong> Run Depl0y behind a reverse proxy (nginx, Caddy, Traefik) with TLS termination.</li>
        <li>Use firewall rules to restrict Depl0y to your management VLAN only.</li>
        <li>Enable IP allowlist in <strong>Settings → Security</strong> to whitelist trusted management IPs.</li>
        <li>Use GeoIP blocking to restrict access to your country if Depl0y must be internet-reachable.</li>
      </ul>

      <h3>Reverse Proxy with TLS (nginx example)</h3>
      ${codeBlock(`server {
    listen 443 ssl;
    server_name depl0y.example.com;

    ssl_certificate     /etc/letsencrypt/live/depl0y.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/depl0y.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # WebSocket support (for xterm.js / noVNC)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}`)}

      <h3>User Security</h3>
      <ul>
        <li>Enable TOTP 2FA for all admin accounts (Settings → Security → 2FA Overview).</li>
        <li>Use the <strong>Operator</strong> role for day-to-day users; reserve <strong>Admin</strong> for designated administrators only.</li>
        <li>Rotate API keys regularly. Revoke old keys from the Profile page.</li>
        <li>Review the Audit Log (Settings → Audit Log) periodically for unexpected actions.</li>
      </ul>

      <h3>Proxmox Token Scope</h3>
      <ul>
        <li>Create a dedicated Proxmox user (e.g. <code>depl0y@pve</code>) rather than using <code>root@pam</code> if you want to limit what Depl0y can do.</li>
        <li>Assign only the required Proxmox roles (e.g. <code>PVEAdmin</code> for full management, <code>PVEAuditor</code> for read-only).</li>
        <li>Enable <strong>Privilege Separation</strong> on the token to further restrict its scope to the token's assigned roles.</li>
      </ul>

      <h3>Data at Rest</h3>
      <ul>
        <li>Proxmox API tokens are stored encrypted using Fernet symmetric encryption. The key is in <code>/etc/depl0y/config.env</code> as <code>ENCRYPTION_KEY</code>.</li>
        <li>Restrict access to <code>/etc/depl0y/config.env</code> and <code>/var/lib/depl0y/db/depl0y.db</code> to the <code>depl0y</code> service user only.</li>
        <li>Back up the database file regularly. It contains all user accounts, host registrations, and settings.</li>
      </ul>
    `
  },
  {
    id: 'troubleshooting',
    icon: '&#128295;',
    title: 'Troubleshooting',
    html: `
      <p>Most issues fall into a few common categories. Use this section to diagnose and fix them.</p>

      <h3>Proxmox Host Shows "Inactive" or "Connection Failed"</h3>
      <ol>
        <li>Verify the host address includes the port: <code>pve.example.com:8006</code> or <code>192.168.1.10:8006</code>.</li>
        <li>Confirm the API token is correct and includes the full prefix: <code>PVEAPIToken=root@pam!tokenid=secret</code>.</li>
        <li>Test connectivity from the Depl0y server: <code>curl -k https://&lt;proxmox-ip&gt;:8006/api2/json/version</code></li>
        <li>Check that the Proxmox firewall allows API access from the Depl0y server's IP.</li>
        <li>In the Depl0y UI, click <strong>Test Connection</strong> on the host card to see the error detail.</li>
      </ol>

      <h3>VMs Not Appearing After Poll</h3>
      <ul>
        <li>Click <strong>Poll</strong> (refresh) on the host card. Wait for the spinner to finish.</li>
        <li>Verify the Proxmox token has at least <code>PVEAuditor</code> role on the target nodes.</li>
        <li>Check backend logs: <code>sudo journalctl -u depl0y -f</code></li>
      </ul>

      <h3>noVNC Console Fails to Connect</h3>
      <ul>
        <li>The console requires WebSocket support. Ensure your reverse proxy is configured to upgrade WebSocket connections (see Security section).</li>
        <li>Verify the VM is running — the console tab shows an error if the VM is stopped.</li>
        <li>Try a direct connection to Proxmox Web UI to confirm VNC works at the Proxmox level.</li>
      </ul>

      <h3>Cloud Image Deploy Fails</h3>
      <ul>
        <li>Run the setup script again: <code>sudo /tmp/enable_cloud_images.sh</code>. It is idempotent.</li>
        <li>Check that the template VM ID exists on the target Proxmox node in the Templates section.</li>
        <li>Verify the Proxmox storage pool selected for the new VM has enough free space.</li>
        <li>Review the Proxmox task log for the clone/create task for the detailed error.</li>
      </ul>

      <h3>Viewing Backend Logs</h3>
      ${codeBlock('sudo journalctl -u depl0y -n 100 --no-pager')}
      <p>Or view the log file directly:</p>
      ${codeBlock('sudo tail -f /var/log/depl0y/app.log')}

      <h3>Restarting the Service</h3>
      ${codeBlock('sudo systemctl restart depl0y\nsudo systemctl status depl0y')}

      <h3>Database Issues</h3>
      <p>Use the <strong>Support → Diagnostics → Database Integrity</strong> check to run <code>PRAGMA integrity_check</code>. If corruption is found:</p>
      ${codeBlock('sudo systemctl stop depl0y\nsqlite3 /var/lib/depl0y/db/depl0y.db ".recover" | sqlite3 /var/lib/depl0y/db/depl0y_recovered.db\nsudo mv /var/lib/depl0y/db/depl0y.db /var/lib/depl0y/db/depl0y.db.bak\nsudo mv /var/lib/depl0y/db/depl0y_recovered.db /var/lib/depl0y/db/depl0y.db\nsudo systemctl start depl0y')}

      <h3>Checking Configuration</h3>
      ${codeBlock('sudo cat /etc/depl0y/config.env')}

      <h3>Getting Help</h3>
      <p>If you cannot resolve the issue:</p>
      <ol>
        <li>Go to <router-link to="/support">Support</router-link> and download a Diagnostic Bundle.</li>
        <li>Open a <a href="https://github.com/agit8or1/Depl0y/issues/new?template=bug_report.md" target="_blank">GitHub Issue</a> and attach the diagnostic JSON (redact any sensitive information before posting).</li>
      </ol>
    `
  }
]

export default {
  name: 'Documentation',
  setup() {
    const toast = useToast()
    const mainRef = ref(null)
    const sectionRefs = ref({})
    const activeSection = ref('')
    const sidebarOpen = ref(false)
    const showQuickStart = ref(false)
    const searchQuery = ref('')
    const searchResults = ref([])
    const downloadingPDF = ref(false)

    const sections = SECTIONS

    const activeSectionTitle = computed(() => {
      const sec = sections.find(s => s.id === activeSection.value)
      return sec ? sec.title : ''
    })

    // Intersection observer for active section highlight
    let observer = null

    const scrollToSection = (id) => {
      sidebarOpen.value = false
      const el = sectionRefs.value[id]
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }

    const onSearch = () => {
      const q = searchQuery.value.trim().toLowerCase()
      if (!q) {
        searchResults.value = []
        return
      }
      const results = []
      sections.forEach((section) => {
        // Strip HTML tags for plain text search
        const plain = section.html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
        const idx = plain.toLowerCase().indexOf(q)
        if (idx !== -1) {
          const start = Math.max(0, idx - 40)
          const end = Math.min(plain.length, idx + 80)
          let snippet = plain.slice(start, end)
          // Highlight the match
          const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
          snippet = snippet.replace(re, '<mark>$1</mark>')
          results.push({
            sectionId: section.id,
            sectionTitle: section.title,
            snippet: (start > 0 ? '...' : '') + snippet + (end < plain.length ? '...' : ''),
            index: idx
          })
        }
      })
      searchResults.value = results
    }

    const navigateToResult = (hit) => {
      searchQuery.value = ''
      searchResults.value = []
      scrollToSection(hit.sectionId)
    }

    const copyCode = (text) => {
      navigator.clipboard.writeText(text).then(() => {
        toast.success('Copied to clipboard')
      })
    }

    const downloadPDF = async () => {
      downloadingPDF.value = true
      try {
        const response = await api.docs.downloadPDF()
        const blob = new Blob([response.data], { type: 'application/pdf' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const cd = response.headers['content-disposition']
        let filename = 'Depl0y_Documentation.pdf'
        if (cd) {
          const m = cd.match(/filename="?(.+)"?/)
          if (m) filename = m[1]
        }
        a.download = filename
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        toast.success('PDF downloaded')
      } catch (e) {
        toast.error('PDF download failed')
      } finally {
        downloadingPDF.value = false
      }
    }

    onMounted(() => {
      // Observe section visibility
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              activeSection.value = entry.target.id
            }
          })
        },
        { rootMargin: '-20% 0px -70% 0px', threshold: 0 }
      )
      Object.entries(sectionRefs.value).forEach(([id, el]) => {
        if (el) observer.observe(el)
      })
    })

    onUnmounted(() => {
      if (observer) observer.disconnect()
    })

    return {
      sections,
      mainRef,
      sectionRefs,
      activeSection,
      activeSectionTitle,
      sidebarOpen,
      showQuickStart,
      searchQuery,
      searchResults,
      downloadingPDF,
      scrollToSection,
      onSearch,
      navigateToResult,
      copyCode,
      downloadPDF,
    }
  }
}
</script>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────── */
.doc-layout {
  display: flex;
  min-height: calc(100vh - 4rem);
  gap: 0;
  max-width: 1400px;
  margin: 0 auto;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.doc-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  position: sticky;
  top: 0;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
  background: var(--card-bg, white);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-title {
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.sidebar-close {
  display: none;
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--text-secondary);
}

/* Search */
.sidebar-search {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  background: var(--background, #f9fafb);
}

.search-icon {
  font-size: 0.85rem;
  opacity: 0.6;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.85rem;
  outline: none;
  min-width: 0;
}

.search-input::placeholder {
  color: var(--text-secondary);
}

.search-clear {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.search-results {
  display: flex;
  flex-direction: column;
  max-height: 300px;
  overflow-y: auto;
}

.search-hit {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.search-hit:hover {
  background: var(--background, #f9fafb);
}

.hit-section {
  font-weight: 600;
  font-size: 0.78rem;
  color: var(--primary-color);
}

.hit-snippet {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.hit-snippet :deep(mark) {
  background: #fef08a;
  color: #713f12;
  border-radius: 0.2rem;
  padding: 0 0.1rem;
}

.search-no-results {
  padding: 0.75rem 1rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* TOC */
.toc {
  display: flex;
  flex-direction: column;
  padding: 0.5rem 0;
  flex: 1;
}

.toc-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 1rem;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 0.82rem;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.toc-item:hover {
  color: var(--text-primary);
  background: var(--background, #f9fafb);
}

.toc-item.active {
  color: var(--primary-color);
  border-left-color: var(--primary-color);
  background: rgba(59, 130, 246, 0.06);
  font-weight: 600;
}

.toc-icon {
  font-size: 0.95rem;
  flex-shrink: 0;
  width: 1.25rem;
  text-align: center;
}

.toc-label {
  line-height: 1.3;
}

.sidebar-footer {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.sidebar-link {
  font-size: 0.78rem;
  color: var(--primary-color);
  text-decoration: none;
}

.sidebar-link:hover {
  text-decoration: underline;
}

/* ── Main ────────────────────────────────────────────────────────────────── */
.doc-main {
  flex: 1;
  min-width: 0;
  padding: 0 2rem 3rem;
  overflow-y: auto;
}

.doc-topbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.sidebar-toggle {
  display: none;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.bc-link {
  color: var(--primary-color);
  text-decoration: none;
}

.bc-link:hover {
  text-decoration: underline;
}

.bc-sep {
  opacity: 0.5;
}

.bc-current {
  color: var(--text-primary);
}

/* Page header */
.doc-page-header {
  margin-bottom: 2.5rem;
}

.doc-page-header h1 {
  font-size: 2.25rem;
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
}

.doc-page-header p {
  font-size: 1.05rem;
  color: var(--text-secondary);
  margin: 0 0 1rem 0;
}

.doc-header-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* Sections */
.doc-section {
  margin-bottom: 3rem;
  padding-top: 0.5rem;
  scroll-margin-top: 1rem;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--primary-color);
}

.section-title {
  font-size: 1.6rem;
  margin: 0;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.section-icon {
  font-size: 1.4rem;
}

.anchor-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 1.2rem;
  opacity: 0.4;
  transition: opacity 0.15s;
}

.anchor-link:hover {
  opacity: 1;
  color: var(--primary-color);
}

/* Section body styles (applied via :deep since content is v-html) */
.section-body :deep(h3) {
  font-size: 1.15rem;
  color: var(--text-primary);
  margin: 1.75rem 0 0.75rem;
  font-weight: 700;
}

.section-body :deep(h4) {
  font-size: 1rem;
  color: var(--primary-color);
  margin: 1.25rem 0 0.5rem;
  font-weight: 600;
}

.section-body :deep(p) {
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0 0 0.85rem;
}

.section-body :deep(ul),
.section-body :deep(ol) {
  margin: 0 0 1rem 1.5rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.section-body :deep(li) {
  margin-bottom: 0.35rem;
}

.section-body :deep(a) {
  color: var(--primary-color);
  text-decoration: underline;
}

.section-body :deep(code) {
  background: var(--background, #f9fafb);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.88em;
  font-family: monospace;
  color: var(--text-primary);
}

.section-body :deep(.code-block-wrap) {
  position: relative;
  margin: 0.75rem 0 1rem;
}

.section-body :deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem 1rem 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-family: monospace;
  font-size: 0.88rem;
  line-height: 1.6;
  margin: 0;
  white-space: pre;
}

.section-body :deep(.copy-btn) {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: #94a3b8;
  font-size: 0.75rem;
  padding: 0.2rem 0.6rem;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.15s;
}

.section-body :deep(.copy-btn:hover) {
  background: rgba(255,255,255,0.2);
  color: #f8fafc;
}

.section-body :deep(.info-box) {
  background: #dbeafe;
  border: 2px solid #3b82f6;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  color: #1e40af;
  font-size: 0.9rem;
  line-height: 1.6;
}

.section-body :deep(.warn-box) {
  background: #fef9c3;
  border: 2px solid #eab308;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  color: #713f12;
  font-size: 0.9rem;
  line-height: 1.6;
}

.section-body :deep(.info-box ul),
.section-body :deep(.warn-box ul) {
  margin: 0.5rem 0 0 1.25rem;
}

.section-body :deep(.tab-list) {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0.75rem 0 1rem;
}

.section-body :deep(.tab-item) {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 1rem;
  padding: 0.7rem 1rem;
  background: var(--background, #f9fafb);
  border-radius: 0.375rem;
  border-left: 3px solid var(--primary-color);
  align-items: start;
}

.section-body :deep(.tab-item strong) {
  color: var(--text-primary);
  font-size: 0.88rem;
  padding-top: 0.05rem;
}

.section-body :deep(.tab-item span) {
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.5;
}

.section-body :deep(.doc-step) {
  display: flex;
  gap: 1rem;
  margin: 0.75rem 0;
  align-items: flex-start;
}

.section-body :deep(.step-num) {
  background: var(--primary-color);
  color: white;
  font-weight: 700;
  font-size: 0.8rem;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.section-body :deep(.step-body) {
  flex: 1;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.section-body :deep(.step-body strong) {
  color: var(--text-primary);
  display: block;
  margin-bottom: 0.25rem;
}

.section-body :deep(.step-body p) {
  margin: 0;
}

/* Quick links card grid */
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
}

.doc-card {
  background: var(--card-bg, white);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: var(--shadow-md);
  border: 2px solid transparent;
  transition: transform 0.2s, box-shadow 0.2s;
}

.doc-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.doc-card.featured {
  border-color: var(--primary-color);
}

.doc-icon {
  font-size: 2rem;
  margin-bottom: 0.75rem;
}

.doc-card h3 {
  font-size: 1.05rem;
  margin: 0 0 0.5rem;
  color: var(--text-primary);
}

.doc-card p {
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0 0 1rem;
}

.doc-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* Modal */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content.doc-modal {
  background: var(--card-bg, white);
  border-radius: 0.75rem;
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.3rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body {
  padding: 1.5rem;
}

.modal-body h4 {
  font-size: 1rem;
  color: var(--primary-color);
  margin: 1.25rem 0 0.5rem;
}

.modal-body h4:first-child {
  margin-top: 0;
}

.modal-body p {
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
}

.modal-body ul {
  margin: 0 0 0.75rem 1.25rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.step {
  background: var(--background, #f9fafb);
  padding: 1rem 1.25rem;
  border-radius: 0.375rem;
  border-left: 4px solid var(--primary-color);
  margin-bottom: 0.75rem;
}

.step strong {
  display: block;
  margin-bottom: 0.4rem;
  color: var(--primary-color);
}

.code-block-wrap {
  position: relative;
  margin: 0.5rem 0;
}

.code-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.75rem 1rem;
  border-radius: 0.375rem;
  font-family: monospace;
  font-size: 0.9rem;
  overflow-x: auto;
  margin: 0;
}

.copy-btn {
  position: absolute;
  top: 0.4rem;
  right: 0.4rem;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: #94a3b8;
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.25rem;
  cursor: pointer;
}

.copy-btn:hover {
  background: rgba(255,255,255,0.2);
  color: #f8fafc;
}

.info-box {
  background: #dbeafe;
  border: 2px solid #3b82f6;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  color: #1e40af;
  font-size: 0.9rem;
  line-height: 1.6;
}

.info-box ul {
  margin: 0.5rem 0 0 1.25rem;
}

/* Responsive */
@media (max-width: 900px) {
  .doc-sidebar {
    position: fixed;
    top: 0;
    left: -260px;
    width: 260px;
    height: 100vh;
    max-height: 100vh;
    z-index: 200;
    box-shadow: var(--shadow-lg);
    transition: left 0.25s ease;
  }

  .doc-sidebar.sidebar-open {
    left: 0;
  }

  .sidebar-close {
    display: block;
  }

  .sidebar-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .doc-main {
    padding: 0 1rem 2rem;
  }
}
</style>
