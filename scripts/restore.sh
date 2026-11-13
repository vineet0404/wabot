#!/usr/bin/env bash
# Backup se database wapas laata hai. DHYAN: maujooda data mita deta hai.
# Chalao: ./scripts/restore.sh backups/wabot-20261107-031500.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."

file="${1:?backup file ka naam do}"
[ -f "$file" ] || { echo "file nahi mili: $file" >&2; exit 1; }
read -r -p "Maujooda database mit jayega. Pakka? (haan likho): " answer
[ "$answer" = "haan" ] || { echo "ruk gaya"; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
$COMPOSE stop web worker
$COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)" -c "CREATE DATABASE \"$POSTGRES_DB\""'
gunzip -c "$file" | $COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$COMPOSE start web worker
echo "restore ho gaya"
