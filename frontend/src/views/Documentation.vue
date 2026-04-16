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
        <a href="/docs" target="_blank" class="sidebar-link">Swagger UI</a>
        <router-link to="/api-explorer" class="sidebar-link">API Explorer</router-link>
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
        <div style="margin-left:auto;display:flex;gap:0.5rem;">
          <a href="/docs" target="_blank" class="btn btn-outline btn-sm">Swagger UI</a>
          <button class="btn btn-outline btn-sm" :disabled="downloadingPDF" @click="downloadPDF">
            {{ downloadingPDF ? 'Generating...' : 'Download PDF' }}
          </button>
        </div>
      </div>

      <!-- Page header -->
      <div class="doc-page-header">
        <h1>Documentation</h1>
        <p>Complete guide to installing, configuring, and using Depl0y — an open-source Proxmox VE management platform.</p>
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
            <span v-html="section.title"></span>
          </h2>
          <a :href="'#' + section.id" class="anchor-link" title="Link to section">&#182;</a>
        </div>
        <div class="section-body" v-html="section.html"></div>
      </section>

      <!-- Quick Links -->
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
              <button @click="showQuickStart = true" class="btn btn-primary btn-sm">View Guide</button>
              <router-link to="/settings" class="btn btn-outline btn-sm">Settings</router-link>
            </div>
          </div>
          <div class="doc-card">
            <div class="doc-icon">&#128295;</div>
            <h3>Interactive API Explorer</h3>
            <p>Test every API endpoint interactively — enter parameters and send live requests.</p>
            <div class="doc-actions">
              <router-link to="/api-explorer" class="btn btn-primary btn-sm">Open Explorer</router-link>
              <a href="/docs" target="_blank" class="btn btn-outline btn-sm">Swagger UI</a>
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
              <router-link to="/bug-report" class="btn btn-outline btn-sm">Bug Report</router-link>
              <a href="https://github.com/agit8or1/Depl0y/issues" target="_blank" class="btn btn-outline btn-sm">GitHub</a>
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
            <p>Go to <router-link to="/settings" @click="showQuickStart = false">Settings</router-link> and look for the "Cloud Image Setup" section. A green status means already configured; yellow means setup is needed.</p>
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

// ── Helper functions ─────────────────────────────────────────────────────────
function codeBlock(code, lang = '') {
  const id = 'cb-' + Math.random().toString(36).slice(2, 8)
  return `<div class="code-block-wrap"><pre class="code-block" id="${id}">${code}</pre><button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('${id}').innerText).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)})">Copy</button></div>`
}

function infoBox(text) { return `<div class="info-box">${text}</div>` }
function warnBox(text) { return `<div class="warn-box">${text}</div>` }
function tipBox(text)  { return `<div class="tip-box">${text}</div>` }

function step(num, title, body) {
  return `<div class="doc-step"><span class="step-num">${num}</span><div class="step-body"><strong>${title}</strong>${body}</div></div>`
}

function tabItem(label, content) {
  return `<div class="tab-item"><strong>${label}</strong><span>${content}</span></div>`
}

