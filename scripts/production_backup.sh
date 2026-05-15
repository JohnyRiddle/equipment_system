#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
WEB_CONTAINER="${WEB_CONTAINER:-equipment_web}"
MEDIA_PATH="${MEDIA_PATH:-backend/media}"

BACKUP_ROOT="${BACKUP_ROOT:-/home/ivan/equipment_backups}"
BACKUP_LOCAL_DIR="${BACKUP_LOCAL_DIR:-$BACKUP_ROOT/local}"
BACKUP_PACKAGE_DIR="${BACKUP_PACKAGE_DIR:-$BACKUP_ROOT/packages}"
BACKUP_RETENTION_COUNT="${BACKUP_RETENTION_COUNT:-3}"

BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
BACKUP_GITHUB_REPO_DIR="${BACKUP_GITHUB_REPO_DIR:-}"
BACKUP_GITHUB_SUBDIR="${BACKUP_GITHUB_SUBDIR:-backups}"
BACKUP_ENCRYPTION_PASSWORD="${BACKUP_ENCRYPTION_PASSWORD:-}"

timestamp="$(date +%Y%m%d-%H%M%S)"
work_dir="$BACKUP_LOCAL_DIR/$timestamp"
package_path="$BACKUP_PACKAGE_DIR/equipment-backup-$timestamp.tar.gz"
encrypted_package_path="$package_path.enc"

log() {
    printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

retain_latest() {
    local target_dir="$1"
    local pattern="$2"
    local keep_count="$3"

    if [ ! -d "$target_dir" ]; then
        return
    fi

    find "$target_dir" -maxdepth 1 -name "$pattern" -printf '%T@ %p\n' \
        | sort -rn \
        | awk -v keep="$keep_count" 'NR > keep {sub(/^[^ ]+ /, ""); print}' \
        | while IFS= read -r old_path; do
            if [ -n "$old_path" ]; then
                rm -rf "$old_path"
            fi
        done
}

if [ -n "$BACKUP_RCLONE_REMOTE$BACKUP_GITHUB_REPO_DIR" ] && [ -z "$BACKUP_ENCRYPTION_PASSWORD" ]; then
    echo "BACKUP_ENCRYPTION_PASSWORD is required when cloud or GitHub backup is enabled." >&2
    exit 1
fi

require_command docker
require_command tar

mkdir -p "$work_dir" "$BACKUP_PACKAGE_DIR"

cd "$PROJECT_DIR"

log "Creating XML database backup"
docker compose -f "$COMPOSE_FILE" exec -T web python manage.py backup_database_xml --output /tmp/database.xml
docker cp "$WEB_CONTAINER:/tmp/database.xml" "$work_dir/database.xml"
docker compose -f "$COMPOSE_FILE" exec -T web rm -f /tmp/database.xml >/dev/null

if [ -d "$MEDIA_PATH" ] && find "$MEDIA_PATH" -mindepth 1 -print -quit | grep -q .; then
    log "Archiving media files"
    tar -czf "$work_dir/media.tar.gz" -C "$MEDIA_PATH" .
fi

cat > "$work_dir/manifest.txt" <<EOF
created_at=$(date --iso-8601=seconds)
project_dir=$PROJECT_DIR
compose_file=$COMPOSE_FILE
web_container=$WEB_CONTAINER
database_dump=database.xml
database_format=xml
media_archive=$(if [ -f "$work_dir/media.tar.gz" ]; then echo "media.tar.gz"; fi)
app_version=$(docker compose -f "$COMPOSE_FILE" exec -T web env | awk -F= '/^APP_VERSION=/{print $2}')
EOF

log "Packing backup archive"
tar -czf "$package_path" -C "$BACKUP_LOCAL_DIR" "$timestamp"

upload_path="$package_path"
if [ -n "$BACKUP_ENCRYPTION_PASSWORD" ]; then
    require_command openssl
    log "Encrypting backup archive"
    BACKUP_ENCRYPTION_PASSWORD="$BACKUP_ENCRYPTION_PASSWORD" openssl enc -aes-256-cbc -salt -pbkdf2 \
        -in "$package_path" \
        -out "$encrypted_package_path" \
        -pass env:BACKUP_ENCRYPTION_PASSWORD
    upload_path="$encrypted_package_path"
fi

retain_latest "$BACKUP_LOCAL_DIR" "*" "$BACKUP_RETENTION_COUNT"
retain_latest "$BACKUP_PACKAGE_DIR" "equipment-backup-*.tar.gz" "$BACKUP_RETENTION_COUNT"
retain_latest "$BACKUP_PACKAGE_DIR" "equipment-backup-*.tar.gz.enc" "$BACKUP_RETENTION_COUNT"

if [ -n "$BACKUP_RCLONE_REMOTE" ]; then
    require_command rclone
    log "Uploading backup to Google Drive via rclone: $BACKUP_RCLONE_REMOTE"
    rclone copy "$upload_path" "$BACKUP_RCLONE_REMOTE"
    rclone lsf "$BACKUP_RCLONE_REMOTE" --files-only \
        | grep '^equipment-backup-.*\.tar\.gz\.enc$' \
        | sort -r \
        | awk -v keep="$BACKUP_RETENTION_COUNT" 'NR > keep {print}' \
        | while IFS= read -r old_file; do
            rclone deletefile "$BACKUP_RCLONE_REMOTE/$old_file"
        done
fi

if [ -n "$BACKUP_GITHUB_REPO_DIR" ]; then
    require_command git
    github_backup_dir="$BACKUP_GITHUB_REPO_DIR/$BACKUP_GITHUB_SUBDIR"
    mkdir -p "$github_backup_dir"
    cp "$upload_path" "$github_backup_dir/"

    retain_latest "$github_backup_dir" "equipment-backup-*.tar.gz.enc" "$BACKUP_RETENTION_COUNT"

    log "Committing backup to GitHub backup repository"
    (
        cd "$BACKUP_GITHUB_REPO_DIR"
        git add "$BACKUP_GITHUB_SUBDIR"
        if ! git diff --cached --quiet; then
            git commit -m "Backup $timestamp"
            git push
        fi
    )
fi

log "Backup completed: $work_dir"
