# npm supply-chain audit — agit8or1 public repos

**Date:** 2026-06-08
**Auditor:** Claude Code (Opus 4.7) on behalf of agit8or1
**Trigger:** Active npm supply-chain incident (Shai-Hulud / Mini Shai-Hulud style; reports of compromised packages across `@tanstack/*`, `@mistralai/*`, `@antv/*`, `@redhat-cloud-services/*` namespaces; postinstall-payload credential stealers; `axios` 1.14.1 / 0.30.4 backdoored)
**Tooling:** node 22.21.1, npm 10.9.4, pnpm 11.5.2 (via corepack)
**Constraints applied:** no `npm install` / `pnpm install` without `--ignore-scripts`; lockfile-only mode wherever possible; no build/test execution; no production touching; no `--force`.

## Repos inspected

| Repo | npm ecosystem? | Package manager | Action | Notes |
|---|---|---|---|---|
| **Depl0y** | yes | npm | audited + fixed | single `frontend/` project, Vite SPA |
| **St0r** | yes | npm | audited + fixed; generated missing lockfile in `agent/` | 3 sub-projects (agent / backend / frontend) — `agent/` had no lockfile, now has one |
| **rem0te** | yes | pnpm | audited + fixed | pnpm-workspace monorepo: root + types + launcher + api + web |
| **clientst0r** | no | — | skipped | Python project, no JS files |
| **OPNMGR** | no | — | skipped | PHP project, no JS files |

## Static risk scan — known indicators

Searched every `package.json` and every lockfile for:
`@tanstack/*`, `@antv/*`, `@redhat-cloud-services/*`, `@mistralai/*`, `@bitwarden/cli`, `plain-crypto-js`, `axios@1.14.1`, `axios@0.30.4`, packages with declared lifecycle scripts, non-default registry resolutions, git/tarball URL resolutions.

**Findings:**
- No `@antv/*`, `@redhat-cloud-services/*`, `@mistralai/*`, `@bitwarden/cli`, `plain-crypto-js` declared in any package.
- **One `@tanstack/*` hit:** `@tanstack/react-query@^5.59.20` in `rem0te/apps/web` — resolved to `5.90.21`. This is a current stable release, **not** in any known compromised version window. No remediation needed for this package itself; flagged for awareness only.
- **No `axios@1.14.1` or `axios@0.30.4`** anywhere. Versions found:
  - Depl0y/frontend: `1.15.0` (declared `^1.6.2`) → audit-fixed to a newer 1.15.x
  - St0r/backend: `1.16.1` (declared `^1.13.1`)
  - St0r/frontend: `1.16.1` (declared `^1.6.2`)
  - rem0te/apps/web: was `1.13.6`, now `1.17.0` (declared bumped from `^1.7.7` to `^1.17.0`) — `1.13.6` was affected by ~12 patched CVEs (SSRF / prototype-pollution / header injection / etc.), all resolved in 1.15.2+.
- **No top-level `preinstall/install/postinstall/prepack/prepare/prepublish*` scripts** in any of the 9 inspected `package.json` files.
- **Lockfile-level install scripts** were limited to well-known native-compile packages: `esbuild`, `fsevents`, `vue-demi`, `bcrypt`, `cpu-features`, `sqlite3`, `ssh2`. No anomalous install-script packages.
- **All lockfile resolutions point to `registry.npmjs.org`** with sha512 integrity hashes. No `git+`, `github:`, `file:`, or alternate-tarball resolutions in any lockfile.
- **No `.npmrc` / `.yarnrc` / `.yarnrc.yml`** files anywhere — no token leakage risk in committed files.

**Conclusion on supply-chain indicators:** no obvious indicators of the current Shai-Hulud campaign in any of the three affected repos. The audit still proceeded with full lockfile refresh + advisory fixes as defense-in-depth.

## Audit results (advisory counts)

### Depl0y — `frontend/`
| | Before | After |
|---|---|---|
| critical | 0 | 0 |
| high | 1 (axios) | 0 |
| moderate | 4 (vite, esbuild, @vitejs/plugin-vue, uuid) | 3 (vite/esbuild/@vitejs/plugin-vue) |
| **total** | **5** | **3** |

**Remaining (3 moderate):** all dev-tool only — `vite@5.x`, `esbuild@0.21.x`, `@vitejs/plugin-vue@5.x`. CVEs only affect the local dev server's behaviour (`npm run dev`), not production builds. Patching requires Vite **5 → 8** major bump (`@vitejs/plugin-vue 4 → 6`); deferred to a separate migration ticket — not a runtime risk.

