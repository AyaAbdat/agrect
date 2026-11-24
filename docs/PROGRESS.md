# AGRECT progress

## Current state

T28 in review

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
- T14b
- T02a live at https://app.agrect.com
- T19
- T15
- T16a
- T16b
- T17
- T21
- 20 Nov deploy, commit 1f18e25
- T22
- T23a
- T23b
- T24
- T25
- T26
- T27

## Next

phase 2 continues

## Known issues

- Starlette TestClient httpx deprecation warning (harmless)
- T02 deploy deferred (D-023)
- complete check does not require per_tree emitter fields

## Acceptance checklist (MUST)

- [x] weather service with location only
- [x] GDD base/upper/method per crop with block override
- [x] irrigation logged by run time shows depth and volume matching the registry flow
- [x] water balance matches vectors and recomputes after a backdated entry
- [x] optional soil fields never block saving
- [x] observed stages as facts and the rest predicted with ranges
- [x] confirming a stage moves later predictions
- [x] every test vector passes
- [x] a block completes with only required fields
- [x] a harvest entered as crates, bins, tonnes or per valve, rows or trees gives the same kg/ha as the test vectors
- [x] a harvest inside a product's pre-harvest interval shows a warning
