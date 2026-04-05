<template>
  <div class="documentation-page">
    <div class="page-header">
      <h1>📖 Documentation</h1>
      <p>Learn how to use Depl0y and its features</p>
    </div>

    <!-- v1.7.0 Proxmox Management Features -->
    <div class="section-header">
      <h2>🖥️ v1.7.0 — Proxmox VE Management</h2>
      <p>New in v1.7.0: full Proxmox host management, VM/container control, consoles, templates, backups, and HA.</p>
    </div>

    <div class="doc-grid v170-grid">
      <!-- Proxmox VE Management -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'proxmox-hosts' }" @click="toggleCard('proxmox-hosts')">
        <div class="doc-icon">🖥️</div>
        <h2>Proxmox VE Management</h2>
        <p>Add Proxmox hosts, poll their state, and navigate nodes, VMs, and containers from a single interface.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">3 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('proxmox-hosts')" class="btn btn-primary">
            {{ expandedCard === 'proxmox-hosts' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/proxmox" class="btn btn-outline" @click.stop>Open Hosts</router-link>
        </div>
        <div v-if="expandedCard === 'proxmox-hosts'" class="card-detail" @click.stop>
          <h4>Adding a Proxmox Host</h4>
          <p>Go to <router-link to="/proxmox">Proxmox Hosts</router-link> and click <strong>Add Host</strong>. Enter the host address, API token, and an optional display name. Depl0y stores the token securely and uses it for all subsequent API calls.</p>
          <h4>Polling Host State</h4>
          <p>After adding a host, click <strong>Poll</strong> (or the refresh icon) to sync the current state of all nodes, VMs, and LXC containers. Polling is also triggered automatically when you navigate to a host's detail view. The status badges on each host card reflect the last polled state.</p>
          <h4>Navigating the Hierarchy</h4>
          <ol>
            <li>Select a host from the Proxmox Hosts list to view its nodes.</li>
            <li>Click a node to open the Node Detail page — showing VMs, containers, storage, and tasks.</li>
            <li>Click any VM or container to open its detail page with full management controls.</li>
          </ol>
          <div class="info-box">
            <strong>Tip:</strong> The Datacenter view at <router-link to="/datacenter">/datacenter</router-link> gives an aggregated overview across all registered Proxmox hosts.
          </div>
        </div>
      </div>

      <!-- VM Management -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'vm-management' }" @click="toggleCard('vm-management')">
        <div class="doc-icon">⚙️</div>
        <h2>VM Management</h2>
        <p>The VM detail page provides tabbed access to every aspect of a virtual machine's configuration and state.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">4 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('vm-management')" class="btn btn-primary">
            {{ expandedCard === 'vm-management' ? 'Collapse' : 'Learn More' }}
          </button>
        </div>
        <div v-if="expandedCard === 'vm-management'" class="card-detail" @click.stop>
          <p>Navigate to a VM via <strong>Proxmox Hosts → Node → VM</strong>. The detail page is organized into the following tabs:</p>
          <div class="tab-list">
            <div class="tab-item">
              <strong>Overview</strong>
              <span>Live CPU, memory, disk I/O, and network stats. Power controls (start, stop, reboot, shutdown). Current status badge and uptime.</span>
            </div>
            <div class="tab-item">
              <strong>Config</strong>
              <span>View and edit VM configuration options including CPU cores/sockets, memory, boot order, BIOS/UEFI, and machine type.</span>
            </div>
            <div class="tab-item">
              <strong>Disks</strong>
              <span>List attached disk devices, storage pool, size, and format. Resize disks directly from this tab.</span>
            </div>
            <div class="tab-item">
              <strong>Network</strong>
              <span>View and manage network interfaces (bridges, VLANs, MAC addresses). Add or remove NICs without stopping the VM.</span>
            </div>
            <div class="tab-item">
              <strong>Snapshots</strong>
              <span>Create, restore, and delete snapshots. Each snapshot entry shows its name, creation time, and description. Rollback is a single click.</span>
            </div>
            <div class="tab-item">
              <strong>Firewall</strong>
              <span>Manage per-VM firewall rules and IP sets. Enable or disable the VM-level firewall independently of the host firewall.</span>
            </div>
            <div class="tab-item">
              <strong>Console</strong>
              <span>Launch the noVNC graphical console directly in the browser. See the VNC Console section below for details.</span>
            </div>
          </div>
        </div>
      </div>

      <!-- VNC Console -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'vnc-console' }" @click="toggleCard('vnc-console')">
        <div class="doc-icon">🖱️</div>
        <h2>VNC Console</h2>
        <p>Access a full graphical console for any VM directly in your browser via noVNC — no client software required.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">2 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('vnc-console')" class="btn btn-primary">
            {{ expandedCard === 'vnc-console' ? 'Collapse' : 'Learn More' }}
          </button>
        </div>
        <div v-if="expandedCard === 'vnc-console'" class="card-detail" @click.stop>
          <h4>Opening the Console</h4>
          <p>From the VM detail page, click the <strong>Console</strong> tab, then click <strong>Open Console</strong>. The noVNC viewer opens in a full-screen overlay. You can also open it directly from the VM list via the console icon.</p>
          <h4>Keyboard Shortcuts</h4>
          <div class="tab-list">
            <div class="tab-item">
              <strong>Ctrl+Alt+Del</strong>
              <span>Use the <strong>Send Ctrl+Alt+Del</strong> button in the console toolbar — your browser intercepts the real key combination before it reaches the VM.</span>
            </div>
            <div class="tab-item">
              <strong>Fullscreen Mode</strong>
              <span>Click the <strong>Fullscreen</strong> button (or press F11) in the noVNC toolbar to expand the console to your entire screen. Press Escape or click the button again to exit.</span>
            </div>
            <div class="tab-item">
              <strong>Clipboard</strong>
              <span>Use the clipboard icon in the noVNC toolbar to paste text into the VM. This bypasses browser clipboard restrictions.</span>
            </div>
          </div>
          <div class="info-box">
            <strong>Note:</strong> The console requires the VM to be running. If the VM is stopped, start it from the Overview tab first.
          </div>
        </div>
      </div>

      <!-- Node Terminal -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'node-terminal' }" @click="toggleCard('node-terminal')">
        <div class="doc-icon">💻</div>
        <h2>Node Terminal</h2>
        <p>Open a live shell session on any Proxmox node or LXC container using the built-in xterm.js terminal.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">2 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('node-terminal')" class="btn btn-primary">
            {{ expandedCard === 'node-terminal' ? 'Collapse' : 'Learn More' }}
          </button>
        </div>
        <div v-if="expandedCard === 'node-terminal'" class="card-detail" @click.stop>
          <h4>Opening a Node Shell</h4>
          <p>Navigate to <strong>Proxmox Hosts → Node Detail</strong> and click <strong>Open Terminal</strong>. The xterm.js terminal opens in a full-screen layout and connects directly to the Proxmox node shell via the PVE API WebSocket.</p>
          <h4>LXC Container Shell</h4>
          <p>From a container's detail page, click <strong>Open Terminal</strong> to attach to a shell running inside the LXC container. This uses the same xterm.js interface but targets the container's namespace rather than the host.</p>
          <h4>Usage Notes</h4>
          <ul>
            <li>The terminal supports full ANSI color codes and interactive programs (vim, htop, etc.).</li>
            <li>Copy and paste work via the browser's standard clipboard shortcuts (Ctrl+C / Ctrl+V on Windows/Linux, Cmd+C / Cmd+V on macOS).</li>
            <li>The session terminates when you close the tab or navigate away. There is no session persistence.</li>
          </ul>
        </div>
      </div>

      <!-- Creating VMs -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'create-pve-vm' }" @click="toggleCard('create-pve-vm')">
        <div class="doc-icon">➕</div>
        <h2>Creating VMs (PVE)</h2>
        <p>Provision a new Proxmox-native VM using the guided 3-step Create VM form.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">3 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('create-pve-vm')" class="btn btn-primary">
            {{ expandedCard === 'create-pve-vm' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/create-pve-vm" class="btn btn-outline" @click.stop>Create VM</router-link>
        </div>
        <div v-if="expandedCard === 'create-pve-vm'" class="card-detail" @click.stop>
          <p>Go to <router-link to="/create-pve-vm">Create VM (PVE)</router-link> to launch the 3-step wizard.</p>
          <div class="step">
            <strong>Step 1: Location</strong>
            <p>Select the target Proxmox host and node where the VM will be created. A VM ID is auto-generated (or you can specify one). Enter a name for the new VM.</p>
          </div>
          <div class="step">
            <strong>Step 2: Hardware</strong>
            <p>Configure the VM's hardware profile:</p>
            <ul>
              <li><strong>CPU:</strong> Number of cores and sockets.</li>
              <li><strong>Memory:</strong> RAM in MB.</li>
              <li><strong>Disk:</strong> Storage pool, disk size, and format (qcow2, raw).</li>
              <li><strong>OS / ISO:</strong> Select an ISO image from the available storage, or choose a cloud image for fast deployment.</li>
              <li><strong>Network:</strong> Bridge interface and optional VLAN tag.</li>
            </ul>
          </div>
          <div class="step">
            <strong>Step 3: Review</strong>
            <p>Review all settings before submission. Click <strong>Create VM</strong> to send the request to Proxmox. A task tracker shows real-time progress and links to the new VM's detail page once creation completes.</p>
          </div>
        </div>
      </div>

      <!-- Creating LXC Containers -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'create-lxc' }" @click="toggleCard('create-lxc')">
        <div class="doc-icon">📦</div>
        <h2>Creating LXC Containers</h2>
        <p>Deploy lightweight Linux containers on Proxmox using the CreateLXC form.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">3 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('create-lxc')" class="btn btn-primary">
            {{ expandedCard === 'create-lxc' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/create-lxc" class="btn btn-outline" @click.stop>Create LXC</router-link>
        </div>
        <div v-if="expandedCard === 'create-lxc'" class="card-detail" @click.stop>
          <p>Go to <router-link to="/create-lxc">Create LXC</router-link> to open the container creation form. Fill in the following fields:</p>
          <div class="tab-list">
            <div class="tab-item"><strong>Host &amp; Node</strong><span>Select which Proxmox host and node to create the container on.</span></div>
            <div class="tab-item"><strong>CT ID</strong><span>Container ID — auto-generated by default. Must be unique on the selected node.</span></div>
            <div class="tab-item"><strong>Hostname</strong><span>The container's hostname, used for DNS and display purposes.</span></div>
            <div class="tab-item"><strong>Template</strong><span>Choose an LXC template (e.g., Ubuntu 22.04, Debian 12, Alpine). Templates are fetched live from the Proxmox node's template storage. Download new templates from the Storage Browser if the one you need is not listed.</span></div>
            <div class="tab-item"><strong>Root Password</strong><span>Password for the root account inside the container.</span></div>
            <div class="tab-item"><strong>CPU &amp; Memory</strong><span>Number of CPU cores and memory in MB.</span></div>
            <div class="tab-item"><strong>Disk</strong><span>Root filesystem size and storage pool.</span></div>
            <div class="tab-item"><strong>Network</strong><span>Bridge, IP address (DHCP or static), and gateway.</span></div>
            <div class="tab-item"><strong>DNS</strong><span>Optional DNS server and search domain overrides.</span></div>
            <div class="tab-item"><strong>Start on Create</strong><span>Toggle to automatically start the container immediately after creation.</span></div>
          </div>
          <p>Click <strong>Create Container</strong> to submit. Progress is shown in the task tracker.</p>
        </div>
      </div>

      <!-- VM Templates -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'templates' }" @click="toggleCard('templates')">
        <div class="doc-icon">🗂️</div>
        <h2>VM Templates</h2>
        <p>Convert VMs into reusable templates and clone new VMs from them in seconds.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">3 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('templates')" class="btn btn-primary">
            {{ expandedCard === 'templates' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/templates" class="btn btn-outline" @click.stop>View Templates</router-link>
        </div>
        <div v-if="expandedCard === 'templates'" class="card-detail" @click.stop>
          <h4>Converting a VM to a Template</h4>
          <p>From the <router-link to="/templates">Templates</router-link> view or a VM's detail page, click <strong>Convert to Template</strong>. This action is irreversible — the VM is stopped and marked as a template in Proxmox. Templates cannot be started directly; they can only be cloned.</p>
          <div class="info-box">
            <strong>Best practice:</strong> Before converting, ensure the VM is fully configured, updated, and has been generalized (e.g., cloud-init reset or sysprep run) so clones start with a clean state.
          </div>
          <h4>Cloning from a Template</h4>
          <ol>
            <li>Go to <router-link to="/templates">Templates</router-link> to see all templates across registered Proxmox hosts.</li>
            <li>Click <strong>Clone</strong> on the template you want to use.</li>
            <li>Enter a name and target node for the new VM.</li>
            <li>Choose <strong>Full Clone</strong> (independent copy) or <strong>Linked Clone</strong> (shares base disk, faster but depends on template remaining intact).</li>
            <li>Click <strong>Clone VM</strong>. The new VM appears in the node's VM list once the task completes.</li>
          </ol>
        </div>
      </div>

      <!-- Backup Management -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'backup-manager' }" @click="toggleCard('backup-manager')">
        <div class="doc-icon">💾</div>
        <h2>Backup Management</h2>
        <p>View backup schedules, run manual backups, and browse Proxmox Backup Server datastores.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">4 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('backup-manager')" class="btn btn-primary">
            {{ expandedCard === 'backup-manager' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/backup" class="btn btn-outline" @click.stop>Backups</router-link>
        </div>
        <div v-if="expandedCard === 'backup-manager'" class="card-detail" @click.stop>
          <h4>Viewing Backup Schedules</h4>
          <p>Navigate to <strong>Proxmox Hosts → (select host) → Backup</strong> to open the BackupManager. The <strong>Schedules</strong> tab lists all configured vzdump backup jobs with their schedule (cron), included VMs/containers, storage target, and retention settings.</p>
          <h4>Running a Manual Backup</h4>
          <ol>
            <li>In BackupManager, click <strong>Run Now</strong> next to any backup job to trigger it immediately.</li>
            <li>Alternatively, use <strong>Backup Now</strong> from a VM's detail page to create a one-off backup of that specific VM to your chosen storage.</li>
            <li>Monitor progress in the task list — a link appears in the notification area when the task starts.</li>
          </ol>
          <h4>PBS Datastore Browsing</h4>
          <p>If a Proxmox Backup Server (PBS) is configured as a storage target, the <strong>Datastores</strong> tab lists available datastores. Click a datastore to browse its backup snapshots, view their size and creation time, and restore or delete individual backups.</p>
          <div class="info-box">
            <strong>Retention:</strong> Backup retention policies (keep daily/weekly/monthly) are configured per job in the schedule settings. PBS manages deduplication automatically.
          </div>
        </div>
      </div>

      <!-- HA Management -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'ha-management' }" @click="toggleCard('ha-management')">
        <div class="doc-icon">🔄</div>
        <h2>HA Management</h2>
        <p>Configure and monitor Proxmox High Availability resources to keep VMs running through node failures.</p>
        <div class="doc-meta">
          <span class="badge badge-warning">Admin Only</span>
          <span class="read-time">4 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('ha-management')" class="btn btn-primary">
            {{ expandedCard === 'ha-management' ? 'Collapse' : 'Learn More' }}
          </button>
          <router-link to="/ha-management" class="btn btn-outline" @click.stop>HA Management</router-link>
        </div>
        <div v-if="expandedCard === 'ha-management'" class="card-detail" @click.stop>
          <h4>Selecting a Host</h4>
          <p>The <router-link to="/ha-management">HA Management</router-link> page opens with a host selector. Choose the Proxmox cluster you want to manage. Only hosts that are part of a cluster (3+ nodes with quorum) support HA.</p>
          <h4>Viewing HA Status</h4>
          <p>The <strong>Status</strong> panel shows the current HA manager state (active/passive), quorum status, and the state of each HA resource (started, stopped, migrating, error). Color-coded badges indicate health at a glance.</p>
          <h4>Adding HA Resources</h4>
          <ol>
            <li>Click <strong>Add HA Resource</strong>.</li>
            <li>Select the VM or container ID to protect.</li>
            <li>Set the <strong>Max Relocate</strong> and <strong>Max Restart</strong> limits — how many times the HA manager will try to move or restart the resource before marking it as failed.</li>
            <li>Choose a priority group if applicable.</li>
            <li>Click <strong>Add</strong>. The resource appears in the HA resource list immediately.</li>
          </ol>
          <h4>Removing HA Resources</h4>
          <p>Click the <strong>Remove</strong> button next to any HA resource to stop protecting it. The VM or container continues running but will no longer be automatically restarted or migrated on node failure.</p>
          <div class="info-box">
            <strong>Requirement:</strong> HA management requires admin-level permissions in Depl0y and a properly fenced Proxmox cluster with an odd number of nodes (minimum 3) for quorum.
          </div>
        </div>
      </div>

      <!-- Global Search -->
      <div class="doc-card" :class="{ expanded: expandedCard === 'global-search' }" @click="toggleCard('global-search')">
        <div class="doc-icon">🔍</div>
        <h2>Global Search</h2>
        <p>Instantly find VMs, containers, nodes, and hosts from anywhere in the UI using the header search bar.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">v1.7.0</span>
          <span class="read-time">2 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click.stop="toggleCard('global-search')" class="btn btn-primary">
            {{ expandedCard === 'global-search' ? 'Collapse' : 'Learn More' }}
          </button>
        </div>
        <div v-if="expandedCard === 'global-search'" class="card-detail" @click.stop>
          <h4>Opening the Search Bar</h4>
          <p>Press <strong>Ctrl+K</strong> (Windows/Linux) or <strong>Cmd+K</strong> (macOS) from any page to open the global search overlay. You can also click the search icon in the top navigation bar.</p>
          <h4>Result Types</h4>
          <p>Search results are grouped by type and are drawn from all registered Proxmox hosts:</p>
          <div class="tab-list">
            <div class="tab-item"><strong>VMs</strong><span>Matched by name, VM ID, or IP address. Click to jump directly to the VM detail page.</span></div>
            <div class="tab-item"><strong>Containers</strong><span>LXC containers matched by name or CT ID. Click to open the container detail page.</span></div>
            <div class="tab-item"><strong>Nodes</strong><span>Proxmox nodes matched by hostname. Click to open the node detail page.</span></div>
            <div class="tab-item"><strong>Hosts</strong><span>Registered Proxmox host entries matched by display name or address.</span></div>
          </div>
          <h4>Keyboard Navigation</h4>
          <ul>
            <li>Use the <strong>Up/Down arrow keys</strong> to move between results.</li>
            <li>Press <strong>Enter</strong> to navigate to the selected result.</li>
            <li>Press <strong>Escape</strong> to close the search overlay without navigating.</li>
          </ul>
          <div class="info-box">
            <strong>Tip:</strong> Search is performed client-side against the last polled state. If a recently created VM is not appearing, poll the relevant host to refresh the data.
          </div>
        </div>
      </div>
    </div>

    <div class="doc-grid">
      <!-- Installation Guide -->
      <div class="doc-card" @click="viewDoc('install')">
        <div class="doc-icon">📥</div>
        <h2>Installation Guide</h2>
        <p>One-line installer and complete installation instructions for Ubuntu and Debian servers.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">Getting Started</span>
          <span class="read-time">5 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('install')" class="btn btn-primary">
            View Guide
          </button>
        </div>
      </div>

      <!-- Deployment Guide -->
      <div class="doc-card" @click="viewDoc('deployment')">
        <div class="doc-icon">🚀</div>
        <h2>Deployment Guide</h2>
        <p>Learn how to deploy code changes, create releases, and manage updates.</p>
        <div class="doc-meta">
          <span class="badge badge-warning">For Developers</span>
          <span class="read-time">15 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('deployment')" class="btn btn-primary">
            View Guide
          </button>
        </div>
      </div>

      <!-- Cloud Images Quick Start -->
      <div class="doc-card featured" @click="viewDoc('cloud-quickstart')">
        <div class="doc-icon">⚡</div>
        <h2>Cloud Images - Quick Start</h2>
        <p>Get started with ultra-fast 30-second VM deployments using cloud images.</p>
        <div class="doc-meta">
          <span class="badge badge-success">Recommended</span>
          <span class="read-time">3 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('cloud-quickstart')" class="btn btn-primary">
            View Guide
          </button>
          <button @click="showCloudQuickStart = true" class="btn btn-outline">
            Quick Preview
          </button>
        </div>
      </div>

      <!-- Cloud Images Complete Guide -->
      <div class="doc-card" @click="viewDoc('cloud-guide')">
        <div class="doc-icon">☁️</div>
        <h2>Cloud Images - Complete Guide</h2>
        <p>Comprehensive 50+ page guide covering setup, usage, troubleshooting, and technical details.</p>
        <div class="doc-meta">
          <span class="badge badge-info">Advanced</span>
          <span class="read-time">20 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('cloud-guide')" class="btn btn-primary">
            View Guide
          </button>
        </div>
      </div>

      <!-- Main README -->
      <div class="doc-card" @click="viewDoc('readme')">
        <div class="doc-icon">📘</div>
        <h2>Getting Started with Depl0y</h2>
        <p>Installation, configuration, and basic usage of Depl0y.</p>
        <div class="doc-meta">
          <span class="badge badge-primary">Basics</span>
          <span class="read-time">10 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('readme')" class="btn btn-primary">
            View README
          </button>
        </div>
      </div>

      <!-- Proxmox API Tokens -->
      <div class="doc-card" @click="viewDoc('proxmox-api-tokens')">
        <div class="doc-icon">🔑</div>
        <h2>Proxmox API Tokens</h2>
        <p>How to create and configure Proxmox API tokens for Depl0y.</p>
        <div class="doc-meta">
          <span class="badge badge-warning">Setup</span>
          <span class="read-time">5 min read</span>
        </div>
        <div class="doc-actions" @click.stop>
          <button @click="viewDoc('proxmox-api-tokens')" class="btn btn-primary">
            View Guide
          </button>
        </div>
      </div>

      <!-- Cloud Image Setup (Settings) -->
      <div class="doc-card highlight">
        <div class="doc-icon">🚀</div>
        <h2>Cloud Image Setup Status</h2>
        <p>Check if cloud images are configured and run the setup script.</p>
        <div class="doc-meta">
          <span class="badge badge-success">Interactive</span>
        </div>
        <div class="doc-actions">
          <router-link to="/settings" class="btn btn-primary">
            Go to Settings
          </router-link>
        </div>
      </div>

      <!-- API Documentation -->
      <div class="doc-card">
        <div class="doc-icon">🔌</div>
        <h2>API Documentation</h2>
        <p>Explore the RESTful API endpoints for automation and integration.</p>
        <div class="doc-meta">
          <span class="badge badge-info">Technical</span>
        </div>
        <div class="doc-actions">
          <a href="/api/v1/docs" target="_blank" class="btn btn-primary">
            Swagger UI
          </a>
          <a href="/api/v1/redoc" target="_blank" class="btn btn-outline">
            ReDoc
          </a>
        </div>
      </div>
    </div>

    <!-- Quick Start Modal -->
    <div v-if="showCloudQuickStart" class="modal" @click.self="showCloudQuickStart = false">
      <div class="modal-content doc-modal">
        <div class="modal-header">
          <h3>⚡ Cloud Images - Quick Start</h3>
          <button @click="showCloudQuickStart = false" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="quick-start-content">
            <h4>What Are Cloud Images?</h4>
            <p>Cloud images let you deploy VMs in <strong>30 seconds</strong> instead of 20 minutes. No manual OS installation needed!</p>

            <h4>One-Time Setup (Takes 1 Minute)</h4>

            <div class="step">
              <strong>Step 1: Check Status in Web UI</strong>
              <p>Go to <router-link to="/settings">Settings</router-link> → Look for "Cloud Image Setup" section</p>
              <ul>
                <li>✅ Green box: Already configured! Skip to "Using Cloud Images" below.</li>
                <li>⚠️ Yellow box: Setup needed. Continue to Step 2.</li>
              </ul>
            </div>

            <div class="step">
              <strong>Step 2: Run Setup Script</strong>
              <p>SSH to your Depl0y server and run:</p>
              <div class="code-block">
                <code>sudo /tmp/enable_cloud_images.sh</code>
              </div>
            </div>

            <div class="step">
              <strong>Step 3: Enter Password</strong>
              <p>When prompted, enter your <strong>Proxmox root password</strong></p>
            </div>

            <div class="step">
              <strong>Step 4: Done!</strong>
              <p>You'll see: <span class="success-text">✅ SUCCESS! Cloud images are now fully configured!</span></p>
            </div>

            <h4>Using Cloud Images</h4>
            <ol>
              <li>Go to <router-link to="/vms/create">Create VM</router-link></li>
              <li>Select <strong>"Cloud Image (Fast)"</strong> installation method</li>
              <li>Choose a cloud image (Ubuntu 24.04, Debian 12, etc.)</li>
              <li>Configure CPU, RAM, disk size</li>
              <li>Enter your credentials</li>
              <li>Click "Create VM"</li>
            </ol>

            <div class="info-box">
              <strong>Deployment Times:</strong>
              <ul>
                <li><strong>First time:</strong> 5-10 minutes (creates template)</li>
                <li><strong>Every time after:</strong> 30 seconds ⚡</li>
              </ul>
            </div>

            <div class="action-buttons">
              <router-link to="/settings" class="btn btn-primary" @click="showCloudQuickStart = false">
                Go to Settings
              </router-link>
              <router-link to="/vms/create" class="btn btn-success" @click="showCloudQuickStart = false">
                Create VM
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Documentation Viewer Modal -->
    <div v-if="currentDoc" class="modal" @click.self="currentDoc = null">
      <div class="modal-content doc-modal doc-viewer">
        <div class="modal-header">
          <h3>{{ docTitle }}</h3>
          <button @click="currentDoc = null" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingDoc" class="loading">
            <p>Loading documentation...</p>
          </div>
          <div v-else-if="docError" class="error">
            <p>{{ docError }}</p>
          </div>
          <div v-else class="markdown-content" v-html="renderedMarkdown"></div>
        </div>
      </div>
    </div>

    <!-- Help Section -->
    <div class="help-section">
      <h2>📞 Need Help?</h2>
      <div class="help-grid">
        <div class="help-card">
          <h3>💬 Report an Issue</h3>
          <p>Found a bug or have a feature request?</p>
          <router-link to="/bug-report" class="btn btn-outline">Report Bug</router-link>
        </div>
        <div class="help-card">
          <h3>🔧 Check Logs</h3>
          <p>View backend logs for troubleshooting</p>
          <router-link to="/settings" class="btn btn-outline">View Logs</router-link>
        </div>
        <div class="help-card">
          <h3>⚙️ System Settings</h3>
          <p>Configure Depl0y and check cloud image setup</p>
          <router-link to="/settings" class="btn btn-outline">Settings</router-link>
        </div>
      </div>
    </div>

    <!-- PDF Download Section -->
    <div class="pdf-download-section">
      <div class="pdf-card">
        <div class="pdf-icon">📄</div>
        <div class="pdf-content">
          <h3>Download Complete Documentation</h3>
          <p>Get all documentation in a single PDF file for offline reading</p>
          <p class="text-sm text-muted">Includes: Installation, Deployment, Cloud Images, and all guides</p>
        </div>
        <div class="pdf-actions">
          <button @click="downloadPDF" class="btn btn-primary btn-lg" :disabled="downloadingPDF">
            <span v-if="downloadingPDF">📥 Generating PDF...</span>
            <span v-else>📥 Download PDF</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'Documentation',
  setup() {
    const toast = useToast()
    const showCloudQuickStart = ref(false)
    const currentDoc = ref(null)
    const docContent = ref('')
    const docTitle = ref('')
    const loadingDoc = ref(false)
    const docError = ref(null)
    const downloadingPDF = ref(false)
    const expandedCard = ref(null)

    const toggleCard = (cardId) => {
      expandedCard.value = expandedCard.value === cardId ? null : cardId
    }

    // Configure marked options
    marked.setOptions({
      breaks: true,
      gfm: true
    })

    const renderedMarkdown = computed(() => {
      if (!docContent.value) return ''
      return marked.parse(docContent.value)
    })

    const viewDoc = async (docId) => {
      currentDoc.value = docId
      loadingDoc.value = true
      docError.value = null
      docContent.value = ''

      try {
        const response = await api.docs.get(docId, 'json')
        docContent.value = response.data.content
        docTitle.value = response.data.title
      } catch (error) {
        console.error('Failed to load documentation:', error)
        docError.value = 'Failed to load documentation. Please try again.'
        toast.error('Failed to load documentation')
      } finally {
        loadingDoc.value = false
      }
    }

    const downloadPDF = async () => {
      downloadingPDF.value = true

      try {
        const response = await api.docs.downloadPDF()

        // Create blob from response
        const blob = new Blob([response.data], { type: 'application/pdf' })

        // Create download link
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url

        // Get filename from response headers or use default
        const contentDisposition = response.headers['content-disposition']
        let filename = 'Depl0y_Documentation.pdf'
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename="?(.+)"?/)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }

        link.setAttribute('download', filename)
        document.body.appendChild(link)
        link.click()

        // Cleanup
        link.remove()
        window.URL.revokeObjectURL(url)

        toast.success('Documentation PDF downloaded successfully!')
      } catch (error) {
        console.error('Failed to download PDF:', error)
        toast.error('Failed to download PDF. Please try again.')
      } finally {
        downloadingPDF.value = false
      }
    }

    return {
      showCloudQuickStart,
      currentDoc,
      docContent,
      docTitle,
      loadingDoc,
      docError,
      downloadingPDF,
      expandedCard,
      renderedMarkdown,
      viewDoc,
      downloadPDF,
      toggleCard
    }
  }
}
</script>

<style scoped>
.documentation-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 3rem;
}

