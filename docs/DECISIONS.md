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
| D-023 | 2026-11-06 | Deadline moved to Tue 10 Nov 2026 (jury time TBC); T02 deploy deferred until server SSH access is fixed (reinstall with SSH key) | VPS root password lost | - |
| D-024 | 2026-11-06 | One owner per farm in the MVP (farm.owner_user_id); get_current_farm returns 404 for other farms | single "owner" role, no data leak | farm_member table with roles later |
| D-025 | 2026-11-06 | Seed lives in backend/app/seed.py (python -m app.seed); scripts/seed_demo.py will wrap it in T19 | import path simplicity | - |
| D-026 | 2026-11-06 | Tests use a separate database agrect_test created by conftest | dev data stays intact | - |
| D-027 | 2026-11-06 | Decimal values travel as JSON strings ("35.62994"); the frontend parses them only for display | exact decimals end to end | - |
| D-028 | 2026-11-06 | JWT stored in localStorage (agrect.token); 401 clears it and returns to /login | simple MVP auth, one role | httpOnly cookie + refresh token later |
| D-029 | 2026-11-06 | API refuses to start with JWT_SECRET shorter than 32 characters; login runs a dummy hash for unknown emails | security baseline | - |
| D-030 | 2026-11-11 | Deadline moved to Mon 16 Nov 2026 | jury rescheduled | - |
| D-031 | 2026-11-11 | Catalogue names live in the DB in fr/ar/en columns (data), not in the UI locale files | crops can be added without code changes | - |
| D-032 | 2026-11-11 | Soil theta_FC/theta_WP per class = midpoint of the FAO-56 Table 19 range; classes absent from Table 19 are null (Saxton & Rawls by % in T12) | cited values only | - |
| D-033 | 2026-11-11 | pyyaml added for catalogue files | YAML is the catalogue format in the plan | - |
| D-034 | 2026-11-11 | Registry calcs keep full Decimal precision; rounding happens only in API response schemas (trees floor, 2 dp flows/rates, 4 dp areas) | no rounding drift | - |
| D-035 | 2026-11-11 | Row bearing stored in [0, 180) because rows have no direction | 0 = N–S | - |
| D-036 | 2026-11-11 | Optimistic locking with If-Match/ETag on every write to an existing record; reason required after completion | PDF API rules | - |
| D-037 | 2026-11-14 | Scope cut for the Mon 16 Nov jury: growth-stage predictions (T15–T17), Saxton & Rawls % mode, prediction ranges, chill portions, fertigation station, and settings beyond Workspace are phase 2 | time | build after the jury in plan order |
| D-038 | 2026-11-14 | Every registry sub-entity write bumps the parent block version (one ETag per block) | one lock for the wizard | - |
| D-039 | 2026-11-14 | Satellite basemap = Esri World Imagery for the MVP demo, with attribution | free, good imagery for drawing blocks | check the commercial licence before launch (PDF open decision) |
| D-040 | 2026-11-14 | react-leaflet pinned to v4 | v5 requires React 19 | upgrade with React 19 |
| D-041 | 2026-11-14 | Wizard crop chips come from the catalogue (table grape, apple, olive, wheat, barley), not the Figma list (pear, nectarine) | PDF/catalogue wins over the design | - |
| D-042 | 2026-11-14 | Geometry preview through POST /v1/calc/registry/geometry (PostGIS), never computed in the browser | one implementation | - |
| D-043 | 2026-11-15 | Rows in the block are entered, not calculated from the outline (Figma shows Calculated) | time; map split at row is phase 2 | compute from outline width ÷ row spacing later |
| D-044 | 2026-11-15 | Scope cut on 15 Nov: soil profile, water balance, irrigation log and "irrigate today" (T12–T14) move to phase 2 unless time remains after T18 | jury on Mon 16 Nov | first module after the jury |
| D-045 | 2026-11-15 | No scheduler tonight: weather refreshes on read when older than 60 min; APScheduler jobs later | time | add jobs keyed by farm+date |
| D-046 | 2026-11-15 | Single-sine trig uses float math; inputs/outputs Decimal, result quantized to 0.0001 °C·day | Decimal has no trig | - |
| D-047 | 2026-11-15 | Base/upper temperatures and frost/heat thresholds are grower-entered farm settings, not catalogue defaults | no uncited numbers | cited suggestions per crop later |
| D-048 | 2026-11-15 | Open-Meteo past_days=92 instead of the archive API tonight; multi-year history (ranges, averages) later | time | archive API + history_daily |
| D-049 | 2026-11-15 | GDD start date stored per crop setting; start from a growth stage, chosen blocks, target and chill portions are phase 2 | MVP scope | - |
| D-050 | 2026-11-15 | recharts added for weather charts | in the locked stack | - |
| D-051 | 2026-11-16 | Kc is entered per block for now (kc_source "entered"); cited FAO-56 Table 12 suggestions come after agronomist validation | no uncited numbers | stage-based Kc from phenology later |
| D-052 | 2026-11-16 | Soil % mode stored but theta not computed until Saxton & Rawls (2006) is implemented and checked | scientific rigor | T12c |
| D-053 | 2026-11-16 | Balance starts at Dr = 0 on soil.full_on, else on the first weather day (flagged) | no soil sensor in MVP | sensor reset later |
| D-054 | 2026-11-16 | irrigation-today returns both "refill" (Dr + ETc) and "maintain" (ETc) and recommends refill when Dr >= RAW | PDF "gross = ETc (or Dr) / E" | - |
| D-055 | 2026-11-16 | Caddy automatic HTTPS for app.agrect.com with 13.140.215.136.sslip.io as a fallback address | real domain + no-DNS fallback | - |
| D-056 | 2026-11-16 | Migrations and the catalogue loader run at api start (idempotent) | one-command deploy | - |
