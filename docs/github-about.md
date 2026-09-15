# GitHub "About" settings

The repository sidebar is set through **Settings → General** and the **About**
gear on the repository home page — not from files in the tree. This page is the
source of truth for what those fields should contain; copy from here.

---

## Short description

Repository description (≤ 350 characters, product value first):

```
Proxmox infrastructure and server hardware management in one dashboard. Manage multiple Proxmox clusters and sites side by side, with integrated iDRAC/iLO health, power and firmware inventory over Redfish. Self-hosted, MIT licensed.
```

## Website

Currently **blank**.

A dedicated product website should take this slot when one exists, because it
serves visitors better than a general link. Until then, leave it empty or point
it at the repository's own documentation:

```
https://github.com/agit8or1/Depl0y#readme
```

> The URL previously configured here, `https://depl0y.mspreboot.com/`, does not
> resolve in public DNS, so it is not a usable project website. Do not restore it
> until the hostname resolves and serves the project site. `deploy.agit8or.net`
> is a running Depl0y instance rather than a project page, so it is not a
> substitute either.
>
> `https://mspreboot.com` resolves and is linked from the README, the screenshot
> gallery and the walkthrough end card. It is the maintainer's consulting
> practice rather than a Depl0y product page, so it is a poor fit for the About
> URL — keep it as an in-content link.

## Topics

```
proxmox
proxmox-ve
virtualization
infrastructure-management
self-hosted
homelab
datacenter-management
idrac
ilo
redfish
bmc
out-of-band-management
vm-management
power-management
fastapi
vue
python
```

`cloud-init` and `dashboard` were dropped from the earlier set in favour of
`infrastructure-management` and `out-of-band-management`. Both are accurate and
there is room for them again if wanted (GitHub allows 20).

## Sidebar toggles

| Setting | Value |
|---|---|
| Releases | shown |
| Packages | hidden |
| Deployments | hidden |

## Social preview image

Settings → General → Social preview. Use
`docs/images/github/infrastructure-dashboard-dark.png` — 1920×1080, which crops
cleanly to GitHub's 1280×640 card.

---

## Checklist for a maintainer

- [x] Description replaced with the text above — applied 2026-09-15
- [x] Website cleared until a real project site resolves — applied 2026-09-15
- [x] Topics set to the list above — applied 2026-09-15
- [ ] Social preview uploaded — **manual only**, GitHub exposes no API for it
- [ ] Walkthrough video attached to a GitHub release, and the README video
      section enabled (see `scripts/screenshots/README.md`)
