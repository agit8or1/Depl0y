import{l as q,c,s as p,f as t,e as A,I as Q,M as j,F as D,j as N,t as y,i as B,n as _,x as v,w as k,g as i,G as f,D as z,H as X,Q as K}from"./vendor-vue-D1x5-_kh.js";import{_ as W,b as Z}from"./index-iWrHHkQw.js";import{u as J}from"./vendor-toast-CrWOxkdI.js";import"./vendor-axios-BBTKOM0z.js";function l(d,e=""){const m="cb-"+Math.random().toString(36).slice(2,8);return`<div class="code-block-wrap"><pre class="code-block" id="${m}">${d}</pre><button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('${m}').innerText).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',1500)})">Copy</button></div>`}function x(d){return`<div class="info-box">${d}</div>`}function R(d){return`<div class="warn-box">${d}</div>`}function Y(d){return`<div class="tip-box">${d}</div>`}function n(d,e,m){return`<div class="doc-step"><span class="step-num">${d}</span><div class="step-body"><strong>${e}</strong>${m}</div></div>`}function a(d,e){return`<div class="tab-item"><strong>${d}</strong><span>${e}</span></div>`}const ee=[{id:"getting-started",icon:"&#9654;",title:"Getting Started",html:`
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
      ${l("curl -fsSL http://deploy.agit8or.net/downloads/install.sh | sudo bash")}
      <p>The installer:</p>
      <ol>
        <li>Installs Python 3, Node.js, nginx, and system dependencies</li>
        <li>Creates <code>/opt/depl0y</code> (app) and <code>/var/lib/depl0y</code> (data)</li>
        <li>Builds the frontend and sets up nginx to serve it on port 80</li>
        <li>Creates a <code>depl0y-backend</code> systemd service that starts on boot</li>
      </ol>

      <h3>First Login</h3>
      ${n(1,"Open your browser","<p>Navigate to <code>http://&lt;server-ip&gt;</code></p>")}
      ${n(2,"Log in","<p>Default credentials: <strong>admin / admin</strong> — change the password immediately after first login.</p>")}
      ${n(3,"Add a Proxmox Datacenter",'<p>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Datacenter</strong>. You will need a Proxmox API token (see <a href="#proxmox-hosts">Proxmox Hosts Setup</a>).</p>')}
      ${n(4,"Poll the host","<p>Click <strong>Poll</strong> on the new host card to sync nodes, VMs, and containers.</p>")}

      ${x("<strong>After login:</strong> Go to <strong>Settings</strong> to configure SMTP notifications, set up cloud images, and enable 2FA.")}

      <h3>Service Management</h3>
      ${l(`# Check status
sudo systemctl status depl0y-backend

# Restart
sudo systemctl restart depl0y-backend

# View live logs
sudo journalctl -u depl0y-backend -f`)}

      <h3>Updating</h3>
      ${l("cd /opt/depl0y && git pull origin main && sudo bash deploy.sh")}
      <p>Or use <strong>Settings → System Updates</strong> to check and install updates from the UI.</p>
    `},{id:"vm-management",icon:"&#9881;&#65039;",title:"VM Management",html:`
      <p>Depl0y offers two paths to create virtual machines: the native PVE VM wizard and the fast Cloud Image deploy path.</p>

      <h3>Method 1: Create VM (PVE Wizard)</h3>
      <p>Go to <strong>Create VM (PVE)</strong> for a guided form that creates a Proxmox-native VM:</p>
      <div class="tab-list">
        ${a("Step 1 — Location","Select target host and node. VM ID is auto-generated (or set your own). Enter a VM name.")}
        ${a("Step 2 — Hardware","CPU cores/sockets, RAM (MB), disk size and storage pool, network bridge and VLAN, ISO image, BIOS/UEFI, and machine type.")}
        ${a("Step 3 — Review","Confirm all settings. Click Create VM to submit. A live task tracker shows Proxmox task progress.")}
      </div>

      <h3>Method 2: Cloud Image Deploy (Fast)</h3>
      <p>Cloud images clone a pre-configured template, inject cloud-init, and boot in about 30 seconds.</p>
      ${n(1,"Run one-time setup",`<p>SSH to your Depl0y host and run:</p>${l("sudo /tmp/enable_cloud_images.sh")}`)}
      ${n(2,"Go to Deploy","<p>Navigate to <strong>Deploy VM</strong> and select <strong>Cloud Image</strong>.</p>")}
      ${n(3,"Configure","<p>Choose image (Ubuntu 24.04, Debian 12, etc.), set CPU/RAM/disk, enter credentials.</p>")}
      ${n(4,"Deploy","<p>Click Create. The VM is cloned and started within ~30 seconds on subsequent runs.</p>")}

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

      ${x("<strong>QEMU Guest Agent:</strong> Install the guest agent inside each VM for accurate memory stats and IP detection: <code>apt install qemu-guest-agent &amp;&amp; systemctl enable --now qemu-guest-agent</code>")}

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
    `},{id:"containers",icon:"&#128230;",title:"Containers (LXC)",html:`
      <p>LXC containers are lightweight OS-level virtualization — faster to create than full VMs and share the host kernel. Depl0y provides full lifecycle management for LXC containers.</p>

      <h3>Creating an LXC Container</h3>
      <p>Go to <strong>Create LXC</strong> and fill in:</p>
      <div class="tab-list">
        ${a("Host &amp; Node","Which Proxmox host and node to create the container on.")}
        ${a("CT ID","Container ID. Auto-generated by default; must be unique on the selected node.")}
        ${a("Hostname","The container's hostname.")}
        ${a("Template","LXC template image (Ubuntu 22.04, Debian 12, Alpine, etc.).")}
        ${a("Root Password","Password for the root account inside the container.")}
        ${a("CPU &amp; Memory","CPU core limit and memory allocation in MB.")}
        ${a("Disk","Root filesystem size and storage pool.")}
        ${a("Network","Bridge, IP assignment (DHCP or static CIDR), and default gateway.")}
        ${a("DNS","Optional DNS server and search domain overrides.")}
        ${a("Start on Create","Automatically start the container immediately after creation.")}
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

      ${x("<strong>Privileged vs Unprivileged:</strong> Depl0y creates unprivileged containers by default (UID mapping enabled, more secure). Set <code>unprivileged: false</code> only if you need root device access inside the container.")}

      <h3>Downloading LXC Templates</h3>
      <p>Go to <strong>Proxmox Hosts → Node Detail → Storage Browser</strong> and navigate to your template storage (usually <code>local</code>). Click <strong>Download Template</strong> to fetch templates from the official Proxmox mirror.</p>
    `},{id:"networking",icon:"&#127760;",title:"Networking",html:`
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

      ${R("<strong>Caution:</strong> Applying network changes immediately takes effect on the Proxmox host. An incorrect network config can cut your access to the node. Always verify settings before applying, and have console access (iDRAC/iLO) as a fallback.")}

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
        ${a("VLAN-aware bridge","The bridge itself is VLAN-aware. Assign VLAN tag per VM NIC. Most flexible — single bridge handles all VLANs.")}
        ${a("VLAN interface","Create a separate bridge per VLAN (<code>vmbr0.10</code>). Simpler but requires one bridge per VLAN.")}
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
      ${l(`# Click "Apply SDN" in the UI, or via the API:
curl -X POST /api/v1/sdn/{host_id}/apply \\
  -H "Authorization: Bearer YOUR_TOKEN"`)}

      <h3>Firewall</h3>
      <p>Proxmox has a stateful firewall at three levels:</p>
      <ul>
        <li><strong>Datacenter (cluster) level</strong> — rules applied to all nodes. Managed via <strong>PVE Firewall → Cluster Rules</strong>.</li>
        <li><strong>Node level</strong> — rules for the Proxmox host OS itself.</li>
        <li><strong>VM/CT level</strong> — per-VM rules. Managed via the VM Detail Firewall tab.</li>
      </ul>
      <p>IPSets group multiple IPs for use in rules. Aliases give friendly names to IPs or CIDR ranges. Both are managed under <strong>PVE Firewall → IPSets / Aliases</strong>.</p>
    `},{id:"backup-recovery",icon:"&#128190;",title:"Backup &amp; Recovery",html:`
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

      ${x("<strong>PBS deduplication:</strong> PBS deduplicates data across all backups automatically. Two VMs sharing the same OS blocks store those blocks only once, making daily backups of many VMs extremely space-efficient.")}

      <h3>Restore Procedure</h3>
      ${n(1,"Go to Backup Manager","<p>Navigate via Proxmox Hosts → (host) → Backup Manager → Datastores tab.</p>")}
      ${n(2,"Select the snapshot","<p>Find the backup by VM name and date. Click <strong>Restore</strong>.</p>")}
      ${n(3,"Configure restore options","<p>Choose target node, storage pool, and VM ID (restore to original or a new ID).</p>")}
      ${n(4,"Confirm","<p>Proxmox creates a task. Monitor progress in the Task list.</p>")}

      <h3>Backup Schedules — Cron Format</h3>
      ${l(`# Daily at 02:00
0 2 * * *

# Every Sunday at 01:30
30 1 * * 0

# Every 6 hours
0 */6 * * *`)}
    `},{id:"high-availability",icon:"&#128736;&#65039;",title:"High Availability",html:`
      <p>Proxmox HA allows VMs and containers to automatically restart on another node in the cluster if the current node fails. Depl0y provides a full management interface for HA resources and groups.</p>

      <h3>Prerequisites</h3>
      <ul>
        <li>Proxmox cluster with at least <strong>3 nodes</strong> (for quorum)</li>
        <li>Shared storage accessible from all nodes (Ceph, NFS, iSCSI, or PBS)</li>
        <li>Corosync cluster network configured between nodes</li>
        <li>All VMs/CTs you want to protect must reside on shared storage</li>
      </ul>

      ${R('<strong>Two-node clusters:</strong> A two-node cluster loses quorum if one node goes down, preventing HA from automatically restarting VMs. Use a third "witness" node or external corosync quorum device (QDevice) to solve this.')}

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
      ${l(`POST /api/v1/pve-node/{host_id}/cluster/ha/resources
Content-Type: application/json

{
  "sid": "vm:100",
  "group": "my-ha-group",
  "max_restart": 3,
  "state": "started"
}`)}

      <h3>Node Evacuation</h3>
      <p>Before taking a node offline for maintenance, use <strong>Cluster Operations → Evacuate Node</strong> to live-migrate all running VMs to other nodes in the cluster. The API endpoint is:</p>
      ${l("POST /api/v1/cluster/{host_id}/nodes/{node}/evacuate")}

      <h3>HA Status</h3>
      <p>Navigate to <strong>HA Management → Status</strong> to see:</p>
      <ul>
        <li>Current quorum status and voter counts</li>
        <li>CRM (Cluster Resource Manager) and LRM (Local Resource Manager) status per node</li>
        <li>Status of each HA resource (started, stopped, error)</li>
      </ul>

      ${x("<strong>Monitoring:</strong> Configure an alert rule in <strong>Alerts</strong> to notify you when a VM starts on an unexpected node or when HA triggers a restart.")}
    `},{id:"api-access",icon:"&#128273;",title:"API Access",html:`
      <p>Depl0y exposes a full REST API that you can use for automation, CI/CD pipelines, and integrations with other tools. The API is documented interactively at <a href="/docs" target="_blank">Swagger UI</a> or explore it in the <router-link to="/api-explorer">API Explorer</router-link>.</p>

      <h3>Authentication Methods</h3>
      <div class="tab-list">
        ${a("JWT Bearer Token","Obtained via POST /api/v1/auth/login. Access token valid for 30 minutes. Refresh using /api/v1/auth/refresh. Used by the web UI automatically.")}
        ${a("API Key","Long-lived token generated in your Profile. Prefixed with <code>dpl0y_</code>. Pass as <code>Authorization: Bearer dpl0y_xxxx</code>. Revoke from Profile at any time.")}
      </div>

      <h3>Generating an API Key</h3>
      ${n(1,"Open Profile","<p>Click your username (top-right) → Profile → API Keys tab.</p>")}
      ${n(2,"Create key",'<p>Click <strong>New API Key</strong>, enter a descriptive name (e.g. "Terraform automation"), and click Create.</p>')}
      ${n(3,"Copy the key","<p>The key is shown only once. Copy it immediately and store it securely (password manager).</p>")}

      <h3>Using the API</h3>
      <p>Start a VM:</p>
      ${l(`curl -X POST https://depl0y.example.com/api/v1/vms/123/start \\
  -H "Authorization: Bearer dpl0y_your_key_here"`)}
      <p>List Proxmox hosts:</p>
      ${l(`curl https://depl0y.example.com/api/v1/proxmox/ \\
  -H "Authorization: Bearer dpl0y_your_key_here"`)}
      <p>Create a snapshot:</p>
      ${l(`curl -X POST https://depl0y.example.com/api/v1/pve-vm/1/pve/100/snapshots \\
  -H "Authorization: Bearer dpl0y_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"snapname": "pre-upgrade", "description": "Before package upgrade"}'`)}

      <h3>Rate Limits</h3>
      <p>The API enforces rate limits to protect the backend:</p>
      <ul>
        <li><strong>General endpoints:</strong> 100 requests/minute per IP</li>
        <li><strong>Login endpoint:</strong> 5 requests/minute per IP (brute-force protection)</li>
      </ul>
      <p>Adjust the limit in <code>/etc/depl0y/config.env</code> by setting <code>RATE_LIMIT_PER_MINUTE</code>. Restart the service after changes.</p>

      ${x('<strong>Hint:</strong> Use the <a href="/api-explorer">API Explorer</a> in Depl0y to test any endpoint with your current session token — no setup needed.')}

      <h3>OpenAPI Schema</h3>
      <p>Machine-readable OpenAPI 3.0 schema is available at:</p>
      <ul>
        <li><a href="/openapi.json" target="_blank"><code>/openapi.json</code></a> — raw JSON schema</li>
        <li><a href="/docs" target="_blank"><code>/docs</code></a> — Swagger UI</li>
        <li><a href="/redoc" target="_blank"><code>/redoc</code></a> — ReDoc</li>
      </ul>
    `},{id:"user-management",icon:"&#128100;",title:"User Management",html:`
      <p>Depl0y has its own user database, independent of Proxmox users. Three roles control what each user can do.</p>

      <h3>Roles</h3>
      <div class="tab-list">
        ${a("Admin","Full access. Can manage users, system settings, API tokens, diagnostics, security rules, and all Proxmox operations.")}
        ${a("Operator","Can create, modify, start, stop, and delete VMs and containers. Cannot manage users or system settings.")}
        ${a("Viewer","Read-only access. Can view VMs, containers, and stats but cannot make changes.")}
      </div>

      <h3>Creating a User</h3>
      <p>Go to <strong>Users</strong> (admin only) and click <strong>Add User</strong>. Set a username, email, temporary password, and role. The user will be prompted to change their password on first login.</p>

      <h3>Two-Factor Authentication (TOTP)</h3>
      <p>Users can enable TOTP 2FA from their <strong>Profile</strong> page:</p>
      ${n(1,"Go to Profile","<p>Click your username in the top-right corner.</p>")}
      ${n(2,"Enable TOTP","<p>Click <strong>Enable Two-Factor Auth</strong>. A QR code is shown.</p>")}
      ${n(3,"Scan","<p>Use Google Authenticator, Authy, or any TOTP app. Scan the QR code.</p>")}
      ${n(4,"Verify","<p>Enter the 6-digit code to confirm setup. Login now requires both password and TOTP code.</p>")}

      <h3>API Keys</h3>
      <p>Users can generate API keys for programmatic access from their Profile page. Keys are prefixed with <code>dpl0y_</code> and grant the same permissions as the user's role. Keys can be revoked at any time.</p>

      ${x("<strong>Admin tip:</strong> Use the <strong>Operator</strong> role for day-to-day users; reserve <strong>Admin</strong> for designated administrators only. Enable TOTP 2FA on all admin accounts.")}
    `},{id:"keyboard-shortcuts",icon:"&#9000;",title:"Keyboard Shortcuts",html:`
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

      ${Y("<strong>Tip:</strong> Press <kbd>?</kbd> at any time while using Depl0y to show the in-app keyboard shortcut reference panel.")}
    `},{id:"proxmox-hosts",icon:"&#127970;",title:"Proxmox Hosts Setup",html:`
      <p>Before managing VMs, you must register at least one Proxmox host. Depl0y communicates with Proxmox exclusively via its REST API using an API token — no root SSH required.</p>

      <h3>Creating a Proxmox API Token</h3>
      ${n(1,"Log into Proxmox Web UI","<p>Navigate to <code>https://&lt;proxmox-ip&gt;:8006</code> and log in as root.</p>")}
      ${n(2,"Create an API token","<p>Go to <strong>Datacenter → Permissions → API Tokens → Add</strong>. Set:</p><ul><li><strong>User:</strong> root@pam (or a dedicated user)</li><li><strong>Token ID:</strong> e.g. <code>depl0y</code></li><li><strong>Privilege Separation:</strong> Leave unchecked for full access</li></ul>")}
      ${n(3,"Copy the token secret","<p>The secret is shown only once. Copy both the token ID and secret.</p>")}

      <h3>Token Format</h3>
      ${l("PVEAPIToken=root@pam!depl0y=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")}

      <h3>Adding the Host in Depl0y</h3>
      <ol>
        <li>Go to <strong>Proxmox Hosts</strong> and click <strong>Add Host</strong>.</li>
        <li>Enter the <strong>Host Address</strong> (e.g. <code>pve.example.com:8006</code> or an IP).</li>
        <li>Paste the full <strong>API Token</strong> string.</li>
        <li>Give it a friendly <strong>Display Name</strong>.</li>
        <li>Click <strong>Save</strong>. Depl0y immediately tests the connection.</li>
      </ol>

      ${R("<strong>Security:</strong> Depl0y stores API tokens encrypted at rest using Fernet symmetric encryption. Never share your <code>config.env</code> or database file.")}

      <h3>Multiple Hosts &amp; Federation</h3>
      <p>Depl0y supports any number of registered hosts. Each host is queried independently. The Federated Dashboard aggregates stats across all active hosts. You can mark a host as inactive to exclude it from live queries without deleting its records.</p>
    `},{id:"security",icon:"&#128274;",title:"Security Best Practices",html:`
      <p>Depl0y stores privileged credentials and provides powerful management capabilities. Follow these recommendations to keep your deployment secure.</p>

      <h3>Network Security</h3>
      <ul>
        <li><strong>Do not expose port 8000 to the internet.</strong> Run Depl0y behind a reverse proxy (nginx, Caddy, Traefik) with TLS termination.</li>
        <li>Use firewall rules to restrict Depl0y to your management VLAN only.</li>
        <li>Enable IP allowlist in <strong>Settings → Security</strong> to whitelist trusted management IPs.</li>
        <li>Use GeoIP blocking to restrict access by country if Depl0y must be internet-reachable.</li>
      </ul>

      <h3>Reverse Proxy with TLS (nginx)</h3>
      ${l(`server {
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
    `},{id:"troubleshooting",icon:"&#128295;",title:"Troubleshooting",html:`
      <p>Most issues fall into a few common categories. Use this section to diagnose and fix them.</p>

      <h3>Proxmox Host Shows "Inactive" or "Connection Failed"</h3>
      <ol>
        <li>Verify the host address includes the port: <code>pve.example.com:8006</code>.</li>
        <li>Confirm the API token format: <code>PVEAPIToken=root@pam!tokenid=secret</code>.</li>
        <li>Test connectivity from the Depl0y server: ${l("curl -k https://&lt;proxmox-ip&gt;:8006/api2/json/version")}</li>
        <li>Click <strong>Test Connection</strong> on the host card to see the exact error.</li>
      </ol>

      <h3>VMs Not Appearing After Poll</h3>
      <ul>
        <li>Click <strong>Poll</strong> on the host card and wait for it to finish.</li>
        <li>Verify the token has at least <code>PVEAuditor</code> role on the target nodes.</li>
        <li>Check backend logs: ${l("sudo journalctl -u depl0y-backend -f")}</li>
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
      ${l("sudo journalctl -u depl0y-backend -n 100 --no-pager")}

      <h3>Database Issues</h3>
      <p>Use <strong>Support → Diagnostics → Database Integrity</strong> to run <code>PRAGMA integrity_check</code>. If corruption is found:</p>
      ${l(`sudo systemctl stop depl0y
sqlite3 /var/lib/depl0y/db/depl0y.db ".recover" | sqlite3 /var/lib/depl0y/db/depl0y_recovered.db
sudo mv /var/lib/depl0y/db/depl0y.db /var/lib/depl0y/db/depl0y.db.bak
sudo mv /var/lib/depl0y/db/depl0y_recovered.db /var/lib/depl0y/db/depl0y.db
sudo systemctl start depl0y`)}

      <h3>Getting Help</h3>
      <ol>
        <li>Go to <router-link to="/support">Support</router-link> and download a Diagnostic Bundle.</li>
        <li>Open a <a href="https://github.com/agit8or1/Depl0y/issues/new?template=bug_report.md" target="_blank">GitHub Issue</a> and attach the diagnostic JSON.</li>
      </ol>
    `}],te={name:"Documentation",setup(){const d=J(),e=f(null),m=f({}),o=f(""),I=f(!1),L=f(!1),u=f(""),s=f([]),b=f(!1),M=ee,$=z(()=>{const r=M.find(g=>g.id===o.value);return r?r.title.replace(/<[^>]*>/g,""):""});let V=null;const H=r=>{I.value=!1;const g=m.value[r];g&&g.scrollIntoView({behavior:"smooth",block:"start"})},F=()=>{const r=u.value.trim().toLowerCase();if(!r){s.value=[];return}const g=[];M.forEach(P=>{const h=P.html.replace(/<[^>]*>/g," ").replace(/\s+/g," "),w=h.toLowerCase().indexOf(r);if(w!==-1){const C=Math.max(0,w-40),S=Math.min(h.length,w+80);let T=h.slice(C,S);const G=new RegExp(`(${r.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")})`,"gi");T=T.replace(G,"<mark>$1</mark>"),g.push({sectionId:P.id,sectionTitle:P.title.replace(/<[^>]*>/g,""),snippet:(C>0?"...":"")+T+(S<h.length?"...":""),index:w})}}),s.value=g},O=r=>{u.value="",s.value=[],H(r.sectionId)},U=r=>{navigator.clipboard.writeText(r).then(()=>{d.success("Copied to clipboard")})},E=async()=>{b.value=!0;try{const r=await Z.docs.downloadPDF(),g=new Blob([r.data],{type:"application/pdf"}),P=URL.createObjectURL(g),h=document.createElement("a");h.href=P;const w=r.headers["content-disposition"];let C="Depl0y_Documentation.pdf";if(w){const S=w.match(/filename="?(.+)"?/);S&&(C=S[1])}h.download=C,document.body.appendChild(h),h.click(),h.remove(),URL.revokeObjectURL(P),d.success("PDF downloaded")}catch{d.error("PDF download failed")}finally{b.value=!1}};return X(()=>{V=new IntersectionObserver(r=>{r.forEach(g=>{g.isIntersecting&&(o.value=g.target.id)})},{rootMargin:"-15% 0px -70% 0px",threshold:0}),Object.entries(m.value).forEach(([,r])=>{r&&V.observe(r)})}),K(()=>{V&&V.disconnect()}),{sections:M,mainRef:e,sectionRefs:m,activeSection:o,activeSectionTitle:$,sidebarOpen:I,showQuickStart:L,searchQuery:u,searchResults:s,downloadingPDF:b,scrollToSection:H,onSearch:F,navigateToResult:O,copyCode:U,downloadPDF:E}}},oe={class:"doc-layout"},se={class:"sidebar-header"},ne={class:"sidebar-search"},re={key:0,class:"search-results"},ae=["onClick"],ie={class:"hit-section"},le=["innerHTML"],de={key:1,class:"search-no-results"},ce={key:2,class:"toc"},pe=["href","onClick"],ue={class:"toc-icon"},ge={class:"toc-label"},he={class:"sidebar-footer"},me={class:"doc-main",ref:"mainRef"},be={class:"doc-topbar"},ye={class:"breadcrumb-nav"},ve={class:"bc-current"},ke={style:{"margin-left":"auto",display:"flex",gap:"0.5rem"}},fe=["disabled"],we=["id"],xe={class:"section-title-row"},Pe={class:"section-title"},Ce={class:"section-icon"},Se=["innerHTML"],Ae=["href"],Ve=["innerHTML"],De={class:"doc-section",id:"quick-links"},Ie={class:"doc-grid"},Me={class:"doc-card featured"},Te={class:"doc-actions"},Ne={class:"doc-card"},Re={class:"doc-actions"},Le={class:"doc-card"},He={class:"doc-actions"},Be=["disabled"],_e={class:"doc-card"},$e={class:"doc-actions"},Fe={class:"modal-content doc-modal"},Oe={class:"modal-header"},Ue={class:"modal-body"},Ee={class:"step"},Ge={class:"step"},qe={class:"code-block-wrap"},Qe={class:"step"};function je(d,e,m,o,I,L){const u=q("router-link");return p(),c("div",oe,[t("aside",{class:_(["doc-sidebar",{"sidebar-open":o.sidebarOpen}])},[t("div",se,[e[13]||(e[13]=t("span",{class:"sidebar-title"},"Documentation",-1)),t("button",{class:"sidebar-close",onClick:e[0]||(e[0]=s=>o.sidebarOpen=!1)},"×")]),t("div",ne,[e[14]||(e[14]=t("span",{class:"search-icon"},"🔍",-1)),Q(t("input",{"onUpdate:modelValue":e[1]||(e[1]=s=>o.searchQuery=s),type:"text",class:"search-input",placeholder:"Search docs...",onInput:e[2]||(e[2]=(...s)=>o.onSearch&&o.onSearch(...s))},null,544),[[j,o.searchQuery]]),o.searchQuery?(p(),c("button",{key:0,class:"search-clear",onClick:e[3]||(e[3]=s=>{o.searchQuery="",o.searchResults=[]})},"×")):A("",!0)]),o.searchQuery&&o.searchResults.length>0?(p(),c("div",re,[(p(!0),c(D,null,N(o.searchResults,s=>(p(),c("div",{key:s.sectionId+"-"+s.index,class:"search-hit",onClick:b=>o.navigateToResult(s)},[t("span",ie,y(s.sectionTitle),1),t("span",{class:"hit-snippet",innerHTML:s.snippet},null,8,le)],8,ae))),128))])):o.searchQuery&&o.searchResults.length===0?(p(),c("div",de,' No results for "'+y(o.searchQuery)+'" ',1)):A("",!0),o.searchQuery?A("",!0):(p(),c("nav",ce,[(p(!0),c(D,null,N(o.sections,s=>(p(),c("a",{key:s.id,href:"#"+s.id,class:_(["toc-item",{active:o.activeSection===s.id}]),onClick:B(b=>o.scrollToSection(s.id),["prevent"])},[t("span",ue,y(s.icon),1),t("span",ge,y(s.title),1)],10,pe))),128))])),t("div",he,[e[17]||(e[17]=t("a",{href:"/docs",target:"_blank",class:"sidebar-link"},"Swagger UI",-1)),v(u,{to:"/api-explorer",class:"sidebar-link"},{default:k(()=>[...e[15]||(e[15]=[i("API Explorer",-1)])]),_:1}),v(u,{to:"/support",class:"sidebar-link"},{default:k(()=>[...e[16]||(e[16]=[i("Support",-1)])]),_:1})])],2),t("main",me,[t("div",be,[t("button",{class:"sidebar-toggle",onClick:e[4]||(e[4]=s=>o.sidebarOpen=!o.sidebarOpen)},"☰ Sections"),t("nav",ye,[v(u,{to:"/",class:"bc-link"},{default:k(()=>[...e[18]||(e[18]=[i("Home",-1)])]),_:1}),e[20]||(e[20]=t("span",{class:"bc-sep"},"/",-1)),e[21]||(e[21]=t("span",{class:"bc-current"},"Documentation",-1)),o.activeSection?(p(),c(D,{key:0},[e[19]||(e[19]=t("span",{class:"bc-sep"},"/",-1)),t("span",ve,y(o.activeSectionTitle),1)],64)):A("",!0)]),t("div",ke,[e[22]||(e[22]=t("a",{href:"/docs",target:"_blank",class:"btn btn-outline btn-sm"},"Swagger UI",-1)),t("button",{class:"btn btn-outline btn-sm",disabled:o.downloadingPDF,onClick:e[5]||(e[5]=(...s)=>o.downloadPDF&&o.downloadPDF(...s))},y(o.downloadingPDF?"Generating...":"Download PDF"),9,fe)])]),e[41]||(e[41]=t("div",{class:"doc-page-header"},[t("h1",null,"Documentation"),t("p",null,"Complete guide to installing, configuring, and using Depl0y — an open-source Proxmox VE management platform.")],-1)),(p(!0),c(D,null,N(o.sections,s=>(p(),c("section",{key:s.id,id:s.id,class:"doc-section",ref_for:!0,ref:b=>{b&&(o.sectionRefs[s.id]=b)}},[t("div",xe,[t("h2",Pe,[t("span",Ce,y(s.icon),1),t("span",{innerHTML:s.title},null,8,Se)]),t("a",{href:"#"+s.id,class:"anchor-link",title:"Link to section"},"¶",8,Ae)]),t("div",{class:"section-body",innerHTML:s.html},null,8,Ve)],8,we))),128)),t("section",De,[e[40]||(e[40]=t("div",{class:"section-title-row"},[t("h2",{class:"section-title"},[t("span",{class:"section-icon"},"🔗"),i(" Quick Links")])],-1)),t("div",Ie,[t("div",Me,[e[24]||(e[24]=t("div",{class:"doc-icon"},"⚡",-1)),e[25]||(e[25]=t("h3",null,"Cloud Images Quick Start",-1)),e[26]||(e[26]=t("p",null,"Deploy VMs in 30 seconds using pre-built cloud images and cloud-init.",-1)),t("div",Te,[t("button",{onClick:e[6]||(e[6]=s=>o.showQuickStart=!0),class:"btn btn-primary btn-sm"},"View Guide"),v(u,{to:"/settings",class:"btn btn-outline btn-sm"},{default:k(()=>[...e[23]||(e[23]=[i("Settings",-1)])]),_:1})])]),t("div",Ne,[e[29]||(e[29]=t("div",{class:"doc-icon"},"🔧",-1)),e[30]||(e[30]=t("h3",null,"Interactive API Explorer",-1)),e[31]||(e[31]=t("p",null,"Test every API endpoint interactively — enter parameters and send live requests.",-1)),t("div",Re,[v(u,{to:"/api-explorer",class:"btn btn-primary btn-sm"},{default:k(()=>[...e[27]||(e[27]=[i("Open Explorer",-1)])]),_:1}),e[28]||(e[28]=t("a",{href:"/docs",target:"_blank",class:"btn btn-outline btn-sm"},"Swagger UI",-1))])]),t("div",Le,[e[32]||(e[32]=t("div",{class:"doc-icon"},"📥",-1)),e[33]||(e[33]=t("h3",null,"Download PDF",-1)),e[34]||(e[34]=t("p",null,"Get all documentation in a single PDF for offline reference.",-1)),t("div",He,[t("button",{class:"btn btn-primary btn-sm",disabled:o.downloadingPDF,onClick:e[7]||(e[7]=(...s)=>o.downloadPDF&&o.downloadPDF(...s))},y(o.downloadingPDF?"Generating...":"Download PDF"),9,Be)])]),t("div",_e,[e[37]||(e[37]=t("div",{class:"doc-icon"},"🐞",-1)),e[38]||(e[38]=t("h3",null,"Report a Bug",-1)),e[39]||(e[39]=t("p",null,"Found an issue? File a detailed bug report with logs and steps to reproduce.",-1)),t("div",$e,[v(u,{to:"/bug-report",class:"btn btn-outline btn-sm"},{default:k(()=>[...e[35]||(e[35]=[i("Bug Report",-1)])]),_:1}),e[36]||(e[36]=t("a",{href:"https://github.com/agit8or1/Depl0y/issues",target:"_blank",class:"btn btn-outline btn-sm"},"GitHub",-1))])])])])],512),o.showQuickStart?(p(),c("div",{key:0,class:"modal",onClick:e[12]||(e[12]=B(s=>o.showQuickStart=!1,["self"]))},[t("div",Fe,[t("div",Oe,[e[42]||(e[42]=t("h3",null,"⚡ Cloud Images — Quick Start",-1)),t("button",{onClick:e[8]||(e[8]=s=>o.showQuickStart=!1),class:"btn-close"},"×")]),t("div",Ue,[e[54]||(e[54]=t("h4",null,"What Are Cloud Images?",-1)),e[55]||(e[55]=t("p",null,[i("Cloud images let you deploy VMs in "),t("strong",null,"30 seconds"),i(" instead of 20 minutes. No manual OS installation needed!")],-1)),t("div",Ee,[e[46]||(e[46]=t("strong",null,"Step 1: Check Status",-1)),t("p",null,[e[44]||(e[44]=i("Go to ",-1)),v(u,{to:"/settings",onClick:e[9]||(e[9]=s=>o.showQuickStart=!1)},{default:k(()=>[...e[43]||(e[43]=[i("Settings",-1)])]),_:1}),e[45]||(e[45]=i(' and look for the "Cloud Image Setup" section. A green status means already configured; yellow means setup is needed.',-1))])]),t("div",Ge,[e[48]||(e[48]=t("strong",null,"Step 2: Run Setup Script",-1)),e[49]||(e[49]=t("p",null,"SSH to your Depl0y server and run:",-1)),t("div",qe,[e[47]||(e[47]=t("pre",{class:"code-block"},"sudo /tmp/enable_cloud_images.sh",-1)),t("button",{class:"copy-btn",onClick:e[10]||(e[10]=s=>o.copyCode("sudo /tmp/enable_cloud_images.sh"))},"Copy")])]),t("div",Qe,[e[53]||(e[53]=t("strong",null,"Step 3: Deploy",-1)),t("p",null,[e[51]||(e[51]=i("Go to ",-1)),v(u,{to:"/deploy",onClick:e[11]||(e[11]=s=>o.showQuickStart=!1)},{default:k(()=>[...e[50]||(e[50]=[i("Deploy VM",-1)])]),_:1}),e[52]||(e[52]=i(", select Cloud Image, choose Ubuntu/Debian/etc., configure resources, and click Create.",-1))])]),e[56]||(e[56]=t("div",{class:"info-box"},[t("strong",null,"Deployment Times:"),t("ul",null,[t("li",null,[t("strong",null,"First deploy:"),i(" 5-10 minutes (creates template)")]),t("li",null,[t("strong",null,"Subsequent deploys:"),i(" ~30 seconds")])])],-1))])])])):A("",!0)])}const Ze=W(te,[["render",je],["__scopeId","data-v-3c5ee2bd"]]);export{Ze as default};
