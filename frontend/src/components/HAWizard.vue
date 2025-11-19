<template>
  <Teleport to="body">
    <div v-if="isOpen" class="wizard-overlay" @click.self="close">
      <div class="wizard-modal">
        <div class="wizard-header">
          <h2>High Availability Setup Wizard</h2>
          <button @click="close" class="close-btn">&times;</button>
        </div>

        <!-- Progress Steps -->
        <div class="wizard-steps">
          <div v-for="(step, index) in steps" :key="index"
               :class="['step', { active: currentStep === index, completed: currentStep > index }]">
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-label">{{ step }}</div>
          </div>
        </div>

        <div class="wizard-body">
          <!-- Step 1: Prerequisites Check -->
          <div v-if="currentStep === 0" class="wizard-step">
            <h3>Checking Prerequisites</h3>
            <p class="step-description">Verifying your cluster is ready for High Availability</p>

            <div v-if="checkingPrerequisites" class="loading">
              <div class="spinner"></div>
              <p>Checking cluster status...</p>
            </div>

            <div v-else-if="prerequisiteResults" class="prerequisite-results">
              <div class="check-item" :class="prerequisiteResults.quorum ? 'success' : 'error'">
                <span class="icon">{{ prerequisiteResults.quorum ? '✓' : '✕' }}</span>
                <div>
                  <strong>Cluster Quorum</strong>
                  <p>{{ prerequisiteResults.quorum ? 'Cluster has quorum - ready for HA' : 'No quorum - HA requires a multi-node cluster' }}</p>
                </div>
              </div>

              <div class="check-item" :class="prerequisiteResults.nodes >= 2 ? 'success' : 'warning'">
                <span class="icon">{{ prerequisiteResults.nodes >= 2 ? '✓' : '⚠' }}</span>
                <div>
                  <strong>Cluster Nodes</strong>
                  <p>{{ prerequisiteResults.nodes }} node(s) detected. {{ prerequisiteResults.nodes >= 2 ? 'Multi-node cluster ready' : 'Single node detected - limited HA functionality' }}</p>
                </div>
              </div>

              <div class="check-item" :class="prerequisiteResults.manager_active ? 'success' : 'warning'">
                <span class="icon">{{ prerequisiteResults.manager_active ? '✓' : '⚠' }}</span>
                <div>
                  <strong>HA Manager</strong>
                  <p>{{ prerequisiteResults.manager_active ? 'HA Manager is active' : 'HA Manager status unclear' }}</p>
                </div>
              </div>

              <div v-if="prerequisiteResults.error" class="error-message">
                {{ prerequisiteResults.error }}
              </div>
            </div>
          </div>

          <!-- Step 2: Create or Select HA Group -->
          <div v-if="currentStep === 1" class="wizard-step">
            <h3>Configure HA Group</h3>
            <p class="step-description">HA groups define which nodes VMs can run on</p>

            <div v-if="groupsMessage" class="info-message">
              <span class="icon">ℹ️</span>
              <p>{{ groupsMessage }}</p>
            </div>

            <div class="form-group">
              <label>
                <input type="radio" v-model="groupMode" value="existing" :disabled="existingGroups.length === 0">
                Use existing HA group {{ existingGroups.length === 0 ? '(none available)' : '' }}
              </label>
            </div>

            <div v-if="groupMode === 'existing' && existingGroups.length > 0" class="group-selection">
              <select v-model="selectedGroup" class="form-control">
                <option :value="null">Select a group...</option>
                <option v-for="group in existingGroups" :key="group.group" :value="group.group">
                  {{ group.group }} ({{ group.nodes }})
                </option>
              </select>
            </div>

            <div class="form-group">
              <label>
                <input type="radio" v-model="groupMode" value="new" :disabled="!canCreateGroups">
                Create new HA group {{ !canCreateGroups ? '(not supported on Proxmox 8+)' : '' }}
              </label>
            </div>

            <div v-if="!canCreateGroups && existingGroups.length === 0" class="form-group">
              <label>
                <input type="radio" v-model="groupMode" value="skip">
                Skip group configuration (Proxmox 8.x - groups managed via web interface)
              </label>
            </div>

            <div v-if="groupMode === 'new'" class="new-group-form">
              <div class="form-group">
                <label class="form-label">Group Name *</label>
                <input v-model="newGroup.name" type="text" class="form-control" placeholder="e.g., production-group" />
                <small class="help-text">Unique identifier for this HA group</small>
              </div>

              <div class="form-group">
                <label class="form-label">Select Nodes *</label>
                <div v-if="loadingNodes" class="loading-inline">
                  <div class="spinner-small"></div>
                  <span>Loading nodes...</span>
                </div>
                <div v-else-if="availableNodes.length === 0" class="empty-state-inline">
                  No nodes available
                </div>
                <div v-else class="node-selection">
                  <label v-for="node in availableNodes" :key="node.id" class="node-checkbox">
                    <input type="checkbox" :value="node.node_name" v-model="selectedNodes">
                    <div class="node-info">
                      <strong>{{ node.node_name }}</strong>
                      <span class="node-status" :class="node.status">{{ node.status }}</span>
                    </div>
                  </label>
                </div>
                <small class="help-text">Select which nodes VMs can run on ({{ selectedNodes.length }} selected)</small>
              </div>

              <div class="form-group">
                <label>
                  <input type="checkbox" v-model="newGroup.restricted">
                  Restricted (VMs can only run on these nodes)
                </label>
              </div>

              <div class="form-group">
                <label>
                  <input type="checkbox" v-model="newGroup.nofailback">
                  No failback (VMs stay on recovery node)
                </label>
              </div>

              <div class="form-group">
                <label class="form-label">Comment (optional)</label>
                <input v-model="newGroup.comment" type="text" class="form-control" placeholder="Description of this group" />
              </div>
            </div>
          </div>

          <!-- Step 3: Select VMs -->
          <div v-if="currentStep === 2" class="wizard-step">
            <h3>Select Virtual Machines</h3>
            <p class="step-description">Choose which VMs to protect with High Availability</p>

            <div v-if="loadingVMs" class="loading">
              <div class="spinner"></div>
              <p>Loading virtual machines...</p>
            </div>

            <div v-else-if="availableVMs.length === 0" class="empty-state">
              <p>No VMs available to add to HA protection</p>
            </div>

            <div v-else class="vm-list">
              <div v-for="vm in availableVMs" :key="vm.vmid" class="vm-item">
                <label class="vm-checkbox">
                  <input type="checkbox" :value="vm.vmid" v-model="selectedVMs">
                  <div class="vm-info">
                    <strong>{{ vm.name || `VM ${vm.vmid}` }}</strong>
                    <span class="vm-details">VMID: {{ vm.vmid }} | Node: {{ vm.node }}</span>
                    <span class="vm-status" :class="vm.status">{{ vm.status }}</span>
                  </div>
                </label>
              </div>
            </div>

            <div v-if="selectedVMs.length > 0" class="selection-summary">
              <strong>{{ selectedVMs.length }}</strong> VM(s) selected for HA protection
            </div>
          </div>

          <!-- Step 4: Configure Policies -->
          <div v-if="currentStep === 3" class="wizard-step">
            <h3>Configure HA Policies</h3>
            <p class="step-description">Set restart and relocation policies for protected VMs</p>

            <div class="form-group">
              <label class="form-label">Default State</label>
              <select v-model="haConfig.state" class="form-control">
                <option value="started">Started (auto-start after failure)</option>
                <option value="stopped">Stopped (don't auto-start)</option>
                <option value="ignored">Ignored (no HA management)</option>
                <option value="disabled">Disabled (temporarily disable HA)</option>
              </select>
              <small class="help-text">How should VMs behave after a node failure</small>
            </div>

            <div class="form-group">
              <label class="form-label">Max Restart Attempts</label>
              <input v-model.number="haConfig.max_restart" type="number" min="0" max="10" class="form-control" />
              <small class="help-text">Maximum times to attempt restarting a failed VM (default: 1)</small>
            </div>

            <div class="form-group">
              <label class="form-label">Max Relocate Attempts</label>
              <input v-model.number="haConfig.max_relocate" type="number" min="0" max="10" class="form-control" />
              <small class="help-text">Maximum times to attempt relocating a VM to another node (default: 1)</small>
            </div>
          </div>

          <!-- Step 5: Review and Confirm -->
          <div v-if="currentStep === 4" class="wizard-step">
            <h3>Review Configuration</h3>
            <p class="step-description">Review your High Availability configuration before applying</p>

            <div class="review-section">
              <h4>HA Group</h4>
              <div class="review-item">
                <strong>Mode:</strong>
                {{ groupMode === 'new' ? 'Create New Group' :
                   groupMode === 'existing' ? 'Use Existing Group' :
                   'Skip (Proxmox 8.x)' }}
              </div>
              <div v-if="groupMode === 'new'" class="review-item">
                <strong>Name:</strong> {{ newGroup.name }}
              </div>
              <div v-if="groupMode === 'new'" class="review-item">
                <strong>Nodes:</strong> {{ selectedNodes.join(', ') }}
              </div>
              <div v-if="groupMode === 'existing'" class="review-item">
                <strong>Group:</strong> {{ selectedGroup || 'None selected' }}
              </div>
              <div v-if="groupMode === 'skip'" class="review-item">
                <strong>Note:</strong> VMs will be added to HA without a group (Proxmox 8.x)
              </div>
            </div>

            <div class="review-section">
              <h4>Protected VMs</h4>
              <div class="review-item">
                <strong>Count:</strong> {{ selectedVMs.length }} VM(s)
              </div>
              <div v-if="selectedVMs.length > 0" class="review-item">
                <strong>VM IDs:</strong> {{ selectedVMs.join(', ') }}
              </div>
            </div>

            <div class="review-section">
              <h4>HA Policies</h4>
              <div class="review-item">
                <strong>State:</strong> {{ haConfig.state }}
              </div>
              <div class="review-item">
                <strong>Max Restart:</strong> {{ haConfig.max_restart }}
              </div>
              <div class="review-item">
                <strong>Max Relocate:</strong> {{ haConfig.max_relocate }}
              </div>
            </div>

            <div v-if="applying" class="loading">
              <div class="spinner"></div>
              <p>Applying HA configuration...</p>
            </div>

            <div v-if="applyResult" class="apply-result">
              <div v-if="applyResult.success" class="success-message">
                <span class="icon">✓</span>
                <p>High Availability configuration applied successfully!</p>
                <ul v-if="applyResult.details && applyResult.details.length > 0">
                  <li v-for="(detail, idx) in applyResult.details" :key="idx">{{ detail }}</li>
                </ul>
              </div>
              <div v-if="applyResult.error" class="error-message">
                <span class="icon">✕</span>
                <p>{{ applyResult.error }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="wizard-footer">
          <button v-if="currentStep > 0 && !applying" @click="previousStep" class="btn btn-secondary">
            Previous
          </button>
          <button v-if="currentStep < steps.length - 1" @click="nextStep" class="btn btn-primary" :disabled="!canProceed">
            Next
          </button>
          <button v-if="currentStep === steps.length - 1 && !applyResult" @click="applyConfiguration" class="btn btn-success" :disabled="applying || !canApply">
            {{ applying ? 'Applying...' : 'Apply Configuration' }}
          </button>
          <button v-if="applyResult && applyResult.success" @click="close" class="btn btn-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { ref, computed, watch } from 'vue'
import api from '@/services/api'

export default {
  name: 'HAWizard',
  props: {
    isOpen: {
      type: Boolean,
      required: true
    }
  },
  emits: ['close', 'complete'],
  setup(props, { emit }) {
    const steps = ['Prerequisites', 'HA Group', 'Select VMs', 'Policies', 'Review']
    const currentStep = ref(0)

    // Step 1: Prerequisites
    const checkingPrerequisites = ref(false)
    const prerequisiteResults = ref(null)

    // Step 2: HA Group
    const groupMode = ref('existing')
    const existingGroups = ref([])
    const selectedGroup = ref(null)
    const groupsMessage = ref(null)
    const canCreateGroups = ref(true)
    const availableNodes = ref([])
    const selectedNodes = ref([])
    const loadingNodes = ref(false)
    const newGroup = ref({
      name: '',
      restricted: false,
      nofailback: false,
      comment: ''
    })

    // Step 3: Select VMs
    const loadingVMs = ref(false)
    const availableVMs = ref([])
    const selectedVMs = ref([])

    // Step 4: Configure Policies
    const haConfig = ref({
      state: 'started',
      max_restart: 1,
      max_relocate: 1
    })

    // Step 5: Apply
    const applying = ref(false)
    const applyResult = ref(null)

    // Check prerequisites when wizard opens
    watch(() => props.isOpen, async (isOpen) => {
      if (isOpen && currentStep.value === 0) {
        await checkPrerequisites()
        await loadExistingGroups()
        await loadNodes()
      }
    })

    const checkPrerequisites = async () => {
      checkingPrerequisites.value = true
      try {
        const response = await api.ha.checkStatus()
        const data = response.data

        prerequisiteResults.value = {
          quorum: data.quorum || false,
          nodes: 1, // Will be updated if we can fetch cluster nodes
          manager_active: data.manager_status === 'active',
          error: data.error || null
        }

        // Try to get node count
        try {
          const hostsResponse = await api.proxmox.listHosts()
          if (hostsResponse.data && hostsResponse.data.length > 0) {
            const hostId = hostsResponse.data[0].id
            const nodesResponse = await api.proxmox.listNodes(hostId)
            prerequisiteResults.value.nodes = nodesResponse.data.length
          }
        } catch (e) {
          console.error('Failed to get node count:', e)
        }
      } catch (error) {
        console.error('Prerequisites check failed:', error)
        prerequisiteResults.value = {
          quorum: false,
          nodes: 0,
          manager_active: false,
          error: error.response?.data?.detail || 'Failed to check prerequisites'
        }
      } finally {
        checkingPrerequisites.value = false
      }
    }

    const loadExistingGroups = async () => {
      try {
        const response = await api.ha.listGroups()
        existingGroups.value = response.data.groups || []

        // Check if there's a migration message (Proxmox 8.x)
        if (response.data.message && response.data.message.includes('migrated to rules')) {
          groupsMessage.value = response.data.message
          canCreateGroups.value = false
          // If no existing groups on Proxmox 8.x, default to skip mode
          if (existingGroups.value.length === 0) {
            groupMode.value = 'skip'
          } else {
            groupMode.value = 'existing'
          }
        } else if (existingGroups.value.length > 0) {
          groupMode.value = 'existing'
        } else {
          groupMode.value = 'new'
        }
      } catch (error) {
        console.error('Failed to load HA groups:', error)
      }
    }

    const loadNodes = async () => {
      loadingNodes.value = true
      try {
        const hostsResponse = await api.proxmox.listHosts()
        if (hostsResponse.data && hostsResponse.data.length > 0) {
          const hostId = hostsResponse.data[0].id
          const nodesResponse = await api.proxmox.listNodes(hostId)
          availableNodes.value = nodesResponse.data || []
        }
      } catch (error) {
        console.error('Failed to load nodes:', error)
      } finally {
        loadingNodes.value = false
      }
    }

    const loadVMs = async () => {
      loadingVMs.value = true
      try {
        const response = await api.vms.list()
        // Filter out VMs that are already in HA
        const haResources = await api.ha.listResources()
        const protectedVMIDs = new Set((haResources.data.resources || []).map(r => {
          const match = r.sid?.match(/vm:(\d+)/)
          return match ? parseInt(match[1]) : null
        }).filter(Boolean))

        availableVMs.value = (response.data || [])
          .filter(vm => vm.vmid && !protectedVMIDs.has(vm.vmid))
          .map(vm => ({
            vmid: vm.vmid,
            name: vm.name,
            node: vm.node_name || 'unknown',
            status: vm.status || 'unknown'
          }))
      } catch (error) {
        console.error('Failed to load VMs:', error)
      } finally {
        loadingVMs.value = false
      }
    }

    const canProceed = computed(() => {
      switch (currentStep.value) {
        case 0:
          return prerequisiteResults.value?.quorum === true
        case 1:
          if (groupMode.value === 'new' && canCreateGroups.value) {
            return newGroup.value.name && selectedNodes.value.length > 0
          } else if (groupMode.value === 'existing') {
            return selectedGroup.value !== null
          } else if (groupMode.value === 'skip') {
            // Allow skipping groups on Proxmox 8.x
            return true
          } else {
            return false
          }
        case 2:
          return selectedVMs.value.length > 0
        case 3:
          return true
        default:
          return false
      }
    })

    const canApply = computed(() => {
      if (selectedVMs.value.length === 0) return false

      if (groupMode.value === 'skip') {
        return true // Allow applying without groups on Proxmox 8.x
      } else if (groupMode.value === 'existing') {
        return selectedGroup.value !== null
      } else if (groupMode.value === 'new') {
        return newGroup.value.name && selectedNodes.value.length > 0
      }

      return false
    })

    const nextStep = async () => {
      if (currentStep.value < steps.length - 1 && canProceed.value) {
        currentStep.value++

        // Load VMs when entering step 3
        if (currentStep.value === 2) {
          await loadVMs()
        }
      }
    }

    const previousStep = () => {
      if (currentStep.value > 0) {
        currentStep.value--
        applyResult.value = null
      }
    }

    const applyConfiguration = async () => {
      applying.value = true
      applyResult.value = null
      const details = []

      try {
        // Step 1: Create HA group if needed
        let targetGroup = null

        if (groupMode.value === 'skip') {
          targetGroup = null // No group for Proxmox 8.x
          details.push('Skipping group configuration (Proxmox 8.x)')
        } else if (groupMode.value === 'existing') {
          targetGroup = selectedGroup.value
        } else if (groupMode.value === 'new' && canCreateGroups.value) {
          try {
            await api.ha.createGroup({
              group: newGroup.value.name,
              nodes: selectedNodes.value.join(','),
              restricted: newGroup.value.restricted ? 1 : 0,
              nofailback: newGroup.value.nofailback ? 1 : 0,
              comment: newGroup.value.comment || null
            })
            targetGroup = newGroup.value.name
            details.push(`Created HA group: ${newGroup.value.name}`)
          } catch (error) {
            throw new Error(`Failed to create HA group: ${error.response?.data?.detail || error.message}`)
          }
        }

        // Step 2: Add VMs to HA protection
        for (const vmid of selectedVMs.value) {
          try {
            const resourceData = {
              sid: `vm:${vmid}`,
              state: haConfig.value.state,
              max_restart: haConfig.value.max_restart,
              max_relocate: haConfig.value.max_relocate
            }

            // Only add group if we have one
            if (targetGroup) {
              resourceData.group = targetGroup
            }

            await api.ha.addResource(resourceData)
            details.push(`Added VM ${vmid} to HA protection${targetGroup ? ` (group: ${targetGroup})` : ''}`)
          } catch (error) {
            details.push(`Failed to add VM ${vmid}: ${error.response?.data?.detail || error.message}`)
          }
        }

        applyResult.value = {
          success: true,
          details: details
        }

        emit('complete')
      } catch (error) {
        applyResult.value = {
          success: false,
          error: error.message || 'Failed to apply configuration'
        }
      } finally {
        applying.value = false
      }
    }

    const close = () => {
      emit('close')
      // Reset wizard state after a delay
      setTimeout(() => {
        currentStep.value = 0
        prerequisiteResults.value = null
        selectedVMs.value = []
        applyResult.value = null
      }, 300)
    }

    return {
      steps,
      currentStep,
      checkingPrerequisites,
      prerequisiteResults,
      groupMode,
      existingGroups,
      selectedGroup,
      groupsMessage,
      canCreateGroups,
      availableNodes,
      selectedNodes,
      loadingNodes,
      newGroup,
      loadingVMs,
      availableVMs,
      selectedVMs,
      haConfig,
      applying,
      applyResult,
      canProceed,
      canApply,
      nextStep,
      previousStep,
      applyConfiguration,
      close
    }
  }
}
</script>

<style scoped>
.wizard-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 2rem;
}

.wizard-modal {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid #e5e7eb;
}

.wizard-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #1f2937;
}

