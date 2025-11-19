<template>
  <div class="documentation-page">
    <div class="page-header">
      <h1>📖 Documentation</h1>
      <p>Learn how to use Depl0y and its features</p>
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
      renderedMarkdown,
      viewDoc,
      downloadPDF
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
  color: #10b981;
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
</style>
