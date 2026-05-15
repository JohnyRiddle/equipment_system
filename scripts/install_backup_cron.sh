#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-$PROJECT_DIR/scripts/backup.env}"
BACKUP_LOG_FILE="${BACKUP_LOG_FILE:-/home/ivan/equipment_backups/backup.log}"
BACKUP_CRON_SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 3 */10 * *}"
CRON_MARKER="equipment_system production_backup"

mkdir -p "$(dirname "$BACKUP_LOG_FILE")"

cron_line="$BACKUP_CRON_SCHEDULE cd $PROJECT_DIR && set -a && [ -f $BACKUP_ENV_FILE ] && . $BACKUP_ENV_FILE && set +a && ./scripts/production_backup.sh >> $BACKUP_LOG_FILE 2>&1 # $CRON_MARKER"

(
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" || true
    echo "$cron_line"
) | crontab -

echo "Backup cron installed:"
echo "$cron_line"
