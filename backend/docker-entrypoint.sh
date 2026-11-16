#!/bin/bash
set -euo pipefail

cd /srv/agrect/backend

uv run python -c 'import os, sys, time
import psycopg

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
deadline = time.monotonic() + 60
last_error = None
ready = False
while time.monotonic() < deadline:
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        ready = True
        break
    except psycopg.Error as exc:
        last_error = exc
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(2.0, remaining))
if not ready:
    print(f"database not ready after 60s: {last_error}", file=sys.stderr)
    raise SystemExit(1)
'

uv run alembic upgrade head
uv run python -m app.modules.catalog.loader
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" --workers 2