.page-header h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.page-header p {
  font-size: 1.125rem;
  color: var(--text-secondary);
}

.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 2rem;
  margin-bottom: 3rem;
}

.v170-grid {
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
}

.doc-card {
  background: white;
  border-radius: 0.75rem;
  padding: 2rem;
  box-shadow: var(--shadow-md);
  transition: transform 0.2s, box-shadow 0.2s;
  border: 2px solid transparent;
  cursor: pointer;
}

.doc-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.doc-card.featured {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(147, 51, 234, 0.05));
}

.doc-card.highlight {
  border-color: #10b981;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(5, 150, 105, 0.05));
  cursor: default;
}

.doc-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.doc-card h2 {
  font-size: 1.5rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.doc-card p {
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-success {
  background: #d1fae5;
  color: #065f46;
}

.badge-info {
  background: #dbeafe;
  color: #1e40af;
}

.badge-primary {
  background: #e0e7ff;
  color: #4338ca;
}

.badge-warning {
  background: #fef3c7;
  color: #92400e;
}

.read-time {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.doc-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.help-section {
  margin-top: 4rem;
  padding: 2rem;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(147, 51, 234, 0.05));
  border-radius: 0.75rem;
}

.help-section h2 {
  text-align: center;
  margin-bottom: 2rem;
  color: var(--text-primary);
}

.help-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
}

.help-card {
  background: white;
  padding: 1.5rem;
  border-radius: 0.5rem;
  text-align: center;
}

.help-card h3 {
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.help-card p {
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

/* Modal Styles */
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
  padding: 1rem;
}

.modal-content.doc-modal {
  background: white;
  border-radius: 0.75rem;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content.doc-viewer {
  max-width: 1200px;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(147, 51, 234, 0.05));
}

.modal-header h3 {
  margin: 0;
  font-size: 1.75rem;
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
  padding: 2rem;
}

.loading,
.error {
  text-align: center;
  padding: 2rem;
}

.error {
  color: #dc2626;
}

.markdown-content {
  line-height: 1.8;
  color: var(--text-primary);
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin-top: 2rem;
  margin-bottom: 1rem;
  color: var(--primary-color);
}

.markdown-content :deep(h1):first-child,
.markdown-content :deep(h2):first-child {
  margin-top: 0;
}

.markdown-content :deep(p) {
  margin-bottom: 1rem;
}

.markdown-content :deep(code) {
  background: #1e293b;
  color: #10b981;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.9rem;
  font-family: monospace;
}

.markdown-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin: 1rem 0;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.5rem;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--primary-color);
  padding-left: 1rem;
  margin: 1rem 0;
  color: var(--text-secondary);
  font-style: italic;
}

