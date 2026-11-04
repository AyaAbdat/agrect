# AGRECT

Prerequisites: Docker Desktop, Python 3.12, uv, PowerShell 5.1.

Dev start, from the repo root, one command per line:

    docker compose up -d
    cd backend
    uv run uvicorn app.main:app --reload --port 8000

Run checks from the repo root:

    ./scripts/check.ps1
