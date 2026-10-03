/**
 * Shared "Help Us Grow" configuration.
 *
 * This is the ONE place to edit project names, URLs and share copy. It is
 * deliberately free of Vue/app-specific imports so the same file can be copied
 * verbatim into sibling apps — only `CURRENT_PROJECT` changes per app.
 *
 * Rules for editing:
 *   - Only add URLs that have been confirmed to resolve publicly.
 *   - `publicUrl` must be the canonical PUBLIC page for the project. Never a
 *     dashboard, tenant, localhost or token-bearing URL — this value is what
 *     gets shared and posted.
 *   - Do not describe a project as free, open source or MIT licensed unless
 *     that is confirmed for that specific project.
 *
 * Descriptions below are taken from each project's own public page (verified
 * 2026-10-03, all returning HTTP 200), not written from assumption.
 */

// ── The app doing the asking ────────────────────────────────────────────────
//
// publicUrl is the product page on mspzero.com rather than the GitHub repo: it
// is the canonical public website for Depl0y and reads better when shared with
// someone non-technical. The repo stays below as `repoUrl` for the star action.
// (The project previously advertised `depl0y.mspreboot.com`, which does not
// resolve in public DNS — see docs/github-about.md. Do not reinstate it.)
export const CURRENT_PROJECT = {
  name: 'Depl0y',
  // Wording from the product page's own meta description.
  shortDescription:
    'every Proxmox cluster, and the hardware underneath it, on one page — ' +
    'self-hosted and MIT licensed',
  publicUrl: 'https://mspzero.com/tools/depl0y',
  repoUrl: 'https://github.com/agit8or1/Depl0y',
}

// ── Sponsorship ─────────────────────────────────────────────────────────────
// Verified against .github/FUNDING.yml (`github: agit8or1`) and the existing
// Support/About pages. Set to null to hide the Sponsor section entirely.
export const SPONSOR_URL = 'https://github.com/sponsors/agit8or1'

// ── GitHub ──────────────────────────────────────────────────────────────────
export const GITHUB_PROFILE_URL = 'https://github.com/agit8or1'

// ── Other projects to cross-promote ─────────────────────────────────────────
//
// MSP Reboot and MSPZero lead the list deliberately. The four tools after them
// are the rest of the MSPZero stack (Depl0y is the fifth and is omitted here
// because it is the current project).
export const OTHER_PROJECTS = [
  {
    name: 'MSP Reboot',
    url: 'https://mspreboot.com',
    description: 'An MSP consulting practice focused on operations, profitability and growth.',
    shareMessage:
      'If you run an MSP or a small business, MSP Reboot is worth a look — ' +
      'consulting focused on operations, profitability and growth. https://mspreboot.com',
  },
  {
    name: 'MSPZero',
    url: 'https://mspzero.com',
    description:
      'Free, open-source tools for MSP documentation, firewalls, infrastructure, ' +
      'backups and remote support. Use one, several or all five.',
    shareMessage:
      'MSPZero is a set of five free, open-source, MIT-licensed tools for MSPs — ' +
      'documentation, firewalls, infrastructure, backups and remote support. ' +
      'Use one, several or all five: https://mspzero.com',
  },
  {
    name: 'clientst0r',
    url: 'https://mspzero.com/tools/clientst0r',
    description: 'Client documentation, assets, credentials and tickets in one database.',
    shareMessage:
      'clientst0r keeps client documentation, assets, credentials and tickets in ' +
      'one database — free, open source and self-hosted: https://mspzero.com/tools/clientst0r',
  },
  {
    name: 'OPNMGR',
    url: 'https://mspzero.com/tools/opnmgr',
    description:
      'Watch firewall health, configuration drift, backups and staged updates across customers.',
    shareMessage:
      'OPNMGR watches OPNsense firewall health, configuration drift, backups and ' +
      'staged updates across customers — free, open source and self-hosted: ' +
      'https://mspzero.com/tools/opnmgr',
  },
  {
    name: 'St0r',
    url: 'https://mspzero.com/tools/st0r',
    description:
      'Endpoint status, file recovery and offsite replication for UrBackup, in one interface.',
    shareMessage:
      'St0r puts UrBackup endpoint status, file recovery and offsite replication in ' +
      'one interface — free, open source and self-hosted: https://mspzero.com/tools/st0r',
  },
  {
    name: 'rem0te',
    url: 'https://mspzero.com/tools/rem0te',
    description:
      'Customer-separated remote access and an audit trail around your own RustDesk server.',
    shareMessage:
      'rem0te adds customer-separated remote access and an audit trail around your ' +
      'own RustDesk server — free, open source and self-hosted: https://mspzero.com/tools/rem0te',
  },
]

// Ready-to-copy message for promoting the wider network of projects.
export const NETWORK_SHARE_MESSAGE =
  'Know an MSP or business owner looking for useful tools and IT services? ' +
  'Check out https://mspreboot.com and https://mspzero.com, and pass them ' +
  'along to someone who could use them.'

// ── The business behind the projects ────────────────────────────────────────
export const BUSINESS = {
  name: 'MSP Reboot',
  url: 'https://mspreboot.com',
  facebookUrl: 'https://facebook.com/mspreboot',
  shareMessage:
    'If you need IT services or know someone who does, MSP Reboot is worth a ' +
    'call: https://mspreboot.com',
}

/**
 * The suggested share message for this project.
 * Kept as a function so the name/description/URL can never drift apart.
 */
export function buildProjectShareMessage(project = CURRENT_PROJECT) {
  return `Check out ${project.name}: ${project.shortDescription}. ` +
    `If it looks useful, give it a try and pass it along! ${project.publicUrl}`
}