.markdown-content :deep(a) {
  color: var(--primary-color);
  text-decoration: underline;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 2px solid var(--border-color);
  margin: 2rem 0;
}

.quick-start-content h4 {
  margin-top: 2rem;
  margin-bottom: 1rem;
  color: var(--primary-color);
  font-size: 1.25rem;
}

.quick-start-content h4:first-child {
  margin-top: 0;
}

.quick-start-content p {
  margin-bottom: 1rem;
  line-height: 1.6;
}

.quick-start-content ul,
.quick-start-content ol {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.quick-start-content li {
  margin-bottom: 0.5rem;
}

.step {
  background: #f9fafb;
  padding: 1.5rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
  border-left: 4px solid var(--primary-color);
}

.step strong {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--primary-color);
}

.code-block {
  background: #1e293b;
  padding: 1rem;
  border-radius: 0.375rem;
  margin: 1rem 0;
}

.code-block code {
  color: #10b981;
  font-family: monospace;
  font-size: 0.95rem;
}

.success-text {
  color: #059669;
  font-weight: 600;
}

.info-box {
  background: #dbeafe;
  border: 2px solid #3b82f6;
  border-radius: 0.5rem;
  padding: 1.5rem;
  margin: 1.5rem 0;
}

.info-box strong {
  color: #1e40af;
  display: block;
  margin-bottom: 0.5rem;
}

