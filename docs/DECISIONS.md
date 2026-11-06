# Decisions

| ID | Date | Decision | Why | Migration path |
| --- | --- | --- | --- | --- |
| D-001 | 2026-11-04 | TimescaleDB hypertables -> plain Postgres tables, same columns, composite PK (farm_id, ts) + indexes | MVP time | convert to hypertables later, no app change |
| D-002 | 2026-11-04 | Message bus -> in-process dispatcher in core/events.py with the PDF event names | MVP time | swap in a bus; handlers already separate |
| D-003 | 2026-11-04 | Row-level security -> farm_id on every farm-owned row + get_current_farm dependency on every query | MVP time | Postgres RLS later |
| D-004 | 2026-11-04 | Offline mobile app/outbox/idempotency keys -> online PWA; keep version column and record_version | MVP time | mobile later |
| D-005 | 2026-11-04 | Weather station ingest -> service only (weather_source=service); station tables and source columns kept | MVP time | station adapters later |
| D-006 | 2026-11-04 | Calcs mirrored in the app -> server only; UI previews via POST /v1/calc/... | one implementation, no drift | - |
| D-007 | 2026-11-04 | Alerts engine and SMS -> not built; forecast frost/heat warnings from farm thresholds on Today (stretch) | MVP time | engine later |
| D-008 | 2026-11-04 | Scouting, labour, equipment, inputs & cost, counts -> not built; operations and harvest are stretch | MVP time | phase 2 |
| D-009 | 2026-11-04 | Weather service = Open-Meteo (forecast + archive), values labelled Estimated | no key, FAO-56 ET0 included | commercial use needs a licence (PDF open decision) |
| D-010 | 2026-11-04 | Dev DB host port 5433 | 5431 taken by another project | - |
| D-011 | 2026-11-04 | pydantic-settings for env config | Pydantic v2 companion package | - |
| D-012 | 2026-11-04 | Alembic autogenerate ignores spatial_ref_sys and tiger/tiger_data/topology schemas; geoalchemy2 alembic_helpers used | PostGIS image creates them | - |
| D-013 | 2026-11-04 | psycopg[binary] | no local libpq on Windows | - |
| D-014 | 2026-11-04 | Desktop Figma frames (D-xx, docs/agrect-desktop.md) supersede the PDF's mobile frame IDs | latest design | - |
| D-015 | 2026-11-04 | T01 split into T01a (backend/infra) and T01b (frontend shell) | 45-minute task limit | - |
| D-016 | 2026-11-04 | Language switcher in the avatar menu and on the login card | the design has no language control; the jury must switch FR/AR/EN | - |
| D-017 | 2026-11-04 | Fonts: Inter + Noto Sans Arabic via Google Fonts, system-ui fallback | Inter has no Arabic glyphs | self-host fonts in T19 (PWA) |
| D-018 | 2026-11-04 | Tailwind v4 (@tailwindcss/vite) and React Router v7 (`react-router` package, declarative mode) on React 18 | current versions compatible with the locked stack | - |
| D-019 | 2026-11-04 | Drawer opens at the inline end (right in FR/EN, left in AR) | RTL mirroring | - |
| D-020 | 2026-11-04 | shadcn/ui on the Base UI ("nova") preset instead of Radix | `shadcn init -d` now scaffolds Next.js; this preset keeps Vite | - |
| D-021 | 2026-11-04 | react-router pinned to v7 | v8 requires React 19; React 18 is locked | upgrade with React 19 later |
| D-022 | 2026-11-04 | TypeScript pinned to 5.9; ESLint (flat config, typescript-eslint) instead of oxlint | TS 7 drops baseUrl and is unsupported by typescript-eslint; ESLint is the locked linter | revisit when typescript-eslint supports TS 7 |
