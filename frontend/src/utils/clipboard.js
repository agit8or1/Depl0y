/**
 * Copy text to the clipboard.
 *
 * Returns `true` only when the copy actually succeeded, so callers can show
 * "Copied!" on success and an explanatory fallback on failure. The previous
 * version returned `true` unconditionally — it ignored `document.execCommand`'s
 * boolean result, so a blocked copy still reported success.
 *
 * Existing callers that do `copyToClipboard(x).then(() => ...)` are unaffected:
 * they ignore the resolved value.
 *
 * @param {string} text
 * @param {{ toast?: boolean }} [opts]
 * @returns {Promise<boolean>} whether the text reached the clipboard
 */
export async function copyToClipboard(text, { toast } = {}) {
  // Preferred path: async Clipboard API. Requires a secure context (HTTPS or
  // localhost) and, in some browsers, an active user gesture.
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      if (toast) window.$toast?.success('Copied to clipboard')
      return true
    } catch {
      // Fall through to the legacy path below.
    }
  }

  // Fallback for non-secure contexts and older browsers.
  try {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.top = '0'
    el.style.left = '0'
    el.style.opacity = '0'
    document.body.appendChild(el)

    // iOS Safari ignores .select() on a readonly textarea without an explicit range.
    el.focus()
    el.select()
    el.setSelectionRange(0, text.length)

    const ok = document.execCommand('copy')
    document.body.removeChild(el)

    if (ok && toast) window.$toast?.success('Copied to clipboard')
    if (!ok && toast) window.$toast?.error('Could not copy — please copy manually')
    return ok
  } catch {
    if (toast) window.$toast?.error('Could not copy — please copy manually')
    return false
  }
}
