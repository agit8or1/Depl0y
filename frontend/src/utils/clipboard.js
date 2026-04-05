export async function copyToClipboard(text, { toast } = {}) {
  try {
    await navigator.clipboard.writeText(text)
    if (toast) window.$toast?.success('Copied to clipboard')
    return true
  } catch {
    // Fallback for non-HTTPS or older browsers
    const el = document.createElement('textarea')
    el.value = text
    el.style.position = 'fixed'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
    if (toast) window.$toast?.success('Copied')
    return true
  }
}
