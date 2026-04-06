<template>
  <div class="firewall-manager">
    <div class="page-header mb-3">
      <div>
        <h2>Firewall Manager</h2>
        <p class="text-muted text-sm">Manage cluster, VM/CT, and node-level firewall rules</p>
      </div>
      <div class="header-actions">
        <select v-model="hostId" class="form-control form-control-sm" @change="onHostChange">
          <option value="">— Select Host —</option>
          <option v-for="h in hosts" :key="h.id" :value="String(h.id)">{{ h.name || h.hostname }}</option>
        </select>
      </div>
    </div>

    <div v-if="!hostId" class="card text-center text-muted" style="padding: 3rem;">
      <p>Select a Proxmox host above to manage its firewall.</p>
    </div>

    <template v-else>
      <!-- Main Tabs -->
      <div class="tabs mb-3">
        <button v-for="tab in mainTabs" :key="tab.id"
          :class="['tab-btn', activeMainTab === tab.id ? 'tab-btn--active' : '']"
          @click="switchMainTab(tab.id)">{{ tab.label }}</button>
      </div>

      <!-- ── VM/CT Firewall Tab ── -->
      <div v-if="activeMainTab === 'vm'">
        <div class="toolbar-card card mb-3">
          <div class="toolbar-row">
            <div class="toolbar-group">
              <label class="form-label mb-0">VM / Container</label>
              <select v-model="selectedVmKey" class="form-control" @change="onVmSelected" :disabled="loadingVms">
                <option value="">{{ loadingVms ? 'Loading...' : '— Select VM/CT —' }}</option>
                <optgroup label="Virtual Machines">
                  <option v-for="vm in vmList.filter(v => v.type === 'qemu')" :key="vm.vmid+'@'+vm.node+'@qemu'"
                    :value="vm.vmid+'@'+vm.node+'@qemu'">
                    {{ vm.name || vm.vmid }} ({{ vm.vmid }}) @ {{ vm.node }}
                  </option>
                </optgroup>
                <optgroup label="Containers">
                  <option v-for="vm in vmList.filter(v => v.type === 'lxc')" :key="vm.vmid+'@'+vm.node+'@lxc'"
                    :value="vm.vmid+'@'+vm.node+'@lxc'">
                    [CT] {{ vm.name || vm.vmid }} ({{ vm.vmid }}) @ {{ vm.node }}
                  </option>
                </optgroup>
              </select>
            </div>

            <template v-if="selectedVmKey && vmFirewallOptions !== null">
              <div class="toolbar-group">
                <label class="form-label mb-0">Firewall</label>
                <div class="toggle-row">
                  <label class="toggle-switch">
                    <input type="checkbox"
                      :checked="vmFirewallOptions.enable == 1 || vmFirewallOptions.enable === true"
                      @change="toggleVmFirewall($event.target.checked)"
                      :disabled="savingVmOptions" />
                    <span class="toggle-slider"></span>
                  </label>
                  <span class="text-sm ml-1" :class="(vmFirewallOptions.enable == 1 || vmFirewallOptions.enable === true) ? 'text-success' : 'text-muted'">
                    {{ (vmFirewallOptions.enable == 1 || vmFirewallOptions.enable === true) ? 'Enabled' : 'Disabled' }}
                  </span>
                </div>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy In</label>
                <select v-model="vmFirewallOptions.policy_in" class="form-control form-control-sm"
                  @change="saveVmFirewallOptions" :disabled="savingVmOptions">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy Out</label>
                <select v-model="vmFirewallOptions.policy_out" class="form-control form-control-sm"
                  @change="saveVmFirewallOptions" :disabled="savingVmOptions">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
            </template>
          </div>
        </div>

        <div v-if="!selectedVmKey" class="card text-center text-muted" style="padding: 2.5rem;">
          <p>Select a VM or container to view and manage its firewall rules.</p>
        </div>

        <template v-else>
          <FirewallRulesPanel
            :rules="vmRules"
            :loading="loadingVmRules"
            :title="selectedVmLabel + ' Firewall Rules'"
            :ipsets="clusterIpsets"
            :aliases="clusterAliases"
            :direction-filter="vmDirFilter"
            @add="openAddVmRuleModal"
            @edit="openEditVmRuleModal"
            @delete="deleteVmRule"
            @toggle="toggleVmRule"
            @reload="loadVmRules"
            @dir-filter="vmDirFilter = $event"
          />
        </template>
      </div>

      <!-- ── Cluster Firewall Tab ── -->
      <div v-if="activeMainTab === 'cluster'">
        <div class="subtabs mb-2">
          <button v-for="st in clusterSubTabs" :key="st.id"
            :class="['subtab-btn', activeClusterSubTab === st.id ? 'active' : '']"
            @click="switchClusterSubTab(st.id)">{{ st.label }}</button>
        </div>

        <!-- Cluster Rules -->
        <div v-if="activeClusterSubTab === 'rules'">
          <div class="toolbar-card card mb-3">
            <div class="toolbar-row">
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy In</label>
                <select v-model="clusterFirewallOptions.policy_in" class="form-control form-control-sm"
                  @change="saveClusterOptions" :disabled="!clusterFirewallOptions.policy_in && !clusterOptionsLoaded">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy Out</label>
                <select v-model="clusterFirewallOptions.policy_out" class="form-control form-control-sm"
                  @change="saveClusterOptions" :disabled="!clusterOptionsLoaded">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Firewall</label>
                <div class="toggle-row">
                  <label class="toggle-switch">
                    <input type="checkbox"
                      :checked="clusterFirewallOptions.enable == 1 || clusterFirewallOptions.enable === true"
                      @change="toggleClusterFirewall($event.target.checked)"
                      :disabled="!clusterOptionsLoaded" />
                    <span class="toggle-slider"></span>
                  </label>
                  <span class="text-sm ml-1">
                    {{ (clusterFirewallOptions.enable == 1 || clusterFirewallOptions.enable === true) ? 'Enabled' : 'Disabled' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <FirewallRulesPanel
            :rules="clusterRules"
            :loading="loadingClusterRules"
            title="Cluster Firewall Rules"
            :ipsets="clusterIpsets"
            :aliases="clusterAliases"
            :direction-filter="clusterDirFilter"
            @add="openAddClusterRuleModal"
            @edit="openEditClusterRuleModal"
            @delete="deleteClusterRule"
            @toggle="toggleClusterRule"
            @reload="loadClusterRules"
            @dir-filter="clusterDirFilter = $event"
          />
        </div>

        <!-- IPSets -->
        <div v-if="activeClusterSubTab === 'ipsets'">
          <div class="two-panel">
            <div class="panel-left">
              <div class="card">
                <div class="card-header">
                  <h3>IP Sets</h3>
                  <button @click="openCreateIpsetModal" class="btn btn-primary btn-sm">+ New</button>
                </div>
                <div v-if="loadingIpsets" class="loading-spinner p-3"></div>
                <div v-else-if="clusterIpsets.length === 0" class="text-center text-muted p-4">
                  No IP sets defined.
                </div>
                <div v-else class="ipset-list">
                  <div v-for="ipset in clusterIpsets" :key="ipset.name"
                    :class="['ipset-item', selectedIpsetName === ipset.name ? 'active' : '']"
                    @click="selectIpset(ipset.name)">
                    <div class="ipset-item-main">
                      <span class="ipset-name">{{ ipset.name }}</span>
                      <span class="text-muted text-sm">{{ ipset.comment || '' }}</span>
                    </div>
                    <button @click.stop="deleteIpset(ipset.name)" class="btn btn-danger btn-xs">✕</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="panel-right">
              <div class="card">
                <div class="card-header">
                  <h3>{{ selectedIpsetName ? `${selectedIpsetName} — Entries` : 'Select an IP Set' }}</h3>
                  <button v-if="selectedIpsetName" @click="openAddCidrModal" class="btn btn-primary btn-sm">+ Add CIDR</button>
                </div>
                <div v-if="!selectedIpsetName" class="text-center text-muted p-4">Select an IP set from the list.</div>
                <div v-else-if="loadingIpsetEntries" class="loading-spinner p-3"></div>
                <div v-else-if="ipsetEntries.length === 0" class="text-center text-muted p-4">No entries. Add a CIDR above.</div>
                <div v-else class="table-container">
                  <table class="table">
                    <thead><tr><th>CIDR</th><th>Nomatch</th><th>Comment</th><th>Remove</th></tr></thead>
                    <tbody>
                      <tr v-for="entry in ipsetEntries" :key="entry.cidr">
                        <td><code>{{ entry.cidr }}</code></td>
                        <td>{{ entry.nomatch ? 'Yes' : '—' }}</td>
                        <td class="text-sm text-muted">{{ entry.comment || '—' }}</td>
                        <td><button @click="removeIpsetEntry(entry.cidr)" class="btn btn-danger btn-sm">Remove</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Aliases -->
        <div v-if="activeClusterSubTab === 'aliases'" class="card">
          <div class="card-header">
            <h3>Aliases</h3>
            <button @click="openCreateAliasModal" class="btn btn-primary btn-sm">+ New Alias</button>
          </div>
          <div v-if="loadingAliases" class="loading-spinner p-3"></div>
          <div v-else-if="clusterAliases.length === 0" class="text-center text-muted p-4">No aliases defined.</div>
          <div v-else class="table-container">
            <table class="table">
              <thead><tr><th>Name</th><th>IP / CIDR</th><th>Comment</th><th>Actions</th></tr></thead>
              <tbody>
                <tr v-for="alias in clusterAliases" :key="alias.name">
                  <td><strong>{{ alias.name }}</strong></td>
                  <td><code>{{ alias.cidr }}</code></td>
                  <td class="text-sm text-muted">{{ alias.comment || '—' }}</td>
                  <td>
                    <div class="action-btns">
                      <button @click="openEditAliasModal(alias)" class="btn btn-outline btn-sm">Edit</button>
                      <button @click="deleteAlias(alias.name)" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Security Groups -->
        <div v-if="activeClusterSubTab === 'secgroups'">
          <div class="two-panel">
            <div class="panel-left">
              <div class="card">
                <div class="card-header">
                  <h3>Security Groups</h3>
                  <button @click="openCreateSecGroupModal" class="btn btn-primary btn-sm">+ New</button>
                </div>
                <div v-if="loadingSecGroups" class="loading-spinner p-3"></div>
                <div v-else-if="securityGroups.length === 0" class="text-center text-muted p-4">No security groups.</div>
                <div v-else class="ipset-list">
                  <div v-for="sg in securityGroups" :key="sg.group"
                    :class="['ipset-item', selectedSecGroup === sg.group ? 'active' : '']"
                    @click="selectSecGroup(sg.group)">
                    <div class="ipset-item-main">
                      <span class="ipset-name">{{ sg.group }}</span>
                      <span class="text-muted text-sm">{{ sg.comment || '' }}</span>
                    </div>
                    <button @click.stop="deleteSecGroup(sg.group)" class="btn btn-danger btn-xs">✕</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="panel-right">
              <div class="card">
                <div class="card-header">
                  <h3>{{ selectedSecGroup ? `${selectedSecGroup} — Rules` : 'Select a Security Group' }}</h3>
                  <button v-if="selectedSecGroup" @click="openAddSecGroupRuleModal" class="btn btn-primary btn-sm">+ Add Rule</button>
                </div>
                <div v-if="!selectedSecGroup" class="text-center text-muted p-4">Select a security group from the list.</div>
                <div v-else-if="loadingSecGroupRules" class="loading-spinner p-3"></div>
                <div v-else-if="secGroupRules.length === 0" class="text-center text-muted p-4">No rules in this group.</div>
                <div v-else class="table-container">
                  <table class="table">
                    <thead>
                      <tr><th>Pos</th><th>Dir</th><th>Action</th><th>Proto</th><th>Source</th><th>Dest</th><th>Port</th><th>Comment</th><th>En</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(rule, i) in secGroupRules" :key="rule.pos ?? i"
                        :class="{ 'rule-disabled': rule.enable == 0 }">
                        <td>{{ rule.pos ?? i }}</td>
                        <td><span :class="['badge', rule.type === 'out' ? 'badge-warning' : 'badge-info']">{{ (rule.type||'in').toUpperCase() }}</span></td>
                        <td><span :class="['badge', actionBadge(rule.action)]">{{ rule.action }}</span></td>
                        <td>{{ rule.proto || 'any' }}</td>
                        <td class="text-sm">{{ rule.source || '—' }}</td>
                        <td class="text-sm">{{ rule.dest || '—' }}</td>
                        <td class="text-sm">{{ rule.dport || rule.sport ? (rule.dport||'')+(rule.sport?' src:'+rule.sport:'') : '—' }}</td>
                        <td class="text-sm text-muted">{{ rule.comment || '—' }}</td>
                        <td>
                          <label class="toggle-switch toggle-sm">
                            <input type="checkbox" :checked="rule.enable == 1 || rule.enable === true"
                              @change="toggleSecGroupRule(rule, $event.target.checked)" />
                            <span class="toggle-slider"></span>
                          </label>
                        </td>
                        <td>
                          <div class="action-btns">
                            <button @click="openEditSecGroupRuleModal(rule)" class="btn btn-outline btn-sm">Edit</button>
                            <button @click="deleteSecGroupRule(rule.pos ?? i)" class="btn btn-danger btn-sm">Del</button>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Node Firewall Tab ── -->
      <div v-if="activeMainTab === 'node'">
        <div class="toolbar-card card mb-3">
          <div class="toolbar-row">
            <div class="toolbar-group">
              <label class="form-label mb-0">Node</label>
              <select v-model="selectedNode" class="form-control" @change="onNodeSelected" :disabled="loadingNodes">
                <option value="">{{ loadingNodes ? 'Loading...' : '— Select Node —' }}</option>
                <option v-for="n in nodeList" :key="n.node_name || n.node" :value="n.node_name || n.node">{{ n.node_name || n.node }}</option>
              </select>
            </div>
            <template v-if="selectedNode && nodeFirewallOptions !== null">
              <div class="toolbar-group">
                <label class="form-label mb-0">Firewall</label>
                <div class="toggle-row">
                  <label class="toggle-switch">
                    <input type="checkbox"
                      :checked="nodeFirewallOptions.enable == 1 || nodeFirewallOptions.enable === true"
                      @change="toggleNodeFirewall($event.target.checked)"
                      :disabled="savingNodeOptions" />
                    <span class="toggle-slider"></span>
                  </label>
                  <span class="text-sm ml-1" :class="(nodeFirewallOptions.enable == 1) ? 'text-success' : 'text-muted'">
                    {{ (nodeFirewallOptions.enable == 1 || nodeFirewallOptions.enable === true) ? 'Enabled' : 'Disabled' }}
                  </span>
                </div>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy In</label>
                <select v-model="nodeFirewallOptions.policy_in" class="form-control form-control-sm"
                  @change="saveNodeFirewallOptions" :disabled="savingNodeOptions">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
              <div class="toolbar-group">
                <label class="form-label mb-0">Policy Out</label>
                <select v-model="nodeFirewallOptions.policy_out" class="form-control form-control-sm"
                  @change="saveNodeFirewallOptions" :disabled="savingNodeOptions">
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
            </template>
          </div>
        </div>

        <div v-if="!selectedNode" class="card text-center text-muted" style="padding: 2.5rem;">
          <p>Select a node above to manage its firewall rules.</p>
        </div>

        <template v-else>
          <FirewallRulesPanel
            :rules="nodeRules"
            :loading="loadingNodeRules"
            :title="selectedNode + ' Node Firewall Rules'"
            :ipsets="clusterIpsets"
            :aliases="clusterAliases"
            :direction-filter="nodeDirFilter"
            @add="openAddNodeRuleModal"
            @edit="openEditNodeRuleModal"
            @delete="deleteNodeRule"
            @toggle="toggleNodeRule"
            @reload="loadNodeRules"
            @dir-filter="nodeDirFilter = $event"
          />
        </template>
      </div>
    </template>

    <!-- ── Rule Add/Edit Modal ── -->
    <div v-if="showRuleModal" class="modal" @click.self="showRuleModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingRule ? 'Edit Firewall Rule' : 'Add Firewall Rule' }}</h3>
          <button @click="showRuleModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitRule" class="modal-body">
          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label">Direction</label>
              <select v-model="ruleForm.type" class="form-control">
                <option value="in">IN (Inbound)</option>
                <option value="out">OUT (Outbound)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Action <span class="text-danger">*</span></label>
              <select v-model="ruleForm.action" class="form-control" required>
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
          </div>
          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label">Protocol</label>
              <select v-model="ruleForm.proto" class="form-control">
                <option value="">any</option>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="icmp">ICMP</option>
                <option value="tcp_udp">TCP+UDP</option>
              </select>
            </div>
            <div class="form-group" style="display:flex;align-items:flex-end;padding-bottom:0.25rem;">
              <label class="toggle-label-inline">
                <input type="checkbox" v-model="ruleForm.enable" :true-value="1" :false-value="0" />
                <span>Enabled</span>
              </label>
            </div>
          </div>
          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label">Source IP / CIDR / IPSet</label>
              <input v-model="ruleForm.source" list="ipset-source-list" class="form-control" placeholder="e.g. 10.0.0.0/8 or +ipsetname" />
              <datalist id="ipset-source-list">
                <option v-for="is in clusterIpsets" :key="is.name" :value="'+'+is.name">+{{ is.name }}</option>
                <option v-for="al in clusterAliases" :key="al.name" :value="al.name">{{ al.name }}</option>
              </datalist>
            </div>
            <div class="form-group">
              <label class="form-label">Destination IP / CIDR / IPSet</label>
              <input v-model="ruleForm.dest" list="ipset-dest-list" class="form-control" placeholder="e.g. 192.168.1.0/24 or +ipsetname" />
              <datalist id="ipset-dest-list">
                <option v-for="is in clusterIpsets" :key="is.name" :value="'+'+is.name">+{{ is.name }}</option>
                <option v-for="al in clusterAliases" :key="al.name" :value="al.name">{{ al.name }}</option>
              </datalist>
            </div>
          </div>
          <div class="form-row-2">
            <div class="form-group">
              <label class="form-label">Source Port</label>
              <input v-model="ruleForm.sport" class="form-control" placeholder="e.g. 1024:65535" />
            </div>
            <div class="form-group">
              <label class="form-label">Destination Port</label>
              <input v-model="ruleForm.dport" class="form-control" placeholder="e.g. 80 or 80:443" />
            </div>
          </div>
          <div v-if="editingRule" class="form-group">
            <label class="form-label">Move to Position</label>
            <input v-model.number="ruleForm.moveto" type="number" class="form-control" placeholder="Leave blank to keep position" />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="ruleForm.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-2 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingRule">
              {{ savingRule ? 'Saving...' : (editingRule ? 'Update Rule' : 'Add Rule') }}
            </button>
            <button type="button" @click="showRuleModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Create IPSet Modal ── -->
    <div v-if="showIpsetModal" class="modal" @click.self="showIpsetModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create IP Set</h3>
          <button @click="showIpsetModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createIpset" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="text-danger">*</span></label>
            <input v-model="ipsetForm.name" class="form-control" placeholder="e.g. webservers" required pattern="[A-Za-z][A-Za-z0-9_-]*" />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="ipsetForm.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-2 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingIpset">Create</button>
            <button type="button" @click="showIpsetModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Add CIDR to IPSet Modal ── -->
    <div v-if="showCidrModal" class="modal" @click.self="showCidrModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add CIDR to {{ selectedIpsetName }}</h3>
          <button @click="showCidrModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addCidrToIpset" class="modal-body">
          <div class="form-group">
            <label class="form-label">CIDR <span class="text-danger">*</span></label>
            <input v-model="cidrForm.cidr" class="form-control" placeholder="e.g. 192.168.1.0/24" required />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="cidrForm.comment" class="form-control" placeholder="Optional" />
          </div>
          <div class="form-group">
            <label class="toggle-label-inline">
              <input type="checkbox" v-model="cidrForm.nomatch" />
              <span>Nomatch (negate / exclude this CIDR)</span>
            </label>
          </div>
          <div class="flex gap-2 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingCidr">Add</button>
            <button type="button" @click="showCidrModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Alias Modal ── -->
    <div v-if="showAliasModal" class="modal" @click.self="showAliasModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingAlias ? 'Edit Alias' : 'Create Alias' }}</h3>
          <button @click="showAliasModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitAlias" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="text-danger">*</span></label>
            <input v-model="aliasForm.name" class="form-control" placeholder="e.g. my-server" required :disabled="!!editingAlias" />
          </div>
          <div class="form-group">
            <label class="form-label">IP / CIDR <span class="text-danger">*</span></label>
            <input v-model="aliasForm.cidr" class="form-control" placeholder="e.g. 192.168.1.100 or 10.0.0.0/8" required />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="aliasForm.comment" class="form-control" placeholder="Optional" />
          </div>
          <div class="flex gap-2 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingAlias">
              {{ editingAlias ? 'Update' : 'Create' }}
            </button>
            <button type="button" @click="showAliasModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ── Create Security Group Modal ── -->
    <div v-if="showSecGroupModal" class="modal" @click.self="showSecGroupModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Security Group</h3>
          <button @click="showSecGroupModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="createSecGroup" class="modal-body">
          <div class="form-group">
            <label class="form-label">Name <span class="text-danger">*</span></label>
            <input v-model="secGroupForm.group" class="form-control" placeholder="e.g. webservers" required pattern="[A-Za-z][A-Za-z0-9_-]*" />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="secGroupForm.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-2 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="savingSecGroup">Create</button>
            <button type="button" @click="showSecGroupModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, defineComponent } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

// ── Inline FirewallRulesPanel sub-component ──────────────────────────────────
const FirewallRulesPanel = defineComponent({
  name: 'FirewallRulesPanel',
  props: {
    rules: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    title: { type: String, default: 'Firewall Rules' },
    ipsets: { type: Array, default: () => [] },
    aliases: { type: Array, default: () => [] },
    directionFilter: { type: String, default: 'all' },
  },
  emits: ['add', 'edit', 'delete', 'toggle', 'reload', 'dir-filter'],
  setup(props, { emit }) {
    const actionFilter = ref('')
    const srcFilter = ref('')
    const dstFilter = ref('')
    const commentFilter = ref('')

    const filtered = computed(() => {
      return props.rules.filter(r => {
        if (props.directionFilter !== 'all' && r.type !== props.directionFilter) return false
        if (actionFilter.value && r.action !== actionFilter.value) return false
        if (srcFilter.value && !(r.source || '').toLowerCase().includes(srcFilter.value.toLowerCase())) return false
        if (dstFilter.value && !(r.dest || '').toLowerCase().includes(dstFilter.value.toLowerCase())) return false
        if (commentFilter.value && !(r.comment || '').toLowerCase().includes(commentFilter.value.toLowerCase())) return false
        return true
      })
    })

    const clearFilters = () => {
      actionFilter.value = ''
      srcFilter.value = ''
      dstFilter.value = ''
      commentFilter.value = ''
      emit('dir-filter', 'all')
    }

    const actionBadge = (a) => ({ ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }[a] || 'badge-info')

    return { actionFilter, srcFilter, dstFilter, commentFilter, filtered, clearFilters, actionBadge }
  },
  template: `
    <div class="fw-rules-panel">
      <div class="card mb-2">
        <div class="card-header">
          <h4 style="margin:0;font-size:0.95rem;font-weight:600;">Filter</h4>
          <button @click="clearFilters" class="btn btn-outline btn-sm">Clear</button>
        </div>
        <div class="card-body" style="padding:0.75rem 1rem;">
          <div class="filter-grid">
            <div class="form-group mb-0">
              <label class="form-label">Direction</label>
              <select :value="directionFilter" @change="$emit('dir-filter', $event.target.value)" class="form-control form-control-sm">
                <option value="all">All</option>
                <option value="in">IN</option>
                <option value="out">OUT</option>
              </select>
            </div>
            <div class="form-group mb-0">
              <label class="form-label">Action</label>
              <select v-model="actionFilter" class="form-control form-control-sm">
                <option value="">All</option>
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
            <div class="form-group mb-0">
              <label class="form-label">Source</label>
              <input v-model="srcFilter" class="form-control form-control-sm" placeholder="Filter..." />
            </div>
            <div class="form-group mb-0">
              <label class="form-label">Destination</label>
              <input v-model="dstFilter" class="form-control form-control-sm" placeholder="Filter..." />
            </div>
            <div class="form-group mb-0">
              <label class="form-label">Comment</label>
              <input v-model="commentFilter" class="form-control form-control-sm" placeholder="Filter..." />
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3>{{ title }}
            <span v-if="filtered.length !== rules.length" class="text-muted text-sm ml-1">({{ filtered.length }} of {{ rules.length }})</span>
          </h3>
          <div class="header-actions-sm">
            <button @click="$emit('reload')" class="btn btn-outline btn-sm" title="Reload">↺ Reload</button>
            <button @click="$emit('add')" class="btn btn-primary btn-sm">+ Add Rule</button>
          </div>
        </div>

        <div v-if="loading" class="loading-spinner p-3"></div>
        <div v-else-if="filtered.length === 0" class="text-center text-muted p-4">
          <p>{{ rules.length === 0 ? 'No firewall rules configured.' : 'No rules match the current filter.' }}</p>
        </div>
        <div v-else class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Pos</th><th>Dir</th><th>Action</th><th>Proto</th>
                <th>Source</th><th>Destination</th><th>Ports</th>
                <th>Comment</th><th>Enabled</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(rule, idx) in filtered" :key="rule.pos ?? idx"
                :class="{ 'rule-disabled': rule.enable == 0 || rule.enable === false }">
                <td><strong>{{ rule.pos ?? idx }}</strong></td>
                <td>
                  <span :class="['badge', rule.type === 'out' ? 'badge-warning' : 'badge-info']">
                    {{ (rule.type||'in').toUpperCase() }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', actionBadge(rule.action)]">{{ rule.action || '—' }}</span>
                </td>
                <td>{{ rule.proto || 'any' }}</td>
                <td class="text-sm">{{ rule.source || '—' }}</td>
                <td class="text-sm">{{ rule.dest || '—' }}</td>
                <td class="text-sm">
                  <span v-if="rule.dport || rule.sport">
                    <span v-if="rule.dport">dst:{{ rule.dport }}</span>
                    <span v-if="rule.sport"> src:{{ rule.sport }}</span>
                  </span>
                  <span v-else>—</span>
                </td>
                <td class="text-sm text-muted">{{ rule.comment || '—' }}</td>
                <td>
                  <label class="toggle-switch toggle-sm">
                    <input type="checkbox"
                      :checked="rule.enable == 1 || rule.enable === true"
                      @change="$emit('toggle', rule, $event.target.checked)" />
                    <span class="toggle-slider"></span>
                  </label>
                </td>
                <td>
                  <div class="action-btns">
                    <button @click="$emit('edit', rule)" class="btn btn-outline btn-sm">Edit</button>
                    <button @click="$emit('delete', rule.pos ?? idx)" class="btn btn-danger btn-sm">Del</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
})

export default {
  name: 'FirewallManager',
  components: { FirewallRulesPanel },

  setup() {
    const route = useRoute()
    const toast = useToast()

    // ── Host selection ──────────────────────────────────────────────────────
    const hosts = ref([])
    const hostId = ref(route.params.hostId || '')

    const loadHosts = async () => {
      try {
        const res = await api.proxmox.listHosts()
        hosts.value = res.data || []
        if (!hostId.value && hosts.value.length === 1) {
          hostId.value = String(hosts.value[0].id)
          onHostChange()
        }
      } catch (e) {
        toast.error('Failed to load hosts')
      }
    }

    const onHostChange = () => {
      // Reset all state
      vmList.value = []
      selectedVmKey.value = ''
      vmRules.value = []
      vmFirewallOptions.value = null
      nodeList.value = []
      selectedNode.value = ''
      nodeRules.value = []
      nodeFirewallOptions.value = null
      clusterRules.value = []
      clusterIpsets.value = []
      clusterAliases.value = []
      securityGroups.value = []
      clusterOptionsLoaded.value = false

      if (hostId.value) {
        loadClusterData()
      }
    }

    // ── Main tabs ────────────────────────────────────────────────────────────
    const mainTabs = [
      { id: 'vm', label: 'VM / CT Firewall' },
      { id: 'cluster', label: 'Cluster Firewall' },
      { id: 'node', label: 'Node Firewall' },
    ]
    const activeMainTab = ref('vm')

    const switchMainTab = (id) => {
      activeMainTab.value = id
      if (id === 'cluster') {
        loadClusterData()
      } else if (id === 'node' && nodeList.value.length === 0) {
        loadNodeList()
      } else if (id === 'vm' && vmList.value.length === 0) {
        loadVmList()
      }
    }

    // ── Cluster sub-tabs ─────────────────────────────────────────────────────
    const clusterSubTabs = [
      { id: 'rules', label: 'Rules' },
      { id: 'ipsets', label: 'IP Sets' },
      { id: 'aliases', label: 'Aliases' },
      { id: 'secgroups', label: 'Security Groups' },
    ]
    const activeClusterSubTab = ref('rules')

    const switchClusterSubTab = (id) => {
      activeClusterSubTab.value = id
      if (id === 'rules') loadClusterRules()
      else if (id === 'ipsets') loadIpsets()
      else if (id === 'aliases') loadAliases()
      else if (id === 'secgroups') loadSecGroups()
    }

    // ── Cluster data ─────────────────────────────────────────────────────────
    const clusterRules = ref([])
    const loadingClusterRules = ref(false)
    const clusterDirFilter = ref('all')
    const clusterFirewallOptions = ref({ enable: 0, policy_in: 'DROP', policy_out: 'ACCEPT' })
    const clusterOptionsLoaded = ref(false)

    const clusterIpsets = ref([])
    const loadingIpsets = ref(false)
    const selectedIpsetName = ref('')
    const ipsetEntries = ref([])
    const loadingIpsetEntries = ref(false)

    const clusterAliases = ref([])
    const loadingAliases = ref(false)

    const securityGroups = ref([])
    const loadingSecGroups = ref(false)
    const selectedSecGroup = ref('')
    const secGroupRules = ref([])
    const loadingSecGroupRules = ref(false)

    const loadClusterData = async () => {
      if (!hostId.value) return
      loadClusterRules()
      loadIpsets()
      loadAliases()
      loadClusterOptions()
    }

    const loadClusterRules = async () => {
      if (!hostId.value) return
      loadingClusterRules.value = true
      try {
        const res = await api.pveNode.getClusterFirewallRules(hostId.value)
        clusterRules.value = res.data || []
      } catch (e) {
        toast.error('Failed to load cluster firewall rules')
      } finally {
        loadingClusterRules.value = false
      }
    }

    const loadClusterOptions = async () => {
      if (!hostId.value) return
      try {
        const res = await api.pveFirewall.getClusterFirewallOptions(hostId.value)
        clusterFirewallOptions.value = { ...{ enable: 0, policy_in: 'DROP', policy_out: 'ACCEPT' }, ...res.data }
        clusterOptionsLoaded.value = true
      } catch (e) {
        clusterOptionsLoaded.value = true
      }
    }

    const saveClusterOptions = async () => {
      try {
        await api.pveFirewall.setClusterFirewallOptions(hostId.value, {
          enable: clusterFirewallOptions.value.enable ? 1 : 0,
          policy_in: clusterFirewallOptions.value.policy_in,
          policy_out: clusterFirewallOptions.value.policy_out,
        })
        toast.success('Cluster firewall options saved')
      } catch (e) {
        toast.error('Failed to save cluster firewall options')
      }
    }

    const toggleClusterFirewall = async (enabled) => {
      clusterFirewallOptions.value.enable = enabled ? 1 : 0
      await saveClusterOptions()
    }

    const loadIpsets = async () => {
      if (!hostId.value) return
      loadingIpsets.value = true
      try {
        const res = await api.pveFirewall.listIpsets(hostId.value)
        clusterIpsets.value = res.data || []
      } catch (e) {
        toast.error('Failed to load IP sets')
      } finally {
        loadingIpsets.value = false
      }
    }

    const selectIpset = async (name) => {
      selectedIpsetName.value = name
      loadingIpsetEntries.value = true
      try {
        const res = await api.pveFirewall.listIpsetEntries(hostId.value, name)
        ipsetEntries.value = res.data || []
      } catch (e) {
        toast.error('Failed to load IP set entries')
      } finally {
        loadingIpsetEntries.value = false
      }
    }

    const loadAliases = async () => {
      if (!hostId.value) return
      loadingAliases.value = true
      try {
        const res = await api.pveFirewall.listAliases(hostId.value)
        clusterAliases.value = res.data || []
      } catch (e) {
        toast.error('Failed to load aliases')
      } finally {
        loadingAliases.value = false
      }
    }

    const loadSecGroups = async () => {
      if (!hostId.value) return
      loadingSecGroups.value = true
      try {
        const res = await api.pveFirewall.listSecurityGroups(hostId.value)
        securityGroups.value = res.data || []
      } catch (e) {
        toast.error('Failed to load security groups')
      } finally {
        loadingSecGroups.value = false
      }
    }

    const selectSecGroup = async (name) => {
      selectedSecGroup.value = name
      loadingSecGroupRules.value = true
      try {
        const res = await api.pveFirewall.listSecurityGroupRules(hostId.value, name)
        secGroupRules.value = res.data || []
      } catch (e) {
        toast.error('Failed to load security group rules')
      } finally {
        loadingSecGroupRules.value = false
      }
    }

    // ── VM/CT data ────────────────────────────────────────────────────────────
    const vmList = ref([])
    const loadingVms = ref(false)
    const selectedVmKey = ref('')
    const vmRules = ref([])
    const loadingVmRules = ref(false)
    const vmFirewallOptions = ref(null)
    const savingVmOptions = ref(false)
    const vmDirFilter = ref('all')

    const selectedVmId = computed(() => selectedVmKey.value ? selectedVmKey.value.split('@')[0] : null)
    const selectedVmNode = computed(() => selectedVmKey.value ? selectedVmKey.value.split('@')[1] : null)
    const selectedVmType = computed(() => selectedVmKey.value ? selectedVmKey.value.split('@')[2] : null)
    const selectedVmLabel = computed(() => {
      const vm = vmList.value.find(v => `${v.vmid}@${v.node}@${v.type}` === selectedVmKey.value)
      return vm ? (vm.name || vm.vmid) : ''
    })

    const loadVmList = async () => {
      if (!hostId.value) return
      loadingVms.value = true
      try {
        const res = await api.pveNode.clusterResources(hostId.value, 'vm')
        vmList.value = (res.data || []).sort((a, b) => (a.vmid || 0) - (b.vmid || 0))
      } catch (e) {
        toast.error('Failed to load VM list')
      } finally {
        loadingVms.value = false
      }
    }

    const onVmSelected = () => {
      vmRules.value = []
      vmFirewallOptions.value = null
      if (selectedVmKey.value) {
        loadVmRules()
        loadVmFirewallOptions()
      }
    }

    const loadVmRules = async () => {
      if (!selectedVmKey.value) return
      loadingVmRules.value = true
      try {
        let res
        if (selectedVmType.value === 'lxc') {
          res = await api.pveNode.getCtFirewallRules(hostId.value, selectedVmNode.value, selectedVmId.value)
        } else {
          res = await api.pveVm.getFirewallRules(hostId.value, selectedVmNode.value, selectedVmId.value)
        }
        vmRules.value = res.data || []
      } catch (e) {
        toast.error('Failed to load VM firewall rules')
      } finally {
        loadingVmRules.value = false
      }
    }

    const loadVmFirewallOptions = async () => {
      if (!selectedVmKey.value) return
      try {
        let res
        if (selectedVmType.value === 'lxc') {
          res = await api.pveNode.getCtFirewallOptions(hostId.value, selectedVmNode.value, selectedVmId.value)
        } else {
          res = await api.pveVm.getFirewallOptions(hostId.value, selectedVmNode.value, selectedVmId.value)
        }
        vmFirewallOptions.value = { policy_in: 'DROP', policy_out: 'ACCEPT', ...res.data }
      } catch (e) {
        vmFirewallOptions.value = { enable: 0, policy_in: 'DROP', policy_out: 'ACCEPT' }
      }
    }

    const saveVmFirewallOptions = async () => {
      if (!selectedVmKey.value || !vmFirewallOptions.value) return
      savingVmOptions.value = true
      try {
        const payload = {
          enable: vmFirewallOptions.value.enable ? 1 : 0,
          policy_in: vmFirewallOptions.value.policy_in,
          policy_out: vmFirewallOptions.value.policy_out,
        }
        if (selectedVmType.value === 'lxc') {
          await api.pveNode.setCtFirewallOptions(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
        } else {
          await api.pveVm.setFirewallOptions(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
        }
        toast.success('Firewall options saved')
      } catch (e) {
        toast.error('Failed to save firewall options')
      } finally {
        savingVmOptions.value = false
      }
    }

    const toggleVmFirewall = async (enabled) => {
      vmFirewallOptions.value.enable = enabled ? 1 : 0
      await saveVmFirewallOptions()
    }

    // ── Node data ─────────────────────────────────────────────────────────────
    const nodeList = ref([])
    const loadingNodes = ref(false)
    const selectedNode = ref('')
    const nodeRules = ref([])
    const loadingNodeRules = ref(false)
    const nodeFirewallOptions = ref(null)
    const savingNodeOptions = ref(false)
    const nodeDirFilter = ref('all')

    const loadNodeList = async () => {
      if (!hostId.value) return
      loadingNodes.value = true
      try {
        const res = await api.proxmox.listNodes(hostId.value)
        nodeList.value = res.data || []
      } catch (e) {
        toast.error('Failed to load nodes')
      } finally {
        loadingNodes.value = false
      }
    }

    const onNodeSelected = () => {
      nodeRules.value = []
      nodeFirewallOptions.value = null
      if (selectedNode.value) {
        loadNodeRules()
        loadNodeFirewallOptions()
      }
    }

    const loadNodeRules = async () => {
      if (!selectedNode.value) return
      loadingNodeRules.value = true
      try {
        const res = await api.pveFirewall.listNodeFirewallRules(hostId.value, selectedNode.value)
        nodeRules.value = res.data || []
      } catch (e) {
        toast.error('Failed to load node firewall rules')
      } finally {
        loadingNodeRules.value = false
      }
    }

    const loadNodeFirewallOptions = async () => {
      if (!selectedNode.value) return
      try {
        const res = await api.pveFirewall.getNodeFirewallOptions(hostId.value, selectedNode.value)
        nodeFirewallOptions.value = { policy_in: 'DROP', policy_out: 'ACCEPT', ...res.data }
      } catch (e) {
        nodeFirewallOptions.value = { enable: 0, policy_in: 'DROP', policy_out: 'ACCEPT' }
      }
    }

    const saveNodeFirewallOptions = async () => {
      if (!selectedNode.value || !nodeFirewallOptions.value) return
      savingNodeOptions.value = true
      try {
        await api.pveFirewall.setNodeFirewallOptions(hostId.value, selectedNode.value, {
          enable: nodeFirewallOptions.value.enable ? 1 : 0,
          policy_in: nodeFirewallOptions.value.policy_in,
          policy_out: nodeFirewallOptions.value.policy_out,
        })
        toast.success('Node firewall options saved')
      } catch (e) {
        toast.error('Failed to save node firewall options')
      } finally {
        savingNodeOptions.value = false
      }
    }

    const toggleNodeFirewall = async (enabled) => {
      nodeFirewallOptions.value.enable = enabled ? 1 : 0
      await saveNodeFirewallOptions()
    }

    // ── Rule modal ────────────────────────────────────────────────────────────
    const showRuleModal = ref(false)
    const editingRule = ref(null)
    const savingRule = ref(false)
    const ruleModalContext = ref('') // 'vm' | 'cluster' | 'node' | 'secgroup'
    const ruleForm = ref(freshRuleForm())

    function freshRuleForm() {
      return { type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', sport: '', comment: '', enable: 1, moveto: null }
    }

    const openAddVmRuleModal = () => { editingRule.value = null; ruleForm.value = freshRuleForm(); ruleModalContext.value = 'vm'; showRuleModal.value = true }
    const openEditVmRuleModal = (rule) => { editingRule.value = rule; ruleForm.value = ruleToForm(rule); ruleModalContext.value = 'vm'; showRuleModal.value = true }
    const openAddClusterRuleModal = () => { editingRule.value = null; ruleForm.value = freshRuleForm(); ruleModalContext.value = 'cluster'; showRuleModal.value = true }
    const openEditClusterRuleModal = (rule) => { editingRule.value = rule; ruleForm.value = ruleToForm(rule); ruleModalContext.value = 'cluster'; showRuleModal.value = true }
    const openAddNodeRuleModal = () => { editingRule.value = null; ruleForm.value = freshRuleForm(); ruleModalContext.value = 'node'; showRuleModal.value = true }
    const openEditNodeRuleModal = (rule) => { editingRule.value = rule; ruleForm.value = ruleToForm(rule); ruleModalContext.value = 'node'; showRuleModal.value = true }
    const openAddSecGroupRuleModal = () => { editingRule.value = null; ruleForm.value = freshRuleForm(); ruleModalContext.value = 'secgroup'; showRuleModal.value = true }
    const openEditSecGroupRuleModal = (rule) => { editingRule.value = rule; ruleForm.value = ruleToForm(rule); ruleModalContext.value = 'secgroup'; showRuleModal.value = true }

    function ruleToForm(rule) {
      return {
        type: rule.type || 'in',
        action: rule.action || 'ACCEPT',
        proto: rule.proto || '',
        source: rule.source || '',
        dest: rule.dest || '',
        dport: rule.dport || '',
        sport: rule.sport || '',
        comment: rule.comment || '',
        enable: (rule.enable == 1 || rule.enable === true) ? 1 : 0,
        moveto: null,
      }
    }

    const buildPayload = () => {
      const p = { ...ruleForm.value }
      Object.keys(p).forEach(k => { if (p[k] === '' || p[k] === null || p[k] === undefined) delete p[k] })
      return p
    }

    const submitRule = async () => {
      savingRule.value = true
      const payload = buildPayload()
      const pos = editingRule.value?.pos ?? 0
      try {
        if (ruleModalContext.value === 'vm') {
          if (editingRule.value) {
            if (selectedVmType.value === 'lxc') {
              await api.pveNode.updateCtFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, payload)
            } else {
              await api.pveVm.updateFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, payload)
            }
          } else {
            if (selectedVmType.value === 'lxc') {
              await api.pveNode.addCtFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
            } else {
              await api.pveVm.addFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
            }
          }
          await loadVmRules()
        } else if (ruleModalContext.value === 'cluster') {
          if (editingRule.value) {
            await api.pveFirewall.updateClusterFirewallRule(hostId.value, pos, payload)
          } else {
            await api.pveNode.addClusterFirewallRule(hostId.value, payload)
          }
          await loadClusterRules()
        } else if (ruleModalContext.value === 'node') {
          if (editingRule.value) {
            await api.pveFirewall.updateNodeFirewallRule(hostId.value, selectedNode.value, pos, payload)
          } else {
            await api.pveFirewall.addNodeFirewallRule(hostId.value, selectedNode.value, payload)
          }
          await loadNodeRules()
        } else if (ruleModalContext.value === 'secgroup') {
          if (editingRule.value) {
            await api.pveFirewall.updateSecurityGroupRule(hostId.value, selectedSecGroup.value, pos, payload)
          } else {
            await api.pveFirewall.addSecurityGroupRule(hostId.value, selectedSecGroup.value, payload)
          }
          await selectSecGroup(selectedSecGroup.value)
        }
        toast.success(editingRule.value ? 'Rule updated' : 'Rule added')
        showRuleModal.value = false
      } catch (e) {
        toast.error('Failed to save rule')
      } finally {
        savingRule.value = false
      }
    }

    const deleteVmRule = async (pos) => {
      if (!confirm(`Delete firewall rule at position ${pos}?`)) return
      try {
        if (selectedVmType.value === 'lxc') {
          await api.pveNode.deleteCtFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos)
        } else {
          await api.pveVm.deleteFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos)
        }
        toast.success('Rule deleted')
        await loadVmRules()
      } catch (e) { toast.error('Failed to delete rule') }
    }

    const deleteClusterRule = async (pos) => {
      if (!confirm(`Delete cluster firewall rule at position ${pos}?`)) return
      try {
        await api.pveNode.deleteClusterFirewallRule(hostId.value, pos)
        toast.success('Rule deleted')
        await loadClusterRules()
      } catch (e) { toast.error('Failed to delete rule') }
    }

    const deleteNodeRule = async (pos) => {
      if (!confirm(`Delete node firewall rule at position ${pos}?`)) return
      try {
        await api.pveFirewall.deleteNodeFirewallRule(hostId.value, selectedNode.value, pos)
        toast.success('Rule deleted')
        await loadNodeRules()
      } catch (e) { toast.error('Failed to delete rule') }
    }

    const toggleVmRule = async (rule, enabled) => {
      const pos = rule.pos ?? 0
      try {
        if (selectedVmType.value === 'lxc') {
          await api.pveNode.updateCtFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, { enable: enabled ? 1 : 0 })
        } else {
          await api.pveVm.updateFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, { enable: enabled ? 1 : 0 })
        }
        rule.enable = enabled ? 1 : 0
        toast.success(`Rule ${enabled ? 'enabled' : 'disabled'}`)
      } catch (e) { toast.error('Failed to toggle rule'); await loadVmRules() }
    }

    const toggleClusterRule = async (rule, enabled) => {
      const pos = rule.pos ?? 0
      try {
        await api.pveFirewall.updateClusterFirewallRule(hostId.value, pos, { enable: enabled ? 1 : 0 })
        rule.enable = enabled ? 1 : 0
        toast.success(`Rule ${enabled ? 'enabled' : 'disabled'}`)
      } catch (e) { toast.error('Failed to toggle rule'); await loadClusterRules() }
    }

    const toggleNodeRule = async (rule, enabled) => {
      const pos = rule.pos ?? 0
      try {
        await api.pveFirewall.updateNodeFirewallRule(hostId.value, selectedNode.value, pos, { enable: enabled ? 1 : 0 })
        rule.enable = enabled ? 1 : 0
        toast.success(`Rule ${enabled ? 'enabled' : 'disabled'}`)
      } catch (e) { toast.error('Failed to toggle rule'); await loadNodeRules() }
    }

    const toggleSecGroupRule = async (rule, enabled) => {
      const pos = rule.pos ?? 0
      try {
        await api.pveFirewall.updateSecurityGroupRule(hostId.value, selectedSecGroup.value, pos, { enable: enabled ? 1 : 0 })
        rule.enable = enabled ? 1 : 0
        toast.success(`Rule ${enabled ? 'enabled' : 'disabled'}`)
      } catch (e) { toast.error('Failed to toggle rule'); await selectSecGroup(selectedSecGroup.value) }
    }

    const deleteSecGroupRule = async (pos) => {
      if (!confirm(`Delete rule at position ${pos} from security group?`)) return
      try {
        await api.pveFirewall.deleteSecurityGroupRule(hostId.value, selectedSecGroup.value, pos)
        toast.success('Rule deleted')
        await selectSecGroup(selectedSecGroup.value)
      } catch (e) { toast.error('Failed to delete rule') }
    }

    // ── IPSet CRUD ────────────────────────────────────────────────────────────
    const showIpsetModal = ref(false)
    const savingIpset = ref(false)
    const ipsetForm = ref({ name: '', comment: '' })

    const openCreateIpsetModal = () => { ipsetForm.value = { name: '', comment: '' }; showIpsetModal.value = true }

    const createIpset = async () => {
      savingIpset.value = true
      try {
        await api.pveFirewall.createIpset(hostId.value, ipsetForm.value)
        toast.success('IP set created')
        showIpsetModal.value = false
        await loadIpsets()
      } catch (e) { toast.error('Failed to create IP set') } finally { savingIpset.value = false }
    }

    const deleteIpset = async (name) => {
      if (!confirm(`Delete IP set "${name}"? It must be empty first.`)) return
      try {
        await api.pveFirewall.deleteIpset(hostId.value, name)
        toast.success('IP set deleted')
        if (selectedIpsetName.value === name) { selectedIpsetName.value = ''; ipsetEntries.value = [] }
        await loadIpsets()
      } catch (e) { toast.error('Failed to delete IP set') }
    }

    const showCidrModal = ref(false)
    const savingCidr = ref(false)
    const cidrForm = ref({ cidr: '', comment: '', nomatch: false })

    const openAddCidrModal = () => { cidrForm.value = { cidr: '', comment: '', nomatch: false }; showCidrModal.value = true }

    const addCidrToIpset = async () => {
      savingCidr.value = true
      try {
        const payload = { cidr: cidrForm.value.cidr }
        if (cidrForm.value.comment) payload.comment = cidrForm.value.comment
        if (cidrForm.value.nomatch) payload.nomatch = 1
        await api.pveFirewall.addIpsetEntry(hostId.value, selectedIpsetName.value, payload)
        toast.success('CIDR added')
        showCidrModal.value = false
        await selectIpset(selectedIpsetName.value)
      } catch (e) { toast.error('Failed to add CIDR') } finally { savingCidr.value = false }
    }

    const removeIpsetEntry = async (cidr) => {
      if (!confirm(`Remove ${cidr} from ${selectedIpsetName.value}?`)) return
      try {
        await api.pveFirewall.removeIpsetEntry(hostId.value, selectedIpsetName.value, cidr)
        toast.success('Entry removed')
        await selectIpset(selectedIpsetName.value)
      } catch (e) { toast.error('Failed to remove entry') }
    }

    // ── Alias CRUD ────────────────────────────────────────────────────────────
    const showAliasModal = ref(false)
    const savingAlias = ref(false)
    const editingAlias = ref(null)
    const aliasForm = ref({ name: '', cidr: '', comment: '' })

    const openCreateAliasModal = () => { editingAlias.value = null; aliasForm.value = { name: '', cidr: '', comment: '' }; showAliasModal.value = true }
    const openEditAliasModal = (a) => { editingAlias.value = a; aliasForm.value = { name: a.name, cidr: a.cidr, comment: a.comment || '' }; showAliasModal.value = true }

    const submitAlias = async () => {
      savingAlias.value = true
      try {
        if (editingAlias.value) {
          await api.pveFirewall.updateAlias(hostId.value, aliasForm.value.name, { cidr: aliasForm.value.cidr, comment: aliasForm.value.comment, rename: aliasForm.value.name })
          toast.success('Alias updated')
        } else {
          await api.pveFirewall.createAlias(hostId.value, aliasForm.value)
          toast.success('Alias created')
        }
        showAliasModal.value = false
        await loadAliases()
      } catch (e) { toast.error('Failed to save alias') } finally { savingAlias.value = false }
    }

    const deleteAlias = async (name) => {
      if (!confirm(`Delete alias "${name}"?`)) return
      try {
        await api.pveFirewall.deleteAlias(hostId.value, name)
        toast.success('Alias deleted')
        await loadAliases()
      } catch (e) { toast.error('Failed to delete alias') }
    }

    // ── Security Group CRUD ───────────────────────────────────────────────────
    const showSecGroupModal = ref(false)
    const savingSecGroup = ref(false)
    const secGroupForm = ref({ group: '', comment: '' })

    const openCreateSecGroupModal = () => { secGroupForm.value = { group: '', comment: '' }; showSecGroupModal.value = true }

    const createSecGroup = async () => {
      savingSecGroup.value = true
      try {
        await api.pveFirewall.createSecurityGroup(hostId.value, secGroupForm.value)
        toast.success('Security group created')
        showSecGroupModal.value = false
        await loadSecGroups()
      } catch (e) { toast.error('Failed to create security group') } finally { savingSecGroup.value = false }
    }

    const deleteSecGroup = async (name) => {
      if (!confirm(`Delete security group "${name}"?`)) return
      try {
        await api.pveFirewall.deleteSecurityGroup(hostId.value, name)
        toast.success('Security group deleted')
        if (selectedSecGroup.value === name) { selectedSecGroup.value = ''; secGroupRules.value = [] }
        await loadSecGroups()
      } catch (e) { toast.error('Failed to delete security group') }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    const actionBadge = (a) => ({ ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }[a] || 'badge-info')

    onMounted(async () => {
      await loadHosts()
      if (hostId.value) {
        loadVmList()
        loadClusterData()
      }
    })

    return {
      hosts, hostId, onHostChange,
      mainTabs, activeMainTab, switchMainTab,
      clusterSubTabs, activeClusterSubTab, switchClusterSubTab,
      // Cluster
      clusterRules, loadingClusterRules, clusterDirFilter,
      clusterFirewallOptions, clusterOptionsLoaded,
      loadClusterRules, saveClusterOptions, toggleClusterFirewall,
      clusterIpsets, loadingIpsets, selectedIpsetName, ipsetEntries, loadingIpsetEntries,
      selectIpset,
      clusterAliases, loadingAliases,
      securityGroups, loadingSecGroups, selectedSecGroup, secGroupRules, loadingSecGroupRules,
      selectSecGroup,
      // VM/CT
      vmList, loadingVms, selectedVmKey, selectedVmLabel,
      vmRules, loadingVmRules, vmFirewallOptions, savingVmOptions, vmDirFilter,
      onVmSelected, loadVmRules, saveVmFirewallOptions, toggleVmFirewall,
      // Node
      nodeList, loadingNodes, selectedNode,
      nodeRules, loadingNodeRules, nodeFirewallOptions, savingNodeOptions, nodeDirFilter,
      onNodeSelected, loadNodeRules, saveNodeFirewallOptions, toggleNodeFirewall,
      // Rule modal
      showRuleModal, editingRule, savingRule, ruleForm,
      openAddVmRuleModal, openEditVmRuleModal,
      openAddClusterRuleModal, openEditClusterRuleModal,
      openAddNodeRuleModal, openEditNodeRuleModal,
      openAddSecGroupRuleModal, openEditSecGroupRuleModal,
      submitRule,
      deleteVmRule, deleteClusterRule, deleteNodeRule, deleteSecGroupRule,
      toggleVmRule, toggleClusterRule, toggleNodeRule, toggleSecGroupRule,
      // IPSet modal
      showIpsetModal, savingIpset, ipsetForm, openCreateIpsetModal, createIpset, deleteIpset,
      showCidrModal, savingCidr, cidrForm, openAddCidrModal, addCidrToIpset, removeIpsetEntry,
      // Alias modal
      showAliasModal, savingAlias, editingAlias, aliasForm,
      openCreateAliasModal, openEditAliasModal, submitAlias, deleteAlias,
      // Security Group modal
      showSecGroupModal, savingSecGroup, secGroupForm, openCreateSecGroupModal, createSecGroup, deleteSecGroup,
      actionBadge,
    }
  }
}
</script>

<style scoped>
.firewall-manager {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.25rem 0;
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--text-primary);
}

.mb-3 { margin-bottom: 1.25rem; }
.mb-2 { margin-bottom: 0.75rem; }
.p-3 { padding: 1.5rem; }
.p-4 { padding: 2rem; }
.ml-1 { margin-left: 0.25rem; }
.mt-2 { margin-top: 1rem; }
.gap-2 { gap: 0.75rem; }
.flex { display: flex; }

/* Tabs */
.tabs {
  display: flex;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.25rem;
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.6rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover { color: var(--text-primary); }
.tab-btn--active {
  color: var(--color-primary, #3b82f6);
  border-bottom-color: var(--color-primary, #3b82f6);
}

/* Sub-tabs */
.subtabs {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.subtab-btn {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.35rem 0.85rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
}

.subtab-btn:hover { background-color: var(--bg-hover, rgba(0,0,0,0.04)); color: var(--text-primary); }
.subtab-btn.active {
  background-color: var(--color-primary, #3b82f6);
  color: #fff;
  border-color: var(--color-primary, #3b82f6);
}

/* Toolbar card */
.toolbar-card {
  padding: 0.875rem 1.25rem;
}

.toolbar-row {
  display: flex;
  align-items: flex-end;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.15rem;
}

/* Two-panel layout */
.two-panel {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1.25rem;
  align-items: start;
}

.panel-left, .panel-right { min-width: 0; }

/* IPSet list */
.ipset-list {
  display: flex;
  flex-direction: column;
}

.ipset-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 1rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  gap: 0.5rem;
  transition: background-color 0.15s;
}

.ipset-item:hover { background-color: var(--bg-hover, rgba(0,0,0,0.04)); }

.ipset-item.active {
  background-color: rgba(59, 130, 246, 0.08);
  border-left: 3px solid var(--color-primary, #3b82f6);
}

.ipset-item-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.ipset-name { font-weight: 600; font-size: 0.9rem; }

/* Filter grid */
.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.75rem;
}

/* Header with action buttons */
.header-actions-sm {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Action buttons */
.action-btns {
  display: flex;
  gap: 0.3rem;
}

/* Rule disabled styling */
.rule-disabled { opacity: 0.45; }

/* Toggle switches */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  cursor: pointer;
}

.toggle-switch.toggle-sm {
  width: 34px;
  height: 18px;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.toggle-slider {
  position: absolute;
  inset: 0;
  background-color: var(--border-color, #d1d5db);
  border-radius: 24px;
  transition: background-color 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: transform 0.2s;
}

.toggle-switch.toggle-sm .toggle-slider::before {
  height: 12px;
  width: 12px;
  left: 3px;
  bottom: 3px;
}

.toggle-switch input:checked + .toggle-slider { background-color: var(--color-primary, #3b82f6); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }
.toggle-switch.toggle-sm input:checked + .toggle-slider::before { transform: translateX(16px); }

/* Inline toggle label */
.toggle-label-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary);
}

/* Form */
.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group { margin-bottom: 1rem; }
.form-group.mb-0 { margin-bottom: 0; }

.form-control-sm {
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
  width: auto;
  min-width: 130px;
}

.btn-sm { padding: 0.25rem 0.65rem; font-size: 0.875rem; }
.btn-xs { padding: 0.1rem 0.4rem; font-size: 0.75rem; border-radius: 0.25rem; }

/* Text helpers */
.text-success { color: var(--color-success, #22c55e); }
.text-muted { color: var(--text-secondary); }
.text-sm { font-size: 0.85rem; }
.text-center { text-align: center; }
.text-danger { color: var(--color-danger, #ef4444); }

/* Card header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Modal */
.modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card, white);
  border-radius: 0.5rem;
  max-width: 640px;
  width: 90%;
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

.modal-header h3 { margin: 0; }

.btn-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-secondary);
  line-height: 1;
  padding: 0;
}

.modal-body { padding: 1.5rem; }

@media (max-width: 900px) {
  .two-panel { grid-template-columns: 1fr; }
  .toolbar-row { flex-direction: column; align-items: flex-start; }
  .form-row-2 { grid-template-columns: 1fr; }
  .filter-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 600px) {
  .filter-grid { grid-template-columns: 1fr; }
}
</style>
