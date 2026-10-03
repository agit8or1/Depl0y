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
 */

// ── The app doing the asking ────────────────────────────────────────────────
//
// publicUrl is the GitHub repo on purpose. The project previously advertised
// `depl0y.mspreboot.com`, which does not resolve in public DNS (see
// docs/github-about.md); the repo README is the canonical public landing page.
export const CURRENT_PROJECT = {
  name: 'Depl0y',
  // Short and factually checkable against the README.
  shortDescription:
    'a self-hosted panel that puts every Proxmox cluster and standalone host ' +
    'into one view, with the iDRAC and iLO data for the machines underneath',
  publicUrl: 'https://github.com/agit8or1/Depl0y',
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
// `description` is optional and intentionally omitted where we have no
// confirmed copy — better a bare name and a Visit button than invented claims.
export const OTHER_PROJECTS = [
  {
    name: 'MSP Reboot',
    url: 'https://mspreboot.com',
    // Confirmed wording from the project README.
    description: 'An MSP consulting practice focused on operations, profitability and growth.',
    shareMessage:
      'If you run an MSP or a small business, MSP Reboot is worth a look — ' +
      'consulting focused on operations, profitability and growth. https://mspreboot.com',
  },
  {
    name: 'MSPZero',
    url: 'https://mspzero.com',
    // No confirmed description yet — see HELP_US_GROW notes in the summary.
    description: '',
    shareMessage:
      'Worth a look if you work in or around managed services: https://mspzero.com',
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
