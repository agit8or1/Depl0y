# SECURITY-NPM-AUDIT — Depl0y/frontend

**Date:** 2026-06-08
**Trigger:** npm Shai-Hulud / Mini Shai-Hulud supply-chain incident defensive sweep
**Package manager:** npm 10.9.4 (lockfile-only mode, scripts disabled throughout)

## Files inspected

- `frontend/package.json`
- `frontend/package-lock.json`

No `.npmrc` / `.yarnrc` files present. No nested `package.json`. No `node_modules` directory committed.

## Lifecycle scripts found

In `package.json` — none of the risky lifecycle hooks (`preinstall`, `install`, `postinstall`, `prepack`, `prepare`, `prepublish`, `prepublishOnly`). Only: `dev`, `build`, `deploy`, `preview`, `lint`.

In the lockfile, `hasInstallScript: true` was set on **3** transitive packages — all legitimate native-compile / platform-detection packages:
- `node_modules/esbuild` @ 0.21.5 (build tool, native binary)
- `node_modules/fsevents` @ 2.3.3 (macOS file watcher)
- `node_modules/vue-demi` @ 0.14.10 (Vue 2/3 compatibility shim)

No anomalous install-script packages.

## Supply-chain indicator scan

| Indicator | Result |
|---|---|
| `@tanstack/*` declared or resolved | none |
| `@antv/*` | none |
| `@redhat-cloud-services/*` | none |
| `@mistralai/*` | none |
| `@bitwarden/cli` | none |
| `plain-crypto-js` | none |
| `axios@1.14.1` / `axios@0.30.4` | none (declared `^1.6.2`, resolved 1.15.0 before, audit-fixed to newer 1.15.x) |
| Non-`registry.npmjs.org` resolutions | none — all sha512 from default registry |
| `git+` / `github:` / `file:` / `http://` resolutions | none |

**No obvious supply-chain compromise indicators found.**

## Advisories (npm audit)

### Before
- 5 total: 1 high (axios), 4 moderate (`@vitejs/plugin-vue`, `esbuild`, `uuid`, `vite`).

### After `npm audit fix --package-lock-only --ignore-scripts`
- 3 total: 0 critical, 0 high, 3 moderate.

| Remaining | Severity | Status |
|---|---|---|
| `vite` | moderate | dev-server only; needs Vite 5 → 8 major bump (deferred — runtime not affected) |
| `esbuild` | moderate | dev-server only; resolved by Vite 8 bump |
| `@vitejs/plugin-vue` | moderate | dev-server only; needs plugin 4 → 6 major bump |

The 3 remaining advisories are all in build-tooling that only runs in `npm run dev`; production bundles served from `/opt/depl0y/frontend/dist/` are unaffected. **No critical or high-severity runtime risk remains.**

## Files changed in this audit

- `frontend/package-lock.json` — refreshed via `npm audit fix --package-lock-only --ignore-scripts` (axios, uuid bumped within range; vite/esbuild/@vitejs/plugin-vue left because patch requires major bump)
- `frontend/npm-audit.before.json` — full audit JSON snapshot (pre-fix)
- `frontend/npm-audit.after.json` — full audit JSON snapshot (post-fix)
- `frontend/SECURITY-NPM-AUDIT.md` — this file

## Builds / tests skipped

Per audit policy, **no** `npm install`, `npm run build`, or `npm run lint` was executed during this audit — install scripts were intentionally disabled to avoid running any post-install payload that might be present in a compromised transitive dep. A clean install + smoke test in a sandboxed CI run is recommended before merging.

## Manual follow-ups

1. Schedule the **Vite 5 → 8 + @vitejs/plugin-vue 4 → 6** migration when there's capacity. Dev-server CVEs only; not urgent.
