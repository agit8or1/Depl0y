/**
 * Sharing helpers built on native browser features only — no new dependencies.
 *
 * Nothing here posts, sends or publishes anything on the user's behalf. The
 * native share sheet and the per-network URLs both open a composer that the
 * user reviews and submits themselves.
 */

/** Whether the native share sheet is usable (mostly mobile + Safari). */
export function canNativeShare() {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function'
}

/**
 * Offer the native share sheet.
 *
 * @returns {Promise<'shared'|'dismissed'|'unsupported'|'failed'>}
 *   'dismissed' is a normal outcome (the user closed the sheet) and must not be
 *   reported as an error.
 */
export async function nativeShare({ title, text, url }) {
  if (!canNativeShare()) return 'unsupported'
  try {
    await navigator.share({ title, text, url })
    return 'shared'
  } catch (err) {
    // AbortError means the user closed the sheet — not a failure worth surfacing.
    if (err?.name === 'AbortError') return 'dismissed'
    return 'failed'
  }
}

/**
 * Per-network share composer URLs.
 *
 * LinkedIn and Facebook only accept a URL and pull their own preview text, so
 * the message cannot be prefilled there — that is a platform limitation, not an
 * omission here.
 */
export function shareTargets({ url, text, subject }) {
  const u = encodeURIComponent(url)
  const t = encodeURIComponent(text)
  return {
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${u}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
    x: `https://x.com/intent/tweet?text=${t}`,
    email: `mailto:?subject=${encodeURIComponent(subject)}&body=${t}`,
  }
}

/**
 * Open a share composer in a new tab.
 * `mailto:` must stay in the same tab or the mail client may not launch.
 */
export function openShareWindow(href) {
  if (href.startsWith('mailto:')) {
    window.location.href = href
    return
  }
  window.open(href, '_blank', 'noopener,noreferrer')
}
