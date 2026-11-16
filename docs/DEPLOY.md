# Deploy

Production runs three containers from `/opt/agrect`: PostGIS (no published port), the API, and Caddy. Caddy serves the built frontend, proxies `/v1` to the API, and gets certificates for every name in `SITE_ADDRESS`.

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

`scripts/deploy.sh` runs that after a fast-forward pull. On API start the entrypoint waits for Postgres, applies migrations, and loads the catalogue. Both steps are idempotent.

## First install

1. Log in with an SSH key. Leave password login off.

   On your machine, create a key and install the public key for `root` on the server:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/agrect_vps
   ssh -i ~/.ssh/agrect_vps root@13.140.215.136
   ```

2. Install Docker Engine and the Compose plugin:

   ```bash
   curl -fsSL https://get.docker.com | sh
   docker compose version
   ```

3. Open SSH, HTTP, and HTTPS. Do not publish Postgres.

   ```bash
   ufw allow OpenSSH
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```

   If the VPS provider has its own firewall, allow the same three ports there.

4. Create a read-only deploy key so the server can pull:

   ```bash
   ssh-keygen -t ed25519 -f /root/.ssh/agrect_deploy -N ""
   cat /root/.ssh/agrect_deploy.pub
   ```

   Add the public key on GitHub: repository **AyaAbdat/agrect**, Settings, Deploy keys, read-only.

   `/root/.ssh/config`:

   ```
   Host github.com
   HostName github.com
   User git
   IdentityFile /root/.ssh/agrect_deploy
   IdentitiesOnly yes
   ```

5. Clone to `/opt/agrect`:

   ```bash
   git clone git@github.com:AyaAbdat/agrect.git /opt/agrect
   cd /opt/agrect
   ```

6. Create `.env.prod` from the example. Placeholders only — do not commit this file.

   ```bash
   cp .env.prod.example .env.prod
   openssl rand -hex 32
   openssl rand -hex 32
   ```

   The first value is `POSTGRES_PASSWORD`. Put the same value in `DATABASE_URL` in place of `CHANGE_ME` (hex is safe inside the URL). The second value is `JWT_SECRET`. The API refuses to start when that secret is shorter than 32 characters.

   `scripts/deploy.sh` runs the demo seed and exits if any of these are empty: `DEMO_USER_EMAIL`, `DEMO_USER_PASSWORD`, `DEMO_FARM_LAT`, `DEMO_FARM_LON`. Set them in `.env.prod`. Do not invent farm coordinates in the repo.

   `SITE_ADDRESS` lists the names Caddy serves and certifies, separated by a comma and a space. `CORS_ORIGINS` is the same hosts with `https://`, separated by commas.

   Point an A record for `app.agrect.com` at this server. `13.140.215.136.sslip.io` needs no DNS record; it resolves to `13.140.215.136`.

7. Start:

   ```bash
   bash scripts/deploy.sh
   ```

   The first start requests Let's Encrypt certificates. Ports 80 and 443 must reach this host. Certificates are stored in the `caddy_data` volume.

## Update

```bash
cd /opt/agrect
bash scripts/deploy.sh
```

This fast-forwards the checkout, rebuilds, waits up to 120 seconds for the API healthcheck, and runs the demo seed again.

## Backup

As root:

```bash
cd /opt/agrect
bash scripts/backup.sh
```

The dump is `/root/backups/agrect-YYYYMMDD-HHMM.sql.gz`. The script keeps the newest 14 files. Copy dumps off the server as well; this directory lives on the same disk as the database.

## Restore

Stop the API, replace the database, load one dump, then start the API. Use the backup filename you want. Starting the API runs migrations and the catalogue loader again; both are idempotent.

```bash
cd /opt/agrect
docker compose --env-file .env.prod -f docker-compose.prod.yml stop api
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -c 'dropdb --username="$POSTGRES_USER" --force --if-exists "$POSTGRES_DB" && createdb --username="$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c /root/backups/agrect-YYYYMMDD-HHMM.sql.gz \
  | docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
    sh -c 'psql --set ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
docker compose --env-file .env.prod -f docker-compose.prod.yml start api
```

## Logs

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
```

Certificate errors are on the web service: the same command with `web` instead of `api`.
