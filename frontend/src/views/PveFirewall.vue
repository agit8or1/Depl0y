<template>
  <div class="pve-firewall-page">
    <div class="page-header mb-2">
      <h2>Firewall</h2>
      <p class="text-muted">Manage firewall rules for host {{ hostId }}</p>
    </div>

    <!-- Scope Selector -->
    <div class="scope-bar card mb-2">
      <div class="scope-bar-inner">
        <div class="scope-group">
          <label class="form-label mb-0">Scope</label>
          <div class="btn-group">
            <button
              :class="['btn', scope === 'cluster' ? 'btn-primary' : 'btn-outline']"
              @click="setScope('cluster')"
            >Cluster</button>
            <button
              :class="['btn', scope === 'vm' ? 'btn-primary' : 'btn-outline']"
              @click="setScope('vm')"
            >VM</button>
          </div>
        </div>

        <div v-if="scope === 'vm'" class="scope-group">
          <label class="form-label mb-0">Virtual Machine</label>
          <div class="vm-select-wrap">
            <select
              v-model="selectedVmKey"
              class="form-control"
              @change="onVmChange"
              :disabled="loadingVms"
            >
              <option value="">{{ loadingVms ? 'Loading VMs...' : '— Select VM —' }}</option>
              <option
                v-for="vm in vmList"
                :key="vm.vmid + '@' + vm.node"
                :value="vm.vmid + '@' + vm.node"
              >{{ vm.name || vm.vmid }} ({{ vm.vmid }}) @ {{ vm.node }}</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar mb-2">
      <button
        :class="['tab-btn', activeTab === 'rules' ? 'active' : '']"
        @click="activeTab = 'rules'"
        v-if="scope === 'cluster' || selectedVmKey"
      >Rules</button>
      <button
        :class="['tab-btn', activeTab === 'options' ? 'active' : '']"
        @click="activeTab = 'options'; fetchVmOptions()"
        v-if="scope === 'vm' && selectedVmKey"
      >Firewall Options</button>
      <button
        :class="['tab-btn', activeTab === 'ipsets' ? 'active' : '']"
        @click="activeTab = 'ipsets'; fetchIpsets()"
        v-if="scope === 'cluster'"
      >IP Sets</button>
      <button
        :class="['tab-btn', activeTab === 'aliases' ? 'active' : '']"
        @click="activeTab = 'aliases'; fetchAliases()"
        v-if="scope === 'cluster'"
      >Aliases</button>
    </div>

    <!-- VM Firewall Options Tab -->
    <div v-if="scope === 'vm' && selectedVmKey && activeTab === 'options'" class="card">
      <div class="card-header">
        <h3>VM Firewall Options</h3>
      </div>
      <div class="card-body">
        <div v-if="loadingOptions" class="loading-spinner"></div>
        <div v-else-if="vmOptions === null" class="text-muted">
          Select a VM to view its firewall options.
        </div>
        <div v-else class="options-grid">
          <div class="option-row">
            <div class="option-label">
              <strong>Firewall Enabled</strong>
              <span class="text-muted text-sm">Enable or disable the VM-level firewall</span>
            </div>
            <div class="option-control">
              <label class="toggle-switch">
                <input
                  type="checkbox"
                  :checked="vmOptions.enable == 1 || vmOptions.enable === true"
                  @change="toggleVmFirewall($event.target.checked)"
                  :disabled="savingOptions"
                />
                <span class="toggle-slider"></span>
              </label>
              <span class="text-sm ml-1">
                {{ (vmOptions.enable == 1 || vmOptions.enable === true) ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
          </div>

          <div class="option-row">
            <div class="option-label">
              <strong>Default Inbound Policy</strong>
              <span class="text-muted text-sm">Action for unmatched inbound traffic</span>
            </div>
            <div class="option-control">
              <select
                v-model="vmOptions.policy_in"
                class="form-control form-control-sm"
                @change="saveVmOptions"
                :disabled="savingOptions"
              >
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
          </div>

          <div class="option-row">
            <div class="option-label">
              <strong>Default Outbound Policy</strong>
              <span class="text-muted text-sm">Action for unmatched outbound traffic</span>
            </div>
            <div class="option-control">
              <select
                v-model="vmOptions.policy_out"
                class="form-control form-control-sm"
                @change="saveVmOptions"
                :disabled="savingOptions"
              >
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- IPSets Tab -->
    <div v-if="scope === 'cluster' && activeTab === 'ipsets'">
      <div class="two-panel-layout">
        <!-- Left: IP Set list -->
        <div class="panel-left">
          <div class="card">
            <div class="card-header">
              <h3>IP Sets</h3>
              <button @click="openCreateIpsetModal" class="btn btn-primary btn-sm">+ New</button>
            </div>
            <div v-if="loadingIpsets" class="loading-spinner p-2"></div>
            <div v-else-if="ipsets.length === 0" class="text-center text-muted" style="padding: 1.5rem;">
              <p>No IP sets defined.</p>
            </div>
            <div v-else class="ipset-list">
              <div
                v-for="is in ipsets"
                :key="is.name"
                :class="['ipset-item', selectedIpset === is.name ? 'active' : '']"
                @click="selectIpset(is.name)"
              >
                <div class="ipset-item-name">{{ is.name }}</div>
                <div class="ipset-item-comment text-sm text-muted">{{ is.comment || '' }}</div>
                <button
                  @click.stop="deleteIpset(is.name)"
                  class="btn btn-danger btn-xs"
                  title="Delete IP set"
                >✕</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: IP Set entries -->
        <div class="panel-right">
          <div class="card">
            <div class="card-header">
              <h3>{{ selectedIpset ? `Entries — ${selectedIpset}` : 'Select an IP Set' }}</h3>
              <button v-if="selectedIpset" @click="openAddCidrModal" class="btn btn-primary btn-sm">+ Add CIDR</button>
            </div>
            <div v-if="!selectedIpset" class="text-center text-muted" style="padding: 2rem;">
              <p>Select an IP set to view its entries.</p>
            </div>
            <div v-else-if="loadingIpsetEntries" class="loading-spinner p-2"></div>
            <div v-else-if="ipsetEntries.length === 0" class="text-center text-muted" style="padding: 1.5rem;">
              <p>No entries. Add a CIDR above.</p>
            </div>
            <div v-else class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>CIDR</th>
                    <th>Comment</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="entry in ipsetEntries" :key="entry.cidr">
                    <td><code>{{ entry.cidr }}</code></td>
                    <td class="text-sm">{{ entry.comment || '—' }}</td>
                    <td>
                      <button @click="removeIpsetEntry(entry.cidr)" class="btn btn-danger btn-sm">Remove</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Aliases Tab -->
    <div v-if="scope === 'cluster' && activeTab === 'aliases'" class="card">
      <div class="card-header">
        <h3>Aliases</h3>
        <button @click="openCreateAliasModal" class="btn btn-primary">+ New Alias</button>
      </div>
      <div v-if="loadingAliases" class="loading-spinner"></div>
      <div v-else-if="aliases.length === 0" class="text-center text-muted" style="padding: 2rem;">
        <p>No aliases defined.</p>
      </div>
      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>IP / CIDR</th>
              <th>Comment</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="alias in aliases" :key="alias.name">
              <td><strong>{{ alias.name }}</strong></td>
              <td><code>{{ alias.cidr }}</code></td>
              <td class="text-sm">{{ alias.comment || '—' }}</td>
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

    <!-- Rules Panel (cluster always visible on rules tab; VM when activeTab === 'rules') -->
    <div v-if="activeTab === 'rules' && (scope === 'cluster' || (scope === 'vm' && selectedVmKey))">
      <div class="two-panel-layout">
        <!-- Left panel: Filter + Import/Export -->
        <div class="panel-left">
          <div class="card mb-2">
            <div class="card-header"><h3>Filter Rules</h3></div>
            <div class="card-body">
              <div class="form-group">
                <label class="form-label">Action</label>
                <select v-model="filter.action" class="form-control form-control-sm">
                  <option value="">All</option>
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="DROP">DROP</option>
                  <option value="REJECT">REJECT</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Source</label>
                <input v-model="filter.source" class="form-control form-control-sm" placeholder="Filter by source..." />
              </div>
              <div class="form-group">
                <label class="form-label">Destination</label>
                <input v-model="filter.dest" class="form-control form-control-sm" placeholder="Filter by dest..." />
              </div>
              <div class="form-group">
                <label class="form-label">Comment</label>
                <input v-model="filter.comment" class="form-control form-control-sm" placeholder="Filter by comment..." />
              </div>
              <button @click="clearFilter" class="btn btn-outline btn-sm mt-1">Clear Filter</button>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><h3>Import / Export</h3></div>
            <div class="card-body">
              <div class="flex-col gap-1">
                <button @click="exportRules" class="btn btn-outline btn-sm w-full">Export as JSON</button>
                <label class="btn btn-outline btn-sm w-full text-center cursor-pointer">
                  Import from JSON
                  <input type="file" accept=".json" @change="importRules" class="hidden" ref="importFileRef" />
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- Right panel: Rules -->
        <div class="panel-right">
          <div class="card">
            <div class="card-header">
              <h3>
                {{ scope === 'cluster' ? 'Cluster' : selectedVmLabel }} Firewall Rules
                <span v-if="filteredRules.length !== rules.length" class="text-sm text-muted ml-1">
                  ({{ filteredRules.length }} of {{ rules.length }})
                </span>
              </h3>
              <button @click="openAddModal" class="btn btn-primary">+ Add Rule</button>
            </div>

            <div v-if="loading" class="loading-spinner"></div>

            <div v-else-if="filteredRules.length === 0" class="text-center text-muted" style="padding: 2rem;">
              <p>{{ rules.length === 0 ? 'No firewall rules configured.' : 'No rules match the current filter.' }}</p>
              <p v-if="rules.length === 0" class="text-sm">Add a rule to control traffic.</p>
            </div>

            <div v-else class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th>Dir</th>
                    <th>Action</th>
                    <th>Protocol</th>
                    <th>Source</th>
                    <th>Destination</th>
                    <th>Ports</th>
                    <th>Comment</th>
                    <th>Enabled</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(rule, index) in filteredRules"
                    :key="rule.pos !== undefined ? rule.pos : index"
                    :class="{ 'rule-disabled': rule.enable == 0 || rule.enable === false }"
                  >
                    <td><strong>{{ rule.pos !== undefined ? rule.pos : index }}</strong></td>
                    <td>
                      <span :class="['badge', rule.type === 'out' ? 'badge-warning' : 'badge-info']">
                        {{ (rule.type || 'in').toUpperCase() }}
                      </span>
                    </td>
                    <td>
                      <span :class="['badge', getActionBadge(rule.action)]">
                        {{ rule.action || '—' }}
                      </span>
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
                    <td class="text-sm">{{ rule.comment || '—' }}</td>
                    <td>
                      <label class="toggle-switch toggle-sm" :title="(rule.enable == 1 || rule.enable === true) ? 'Disable rule' : 'Enable rule'">
                        <input
                          type="checkbox"
                          :checked="rule.enable == 1 || rule.enable === true"
                          @change="toggleRule(rule, $event.target.checked)"
                        />
                        <span class="toggle-slider"></span>
                      </label>
                    </td>
                    <td>
                      <div class="action-btns">
                        <button @click="openEditRuleModal(rule)" class="btn btn-outline btn-sm">Edit</button>
                        <button @click="deleteRule(rule.pos !== undefined ? rule.pos : index)" class="btn btn-danger btn-sm">Del</button>
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

    <!-- Placeholder when VM scope but no VM selected -->
    <div v-if="scope === 'vm' && !selectedVmKey" class="card text-center text-muted" style="padding: 3rem;">
      <p>Select a VM above to manage its firewall rules and options.</p>
    </div>

    <!-- Add / Edit Rule Modal -->
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingRule ? 'Edit Firewall Rule' : 'Add Firewall Rule' }}</h3>
          <button @click="showAddModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="submitRule" class="modal-body">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Direction</label>
              <select v-model="newRule.type" class="form-control">
                <option value="in">IN (Inbound)</option>
                <option value="out">OUT (Outbound)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Action</label>
              <select v-model="newRule.action" class="form-control" required>
                <option value="ACCEPT">ACCEPT</option>
                <option value="DROP">DROP</option>
                <option value="REJECT">REJECT</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Protocol</label>
              <select v-model="newRule.proto" class="form-control">
                <option value="">any</option>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
                <option value="icmp">ICMP</option>
                <option value="tcp_udp">TCP+UDP</option>
              </select>
            </div>
            <div class="form-group flex items-center">
              <label class="form-label toggle-label">
                <input type="checkbox" v-model="newRule.enable" :true-value="1" :false-value="0" />
                <span>Enabled</span>
              </label>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Source IP / CIDR</label>
              <input v-model="newRule.source" class="form-control" placeholder="e.g. 10.0.0.0/8" />
            </div>
            <div class="form-group">
              <label class="form-label">Destination IP / CIDR</label>
              <input v-model="newRule.dest" class="form-control" placeholder="e.g. 192.168.1.0/24" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Source Port</label>
              <input v-model="newRule.sport" class="form-control" placeholder="e.g. 1024:65535" />
            </div>
            <div class="form-group">
              <label class="form-label">Destination Port</label>
              <input v-model="newRule.dport" class="form-control" placeholder="e.g. 80 or 80:90" />
            </div>
          </div>

          <div class="form-group" v-if="editingRule">
            <label class="form-label">Move to Position</label>
            <input v-model.number="newRule.moveto" type="number" class="form-control" placeholder="Leave blank to keep current position" />
          </div>

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newRule.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? (editingRule ? 'Updating...' : 'Adding...') : (editingRule ? 'Update Rule' : 'Add Rule') }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create IPSet Modal -->
    <div v-if="showIpsetModal" class="modal" @click="showIpsetModal = false">
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
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">Create</button>
            <button type="button" @click="showIpsetModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add CIDR to IPSet Modal -->
    <div v-if="showCidrModal" class="modal" @click="showCidrModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add CIDR to {{ selectedIpset }}</h3>
          <button @click="showCidrModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addCidrToIpset" class="modal-body">
          <div class="form-group">
            <label class="form-label">CIDR <span class="text-danger">*</span></label>
            <input v-model="cidrForm.cidr" class="form-control" placeholder="e.g. 192.168.1.0/24 or 10.0.0.5" required />
          </div>
          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="cidrForm.comment" class="form-control" placeholder="Optional" />
          </div>
          <div class="form-group">
            <label class="form-label toggle-label">
              <input type="checkbox" v-model="cidrForm.nomatch" />
              <span>Nomatch (negate — exclude this CIDR)</span>
            </label>
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">Add</button>
            <button type="button" @click="showCidrModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create / Edit Alias Modal -->
    <div v-if="showAliasModal" class="modal" @click="showAliasModal = false">
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
            <input v-model="aliasForm.comment" class="form-control" placeholder="Optional description" />
          </div>
          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ editingAlias ? 'Update' : 'Create' }}
            </button>
            <button type="button" @click="showAliasModal = false" class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'PveFirewall',
  setup() {
    const route = useRoute()
    const toast = useToast()
    const hostId = ref(route.params.hostId)

    // Scope
    const scope = ref('cluster')
    const activeTab = ref('rules')

    // VM list
    const vmList = ref([])
    const loadingVms = ref(false)
    const selectedVmKey = ref(route.query.vmid ? '' : '')  // populated from query if provided

    // Derived VM identity
    const selectedVmId = computed(() => {
      if (!selectedVmKey.value) return null
      return selectedVmKey.value.split('@')[0]
    })
    const selectedVmNode = computed(() => {
      if (!selectedVmKey.value) return null
      return selectedVmKey.value.split('@')[1]
    })
    const selectedVmLabel = computed(() => {
      const vm = vmList.value.find(v => v.vmid + '@' + v.node === selectedVmKey.value)
      return vm ? (vm.name || vm.vmid) : ''
    })

    // Rules
    const rules = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)
    const editingRule = ref(null)

    // Filter
    const filter = ref({ action: '', source: '', dest: '', comment: '' })
    const filteredRules = computed(() => {
      return rules.value.filter(rule => {
        if (filter.value.action && rule.action !== filter.value.action) return false
        if (filter.value.source && !(rule.source || '').toLowerCase().includes(filter.value.source.toLowerCase())) return false
        if (filter.value.dest && !(rule.dest || '').toLowerCase().includes(filter.value.dest.toLowerCase())) return false
        if (filter.value.comment && !(rule.comment || '').toLowerCase().includes(filter.value.comment.toLowerCase())) return false
        return true
      })
    })

    const freshRule = () => ({
      type: 'in',
      action: 'ACCEPT',
      proto: '',
      source: '',
      dest: '',
      dport: '',
      sport: '',
      comment: '',
      enable: 1,
      moveto: null,
    })
    const newRule = ref(freshRule())

    // VM firewall options
    const vmOptions = ref(null)
    const loadingOptions = ref(false)
    const savingOptions = ref(false)

    // IPSets
    const ipsets = ref([])
    const loadingIpsets = ref(false)
    const selectedIpset = ref('')
    const ipsetEntries = ref([])
    const loadingIpsetEntries = ref(false)
    const showIpsetModal = ref(false)
    const showCidrModal = ref(false)
    const ipsetForm = ref({ name: '', comment: '' })
    const cidrForm = ref({ cidr: '', comment: '', nomatch: false })

    // Aliases
    const aliases = ref([])
    const loadingAliases = ref(false)
    const showAliasModal = ref(false)
    const editingAlias = ref(null)
    const aliasForm = ref({ name: '', cidr: '', comment: '' })

    // Import file ref
    const importFileRef = ref(null)

    // ── Scope switching ───────────────────────────────────────────────────────
    const setScope = async (s) => {
      scope.value = s
      activeTab.value = 'rules'
      rules.value = []
      vmOptions.value = null
      if (s === 'cluster') {
        fetchRules()
      } else {
        if (vmList.value.length === 0) {
          await fetchVmList()
        }
        if (selectedVmKey.value) {
          fetchRules()
        }
      }
    }

    // ── VM list ───────────────────────────────────────────────────────────────
    const fetchVmList = async () => {
      loadingVms.value = true
      try {
        const res = await api.pveNode.clusterResources(hostId.value, 'vm')
        const data = res.data || []
        vmList.value = data.filter(r => r.type === 'qemu' || r.type === 'lxc')
          .sort((a, b) => (a.vmid || 0) - (b.vmid || 0))
        // If vmid passed as query param, auto-select
        if (route.query.vmid && route.query.node) {
          const key = `${route.query.vmid}@${route.query.node}`
          if (vmList.value.find(v => v.vmid + '@' + v.node === key)) {
            selectedVmKey.value = key
            fetchRules()
          }
        }
      } catch (err) {
        console.error('Failed to load VM list:', err)
        toast.error('Failed to load VM list')
      } finally {
        loadingVms.value = false
      }
    }

    const onVmChange = () => {
      activeTab.value = 'rules'
      vmOptions.value = null
      rules.value = []
      if (selectedVmKey.value) {
        fetchRules()
      }
    }

    // ── Rules ─────────────────────────────────────────────────────────────────
    const fetchRules = async () => {
      loading.value = true
      try {
        let response
        if (scope.value === 'cluster') {
          response = await api.pveNode.getClusterFirewallRules(hostId.value)
        } else {
          response = await api.pveVm.getFirewallRules(hostId.value, selectedVmNode.value, selectedVmId.value)
        }
        rules.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch firewall rules:', error)
        toast.error('Failed to load firewall rules')
      } finally {
        loading.value = false
      }
    }

    const clearFilter = () => {
      filter.value = { action: '', source: '', dest: '', comment: '' }
    }

    const openAddModal = () => {
      editingRule.value = null
      newRule.value = freshRule()
      showAddModal.value = true
    }

    const openEditRuleModal = (rule) => {
      editingRule.value = rule
      newRule.value = {
        type: rule.type || 'in',
        action: rule.action || 'ACCEPT',
        proto: rule.proto || '',
        source: rule.source || '',
        dest: rule.dest || '',
        dport: rule.dport || '',
        sport: rule.sport || '',
        comment: rule.comment || '',
        enable: rule.enable == 1 || rule.enable === true ? 1 : 0,
        moveto: null,
      }
      showAddModal.value = true
    }

    const submitRule = async () => {
      saving.value = true
      try {
        const payload = { ...newRule.value }
        // Remove empty/null fields
        Object.keys(payload).forEach(k => {
          if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
        })
        if (editingRule.value) {
          const pos = editingRule.value.pos !== undefined ? editingRule.value.pos : 0
          if (scope.value === 'cluster') {
            await api.pveFirewall.updateClusterFirewallRule(hostId.value, pos, payload)
          } else {
            await api.pveVm.updateFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, payload)
          }
          toast.success('Firewall rule updated')
        } else {
          if (scope.value === 'cluster') {
            await api.pveNode.addClusterFirewallRule(hostId.value, payload)
          } else {
            await api.pveVm.addFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
          }
          toast.success('Firewall rule added')
        }
        showAddModal.value = false
        newRule.value = freshRule()
        await fetchRules()
      } catch (error) {
        console.error('Failed to save firewall rule:', error)
        toast.error('Failed to save firewall rule')
      } finally {
        saving.value = false
      }
    }

    const deleteRule = async (pos) => {
      if (!confirm(`Delete firewall rule at position ${pos}?`)) return
      try {
        if (scope.value === 'cluster') {
          await api.pveNode.deleteClusterFirewallRule(hostId.value, pos)
        } else {
          await api.pveVm.deleteFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos)
        }
        toast.success('Rule deleted')
        await fetchRules()
      } catch (error) {
        console.error('Failed to delete rule:', error)
        toast.error('Failed to delete rule')
      }
    }

    const toggleRule = async (rule, enabled) => {
      const pos = rule.pos !== undefined ? rule.pos : 0
      try {
        const payload = { enable: enabled ? 1 : 0 }
        if (scope.value === 'cluster') {
          await api.pveFirewall.updateClusterFirewallRule(hostId.value, pos, payload)
        } else {
          await api.pveVm.updateFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, pos, payload)
        }
        rule.enable = enabled ? 1 : 0
        toast.success(`Rule ${enabled ? 'enabled' : 'disabled'}`)
      } catch (err) {
        toast.error('Failed to toggle rule')
        await fetchRules()
      }
    }

    // ── Export / Import ───────────────────────────────────────────────────────
    const exportRules = () => {
      const data = JSON.stringify(rules.value, null, 2)
      const blob = new Blob([data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `firewall-rules-${hostId.value}-${scope.value}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Rules exported')
    }

    const importRules = async (event) => {
      const file = event.target.files[0]
      if (!file) return
      try {
        const text = await file.text()
        const imported = JSON.parse(text)
        if (!Array.isArray(imported)) {
          toast.error('Invalid import file: expected a JSON array of rules')
          return
        }
        if (!confirm(`Import ${imported.length} rule(s)? Existing rules will NOT be removed.`)) return
        saving.value = true
        let added = 0
        for (const rule of imported) {
          const payload = { ...rule }
          delete payload.pos
          Object.keys(payload).forEach(k => {
            if (payload[k] === '' || payload[k] === null || payload[k] === undefined) delete payload[k]
          })
          try {
            if (scope.value === 'cluster') {
              await api.pveNode.addClusterFirewallRule(hostId.value, payload)
            } else {
              await api.pveVm.addFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
            }
            added++
          } catch (e) {
            console.warn('Failed to import rule:', e)
          }
        }
        toast.success(`Imported ${added} of ${imported.length} rule(s)`)
        await fetchRules()
      } catch (err) {
        toast.error('Failed to import rules: ' + err.message)
      } finally {
        saving.value = false
        if (importFileRef.value) importFileRef.value.value = ''
      }
    }

    // ── VM Firewall Options ───────────────────────────────────────────────────
    const fetchVmOptions = async () => {
      if (!selectedVmKey.value) return
      loadingOptions.value = true
      try {
        const res = await api.pveVm.getFirewallOptions(hostId.value, selectedVmNode.value, selectedVmId.value)
        vmOptions.value = { ...res.data }
      } catch (err) {
        console.error('Failed to fetch VM firewall options:', err)
        toast.error('Failed to load firewall options')
      } finally {
        loadingOptions.value = false
      }
    }

    const saveVmOptions = async () => {
      if (!selectedVmKey.value || !vmOptions.value) return
      savingOptions.value = true
      try {
        await api.pveVm.setFirewallOptions(
          hostId.value,
          selectedVmNode.value,
          selectedVmId.value,
          {
            enable: vmOptions.value.enable ? 1 : 0,
            policy_in: vmOptions.value.policy_in,
            policy_out: vmOptions.value.policy_out
          }
        )
        toast.success('Firewall options saved')
      } catch (err) {
        console.error('Failed to save VM firewall options:', err)
        toast.error('Failed to save firewall options')
      } finally {
        savingOptions.value = false
      }
    }

    const toggleVmFirewall = async (enabled) => {
      if (!vmOptions.value) return
      vmOptions.value.enable = enabled ? 1 : 0
      await saveVmOptions()
    }

    // ── IPSets ────────────────────────────────────────────────────────────────
    const fetchIpsets = async () => {
      loadingIpsets.value = true
      try {
        const res = await api.pveFirewall.listIpsets(hostId.value)
        ipsets.value = res.data || []
      } catch (err) {
        toast.error('Failed to load IP sets')
      } finally {
        loadingIpsets.value = false
      }
    }

    const selectIpset = async (name) => {
      selectedIpset.value = name
      loadingIpsetEntries.value = true
      try {
        const res = await api.pveFirewall.listIpsetEntries(hostId.value, name)
        ipsetEntries.value = res.data || []
      } catch (err) {
        toast.error('Failed to load IP set entries')
      } finally {
        loadingIpsetEntries.value = false
      }
    }

    const openCreateIpsetModal = () => {
      ipsetForm.value = { name: '', comment: '' }
      showIpsetModal.value = true
    }

    const createIpset = async () => {
      saving.value = true
      try {
        await api.pveFirewall.createIpset(hostId.value, ipsetForm.value)
        toast.success('IP set created')
        showIpsetModal.value = false
        await fetchIpsets()
      } catch (err) {
        toast.error('Failed to create IP set')
      } finally {
        saving.value = false
      }
    }

    const deleteIpset = async (name) => {
      if (!confirm(`Delete IP set "${name}"? It must be empty to delete.`)) return
      try {
        await api.pveFirewall.deleteIpset(hostId.value, name)
        toast.success(`IP set "${name}" deleted`)
        if (selectedIpset.value === name) {
          selectedIpset.value = ''
          ipsetEntries.value = []
        }
        await fetchIpsets()
      } catch (err) {
        toast.error('Failed to delete IP set')
      }
    }

    const openAddCidrModal = () => {
      cidrForm.value = { cidr: '', comment: '', nomatch: false }
      showCidrModal.value = true
    }

    const addCidrToIpset = async () => {
      saving.value = true
      try {
        const payload = { cidr: cidrForm.value.cidr }
        if (cidrForm.value.comment) payload.comment = cidrForm.value.comment
        if (cidrForm.value.nomatch) payload.nomatch = 1
        await api.pveFirewall.addIpsetEntry(hostId.value, selectedIpset.value, payload)
        toast.success('CIDR added')
        showCidrModal.value = false
        await selectIpset(selectedIpset.value)
      } catch (err) {
        toast.error('Failed to add CIDR')
      } finally {
        saving.value = false
      }
    }

    const removeIpsetEntry = async (cidr) => {
      if (!confirm(`Remove ${cidr} from ${selectedIpset.value}?`)) return
      try {
        await api.pveFirewall.removeIpsetEntry(hostId.value, selectedIpset.value, cidr)
        toast.success('Entry removed')
        await selectIpset(selectedIpset.value)
      } catch (err) {
        toast.error('Failed to remove entry')
      }
    }

    // ── Aliases ───────────────────────────────────────────────────────────────
    const fetchAliases = async () => {
      loadingAliases.value = true
      try {
        const res = await api.pveFirewall.listAliases(hostId.value)
        aliases.value = res.data || []
      } catch (err) {
        toast.error('Failed to load aliases')
      } finally {
        loadingAliases.value = false
      }
    }

    const openCreateAliasModal = () => {
      editingAlias.value = null
      aliasForm.value = { name: '', cidr: '', comment: '' }
      showAliasModal.value = true
    }

    const openEditAliasModal = (alias) => {
      editingAlias.value = alias
      aliasForm.value = { name: alias.name, cidr: alias.cidr, comment: alias.comment || '' }
      showAliasModal.value = true
    }

    const submitAlias = async () => {
      saving.value = true
      try {
        if (editingAlias.value) {
          await api.pveFirewall.updateAlias(hostId.value, aliasForm.value.name, {
            cidr: aliasForm.value.cidr,
            comment: aliasForm.value.comment,
            rename: aliasForm.value.name,
          })
          toast.success('Alias updated')
        } else {
          await api.pveFirewall.createAlias(hostId.value, aliasForm.value)
          toast.success('Alias created')
        }
        showAliasModal.value = false
        await fetchAliases()
      } catch (err) {
        toast.error(editingAlias.value ? 'Failed to update alias' : 'Failed to create alias')
      } finally {
        saving.value = false
      }
    }

    const deleteAlias = async (name) => {
      if (!confirm(`Delete alias "${name}"?`)) return
      try {
        await api.pveFirewall.deleteAlias(hostId.value, name)
        toast.success('Alias deleted')
        await fetchAliases()
      } catch (err) {
        toast.error('Failed to delete alias')
      }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    const getActionBadge = (action) => {
      const map = { ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }
      return map[action] || 'badge-info'
    }

    onMounted(() => {
      fetchRules()
      // If vmid in query, switch to VM scope
      if (route.query.vmid) {
        setScope('vm')
      }
    })

    return {
      hostId,
      scope,
      activeTab,
      setScope,
      vmList,
      loadingVms,
      selectedVmKey,
      selectedVmLabel,
      onVmChange,
      rules,
      filteredRules,
      filter,
      clearFilter,
      loading,
      saving,
      showAddModal,
      editingRule,
      newRule,
      openAddModal,
      openEditRuleModal,
      submitRule,
      deleteRule,
      toggleRule,
      exportRules,
      importRules,
      importFileRef,
      vmOptions,
      loadingOptions,
      savingOptions,
      fetchVmOptions,
      saveVmOptions,
      toggleVmFirewall,
      getActionBadge,
      // IPSets
      ipsets, loadingIpsets, selectedIpset, ipsetEntries, loadingIpsetEntries,
      showIpsetModal, showCidrModal,
      ipsetForm, cidrForm,
      fetchIpsets, selectIpset,
      openCreateIpsetModal, createIpset, deleteIpset,
      openAddCidrModal, addCidrToIpset, removeIpsetEntry,
      // Aliases
      aliases, loadingAliases,
      showAliasModal, editingAlias, aliasForm,
      fetchAliases,
      openCreateAliasModal, openEditAliasModal, submitAlias, deleteAlias,
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Scope bar */
.scope-bar {
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}

.scope-bar-inner {
  display: flex;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
}

.scope-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.btn-group {
  display: flex;
}

.btn-group .btn {
  border-radius: 0;
}

.btn-group .btn:first-child {
  border-radius: 0.375rem 0 0 0.375rem;
}

.btn-group .btn:last-child {
  border-radius: 0 0.375rem 0.375rem 0;
}

.vm-select-wrap select {
  min-width: 280px;
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1rem;
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

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--color-primary, #3b82f6);
  border-bottom-color: var(--color-primary, #3b82f6);
}

/* Two-panel layout */
.two-panel-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 1.5rem;
  align-items: start;
}

.panel-left, .panel-right {
  min-width: 0;
}

.card-body {
  padding: 1.25rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-control-sm {
  padding: 0.3rem 0.6rem;
  font-size: 0.875rem;
  width: auto;
  min-width: 140px;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.btn-xs {
  padding: 0.1rem 0.4rem;
  font-size: 0.75rem;
  border-radius: 0.25rem;
}

/* Toggle label in form */
.toggle-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  margin-top: 1.75rem;
}

/* Firewall Options */
.options-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
  gap: 1rem;
}

.option-row:last-child {
  border-bottom: none;
}

.option-label {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.option-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

/* Toggle switch */
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

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

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

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--color-primary, #3b82f6);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(20px);
}

.toggle-switch.toggle-sm input:checked + .toggle-slider::before {
  transform: translateX(16px);
}

.ml-1 {
  margin-left: 0.25rem;
}

/* Rule disabled row */
.rule-disabled {
  opacity: 0.5;
}

/* IPSet list */
.ipset-list {
  display: flex;
  flex-direction: column;
}

.ipset-item {
  display: flex;
  align-items: center;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  gap: 0.5rem;
  transition: background-color 0.15s;
}

.ipset-item:hover {
  background-color: var(--bg-hover, rgba(0,0,0,0.04));
}

.ipset-item.active {
  background-color: rgba(59, 130, 246, 0.1);
  border-left: 3px solid var(--color-primary, #3b82f6);
}

.ipset-item-name {
  font-weight: 600;
  flex: 1;
}

.ipset-item-comment {
  flex: 2;
}

/* Action buttons */
.action-btns {
  display: flex;
  gap: 0.3rem;
}

/* Filter sidebar */
.mb-2 {
  margin-bottom: 1rem;
}

/* Import / Export */
.flex-col {
  display: flex;
  flex-direction: column;
}

.gap-1 {
  gap: 0.5rem;
}

.w-full {
  width: 100%;
}

.cursor-pointer {
  cursor: pointer;
}

.hidden {
  display: none;
}

.mt-1 {
  margin-top: 0.5rem;
}

.text-danger {
  color: var(--color-danger, #ef4444);
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
  background: white;
  border-radius: 0.5rem;
  max-width: 640px;
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

.modal-header h3 { margin: 0; }

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

.items-center {
  align-items: center;
}

@media (max-width: 900px) {
  .two-panel-layout {
    grid-template-columns: 1fr;
  }

  .scope-bar-inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .vm-select-wrap select {
    min-width: 220px;
  }
}
</style>
