#!/usr/bin/env bash
# 社交关系数据同步脚本
# 用法:
#   bash scripts/sync_data.sh save     # 数据 → git (备份到 data_local/)
#   bash scripts/sync_data.sh restore  # git → 数据 (从 data_local/ 恢复)
#   bash scripts/sync_data.sh status   # 查看差异

set -euo pipefail
cd "$(dirname "$0")/.."

DATA_Local="data_local"
DATA_SYMLINK="data"

cmd="${1:-status}"

case "$cmd" in
  save)
    echo ":: 备份数据到 git 跟踪目录 (data_local/)..."
    mkdir -p "$DATA_Local"
    for f in contacts.json timeline.json todos.json wechat_ids.json; do
      src="$DATA_SYMLINK/$f"
      if [ -f "$src" ]; then
        cp "$src" "$DATA_Local/$f"
        echo "   ✓ $f ($(wc -c < "$src") bytes)"
      fi
    done
    echo "  运行 git add data_local && git commit 以保存版本"
    ;;

  restore)
    echo ":: 从 git 恢复数据到 data/..."
    for f in contacts.json timeline.json todos.json wechat_ids.json; do
      src="$DATA_Local/$f"
      if [ -f "$src" ]; then
        cp "$src" "$DATA_SYMLINK/$f"
        echo "   ✓ $f ($(wc -c < "$src") bytes)"
      fi
    done
    ;;

  status)
    echo "=== data/ (运行时) vs data_local/ (git 版本) ==="
    for f in contacts.json timeline.json todos.json wechat_ids.json; do
      a="$DATA_SYMLINK/$f"
      b="$DATA_Local/$f"
      if [ -f "$a" ] && [ -f "$b" ]; then
        if diff -q "$a" "$b" &>/dev/null; then
          echo "   ✓ $f — 一致"
        else
          diff_size=$(diff <(wc -c < "$a") <(wc -c < "$b") 2>/dev/null || echo "differs")
          echo "   ⚠ $f — 有差异"
        fi
      elif [ -f "$a" ]; then
        echo "   ➕ $f — 仅在 data/ 中"
      elif [ -f "$b" ]; then
        echo "   ➖ $f — 仅在 data_local/ 中"
      else
        echo "   - $f — 两处均无"
      fi
    done
    echo ""
    echo "   data_local/ 中的文件由 git 跟踪，由 pre-push hook 阻止推送到公开仓库"
    ;;

  *)
    echo "用法: bash scripts/sync_data.sh {save|restore|status}"
    exit 1
    ;;
esac
