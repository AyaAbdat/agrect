#!/usr/bin/env bash
set -euo pipefail

cd /opt/agrect

umask 077
mkdir -p /root/backups
stamp="$(date +%Y%m%d-%H%M)"
out="/root/backups/agrect-${stamp}.sql.gz"
tmp="${out}.partial"
trap 'rm -f "${tmp}"' EXIT

docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  | gzip > "${tmp}"

mv "${tmp}" "${out}"

mapfile -t sorted < <(ls -1t /root/backups/agrect-*.sql.gz)
if (( ${#sorted[@]} > 14 )); then
  rm -f "${sorted[@]:14}"
fi

echo "backup: ${out}"
