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

    <!-- Tab Bar (VM scope only) -->
    <div v-if="scope === 'vm' && selectedVmKey" class="tab-bar mb-2">
      <button
        :class="['tab-btn', activeTab === 'rules' ? 'active' : '']"
        @click="activeTab = 'rules'"
      >Rules</button>
      <button
        :class="['tab-btn', activeTab === 'options' ? 'active' : '']"
        @click="activeTab = 'options'; fetchVmOptions()"
      >Firewall Options</button>
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

    <!-- Rules Panel (cluster always, VM when activeTab === 'rules') -->
    <div v-if="scope === 'cluster' || (scope === 'vm' && selectedVmKey && activeTab === 'rules')">
      <div class="two-panel-layout">
        <!-- Left panel: IPSets & Aliases -->
        <div class="panel-left">
          <div class="card">
            <div class="card-header">
              <h3>IPSets &amp; Aliases</h3>
            </div>
            <div class="card-body text-center text-muted">
              <p style="padding: 2rem 1rem;">IPSet and alias management coming soon.</p>
            </div>
          </div>
        </div>

        <!-- Right panel: Rules -->
        <div class="panel-right">
          <div class="card">
            <div class="card-header">
              <h3>
                {{ scope === 'cluster' ? 'Cluster' : selectedVmLabel }} Firewall Rules
              </h3>
              <button @click="openAddModal" class="btn btn-primary">+ Add Rule</button>
            </div>

            <div v-if="loading" class="loading-spinner"></div>

            <div v-else-if="rules.length === 0" class="text-center text-muted" style="padding: 2rem;">
              <p>No firewall rules configured.</p>
              <p class="text-sm">Add a rule to control traffic.</p>
            </div>

            <div v-else class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>Pos</th>
                    <th>Direction</th>
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
                  <tr v-for="(rule, index) in rules" :key="index">
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
                      <span :class="['badge', rule.enable == 1 || rule.enable === true ? 'badge-success' : 'badge-danger']">
                        {{ rule.enable == 1 || rule.enable === true ? 'Yes' : 'No' }}
                      </span>
                    </td>
                    <td>
                      <button @click="deleteRule(rule.pos !== undefined ? rule.pos : index)" class="btn btn-danger btn-sm">Delete</button>
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

    <!-- Add Rule Modal -->
    <div v-if="showAddModal" class="modal" @click="showAddModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Firewall Rule</h3>
          <button @click="showAddModal = false" class="btn-close">×</button>
        </div>
        <form @submit.prevent="addRule" class="modal-body">
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

          <div class="form-group">
            <label class="form-label">Comment</label>
            <input v-model="newRule.comment" class="form-control" placeholder="Optional description" />
          </div>

          <div class="flex gap-1 mt-2">
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? 'Adding...' : 'Add Rule' }}
            </button>
            <button type="button" @click="showAddModal = false" class="btn btn-outline">Cancel</button>
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
    const selectedVmKey = ref('')  // "vmid@node"

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

    const freshRule = () => ({
      type: 'in',
      action: 'ACCEPT',
      proto: '',
      source: '',
      dest: '',
      dport: '',
      sport: '',
      comment: '',
      enable: 1
    })
    const newRule = ref(freshRule())

    // VM firewall options
    const vmOptions = ref(null)
    const loadingOptions = ref(false)
    const savingOptions = ref(false)

    // ----------------------------------------------------------------
    // Scope switching
    // ----------------------------------------------------------------
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
        // If a VM was previously selected, reload its rules
        if (selectedVmKey.value) {
          fetchRules()
        }
      }
    }

    // ----------------------------------------------------------------
    // VM list
    // ----------------------------------------------------------------
    const fetchVmList = async () => {
      loadingVms.value = true
      try {
        const res = await api.pveNode.clusterResources(hostId.value, 'vm')
        const data = res.data || []
        // clusterResources returns array; filter to only qemu/lxc
        vmList.value = data.filter(r => r.type === 'qemu' || r.type === 'lxc')
          .sort((a, b) => (a.vmid || 0) - (b.vmid || 0))
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

    // ----------------------------------------------------------------
    // Rules
    // ----------------------------------------------------------------
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

    const openAddModal = () => {
      newRule.value = freshRule()
      showAddModal.value = true
    }

    const addRule = async () => {
      saving.value = true
      try {
        const payload = { ...newRule.value }
        // Remove empty fields
        Object.keys(payload).forEach(k => {
          if (payload[k] === '' || payload[k] === null) delete payload[k]
        })
        if (scope.value === 'cluster') {
          await api.pveNode.addClusterFirewallRule(hostId.value, payload)
        } else {
          await api.pveVm.addFirewallRule(hostId.value, selectedVmNode.value, selectedVmId.value, payload)
        }
        toast.success('Firewall rule added')
        showAddModal.value = false
        newRule.value = freshRule()
        await fetchRules()
      } catch (error) {
        console.error('Failed to add firewall rule:', error)
        toast.error('Failed to add firewall rule')
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

    // ----------------------------------------------------------------
    // VM Firewall Options
    // ----------------------------------------------------------------
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

    const getActionBadge = (action) => {
      const map = { ACCEPT: 'badge-success', DROP: 'badge-danger', REJECT: 'badge-warning' }
      return map[action] || 'badge-info'
    }

    onMounted(() => {
      fetchRules()
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
      loading,
      saving,
      showAddModal,
      newRule,
      openAddModal,
      addRule,
      deleteRule,
      vmOptions,
      loadingOptions,
      savingOptions,
      fetchVmOptions,
      saveVmOptions,
      toggleVmFirewall,
      getActionBadge
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
  padding: 1.5rem;
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

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--color-primary, #3b82f6);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(20px);
}

.ml-1 {
  margin-left: 0.25rem;
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
