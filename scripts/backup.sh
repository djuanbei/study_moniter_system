#!/usr/bin/env bash
# 学习陪伴系统 - 备份脚本
# Creates a timestamped tarball containing the SQLite database and uploaded
# submission images. Run from cron: 0 3 * * * /opt/study-moniter-system/scripts/backup.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
OUT="$BACKUP_DIR/sms-backup-$TIMESTAMP.tar.gz"
RETAIN_DAYS="${RETAIN_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

# Sanity check
if [ ! -f "$PROJECT_ROOT/data/app.sqlite" ]; then
  echo "Database not found at $PROJECT_ROOT/data/app.sqlite" >&2
  exit 1
fi

# Force WAL checkpoint so the snapshot is self-contained.
DB_PATH="$PROJECT_ROOT/data/app.sqlite"
"$PROJECT_ROOT/backend/.venv/bin/python" - "$DB_PATH" <<'PY'
import sqlite3, sys, pathlib
db = pathlib.Path(sys.argv[1])
con = sqlite3.connect(str(db))
con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
con.close()
PY

tar -czf "$OUT" \
  -C "$PROJECT_ROOT" \
  data/app.sqlite \
  data/app.sqlite-wal \
  data/app.sqlite-shm \
  uploads \
  .env

# .env contains secrets; tighten permissions.
chmod 600 "$OUT"

# Prune old backups
find "$BACKUP_DIR" -name 'sms-backup-*.tar.gz' -mtime "+$RETAIN_DAYS" -delete

echo "Backup written to $OUT"
echo "Size: $(du -h "$OUT" | cut -f1)"