.close-btn {
  background: none;
  border: none;
  font-size: 2rem;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #1f2937;
}

.wizard-steps {
  display: flex;
  justify-content: space-between;
  padding: 2rem 2rem 1rem;
  border-bottom: 1px solid #e5e7eb;
  position: relative;
}

.wizard-steps::before {
  content: '';
  position: absolute;
  top: 2.75rem;
  left: 15%;
  right: 15%;
  height: 2px;
  background: #e5e7eb;
  z-index: 0;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  position: relative;
  z-index: 1;
}

.step-number {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  transition: all 0.3s;
}

.step.active .step-number {
  background: #3b82f6;
  color: white;
}

.step.completed .step-number {
  background: #10b981;
  color: white;
}

.step-label {
  font-size: 0.875rem;
  color: #6b7280;
  text-align: center;
}

.step.active .step-label {
  color: #3b82f6;
  font-weight: 600;
}

.wizard-body {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.wizard-step h3 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
  color: #1f2937;
}

.step-description {
  margin: 0 0 1.5rem;
  color: #6b7280;
}

.loading {
  text-align: center;
  padding: 2rem;
}

.spinner {
  width: 3rem;
  height: 3rem;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.prerequisite-results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.check-item {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #e5e7eb;
}

.check-item.success {
  border-color: #10b981;
  background: #f0fdf4;
}

.check-item.warning {
  border-color: #f59e0b;
  background: #fffbeb;
}

.check-item.error {
  border-color: #ef4444;
  background: #fef2f2;
}

.check-item .icon {
  font-size: 1.5rem;
  font-weight: bold;
}

.check-item.success .icon {
  color: #10b981;
}

.check-item.warning .icon {
  color: #f59e0b;
}

.check-item.error .icon {
  color: #ef4444;
}

.check-item strong {
  display: block;
  margin-bottom: 0.25rem;
  color: #1f2937;
}

.check-item p {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.form-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

.form-control {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 1rem;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.help-text {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.new-group-form {
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  margin-top: 1rem;
}

.vm-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 400px;
  overflow-y: auto;
}

.vm-item {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.vm-item:hover {
  border-color: #3b82f6;
  background: #f9fafb;
}

.vm-checkbox {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  cursor: pointer;
}

.vm-checkbox input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.vm-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.vm-details {
  font-size: 0.875rem;
  color: #6b7280;
}

.vm-status {
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  background: #e5e7eb;
  color: #4b5563;
  align-self: flex-start;
}

.vm-status.running {
  background: #d1fae5;
  color: #065f46;
}

.selection-summary {
  margin-top: 1rem;
  padding: 1rem;
  background: #eff6ff;
  border-radius: 6px;
  text-align: center;
  color: #1e40af;
}

.empty-state {
  text-align: center;
  padding: 3rem 2rem;
  color: #6b7280;
}

.review-section {
  margin-bottom: 2rem;
}

.review-section h4 {
  margin: 0 0 1rem;
  font-size: 1rem;
  color: #1f2937;
  font-weight: 600;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0.5rem;
}

.review-item {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f3f4f6;
}

.review-item strong {
  min-width: 150px;
  color: #6b7280;
}

.success-message {
  padding: 1rem;
  background: #f0fdf4;
  border: 2px solid #10b981;
  border-radius: 8px;
  color: #065f46;
}

.success-message .icon {
  font-size: 1.5rem;
  color: #10b981;
  margin-right: 0.5rem;
}

.success-message ul {
  margin: 1rem 0 0;
  padding-left: 1.5rem;
}

.error-message {
  padding: 1rem;
  background: #fef2f2;
  border: 2px solid #ef4444;
  border-radius: 8px;
  color: #991b1b;
}

.error-message .icon {
  font-size: 1.5rem;
  color: #ef4444;
  margin-right: 0.5rem;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1.5rem 2rem;
  border-top: 1px solid #e5e7eb;
}

.btn {
  padding: 0.625rem 1.25rem;
  border-radius: 6px;
  border: none;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-success {
  background: #10b981;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #059669;
}

/* Node selection styles */
.node-selection {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f9fafb;
}

.node-checkbox {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  cursor: pointer;
  border-radius: 4px;
  background: white;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.node-checkbox:hover {
  border-color: #3b82f6;
  background: #f0f9ff;
}

.node-checkbox input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.node-info {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.node-status {
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  background: #e5e7eb;
  color: #4b5563;
}

.node-status.online {
  background: #d1fae5;
  color: #065f46;
}

.loading-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  color: #6b7280;
}

.spinner-small {
  width: 1rem;
  height: 1rem;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.empty-state-inline {
  padding: 1rem;
  text-align: center;
  color: #6b7280;
  background: #f9fafb;
  border-radius: 6px;
}

.info-message {
  padding: 1rem;
  background: #eff6ff;
  border: 2px solid #3b82f6;
  border-radius: 8px;
  color: #1e40af;
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.info-message .icon {
  font-size: 1.25rem;
}

.info-message p {
  margin: 0;
  flex: 1;
}
</style>
