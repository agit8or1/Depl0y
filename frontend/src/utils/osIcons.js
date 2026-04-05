/**
 * OS detection and icon utilities for LXC templates and containers.
 */

export function detectOs(name) {
  const n = (name || '').toLowerCase()
  if (n.includes('ubuntu')) return { name: 'Ubuntu', color: '#E95420', icon: '🟠' }
  if (n.includes('debian')) return { name: 'Debian', color: '#A80030', icon: '🔴' }
  if (n.includes('alpine')) return { name: 'Alpine', color: '#0D597F', icon: '🔵' }
  if (n.includes('centos') || n.includes('rocky') || n.includes('almalinux')) return { name: 'Enterprise Linux', color: '#00843F', icon: '🟢' }
  if (n.includes('fedora')) return { name: 'Fedora', color: '#294172', icon: '🔵' }
  if (n.includes('opensuse') || n.includes('suse')) return { name: 'openSUSE', color: '#73BA25', icon: '🟢' }
  if (n.includes('arch')) return { name: 'Arch', color: '#1793D1', icon: '🔵' }
  if (n.includes('windows')) return { name: 'Windows', color: '#00A4EF', icon: '🔷' }
  if (n.includes('devuan')) return { name: 'Devuan', color: '#404FA2', icon: '🔴' }
  if (n.includes('gentoo')) return { name: 'Gentoo', color: '#54487A', icon: '🔵' }
  if (n.includes('nixos') || n.includes('nix')) return { name: 'NixOS', color: '#5277C3', icon: '🔵' }
  if (n.includes('turnkey')) return { name: 'TurnKey', color: '#2C6FAC', icon: '🔵' }
  return { name: 'Linux', color: '#555', icon: '🐧' }
}

/**
 * Parse a version string out of a template filename.
 * e.g. "ubuntu-22.04-standard_22.04-1_amd64.tar.zst" → "22.04"
 */
export function parseTemplateVersion(filename) {
  const n = (filename || '').toLowerCase()
  // Match patterns like ubuntu-22.04, debian-12, alpine-3.19
  const match = n.match(/[-_](\d+\.\d+(?:\.\d+)?)/)
  return match ? match[1] : ''
}

/**
 * Friendly display name from a template filename.
 * Strips storage prefix, extension, and arch suffix.
 */
export function templateDisplayName(volid) {
  // volid looks like "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
  const fname = (volid || '').split('/').pop()
  // Remove extension
  return fname.replace(/\.(tar\.gz|tar\.xz|tar\.zst|tar\.bz2)$/, '')
}

/**
 * Format a byte count from the pveam 'size' field into a human-readable string.
 * pveam returns size in bytes.
 */
export function formatTemplateSize(bytes) {
  if (!bytes && bytes !== 0) return '—'
  const n = Number(bytes)
  if (n >= 1024 * 1024 * 1024) return (n / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(0) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB'
  return n + ' B'
}
