# Security review — 2026-10-02

## Changes

- Only access JWTs authorize HTTP and console sessions. Refresh tokens can no longer be reused as API bearer tokens; WebSockets honor token-version revocation and inactive accounts.
- Host-id routes enforce assigned-host permissions on direct requests. Viewing requires can_view; changing resources requires operator role plus can_manage/can_admin. Node shells require can_admin. Global administrators retain access.
- Console tickets require host management permission; cluster join material requires a global administrator.
- Console TLS connections honor the host verify_ssl setting. Token jti values prevent identical refresh tokens issued in the same second.
- Refresh the frontend lockfile to patched versions allowed by its manifest.

## Validation

From backend, install the existing requirements and run:

```sh
python -m pytest tests/test_security_authorization.py -q
```

15 offline tests passed using SQLite, real JWT verification, FastAPI requests and mocked Proxmox. Frontend production build passed. No live Proxmox operations were performed.

## Rollout

Build the frontend with npm ci && npm run build, and restart the backend through the normal deployment procedure. Review host assignments before rollout: operators/viewers who previously relied on unassigned direct URLs will receive 403. Assign only the required host privileges. If verify_ssl is enabled, ensure the system trusts the Proxmox CA and the certificate matches the node connection address. No schema migration is required.

## Remaining scope

The shared router guard covers host_id path parameters; collection endpoints and routes keyed only by a VM/body ID retain their existing controls. This is not a claim of complete resource-level authorization coverage. Paramiko 3.5.1 still matches a low-severity SHA-1 advisory with no patched version listed by OSV. AutoAddPolicy in existing SSH workflows requires a separate host-key enrollment design; it is not silently replaced in this patch.
