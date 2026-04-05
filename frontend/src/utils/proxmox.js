/**
 * Utility functions for Proxmox data parsing and formatting.
 */

/**
 * Parse a Proxmox disk string like "local-lvm:vm-100-disk-0,size=32G,format=qcow2,ssd=1"
 * into a structured object.
 */
export function parseProxmoxDisk(str) {
  if (!str) return null
  const result = {
    storage: '',
    volume: '',
    size: '',
    format: '',
    ssd: false,
    cache: '',
    backup: true,
    discard: false,
    iothread: false,
    raw: str,
  }

  const parts = str.split(',')
  const first = parts[0]

  if (first.includes(':')) {
    const [storage, volume] = first.split(':')
    result.storage = storage
    result.volume = volume
  } else {
    result.volume = first
  }

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i]
    if (!part.includes('=')) continue
    const eqIdx = part.indexOf('=')
    const key = part.slice(0, eqIdx)
    const val = part.slice(eqIdx + 1)
    switch (key) {
      case 'size':
        result.size = val
        break
      case 'format':
        result.format = val
        break
      case 'ssd':
        result.ssd = val === '1'
        break
      case 'cache':
        result.cache = val
        break
      case 'backup':
        result.backup = val !== '0'
        break
      case 'discard':
        result.discard = val === 'on' || val === '1'
        break
      case 'iothread':
        result.iothread = val === '1'
        break
      default:
        break
    }
  }

  return result
}

/**
 * Parse a Proxmox NIC string like "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=10,firewall=1"
 * into a structured object.
 */
export function parseProxmoxNIC(str) {
  if (!str) return null
  const result = {
    model: '',
    mac: '',
    bridge: '',
    vlan: '',
    firewall: false,
    rate: '',
    queues: '',
    raw: str,
  }

  const parts = str.split(',')
  const first = parts[0]

  if (first.includes('=')) {
    const eqIdx = first.indexOf('=')
    result.model = first.slice(0, eqIdx)
    result.mac = first.slice(eqIdx + 1)
  } else {
    result.model = first
  }

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i]
    if (!part.includes('=')) continue
    const eqIdx = part.indexOf('=')
    const key = part.slice(0, eqIdx)
    const val = part.slice(eqIdx + 1)
    switch (key) {
      case 'bridge':
        result.bridge = val
        break
      case 'tag':
        result.vlan = val
        break
      case 'firewall':
        result.firewall = val === '1'
        break
      case 'rate':
        result.rate = val
        break
      case 'queues':
        result.queues = val
        break
      default:
        break
    }
  }

  return result
}

/**
 * Format bytes to a human-readable string (KB, MB, GB, TB).
 */
export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return 'N/A'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const idx = Math.min(i, units.length - 1)
  return (bytes / Math.pow(1024, idx)).toFixed(idx === 0 ? 0 : 2) + ' ' + units[idx]
}

/**
 * Format uptime in seconds to "3d 4h 5m".
 */
export function formatUptime(seconds) {
  if (!seconds && seconds !== 0) return 'N/A'
  const s = Math.floor(seconds)
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  const parts = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}m`)
  return parts.join(' ')
}

/**
 * Extract CPU usage percentage from a Proxmox VM status object.
 * The cpu field is a float 0..1 (e.g. 0.023 = 2.3%).
 */
export function cpuPercent(status) {
  if (!status) return 0
  const val = status.cpu ?? status.cpus ?? 0
  // If value is already > 1 it is already a percentage
  if (val > 1) return parseFloat(val.toFixed(1))
  return parseFloat((val * 100).toFixed(1))
}