// ── Section content ───────────────────────────────────────────────────────────
const SECTIONS = [
  {
    id: 'getting-started',
    icon: '&#9654;',
    title: 'Getting Started',
    html: `
      <p>Depl0y is a self-hosted Proxmox VE management panel. It gives you a single web interface to manage VMs, LXC containers, storage, backups, and clusters across multiple Proxmox hosts.</p>

      <h3>System Requirements</h3>
      <ul>
        <li><strong>OS:</strong> Ubuntu 22.04/24.04 or Debian 12</li>
        <li><strong>RAM:</strong> 1 GB minimum (2 GB recommended)</li>
        <li><strong>Disk:</strong> 4 GB free (more if storing ISOs locally)</li>
        <li><strong>Network:</strong> Must be able to reach Proxmox API on port 8006</li>
        <li><strong>Browser:</strong> Any modern browser (Chrome, Firefox, Edge, Safari)</li>
      </ul>

      <h3>Installation</h3>
      <p>Run on a fresh Ubuntu or Debian server:</p>
      ${codeBlock('curl -fsSL http://deploy.agit8or.net/downloads/install.sh | sudo bash')}
      <p>The installer:</p>
      <ol>
        <li>Installs Python 3, Node.js, nginx, and system dependencies</li>
        <li>Creates <code>/opt/depl0y</code> (app) and <code>/var/lib/depl0y</code> (data)</li>
        <li>Builds the frontend and sets up nginx to serve it on port 80</li>
        <li>Creates a <code>depl0y-backend</code> systemd service that starts on boot</li>
      </ol>

      <h3>First Login</h3>
      ${step(1, 'Open your browser', '<p>Navigate to <code>http://&lt;server-ip&gt;</code></p>')}
      ${step(2, 'Log in', '<p>Default credentials: <strong>admin / admin</strong> — change the password immediately after first login.</p>')}
      ${step(3, 'Add a Proxmox Datacenter', '<p>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Datacenter</strong>. You will need a Proxmox API token (see <a href="#proxmox-hosts">Proxmox Hosts Setup</a>).</p>')}
      ${step(4, 'Poll the host', '<p>Click <strong>Poll</strong> on the new host card to sync nodes, VMs, and containers.</p>')}

      ${infoBox('<strong>After login:</strong> Go to <strong>Settings</strong> to configure SMTP notifications, set up cloud images, and enable 2FA.')}

      <h3>Service Management</h3>
      ${codeBlock('# Check status\nsudo systemctl status depl0y-backend\n\n# Restart\nsudo systemctl restart depl0y-backend\n\n# View live logs\nsudo journalctl -u depl0y-backend -f')}

      <h3>Updating</h3>
      ${codeBlock('cd /opt/depl0y && git pull origin main && sudo bash deploy.sh')}
      <p>Or use <strong>Settings → System Updates</strong> to check and install updates from the UI.</p>
    `
  },
  {
    id: 'vm-management',
    icon: '&#9881;&#65039;',
    title: 'VM Management',
    html: `
      <p>Depl0y offers two paths to create virtual machines: the native PVE VM wizard and the fast Cloud Image deploy path.</p>

      <h3>Method 1: Create VM (PVE Wizard)</h3>
      <p>Go to <strong>Create VM (PVE)</strong> for a guided form that creates a Proxmox-native VM:</p>
      <div class="tab-list">
        ${tabItem('Step 1 — Location', 'Select target host and node. VM ID is auto-generated (or set your own). Enter a VM name.')}
        ${tabItem('Step 2 — Hardware', 'CPU cores/sockets, RAM (MB), disk size and storage pool, network bridge and VLAN, ISO image, BIOS/UEFI, and machine type.')}
        ${tabItem('Step 3 — Review', 'Confirm all settings. Click Create VM to submit. A live task tracker shows Proxmox task progress.')}
      </div>

      <h3>Method 2: Cloud Image Deploy (Fast)</h3>
      <p>Cloud images clone a pre-configured template, inject cloud-init, and boot in about 30 seconds.</p>
      ${step(1, 'Run one-time setup', `<p>SSH to your Depl0y host and run:</p>${codeBlock('sudo /tmp/enable_cloud_images.sh')}`)}
      ${step(2, 'Go to Deploy', '<p>Navigate to <strong>Deploy VM</strong> and select <strong>Cloud Image</strong>.</p>')}
      ${step(3, 'Configure', '<p>Choose image (Ubuntu 24.04, Debian 12, etc.), set CPU/RAM/disk, enter credentials.</p>')}
      ${step(4, 'Deploy', '<p>Click Create. The VM is cloned and started within ~30 seconds on subsequent runs.</p>')}

      <h3>VM Controls</h3>
      <p>From the VM Detail page you can:</p>
      <ul>
        <li><strong>Start / Stop / Reboot / Shutdown</strong> — power controls with confirmation dialogs</li>
        <li><strong>Force Stop</strong> — equivalent to pulling the power cord</li>
        <li><strong>Suspend / Resume</strong> — save and restore VM state to disk</li>
        <li><strong>Clone</strong> — full or linked clone to any node</li>
        <li><strong>Migrate</strong> — live migration to another node in the same cluster</li>
        <li><strong>Convert to Template</strong> — create a reusable base image</li>
        <li><strong>Snapshots</strong> — create, restore, and delete point-in-time snapshots</li>
        <li><strong>Open Console</strong> — noVNC browser console or xterm.js terminal</li>
      </ul>

      <h3>VM Configuration (Hardware Tab)</h3>
      <p>The Hardware tab in VM Detail lets you:</p>
      <ul>
        <li>Add, resize, and delete virtual disks</li>
        <li>Add and remove network interfaces (NICs)</li>
        <li>Modify CPU count and memory allocation (requires reboot)</li>
        <li>Pass through PCI devices (GPU, NVMe) and USB devices</li>
        <li>Configure serial ports</li>
        <li>Edit cloud-init drive configuration</li>
      </ul>

      ${infoBox('<strong>QEMU Guest Agent:</strong> Install the guest agent inside each VM for accurate memory stats and IP detection: <code>apt install qemu-guest-agent &amp;&amp; systemctl enable --now qemu-guest-agent</code>')}

      <h3>Bulk Operations</h3>
      <p>Go to <strong>Bulk Operations</strong> to perform actions across multiple VMs simultaneously:</p>
      <ul>
        <li>Bulk start, stop, shutdown, or reboot</li>
        <li>Bulk snapshot creation and deletion</li>
        <li>Bulk config update (tags, memory, CPU)</li>
        <li>Bulk live migration to a different node</li>
        <li>Tag compliance enforcement</li>
        <li>Resource usage audit</li>
      </ul>
    `
  },
  {
    id: 'containers',
    icon: '&#128230;',
    title: 'Containers (LXC)',
    html: `
      <p>LXC containers are lightweight OS-level virtualization — faster to create than full VMs and share the host kernel. Depl0y provides full lifecycle management for LXC containers.</p>

      <h3>Creating an LXC Container</h3>
      <p>Go to <strong>Create LXC</strong> and fill in:</p>
      <div class="tab-list">
        ${tabItem('Host &amp; Node', 'Which Proxmox host and node to create the container on.')}
        ${tabItem('CT ID', 'Container ID. Auto-generated by default; must be unique on the selected node.')}
        ${tabItem('Hostname', "The container's hostname.")}
        ${tabItem('Template', 'LXC template image (Ubuntu 22.04, Debian 12, Alpine, etc.).')}
        ${tabItem('Root Password', 'Password for the root account inside the container.')}
        ${tabItem('CPU &amp; Memory', 'CPU core limit and memory allocation in MB.')}
        ${tabItem('Disk', 'Root filesystem size and storage pool.')}
        ${tabItem('Network', 'Bridge, IP assignment (DHCP or static CIDR), and default gateway.')}
        ${tabItem('DNS', 'Optional DNS server and search domain overrides.')}
        ${tabItem('Start on Create', 'Automatically start the container immediately after creation.')}
      </div>

      <h3>Container Management</h3>
      <p>From a container's detail page you can:</p>
      <ul>
        <li>Start, stop, restart, and destroy the container</li>
        <li>Open an interactive shell via the built-in xterm.js terminal</li>
        <li>View resource usage (CPU, memory, network, disk I/O)</li>
        <li>Edit configuration (memory, CPU, network interfaces)</li>
        <li>Create and restore snapshots</li>
        <li>Clone the container to a new CT ID</li>
        <li>Migrate to another node in the cluster</li>
        <li>Resize the root disk</li>
      </ul>

      ${infoBox('<strong>Privileged vs Unprivileged:</strong> Depl0y creates unprivileged containers by default (UID mapping enabled, more secure). Set <code>unprivileged: false</code> only if you need root device access inside the container.')}

      <h3>Downloading LXC Templates</h3>
      <p>Go to <strong>Proxmox Hosts → Node Detail → Storage Browser</strong> and navigate to your template storage (usually <code>local</code>). Click <strong>Download Template</strong> to fetch templates from the official Proxmox mirror.</p>
    `
  },
  {
    id: 'networking',
    icon: '&#127760;',
    title: 'Networking',
    html: `
      <p>Depl0y exposes Proxmox's full networking stack: Linux bridges, VLANs, bonds, and the Software-Defined Networking (SDN) layer for advanced multi-tenant setups.</p>

      <h3>Node Network Interfaces</h3>
      <p>Go to <strong>Proxmox Hosts → (host) → Node Detail → Network</strong> to manage network interfaces on a Proxmox node. You can:</p>
      <ul>
        <li>View all current network interfaces (bridges, bonds, VLANs, physical NICs)</li>
        <li>Create a new Linux bridge (<code>vmbr0</code>, etc.) for VM networking</li>
        <li>Create a bond (LACP or active-backup) across two physical NICs</li>
        <li>Create a VLAN interface on a physical or bridge interface</li>
        <li>Edit IP address, gateway, and VLAN settings</li>
        <li>Apply pending changes (reloads <code>/etc/network/interfaces</code>)</li>
        <li>Revert unapplied changes</li>
      </ul>

      ${warnBox('<strong>Caution:</strong> Applying network changes immediately takes effect on the Proxmox host. An incorrect network config can cut your access to the node. Always verify settings before applying, and have console access (iDRAC/iLO) as a fallback.')}

      <h3>VM Network Interfaces</h3>
      <p>Each VM can have multiple virtual NICs. From the VM Hardware tab you can:</p>
      <ul>
        <li>Add a new NIC — choose bridge, model (virtio, e1000), VLAN tag, and firewall setting</li>
        <li>Remove a NIC (the device is detached and the slot is freed)</li>
        <li>Set MAC address manually or let Proxmox assign one</li>
      </ul>

      <h3>VLANs</h3>
      <p>Proxmox supports VLAN tagging in two modes:</p>
      <div class="tab-list">
        ${tabItem('VLAN-aware bridge', 'The bridge itself is VLAN-aware. Assign VLAN tag per VM NIC. Most flexible — single bridge handles all VLANs.')}
        ${tabItem('VLAN interface', 'Create a separate bridge per VLAN (<code>vmbr0.10</code>). Simpler but requires one bridge per VLAN.')}
      </div>
      <p>To enable VLAN-aware on an existing bridge, edit it in the Network tab and check <strong>VLAN aware</strong>. Then assign VLAN tags in each VM's NIC configuration.</p>

      <h3>Software-Defined Networking (SDN)</h3>
      <p>SDN provides overlay networks for multi-node, multi-tenant environments. Access it via <strong>Network Management → SDN</strong>.</p>

      <h4>Zones</h4>
      <p>A Zone defines the SDN transport type:</p>
      <ul>
        <li><strong>Simple Zone</strong> — basic isolated L2 network on a single node</li>
        <li><strong>VLAN Zone</strong> — maps VNets to 802.1Q VLAN tags on a physical bridge</li>
        <li><strong>VXLAN Zone</strong> — L2 overlay over L3 IP networks for cross-node isolation</li>
        <li><strong>EVPN Zone</strong> — advanced BGP-based L2/L3 VPN with route distribution</li>
      </ul>

      <h4>VNets</h4>
      <p>VNets are virtual networks attached to a Zone. VMs connect to a VNet as if it were a normal bridge. Create a VNet, assign it to a Zone, and select it when creating or editing a VM NIC.</p>

      <h4>Subnets</h4>
      <p>Optional DHCP/IPAM subnets within a VNet. When defined, Proxmox can auto-assign IPs to VMs via DHCP from a built-in server.</p>

      <h4>Applying SDN Configuration</h4>
      ${codeBlock('# Click "Apply SDN" in the UI, or via the API:\ncurl -X POST /api/v1/sdn/{host_id}/apply \\\n  -H "Authorization: Bearer YOUR_TOKEN"')}

      <h3>Firewall</h3>
      <p>Proxmox has a stateful firewall at three levels:</p>
      <ul>
        <li><strong>Datacenter (cluster) level</strong> — rules applied to all nodes. Managed via <strong>PVE Firewall → Cluster Rules</strong>.</li>
        <li><strong>Node level</strong> — rules for the Proxmox host OS itself.</li>
        <li><strong>VM/CT level</strong> — per-VM rules. Managed via the VM Detail Firewall tab.</li>
      </ul>
      <p>IPSets group multiple IPs for use in rules. Aliases give friendly names to IPs or CIDR ranges. Both are managed under <strong>PVE Firewall → IPSets / Aliases</strong>.</p>
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
        <li><strong>Schedules tab:</strong> Lists all configured backup jobs with cron schedule, included VMs, storage target, and retention policy.</li>
        <li><strong>Run Now:</strong> Trigger any backup job immediately.</li>
        <li><strong>Retention:</strong> Configure keep-last, keep-daily, keep-weekly, and keep-monthly counts per job.</li>
      </ul>

      <h3>Manual VM Backup</h3>
      <p>From any VM's detail page, click <strong>Backup Now</strong>. Select the storage target and compression mode (zstd recommended for best speed/ratio).</p>

      <h3>Proxmox Backup Server (PBS)</h3>
      <p>If PBS is registered as a storage target on your Proxmox host, Depl0y's Backup Manager shows a <strong>Datastores</strong> tab:</p>
      <ul>
        <li>Available datastores and their used/total capacity</li>
        <li>Individual backup snapshots with size and creation timestamp</li>
        <li><strong>Restore:</strong> One-click restore of any snapshot to a target node and storage</li>
        <li><strong>Verify:</strong> Trigger PBS to verify backup integrity</li>
        <li><strong>Prune:</strong> Remove old snapshots based on a keep policy</li>
        <li><strong>Delete:</strong> Remove individual snapshots to reclaim space</li>
      </ul>

      ${infoBox('<strong>PBS deduplication:</strong> PBS deduplicates data across all backups automatically. Two VMs sharing the same OS blocks store those blocks only once, making daily backups of many VMs extremely space-efficient.')}

      <h3>Restore Procedure</h3>
      ${step(1, 'Go to Backup Manager', '<p>Navigate via Proxmox Hosts → (host) → Backup Manager → Datastores tab.</p>')}
      ${step(2, 'Select the snapshot', '<p>Find the backup by VM name and date. Click <strong>Restore</strong>.</p>')}
      ${step(3, 'Configure restore options', '<p>Choose target node, storage pool, and VM ID (restore to original or a new ID).</p>')}
      ${step(4, 'Confirm', '<p>Proxmox creates a task. Monitor progress in the Task list.</p>')}

      <h3>Backup Schedules — Cron Format</h3>
      ${codeBlock(`# Daily at 02:00\n0 2 * * *\n\n# Every Sunday at 01:30\n30 1 * * 0\n\n# Every 6 hours\n0 */6 * * *`)}
    `
  },
  {
    id: 'high-availability',
    icon: '&#128736;&#65039;',
    title: 'High Availability',
    html: `
      <p>Proxmox HA allows VMs and containers to automatically restart on another node in the cluster if the current node fails. Depl0y provides a full management interface for HA resources and groups.</p>

      <h3>Prerequisites</h3>
      <ul>
        <li>Proxmox cluster with at least <strong>3 nodes</strong> (for quorum)</li>
        <li>Shared storage accessible from all nodes (Ceph, NFS, iSCSI, or PBS)</li>
        <li>Corosync cluster network configured between nodes</li>
        <li>All VMs/CTs you want to protect must reside on shared storage</li>
      </ul>

      ${warnBox('<strong>Two-node clusters:</strong> A two-node cluster loses quorum if one node goes down, preventing HA from automatically restarting VMs. Use a third "witness" node or external corosync quorum device (QDevice) to solve this.')}

      <h3>HA Groups</h3>
      <p>HA groups define which nodes are <em>preferred</em> for running a set of VMs and their relative priority. Navigate to <strong>HA Management → Groups</strong> to:</p>
      <ul>
        <li>Create a group with a list of nodes and per-node priority (0–1000, higher = more preferred)</li>
        <li>Set <strong>Restricted</strong> to prevent VMs from running on nodes not in the group</li>
        <li>Set <strong>No-Fail Back</strong> to keep VMs on the current node after recovery (avoids unnecessary migrations)</li>
      </ul>

      <h3>HA Resources</h3>
      <p>An HA resource is a VM or container enrolled for HA protection. Navigate to <strong>HA Management → Resources</strong> to:</p>
      <ul>
        <li>Add a VM or CT to HA (select it, choose a group and max-restart count)</li>
        <li>Set the <strong>State</strong>: <code>started</code> (HA keeps it running), <code>stopped</code> (HA keeps it stopped), <code>disabled</code> (HA ignores it)</li>
        <li>Remove a resource from HA protection</li>
      </ul>

      <h3>Enrolling a VM in HA via API</h3>
      ${codeBlock(`POST /api/v1/pve-node/{host_id}/cluster/ha/resources\nContent-Type: application/json\n\n{\n  "sid": "vm:100",\n  "group": "my-ha-group",\n  "max_restart": 3,\n  "state": "started"\n}`)}

      <h3>Node Evacuation</h3>
      <p>Before taking a node offline for maintenance, use <strong>Cluster Operations → Evacuate Node</strong> to live-migrate all running VMs to other nodes in the cluster. The API endpoint is:</p>
      ${codeBlock('POST /api/v1/cluster/{host_id}/nodes/{node}/evacuate')}

      <h3>HA Status</h3>
      <p>Navigate to <strong>HA Management → Status</strong> to see:</p>
      <ul>
        <li>Current quorum status and voter counts</li>
        <li>CRM (Cluster Resource Manager) and LRM (Local Resource Manager) status per node</li>
        <li>Status of each HA resource (started, stopped, error)</li>
      </ul>

      ${infoBox('<strong>Monitoring:</strong> Configure an alert rule in <strong>Alerts</strong> to notify you when a VM starts on an unexpected node or when HA triggers a restart.')}
    `
  },
  {
    id: 'api-access',
    icon: '&#128273;',
    title: 'API Access',
    html: `
      <p>Depl0y exposes a full REST API that you can use for automation, CI/CD pipelines, and integrations with other tools. The API is documented interactively at <a href="/docs" target="_blank">Swagger UI</a> or explore it in the <router-link to="/api-explorer">API Explorer</router-link>.</p>

      <h3>Authentication Methods</h3>
      <div class="tab-list">
        ${tabItem('JWT Bearer Token', 'Obtained via POST /api/v1/auth/login. Access token valid for 30 minutes. Refresh using /api/v1/auth/refresh. Used by the web UI automatically.')}
        ${tabItem('API Key', 'Long-lived token generated in your Profile. Prefixed with <code>dpl0y_</code>. Pass as <code>Authorization: Bearer dpl0y_xxxx</code>. Revoke from Profile at any time.')}
      </div>

      <h3>Generating an API Key</h3>
      ${step(1, 'Open Profile', '<p>Click your username (top-right) → Profile → API Keys tab.</p>')}
      ${step(2, 'Create key', '<p>Click <strong>New API Key</strong>, enter a descriptive name (e.g. "Terraform automation"), and click Create.</p>')}
      ${step(3, 'Copy the key', '<p>The key is shown only once. Copy it immediately and store it securely (password manager).</p>')}

      <h3>Using the API</h3>
      <p>Start a VM:</p>
      ${codeBlock(`curl -X POST https://depl0y.example.com/api/v1/vms/123/start \\\n  -H "Authorization: Bearer dpl0y_your_key_here"`)}
      <p>List Proxmox hosts:</p>
      ${codeBlock(`curl https://depl0y.example.com/api/v1/proxmox/ \\\n  -H "Authorization: Bearer dpl0y_your_key_here"`)}
      <p>Create a snapshot:</p>
      ${codeBlock(`curl -X POST https://depl0y.example.com/api/v1/pve-vm/1/pve/100/snapshots \\\n  -H "Authorization: Bearer dpl0y_your_key_here" \\\n  -H "Content-Type: application/json" \\\n  -d '{"snapname": "pre-upgrade", "description": "Before package upgrade"}'`)}

      <h3>Rate Limits</h3>
      <p>The API enforces rate limits to protect the backend:</p>
      <ul>
        <li><strong>General endpoints:</strong> 100 requests/minute per IP</li>
        <li><strong>Login endpoint:</strong> 5 requests/minute per IP (brute-force protection)</li>
      </ul>
      <p>Adjust the limit in <code>/etc/depl0y/config.env</code> by setting <code>RATE_LIMIT_PER_MINUTE</code>. Restart the service after changes.</p>

      ${infoBox('<strong>Hint:</strong> Use the <a href="/api-explorer">API Explorer</a> in Depl0y to test any endpoint with your current session token — no setup needed.')}

      <h3>OpenAPI Schema</h3>
      <p>Machine-readable OpenAPI 3.0 schema is available at:</p>
      <ul>
        <li><a href="/openapi.json" target="_blank"><code>/openapi.json</code></a> — raw JSON schema</li>
        <li><a href="/docs" target="_blank"><code>/docs</code></a> — Swagger UI</li>
        <li><a href="/redoc" target="_blank"><code>/redoc</code></a> — ReDoc</li>
      </ul>
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
        ${tabItem('Admin', 'Full access. Can manage users, system settings, API tokens, diagnostics, security rules, and all Proxmox operations.')}
        ${tabItem('Operator', 'Can create, modify, start, stop, and delete VMs and containers. Cannot manage users or system settings.')}
        ${tabItem('Viewer', 'Read-only access. Can view VMs, containers, and stats but cannot make changes.')}
      </div>

      <h3>Creating a User</h3>
      <p>Go to <strong>Users</strong> (admin only) and click <strong>Add User</strong>. Set a username, email, temporary password, and role. The user will be prompted to change their password on first login.</p>

      <h3>Two-Factor Authentication (TOTP)</h3>
      <p>Users can enable TOTP 2FA from their <strong>Profile</strong> page:</p>
      ${step(1, 'Go to Profile', '<p>Click your username in the top-right corner.</p>')}
      ${step(2, 'Enable TOTP', '<p>Click <strong>Enable Two-Factor Auth</strong>. A QR code is shown.</p>')}
      ${step(3, 'Scan', '<p>Use Google Authenticator, Authy, or any TOTP app. Scan the QR code.</p>')}
      ${step(4, 'Verify', '<p>Enter the 6-digit code to confirm setup. Login now requires both password and TOTP code.</p>')}

      <h3>API Keys</h3>
      <p>Users can generate API keys for programmatic access from their Profile page. Keys are prefixed with <code>dpl0y_</code> and grant the same permissions as the user's role. Keys can be revoked at any time.</p>

      ${infoBox('<strong>Admin tip:</strong> Use the <strong>Operator</strong> role for day-to-day users; reserve <strong>Admin</strong> for designated administrators only. Enable TOTP 2FA on all admin accounts.')}
    `
  },
  {
    id: 'keyboard-shortcuts',
    icon: '&#9000;',
    title: 'Keyboard Shortcuts',
    html: `
      <p>Depl0y supports keyboard shortcuts to speed up common navigation and actions. Shortcuts are active when no text input is focused.</p>

      <h3>Global Navigation</h3>
      <div class="shortcuts-table">
        <div class="shortcut-row header-row">
          <span>Shortcut</span>
          <span>Action</span>
        </div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>D</kbd></span><span>Go to Dashboard</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>V</kbd></span><span>Go to Virtual Machines</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>C</kbd></span><span>Go to Containers (LXC)</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>N</kbd></span><span>Go to Nodes / Proxmox Hosts</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>B</kbd></span><span>Go to Backup Manager</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>T</kbd></span><span>Go to Tasks</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>S</kbd></span><span>Go to Settings</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>A</kbd></span><span>Go to API Explorer</span></div>
        <div class="shortcut-row"><span><kbd>G</kbd> then <kbd>?</kbd></span><span>Show this keyboard shortcut reference</span></div>
      </div>

      <h3>VM / Container Actions (when a VM is selected)</h3>
      <div class="shortcuts-table">
        <div class="shortcut-row header-row">
          <span>Shortcut</span>
          <span>Action</span>
        </div>
        <div class="shortcut-row"><span><kbd>S</kbd></span><span>Start VM/CT</span></div>
        <div class="shortcut-row"><span><kbd>X</kbd></span><span>Stop VM/CT</span></div>
        <div class="shortcut-row"><span><kbd>R</kbd></span><span>Reboot VM/CT</span></div>
        <div class="shortcut-row"><span><kbd>C</kbd></span><span>Open Console</span></div>
        <div class="shortcut-row"><span><kbd>E</kbd></span><span>Edit / Settings</span></div>
        <div class="shortcut-row"><span><kbd>Delete</kbd></span><span>Delete VM/CT (with confirmation)</span></div>
      </div>

      <h3>UI Controls</h3>
      <div class="shortcuts-table">
        <div class="shortcut-row header-row">
          <span>Shortcut</span>
          <span>Action</span>
        </div>
        <div class="shortcut-row"><span><kbd>/</kbd></span><span>Focus global search</span></div>
        <div class="shortcut-row"><span><kbd>Escape</kbd></span><span>Close modal / clear search</span></div>
        <div class="shortcut-row"><span><kbd>?</kbd></span><span>Show keyboard shortcut help</span></div>
        <div class="shortcut-row"><span><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd></span><span>Toggle dark/light mode</span></div>
      </div>

      <h3>Tables &amp; Lists</h3>
      <div class="shortcuts-table">
        <div class="shortcut-row header-row">
          <span>Shortcut</span>
          <span>Action</span>
        </div>
        <div class="shortcut-row"><span><kbd>&#8593;</kbd> / <kbd>&#8595;</kbd></span><span>Navigate rows in a table</span></div>
        <div class="shortcut-row"><span><kbd>Enter</kbd></span><span>Open selected row</span></div>
        <div class="shortcut-row"><span><kbd>Space</kbd></span><span>Select/deselect row (for bulk operations)</span></div>
      </div>

      ${tipBox('<strong>Tip:</strong> Press <kbd>?</kbd> at any time while using Depl0y to show the in-app keyboard shortcut reference panel.')}
    `
  },
  {
    id: 'proxmox-hosts',
    icon: '&#127970;',
    title: 'Proxmox Hosts Setup',
    html: `
      <p>Before managing VMs, you must register at least one Proxmox host. Depl0y communicates with Proxmox exclusively via its REST API using an API token — no root SSH required.</p>

      <h3>Creating a Proxmox API Token</h3>
      ${step(1, 'Log into Proxmox Web UI', '<p>Navigate to <code>https://&lt;proxmox-ip&gt;:8006</code> and log in as root.</p>')}
      ${step(2, 'Create an API token', `<p>Go to <strong>Datacenter → Permissions → API Tokens → Add</strong>. Set:</p><ul><li><strong>User:</strong> root@pam (or a dedicated user)</li><li><strong>Token ID:</strong> e.g. <code>depl0y</code></li><li><strong>Privilege Separation:</strong> Leave unchecked for full access</li></ul>`)}
      ${step(3, 'Copy the token secret', '<p>The secret is shown only once. Copy both the token ID and secret.</p>')}

      <h3>Token Format</h3>
      ${codeBlock('PVEAPIToken=root@pam!depl0y=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')}

      <h3>Adding the Host in Depl0y</h3>
      <ol>
        <li>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Host</strong>.</li>
        <li>Enter the <strong>Host Address</strong> (e.g. <code>pve.example.com:8006</code> or an IP).</li>
        <li>Paste the full <strong>API Token</strong> string.</li>
        <li>Give it a friendly <strong>Display Name</strong>.</li>
        <li>Click <strong>Save</strong>. Depl0y immediately tests the connection.</li>
      </ol>

      ${warnBox('<strong>Security:</strong> Depl0y stores API tokens encrypted at rest using Fernet symmetric encryption. Never share your <code>config.env</code> or database file.')}

      <h3>Multiple Hosts &amp; Federation</h3>
      <p>Depl0y supports any number of registered hosts. Each host is queried independently. The Federated Dashboard aggregates stats across all active hosts. You can mark a host as inactive to exclude it from live queries without deleting its records.</p>
    `
  },
  {
    id: 'security',
    icon: '&#128274;',
    title: 'Security Best Practices',
    html: `
      <p>Depl0y stores privileged credentials and provides powerful management capabilities. Follow these recommendations to keep your deployment secure.</p>

      <h3>Network Security</h3>
      <ul>
        <li><strong>Do not expose port 8000 to the internet.</strong> Run Depl0y behind a reverse proxy (nginx, Caddy, Traefik) with TLS termination.</li>
        <li>Use firewall rules to restrict Depl0y to your management VLAN only.</li>
        <li>Enable IP allowlist in <strong>Settings → Security</strong> to whitelist trusted management IPs.</li>
        <li>Use GeoIP blocking to restrict access by country if Depl0y must be internet-reachable.</li>
      </ul>

      <h3>Reverse Proxy with TLS (nginx)</h3>
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
        <li>Review the Audit Log periodically for unexpected actions.</li>
      </ul>

      <h3>Data at Rest</h3>
      <ul>
        <li>Proxmox API tokens are encrypted using Fernet symmetric encryption. The key is in <code>/etc/depl0y/config.env</code>.</li>
        <li>Restrict access to <code>/etc/depl0y/config.env</code> and <code>/var/lib/depl0y/db/depl0y.db</code> to the <code>depl0y</code> service user only.</li>
        <li>Back up the database file regularly.</li>
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
        <li>Verify the host address includes the port: <code>pve.example.com:8006</code>.</li>
        <li>Confirm the API token format: <code>PVEAPIToken=root@pam!tokenid=secret</code>.</li>
        <li>Test connectivity from the Depl0y server: ${codeBlock('curl -k https://&lt;proxmox-ip&gt;:8006/api2/json/version')}</li>
        <li>Click <strong>Test Connection</strong> on the host card to see the exact error.</li>
      </ol>

      <h3>VMs Not Appearing After Poll</h3>
      <ul>
        <li>Click <strong>Poll</strong> on the host card and wait for it to finish.</li>
        <li>Verify the token has at least <code>PVEAuditor</code> role on the target nodes.</li>
        <li>Check backend logs: ${codeBlock('sudo journalctl -u depl0y-backend -f')}</li>
      </ul>

      <h3>noVNC Console Fails to Connect</h3>
      <ul>
        <li>The console requires WebSocket support. Ensure your reverse proxy upgrades WebSocket connections.</li>
        <li>Verify the VM is running — the console tab shows an error if the VM is stopped.</li>
      </ul>

      <h3>Cloud Image Deploy Fails</h3>
      <ul>
        <li>Run the setup script again: <code>sudo /tmp/enable_cloud_images.sh</code>. It is idempotent.</li>
        <li>Check that the template VM exists on the target Proxmox node in the Templates section.</li>
        <li>Verify the storage pool has enough free space for the new VM.</li>
      </ul>

      <h3>Viewing Backend Logs</h3>
      ${codeBlock('sudo journalctl -u depl0y-backend -n 100 --no-pager')}

      <h3>Database Issues</h3>
      <p>Use <strong>Support → Diagnostics → Database Integrity</strong> to run <code>PRAGMA integrity_check</code>. If corruption is found:</p>
      ${codeBlock('sudo systemctl stop depl0y\nsqlite3 /var/lib/depl0y/db/depl0y.db ".recover" | sqlite3 /var/lib/depl0y/db/depl0y_recovered.db\nsudo mv /var/lib/depl0y/db/depl0y.db /var/lib/depl0y/db/depl0y.db.bak\nsudo mv /var/lib/depl0y/db/depl0y_recovered.db /var/lib/depl0y/db/depl0y.db\nsudo systemctl start depl0y')}

      <h3>Getting Help</h3>
      <ol>
        <li>Go to <router-link to="/support">Support</router-link> and download a Diagnostic Bundle.</li>
        <li>Open a <a href="https://github.com/agit8or1/Depl0y/issues/new?template=bug_report.md" target="_blank">GitHub Issue</a> and attach the diagnostic JSON.</li>
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
      return sec ? sec.title.replace(/<[^>]*>/g, '') : ''
    })

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
      if (!q) { searchResults.value = []; return }
      const results = []
      sections.forEach((section) => {
        const plain = section.html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
        const idx = plain.toLowerCase().indexOf(q)
        if (idx !== -1) {
          const start = Math.max(0, idx - 40)
          const end = Math.min(plain.length, idx + 80)
          let snippet = plain.slice(start, end)
          const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
          snippet = snippet.replace(re, '<mark>$1</mark>')
          results.push({
            sectionId: section.id,
            sectionTitle: section.title.replace(/<[^>]*>/g, ''),
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
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              activeSection.value = entry.target.id
            }
          })
        },
        { rootMargin: '-15% 0px -70% 0px', threshold: 0 }
      )
      Object.entries(sectionRefs.value).forEach(([, el]) => {
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

.search-icon { font-size: 0.85rem; opacity: 0.6; flex-shrink: 0; }

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.85rem;
  outline: none;
  min-width: 0;
}

.search-input::placeholder { color: var(--text-secondary); }

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

.search-hit:hover { background: var(--background, #f9fafb); }

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
  padding: 0.42rem 1rem;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 0.81rem;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.toc-item:hover { color: var(--text-primary); background: var(--background, #f9fafb); }

.toc-item.active {
  color: var(--primary-color);
  border-left-color: var(--primary-color);
  background: rgba(59, 130, 246, 0.06);
  font-weight: 600;
}

.toc-icon { font-size: 0.9rem; flex-shrink: 0; width: 1.2rem; text-align: center; }

.toc-label { line-height: 1.3; }

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

.sidebar-link:hover { text-decoration: underline; }

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
  flex-wrap: wrap;
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

.bc-link { color: var(--primary-color); text-decoration: none; }
.bc-link:hover { text-decoration: underline; }
.bc-sep { opacity: 0.5; }
.bc-current { color: var(--text-primary); }

/* Page header */
.doc-page-header { margin-bottom: 2.5rem; }

.doc-page-header h1 {
  font-size: 1.6rem;
  margin: 0 0 0.4rem 0;
  color: var(--text-primary);
}

.doc-page-header p {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin: 0 0 1rem 0;
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
  font-size: 1.2rem;
  margin: 0;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.section-icon { font-size: 1.4rem; }

.anchor-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 1.2rem;
  opacity: 0.4;
  transition: opacity 0.15s;
}

.anchor-link:hover { opacity: 1; color: var(--primary-color); }

/* Section body — styles via :deep since content is v-html */
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

.section-body :deep(li) { margin-bottom: 0.35rem; }

.section-body :deep(a) {
  color: var(--primary-color);
  text-decoration: underline;
}

.section-body :deep(code) {
  background: rgba(255,255,255,0.07);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
  font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  color: var(--text-primary);
}

.section-body :deep(.code-block-wrap) {
  position: relative;
  margin: 0.75rem 0 1rem;
}

.section-body :deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem 3rem 1rem 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'Consolas', 'Courier New', monospace;
  font-size: 0.84rem;
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

.section-body :deep(.tip-box) {
  background: #f0fdf4;
  border: 2px solid #22c55e;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  color: #15803d;
  font-size: 0.9rem;
  line-height: 1.6;
}

.section-body :deep(.info-box ul),
.section-body :deep(.warn-box ul),
.section-body :deep(.tip-box ul) {
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
  grid-template-columns: 170px 1fr;
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

.section-body :deep(.step-body p) { margin: 0; }

/* Keyboard shortcuts table */
.section-body :deep(.shortcuts-table) {
  border: 1px solid var(--border-color);
  border-radius: 0.4rem;
  overflow: hidden;
  margin: 0.75rem 0 1.5rem;
  font-size: 0.875rem;
}

.section-body :deep(.shortcut-row) {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  padding: 0.55rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.section-body :deep(.shortcut-row:last-child) { border-bottom: none; }

.section-body :deep(.header-row) {
  background: var(--surface, #f9fafb);
  font-weight: 700;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.section-body :deep(kbd) {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 0.25rem;
  font-family: monospace;
  font-size: 0.82em;
  background: var(--card-bg, white);
  color: var(--text-primary);
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
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

.doc-card.featured { border-color: var(--primary-color); }

.doc-icon { font-size: 2rem; margin-bottom: 0.75rem; }

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

.doc-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

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

.modal-header h3 { margin: 0; font-size: 1.3rem; }

.btn-close {
  background: none;
  border: none;
  font-size: 1.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
}

.modal-body { padding: 1.5rem; }

.modal-body h4 { font-size: 1rem; color: var(--primary-color); margin: 1.25rem 0 0.5rem; }
.modal-body h4:first-child { margin-top: 0; }

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

.code-block-wrap { position: relative; margin: 0.5rem 0; }

.code-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.75rem 3rem 0.75rem 1rem;
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

.copy-btn:hover { background: rgba(255,255,255,0.2); color: #f8fafc; }

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

.info-box ul { margin: 0.5rem 0 0 1.25rem; }

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

  .doc-sidebar.sidebar-open { left: 0; }

  .sidebar-close { display: block; }

  .sidebar-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .doc-main { padding: 0 1rem 2rem; }

  .doc-topbar { flex-wrap: wrap; }

  .section-body :deep(.tab-item) {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }

  .section-body :deep(.shortcut-row) {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }
}
</style>
