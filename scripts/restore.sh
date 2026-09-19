#!/usr/bin/env bash
# 学习陪伴系统 - 恢复脚本
# Usage: ./scripts/restore.sh /path/to/sms-backup-YYYYMMDDTHHMMSS.tar.gz

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${1:-}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "Usage: $0 /path/to/backup.tar.gz" >&2
  exit 1
fi

# Refuse to overwrite without confirmation
read -r -p "This will overwrite data/ and uploads/. Continue? [y/N] " ans
if [ "${ans,,}" != "y" ]; then
  echo "Aborted."
  exit 1
fi

# Stop any running service (best-effort)
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet study-moniter.service; then
  systemctl stop study-moniter.service || true
fi

# Replace data/ and uploads/ with the archived snapshot.
tar -xzf "$ARCHIVE" -C "$PROJECT_ROOT"

echo "Restored from $ARCHIVE"
echo "Restart the service:  systemctl start study-moniter.service"