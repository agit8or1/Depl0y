<template>
  <div class="bug-report-page">
    <div class="page-header">
      <h1>Report a Bug</h1>
      <p class="subtitle">Help us improve Depl0y by reporting issues you encounter</p>
    </div>

    <div class="card">
      <form @submit.prevent="submitReport" class="bug-report-form">
        <div class="form-section">
          <h3>Bug Information</h3>

          <div class="form-group">
            <label class="form-label required">Subject</label>
            <input
              v-model="formData.subject"
              type="text"
              required
              class="form-control"
              placeholder="Brief description of the issue"
            />
          </div>

          <div class="form-group">
            <label class="form-label required">Description</label>
            <textarea
              v-model="formData.description"
              required
              rows="8"
              class="form-control"
              placeholder="Detailed description of what happened, steps to reproduce, expected vs actual behavior..."
            ></textarea>
            <p class="help-text">Please be as detailed as possible to help us understand and fix the issue</p>
          </div>

          <div class="form-group">
            <label class="form-label">Error Details (optional)</label>
            <textarea
              v-model="formData.error_details"
              rows="6"
              class="form-control code-input"
              placeholder="Paste any error messages, console logs, or stack traces here..."
            ></textarea>
            <p class="help-text">Check your browser console (F12) for any error messages</p>
          </div>
        </div>

        <div class="form-section">
          <h3>Automatically Captured Information</h3>

          <div class="info-grid">
            <div class="info-item">
              <label class="info-label">Page URL</label>
              <code class="info-value">{{ formData.page_url }}</code>
            </div>
            <div class="info-item">
              <label class="info-label">Browser</label>
              <code class="info-value">{{ browserInfo }}</code>
            </div>
          </div>
        </div>

        <div class="form-actions">
          <button
            type="button"
            @click="$router.go(-1)"
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            :disabled="submitting"
            class="btn btn-primary"
          >
            {{ submitting ? 'Submitting...' : 'Submit Bug Report' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import api from '../services/api'

export default {
  name: 'BugReport',
  setup() {
    const router = useRouter()
    const toast = useToast()

    const submitting = ref(false)
    const formData = ref({
      subject: '',
      description: '',
      error_details: '',
      page_url: '',
      browser_info: ''
    })

    const browserInfo = computed(() => {
      return navigator.userAgent
    })

    onMounted(() => {
      formData.value.page_url = document.referrer || window.location.href
      formData.value.browser_info = browserInfo.value
    })

    const submitReport = async () => {
      submitting.value = true
      try {
        await api.bugReport.submit({
          subject: formData.value.subject,
          description: formData.value.description,
          error_details: formData.value.error_details || null,
          page_url: formData.value.page_url,
          browser_info: formData.value.browser_info
        })

        toast.success('Bug report submitted successfully! Thank you for your feedback.')

        // Reset form
        formData.value = {
          subject: '',
          description: '',
          error_details: '',
          page_url: document.referrer || window.location.href,
          browser_info: browserInfo.value
        }

        // Navigate back after short delay
        setTimeout(() => {
          router.go(-1)
        }, 1500)
      } catch (error) {
        console.error('Failed to submit bug report:', error)
        toast.error('Failed to submit bug report. Please try again later.')
      } finally {
        submitting.value = false
      }
    }

    return {
      formData,
      browserInfo,
      submitting,
      submitReport
    }
  }
}
</script>

<style scoped>
.bug-report-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
}

.page-header h1 {
  margin: 0 0 0.5rem 0;
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  font-size: 1rem;
  color: var(--text-secondary);
}

.card {
  background: white;
  border-radius: 0.5rem;
  box-shadow: var(--shadow-md);
  padding: 2rem;
}

.bug-report-form {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-section h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--border-color);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.form-label.required::after {
  content: ' *';
  color: #ef4444;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.code-input {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.8rem;
  background-color: #f9fafb;
}

.help-text {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  background-color: #f9fafb;
  border-radius: 0.375rem;
  border: 1px solid var(--border-color);
}

.info-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.info-value {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.8rem;
  color: var(--text-primary);
  word-break: break-all;
  background-color: white;
  padding: 0.5rem;
  border-radius: 0.25rem;
  border: 1px solid var(--border-color);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-secondary {
  background-color: white;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background-color: #f9fafb;
}

.btn-primary {
  background-color: #ef4444;
  color: white;
}

.btn-primary:hover {
  background-color: #dc2626;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .card {
    padding: 1.5rem;
  }

  .form-actions {
    flex-direction: column;
  }

  .btn {
    width: 100%;
  }
}
</style>
