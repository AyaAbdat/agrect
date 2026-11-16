# Paths under /srv/agrect keep REPO_ROOT (config.py: parents[3]).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_FROZEN=1 \
    HOME=/home/agrect \
    UV_CACHE_DIR=/home/agrect/.cache/uv

RUN useradd --create-home --uid 1000 agrect \
    && mkdir -p /srv/agrect/backend /home/agrect/.cache/uv \
    && chown -R agrect:agrect /srv/agrect /home/agrect

WORKDIR /srv/agrect/backend

COPY --chown=agrect:agrect backend/pyproject.toml backend/uv.lock ./

USER agrect

RUN uv sync --frozen --no-dev

COPY --chown=agrect:agrect backend/ ./
COPY --chown=agrect:agrect data/ /srv/agrect/data
COPY --chown=agrect:agrect shared/ /srv/agrect/shared

RUN chmod 755 /srv/agrect/backend/docker-entrypoint.sh

HEALTHCHECK --interval=5s --timeout=3s --start-period=40s --retries=12 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health')"]

ENTRYPOINT ["/srv/agrect/backend/docker-entrypoint.sh"]