### St0r — `agent/`, `backend/`, `frontend/`
| Project | Before | After | Notes |
|---|---|---|---|
| `agent/` | (no lockfile) → 0 | 0 | Lockfile was missing — generated with `npm install --package-lock-only --ignore-scripts`. |
| `backend/` | 3 moderate (qs / body-parser / express) | 0 | |
| `frontend/` | 2 moderate (react-router / react-router-dom) | 0 | |

### rem0te — pnpm workspace
| | Before | After |
|---|---|---|
| critical | 1 (Next.js middleware auth bypass) | 0 |
| high | 26 | 6 |
| moderate | 40 | 11 |
| low | 5 | 2 |
| **total advisories** | **72** | **19** |

**Critical** (CVE Next.js middleware authorization bypass) is resolved by bumping `next` from pinned `14.2.18` → `14.2.35` (latest secure 14.2.x release).

**Remaining 19 advisories** all fall into one of two buckets:
1. **Requires Next.js 15.x major upgrade** (14 of 19 next-related findings). Patched only in 15.x; Next 14 → 15 is a major migration (React 19 alignment, new caching semantics) — **explicitly deferred** to a separate task per the audit rule "Avoid broad pnpm update --latest unless required and explain why".
2. **Deep transitive deps** (`fast-uri`, `flatted`, `glob`, `lodash`, `path-to-regexp`, `picomatch`, `brace-expansion`, `ajv`, `qs`, `file-type`, `esbuild`, `vite`) pulled in via `@nestjs/cli`, `eslint`, `eslint-config-next`, `tailwindcss`. Direct fix would require either: (a) major bumps in those direct dev/build deps, or (b) `pnpm.overrides` injection. Both have non-trivial blast radius and were deferred.

## What got changed

| Repo | Files modified | New files |
|---|---|---|
| Depl0y | `frontend/package-lock.json` | `frontend/SECURITY-NPM-AUDIT.md`, `frontend/npm-audit.before.json`, `frontend/npm-audit.after.json` |
| St0r | `backend/package-lock.json`, `frontend/package-lock.json` | `agent/package-lock.json` (new), `agent/SECURITY-NPM-AUDIT.md`, `backend/SECURITY-NPM-AUDIT.md`, `frontend/SECURITY-NPM-AUDIT.md`, `agent/npm-audit.{before,after}.json`, `backend/npm-audit.{before,after}.json`, `frontend/npm-audit.{before,after}.json` |
| rem0te | `pnpm-lock.yaml`, `apps/api/package.json`, `apps/web/package.json`, `apps/launcher/package.json`, `package.json` | `SECURITY-NPM-AUDIT.md`, `pnpm-audit.before.json`, `pnpm-audit.after.json` |

**Production files NOT touched** — server installs at `/opt/depl0y/`, etc. remain on prior bundles.

## What needs manual review

- **Depl0y/frontend:** plan Vite 5 → 8 + `@vitejs/plugin-vue` 4 → 6 migration. Low urgency (dev-server-only CVEs) but worth a separate PR to clear the audit cleanly.
- **rem0te/apps/web:** plan Next.js 14 → 15 migration. Higher urgency — clears 14 remaining advisories including high-severity SSRF/DoS variants. Requires React 19 alignment, caching-API review.
- **rem0te (general):** evaluate `pnpm.overrides` for the deep transitives (`lodash@^4.17.24`, `glob@^10.5.0`, `picomatch@^4.0.4`, `path-to-regexp@^8.4.0`, `brace-expansion@^2.0.2`, `fast-uri@^3.1.2`, `flatted@^3.4.2`). Adds maintenance burden, but cheap individually.
- **St0r/agent:** new lockfile is now in place — schedule a clean-install CI run with `--ignore-scripts` first to verify no postinstall has been silently relied upon.

## Credentials/tokens — rotation guidance

No tokens were found in any committed file (`.npmrc`, `.yarnrc`, `.yarnrc.yml` are absent from all repos). No `_authToken` or `npmRegistryServer` overrides in any repo. **No credential rotation indicated by this audit.** Independently of this audit:
- A prior GitHub PAT (`ghp_faUGfW…`) was embedded in the depl0y origin URL until 2026-06-08; that one was rotated; the replacement is now stored in a 0600 git credential file. If you ever pushed those repos to a CI runner that logged the remote URL, treat the old PAT as compromised and confirm it's been revoked at github.com/settings/tokens.

## Branches pushed

- `chore/npm-supply-chain-audit-2026-06` on:
  - github.com/agit8or1/Depl0y
  - github.com/agit8or1/St0r
  - github.com/agit8or1/rem0te

`clientst0r` and `OPNMGR` had no npm ecosystem and were not touched.
