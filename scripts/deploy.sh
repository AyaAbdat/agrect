#!/usr/bin/env bash
set -euo pipefail

cd /opt/agrect

if [[ ! -f .env.prod ]]; then
  echo "missing .env.prod (copy .env.prod.example and set secrets)" >&2
  exit 1
fi

git pull --ff-only
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

deadline=$((SECONDS + 120))
status="missing"
while true; do
  cid="$(docker compose --env-file .env.prod -f docker-compose.prod.yml ps -q api)"
  if [[ -n "${cid}" ]]; then
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${cid}" 2>/dev/null || true)"
    if [[ "${status}" == "healthy" ]]; then
      break
    fi
  fi
  if (( SECONDS >= deadline )); then
    echo "api did not become healthy within 120s (status: ${status})" >&2
    exit 1
  fi
  sleep 2
done

docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T api uv run python -m app.seed

site_line="$(grep -E '^SITE_ADDRESS=' .env.prod | tail -n 1 | cut -d= -f2-)"
site_line="${site_line//$'\r'/}"
site_line="${site_line#\"}"
site_line="${site_line%\"}"
site_line="${site_line#\'}"
site_line="${site_line%\'}"

echo "Site addresses:"
echo "${site_line}" | tr ',' '\n' | while IFS= read -r addr; do
  addr="${addr#"${addr%%[![:space:]]*}"}"
  addr="${addr%"${addr##*[![:space:]]}"}"
  if [[ -n "${addr}" ]]; then
    printf 'https://%s\n' "${addr}"
  fi
done
