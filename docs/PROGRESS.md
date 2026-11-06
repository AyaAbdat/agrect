# AGRECT progress

## Current state

T01b in review

## Done

- T01a repo skeleton, dev PostGIS 5433, /v1/health, Alembic + PostGIS, test vectors, check.ps1

## Next

T02 deploy skeleton (needs VPS IP), else T03 auth + farm

## Known issues

- Starlette TestClient httpx deprecation warning (harmless)

## Acceptance checklist (MUST)

- [ ] weather service with location only
- [ ] GDD base/upper/method per crop with block override
- [ ] irrigation by run time matches registry flow
- [ ] water balance matches vectors and recomputes after backdated entry
- [ ] optional soil fields never block
- [ ] observed stages as facts and the rest predicted with ranges
- [ ] confirming a stage moves later predictions
- [ ] every test vector passes
- [ ] a block completes with only required fields
