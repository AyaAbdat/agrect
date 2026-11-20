# QA pass (T20)

Walked the MUST screens in French, Arabic, and English as the demo user, at 1440×900 and 1366×768. Console stayed clear. The only API 404s were `GET /v1/blocks/{id}/stages?year=2026` for a season that has not been started; the stages screen shows that empty state.

| Screen | Language | Issue | Severity | Fixed | File |
| --- | --- | --- | --- | --- | --- |
| Soil and water | FR, AR, EN | "Water left in the soil" used yesterday's balance (106.14 mm) and did not say which day. Today's balance row is 103.83 mm on 20 Nov 2026. | high | yes | `frontend/src/features/soilwater/SoilWaterPage.tsx` |
| Weather | FR, AR, EN | Gust speed was a number with no unit. | medium | yes | `frontend/src/i18n/locales/en.json`, `fr.json`, `ar.json` |
| Today | FR, AR, EN | The irrigate-today dose is calculated and had no source tag. | medium | yes | `frontend/src/features/today/TodayPage.tsx` |
| Blocks map, new-block wizard | FR, AR, EN | Map credit line stays in English (Esri / Leaflet). | low | no | `frontend/src/components/map/SatelliteMap.tsx` |
| Blocks map, new-block wizard | AR | Zoom control stays on the physical left. The map is pinned left-to-right so the tiles are not mirrored. | low | yes | `frontend/src/components/map/SatelliteMap.tsx` |
| Weather, degree days, soil and water | AR | Charts stay left-to-right so the time axis does not reverse. | low | no | `frontend/src/features/weather/charts.tsx`, `frontend/src/features/soilwater/chart.tsx` |
| Soil setup | FR | The compaction label is the English word "Compaction". | low | yes | `frontend/src/i18n/locales/fr.json` |
| New block wizard, opened on an existing block | FR, AR, EN | The crumb still says "New block". | low | yes | `frontend/src/i18n/locales/en.json`, `fr.json`, `ar.json` |
| pytest | — | Starlette `TestClient` warns that `httpx` is deprecated and `httpx2` should be installed. Removing it needs a new dependency. | low | no | `starlette/testclient.py` (installed package) |

Counts: high 1 (fixed 1), medium 2 (fixed 2), low 6 (fixed 3).
