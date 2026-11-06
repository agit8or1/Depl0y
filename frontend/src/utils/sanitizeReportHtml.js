import DOMPurify from 'dompurify'

// The report renderer never emits form controls; dropping them stops an
// LLM-written report from showing a convincing fake login form.
const FORBID_TAGS = ['form', 'input', 'button', 'textarea', 'select', 'option']

// Sanitize server-rendered AI report HTML before it is bound with v-html. The
// backend escapes report text, but the narrative is LLM-produced, so scripts,
// event handlers and javascript: URLs are stripped here as well. `purifier`
// lets tests pass a DOMPurify instance bound to a jsdom window.
export function sanitizeReportHtml (raw, purifier = DOMPurify) {
  if (!raw) return ''
  return purifier.sanitize(raw, { USE_PROFILES: { html: true }, FORBID_TAGS })
}
