#!/usr/bin/env bash
# ccc-opencode-gc.sh — 裁剪 OpenCode 会话库膨胀（event 流 + 可选旧会话）
# 用法：bash scripts/ccc-opencode-gc.sh [--days 7] [--dry-run]
set -euo pipefail

DAYS=7
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="${2:?}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown: $1" >&2; exit 2 ;;
  esac
done

DB="${HOME}/.local/share/opencode/opencode.db"
[[ -f "$DB" ]] || { echo "missing $DB"; exit 1; }

if pgrep -lf '[o]pencode' >/dev/null 2>&1; then
  echo "ABORT: opencode process running" >&2
  exit 1
fi

SIZE_MB=$(du -m "$DB" | awk '{print $1}')
echo "db=${DB} size_mb=${SIZE_MB} days=${DAYS}"

CUT_MS=$(python3 - <<PY
import time
print(int(time.time()*1000) - int("${DAYS}")*86400*1000)
PY
)

if [[ "$DRY" == "1" ]]; then
  sqlite3 "$DB" "SELECT COUNT(*) AS stale_sessions FROM session WHERE COALESCE(time_updated,time_created)<${CUT_MS};"
  sqlite3 "$DB" "SELECT COUNT(*) AS events FROM event;"
  exit 0
fi

sqlite3 "$DB" <<SQL
PRAGMA foreign_keys=ON;
BEGIN;
CREATE TEMP TABLE stale AS
  SELECT id FROM session WHERE COALESCE(time_updated, time_created) < ${CUT_MS};
DELETE FROM event;
DELETE FROM session WHERE id IN (SELECT id FROM stale);
DELETE FROM message WHERE length(data) > 2000000;
COMMIT;
SQL
sqlite3 "$DB" "VACUUM;"
echo "after: $(du -h "$DB" | awk '{print $1}') sessions=$(sqlite3 "$DB" 'SELECT COUNT(*) FROM session;')"
