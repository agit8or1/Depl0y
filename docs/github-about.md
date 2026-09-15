# GitHub "About" settings

The repository sidebar is set through **Settings → General** and the **About**
gear on the repository home page — not from files in the tree. This page is the
source of truth for what those fields should contain; copy from here.

---

## Short description

Use this as the repository description (≤ 350 characters, no emoji-led sentence,
product value first):

```
Proxmox infrastructure and server hardware management in one dashboard. Manage multiple Proxmox clusters and sites side by side, with integrated iDRAC/iLO health, power and firmware inventory over Redfish. Self-hosted, MIT licensed.
```

## Website

Leave the **Website** field **blank**, or point it at the repository's own
documentation:

```
https://github.com/agit8or1/Depl0y#readme
```

> The URL previously configured here, `https://depl0y.mspreboot.com/`, does not
> resolve in public DNS, so it is not a usable project website. Do not restore it
> until the hostname resolves and serves the project site. `deploy.agit8or.net`
> is a running Depl0y instance rather than a project page, so it is not a
> substitute.

## Topics

Set exactly these topics (GitHub allows up to 20; these are all accurate for
what the code does):

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

## Sidebar toggles

| Setting | Value |
|---|---|
| Releases | shown |
| Packages | hidden |
| Deployments | hidden |
| Include in the home page | Description, Website (if set), Topics |

## Social preview image

Settings → General → Social preview. Use
`docs/images/github/01-infrastructure-overview.png` — it is 1920×1080, which
crops cleanly to GitHub's 1280×640 card.

---

## Checklist for a maintainer

- [ ] Description replaced with the text above
- [ ] Website cleared (or repointed) until a real project site resolves
- [ ] Topics set to the list above
- [ ] Social preview uploaded
- [ ] `v2.2.74` release notes reference the new README sections if useful
