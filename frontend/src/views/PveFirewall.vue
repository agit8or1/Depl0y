<template>
  <div class="pve-firewall-page">
    <div class="page-header mb-2">
      <h2>Datacenter Firewall</h2>
      <p class="text-muted">Manage cluster-level firewall rules for host {{ hostId }}</p>
    </div>

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
            <h3>Firewall Rules</h3>
            <button @click="showAddModal = true" class="btn btn-primary">+ Add Rule</button>
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
            <div class="form-group">
              <label class="form-label">
                <input type="checkbox" v-model="newRule.enable" :true-value="1" :false-value="0" />
                Enabled
              </label>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Source CIDR</label>
              <input v-model="newRule.source" class="form-control" placeholder="e.g. 10.0.0.0/8" />
            </div>
            <div class="form-group">
              <label class="form-label">Destination CIDR</label>
              <input v-model="newRule.dest" class="form-control" placeholder="e.g. 192.168.1.0/24" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Dest Port (dport)</label>
              <input v-model="newRule.dport" class="form-control" placeholder="e.g. 80 or 80:90" />
            </div>
            <div class="form-group">
              <label class="form-label">Source Port (sport)</label>
              <input v-model="newRule.sport" class="form-control" placeholder="e.g. 1024:65535" />
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useToast } from 'vue-toastification'

export default {
  name: 'PveFirewall',
  setup() {
    const route = useRoute()
    const toast = useToast()
    const hostId = ref(route.params.hostId)
    const rules = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const showAddModal = ref(false)

    const newRule = ref({
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

    const fetchRules = async () => {
      loading.value = true
      try {
        const response = await api.pveNode.getClusterFirewallRules(hostId.value)
        rules.value = response.data || []
      } catch (error) {
        console.error('Failed to fetch firewall rules:', error)
        toast.error('Failed to load firewall rules')
      } finally {
        loading.value = false
      }
    }

    const addRule = async () => {
      saving.value = true
      try {
        const payload = { ...newRule.value }
        // Remove empty fields
        Object.keys(payload).forEach(k => {
          if (payload[k] === '' || payload[k] === null) delete payload[k]
        })
        await api.pveNode.addClusterFirewallRule(hostId.value, payload)
        toast.success('Firewall rule added')
        showAddModal.value = false
        newRule.value = { type: 'in', action: 'ACCEPT', proto: '', source: '', dest: '', dport: '', sport: '', comment: '', enable: 1 }
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
        await api.pveNode.deleteClusterFirewallRule(hostId.value, pos)
        toast.success('Rule deleted')
        await fetchRules()
      } catch (error) {
        console.error('Failed to delete rule:', error)
        toast.error('Failed to delete rule')
      }
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
      rules,
      loading,
      saving,
      showAddModal,
      newRule,
      addRule,
      deleteRule,
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

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

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

@media (max-width: 900px) {
  .two-panel-layout {
    grid-template-columns: 1fr;
  }
}
</style>
