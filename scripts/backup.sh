#!/usr/bin/env bash
# Database ka backup banata hai: backups/wabot-YYYYmmdd-HHMMSS.sql.gz, purane (14 din se) hata deta hai.
# Roz chalane ke liye cron (docs/GO_LIVE.md me likha hai):
#   15 3 * * * cd /home/ubuntu/wabot && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p backups
chmod 700 backups

file="backups/wabot-$(date +%Y%m%d-%H%M%S).sql.gz"
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$file"

# Khali ya kharab backup ko pakdo
if [ "$(stat -c %s "$file")" -lt 200 ]; then
  echo "BACKUP FAIL: file bahut chhoti hai ($file)" >&2
  rm -f "$file"
  exit 1
fi
gzip -t "$file"
chmod 600 "$file"
find backups -name 'wabot-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "$(date -Is) backup ok: $file ($(du -h "$file" | cut -f1))"
