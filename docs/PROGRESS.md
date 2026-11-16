# AGRECT progress

## Current state

T02a in review

## Done

- T01a repo skeleton, dev PostGIS 5433, /v1/health, Alembic + PostGIS, test vectors, check.ps1
- T01b frontend shell
- T03a backend auth, farm scoping, demo seed
- T03b frontend login, auth guard, logout, JWT secret check
- T04 (22 varieties)
- T05
- T06a
- T06b
- T07a
- T07b
- T07c
- T08a
- T08b
- T18-lite
- demo
- T12a
- T13
- T14a

## Next

T02b server go-live

## Known issues

- Starlette TestClient httpx deprecation warning (harmless)
- T02 deploy deferred (D-023)
- complete check does not require per_tree emitter fields
- bundle > 500 kB (code-split in T19)
- JS bundle 1.6 MB (code-split in T19)

## Acceptance checklist (MUST)

- [ ] weather service with location only
- [ ] GDD base/upper/method per crop with block override
- [x] irrigation logged by run time shows depth and volume matching the registry flow
- [x] water balance matches vectors and recomputes after a backdated entry
- [x] optional soil fields never block saving
- [ ] observed stages as facts and the rest predicted with ranges
- [ ] confirming a stage moves later predictions
- [ ] every test vector passes
- [ ] a block completes with only required fields