.info-box ul {
  margin: 0;
  padding-left: 1.5rem;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .doc-grid {
    grid-template-columns: 1fr;
  }

  .help-grid {
    grid-template-columns: 1fr;
  }

  .page-header h1 {
    font-size: 2rem;
  }

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons .btn {
    width: 100%;
  }

  .pdf-card {
    flex-direction: column;
  }

  .pdf-content {
    text-align: center;
  }

  .pdf-actions {
    width: 100%;
  }

  .pdf-actions .btn {
    width: 100%;
  }
}

/* PDF Download Section */
.pdf-download-section {
  margin-top: 3rem;
  padding: 2rem;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.05), rgba(220, 38, 38, 0.05));
  border-radius: 0.75rem;
  border: 2px solid #ef4444;
}

.pdf-card {
  display: flex;
  align-items: center;
  gap: 2rem;
  background: white;
  padding: 2rem;
  border-radius: 0.75rem;
  box-shadow: var(--shadow-md);
}

.pdf-icon {
  font-size: 4rem;
  filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.1));
}

.pdf-content {
  flex: 1;
}

.pdf-content h3 {
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.pdf-content p {
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.pdf-actions {
  flex-shrink: 0;
}

.btn-lg {
  padding: 0.875rem 2rem;
  font-size: 1.125rem;
  font-weight: 600;
}

.text-sm {
  font-size: 0.875rem;
}

.text-muted {
  color: var(--text-secondary);
}

/* v1.7.0 Section Header */
.section-header {
  margin: 3rem 0 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid var(--primary-color);
}

.section-header h2 {
  font-size: 1.75rem;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.section-header p {
  font-size: 1rem;
  color: var(--text-secondary);
}

/* Expandable card details */
.doc-card.expanded {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.04), rgba(147, 51, 234, 0.04));
}

.card-detail {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
  cursor: default;
}

.card-detail h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--primary-color);
  margin: 1.25rem 0 0.5rem;
}

.card-detail h4:first-child {
  margin-top: 0;
}

.card-detail p {
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.75rem;
}

.card-detail ol,
.card-detail ul {
  margin-left: 1.5rem;
  margin-bottom: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.card-detail li {
  margin-bottom: 0.4rem;
}

/* Tab-style list for VM tabs documentation */
.tab-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0.75rem 0 1rem;
}

.tab-item {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border-radius: 0.375rem;
  border-left: 3px solid var(--primary-color);
  align-items: start;
}

.tab-item strong {
  color: var(--text-primary);
  font-size: 0.9rem;
  padding-top: 0.05rem;
}

.tab-item span {
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .v170-grid {
    grid-template-columns: 1fr;
  }

  .tab-item {
    grid-template-columns: 1fr;
    gap: 0.25rem;
  }

  .section-header h2 {
    font-size: 1.4rem;
  }
}
</style>
