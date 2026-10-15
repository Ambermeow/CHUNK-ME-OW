#!/usr/bin/env bash
# 备份：数据库 + 音频库 → 单个 tar.gz
# 用法: ./scripts/backup.sh [输出目录]
set -euo pipefail
cd "$(dirname "$0")/.."

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
TS=$(date +%Y%m%d_%H%M%S)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

DB_URL="${DATABASE_URL:-}"
if [[ "$DB_URL" == postgres* ]]; then
  # 服务器模式：pg_dump（容器内执行）
  docker compose exec -T db pg_dump -U spelling spelling > "$TMP/db.sql"
else
  # 本地模式：直接复制 SQLite 文件
  cp "${DATA_DIR:-./data}/app.db" "$TMP/app.db" 2>/dev/null || true
fi

# 音频库（只读打包）
AUDIO="${AUDIO_DIR:-./data/voice_lib}"
[[ -d "$AUDIO" ]] && cp -r "$AUDIO" "$TMP/voice_lib"

tar -czf "$OUT_DIR/spelling_backup_$TS.tar.gz" -C "$TMP" .
echo "备份完成: $OUT_DIR/spelling_backup_$TS.tar.gz"
