/**
 * Form validation rules for Depl0y.
 *
 * Each rule is a function that receives a value and returns:
 *   - true   → valid
 *   - string → error message
 *
 * Factory rules (e.g. maxLength, password) return a rule function when called.
 *
 * Usage with FormField.vue:
 *   :rules="[rules.required, rules.vmName]"
 *
 * Usage standalone:
 *   const err = validate(value, [rules.required, rules.vmName])
 *   if (err !== true) alert(err)
 */

// ── Primitive rules ────────────────────────────────────────────────────────────

export const rules = {
  /** Value must be non-empty (works for strings, numbers, arrays). */
  required: (v) => {
    if (v === null || v === undefined) return 'This field is required'
    if (typeof v === 'string' && !v.trim()) return 'This field is required'
    if (Array.isArray(v) && v.length === 0) return 'This field is required'
    return true
  },

  // ── VM / CT ──────────────────────────────────────────────────────────────

  /** VM/CT ID must be an integer 100–999999999. */
  vmId: (v) => {
    if (v === '' || v === null || v === undefined) return true // optional
    const n = parseInt(v, 10)
    if (isNaN(n)) return 'Must be a number'
    if (n < 100) return 'VM ID must be at least 100'
    if (n > 999999999) return 'VM ID is too large (max 999999999)'
    return true
  },

  /** VM name: 1–63 chars, alphanumeric / hyphen / dot, no spaces. */
  vmName: (v) => {
    if (!v) return 'Required'
    const s = String(v).trim()
    if (!s) return 'Required'
    if (s.length > 63) return 'Maximum 63 characters'
    if (/\s/.test(s)) return 'Name cannot contain spaces'
    if (!/^[a-zA-Z0-9]([a-zA-Z0-9\-.]*[a-zA-Z0-9])?$/.test(s)) {
      return 'Only letters, numbers, hyphens and dots — must start and end with alphanumeric'
    }
    return true
  },

  /** Container hostname: 1–63 chars, alphanumeric / hyphen, no dots. */
  hostname: (v) => {
    if (!v) return 'Required'
    const s = String(v).trim()
    if (!s) return 'Required'
    if (s.length > 63) return 'Maximum 63 characters'
    if (/\s/.test(s)) return 'Hostname cannot contain spaces'
    if (!/^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$/.test(s)) {
      return 'Only letters, numbers and hyphens — must start and end with alphanumeric'
    }
    return true
  },

  // ── Network ───────────────────────────────────────────────────────────────

  /** IPv4 address (optional). */
  ipAddress: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(s)) return 'Invalid IPv4 address'
    const octets = s.split('.')
    for (const o of octets) {
      if (parseInt(o, 10) > 255) return 'Each octet must be 0–255'
    }
    return true
  },

  /** IPv4 CIDR (optional). */
  cidr: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    if (!/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/.test(s)) return 'Invalid CIDR (e.g. 192.168.1.0/24)'
    const [ip, prefix] = s.split('/')
    const octets = ip.split('.')
    for (const o of octets) {
      if (parseInt(o, 10) > 255) return 'Each octet must be 0–255'
    }
    const p = parseInt(prefix, 10)
    if (p < 0 || p > 32) return 'Prefix must be 0–32'
    return true
  },

  /** IPv4 or CIDR (optional) — accepts both 10.0.0.1 and 10.0.0.1/24. */
  ipOrCidr: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    const isCidr = s.includes('/')
    return isCidr ? rules.cidr(s) : rules.ipAddress(s)
  },

  /** MAC address (optional): XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX. */
  macAddress: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    if (!/^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$/.test(s)) {
      return 'Invalid MAC address (e.g. AA:BB:CC:DD:EE:FF)'
    }
    return true
  },

  /** TCP port 1–65535 (optional). */
  port: (v) => {
    if (v === '' || v === null || v === undefined) return true
    const n = parseInt(v, 10)
    if (isNaN(n) || n < 1 || n > 65535) return 'Port must be 1–65535'
    return true
  },

  /** Required TCP port 1–65535. */
  portRequired: (v) => {
    const base = rules.required(v)
    if (base !== true) return base
    return rules.port(v)
  },

  // ── Auth / User ──────────────────────────────────────────────────────────

  /** Email address (optional). */
  email: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) return 'Invalid email address'
    return true
  },

  /** Proxmox API token in "user@realm!tokenname" format (optional). */
  proxmoxToken: (v) => {
    if (!v) return true
    const s = String(v).trim()
    if (!s) return true
    // Allow bare token name (no "!") OR full "user@realm!tokenname"
    if (s.includes('!') && !/^[^@]+@[^!]+![^\s]+$/.test(s)) {
      return 'Token must be in "user@realm!tokenname" format (e.g. root@pam!mytoken)'
    }
    return true
  },

  /** URL starting with http:// or https:// (required). */
  url: (v) => {
    if (!v) return 'Required'
    const s = String(v).trim()
    if (!s) return 'Required'
    try {
      const u = new URL(s.startsWith('http') ? s : `https://${s}`)
      if (!u.hostname) return 'Invalid URL — hostname required'
    } catch {
      return 'Invalid URL format'
    }
    return true
  },

  // ── String / length ───────────────────────────────────────────────────────

  /** Maximum length factory. */
  maxLength: (max) => (v) => {
    if (!v) return true
    return String(v).length <= max || `Maximum ${max} characters`
  },

  /** Minimum length factory. */
  minLength: (min) => (v) => {
    if (!v) return `Minimum ${min} characters`
    return String(v).length >= min || `Minimum ${min} characters`
  },

  /** Password minimum length factory (default 8). */
  password: (min = 8) => (v) => {
    if (!v || String(v).length < min) return `Password must be at least ${min} characters`
    return true
  },

  // ── Numeric ───────────────────────────────────────────────────────────────

  /** Must be a positive integer. */
  positiveInt: (v) => {
    if (v === '' || v === null || v === undefined) return true
    const n = parseInt(v, 10)
    if (isNaN(n) || n < 1) return 'Must be a positive integer'
    return true
  },

  /** Integer range factory — inclusive. */
  intRange: (min, max) => (v) => {
    if (v === '' || v === null || v === undefined) return true
    const n = parseInt(v, 10)
    if (isNaN(n)) return 'Must be a number'
    if (n < min) return `Must be at least ${min}`
    if (n > max) return `Must be at most ${max}`
    return true
  },

  /**
   * Disk size — accepts:
   *   - Plain integer or decimal (interpreted as GiB)
   *   - "32G", "512M", "1T", "500K"
   * Returns true on valid, error string on invalid.
   */
  diskSize: (v) => {
    if (!v && v !== 0) return true
    const s = String(v).trim()
    if (!s) return true
    // Plain number (GB)
    if (/^\d+(\.\d+)?$/.test(s)) {
      if (parseFloat(s) <= 0) return 'Disk size must be greater than 0'
      return true
    }
    // With unit suffix
    if (/^\d+(\.\d+)?[KkMmGgTt]$/.test(s)) return true
    return 'Invalid disk size — use a number (GB) or suffix like 32G, 512M, 1T'
  },

  /**
   * Disk resize delta — accepts "+10G", "+512M", "+1T" or absolute "50G".
   */
  diskResize: (v) => {
    if (!v) return 'Required'
    const s = String(v).trim()
    if (!s) return 'Required'
    if (!/^(\+)?\d+(\.\d+)?[KkMmGgTt]?$/.test(s)) {
      return 'Use format like +10G, 50G, +512M'
    }
    return true
  },
}

// ── Composite helper ──────────────────────────────────────────────────────────

/**
 * Run a value through an array of rules.
 * Returns true if all pass, or the first error message encountered.
 *
 * @param {*} value
 * @param {Array<Function>} rulesArr
 * @returns {true|string}
 */
export function validate(value, rulesArr) {
  for (const rule of rulesArr) {
    const result = rule(value)
    if (result !== true) return result
  }
  return true
}

/**
 * Run multiple field validations at once.
 * Returns an object of { fieldName: errorMessage } for every failing field.
 *
 * @param {Object} fields  — { fieldName: value }
 * @param {Object} schema  — { fieldName: [rule, ...] }
 * @returns {Object}       — { fieldName: errorMessage } (empty if all pass)
 */
export function validateAll(fields, schema) {
  const errors = {}
  for (const [field, rulesArr] of Object.entries(schema)) {
    const result = validate(fields[field], rulesArr)
    if (result !== true) {
      errors[field] = result
    }
  }
  return errors
}
