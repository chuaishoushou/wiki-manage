#!/usr/bin/env bash
#
# flux-wiki 一键安装 —— 团队成员只需要这一条命令(三平台统一,自动探测):
#
#   git clone https://github.com/chuaishoushou/wiki-manage && cd wiki-manage && ./install.sh
#
# 脚本会自动认出本机装了 Claude Code / Codex / Cursor,挨个配好:
#   - Claude Code : 写 ~/.claude/CLAUDE.md 指针 + 软链 skills/命令(全局,自动)
#   - Codex       : 写 ~/.codex/AGENTS.md 指针(全局,自动)
#   - Cursor      : 打印一段规则文本,你粘进 设置→Rules→User Rules 一次(全局,手动一步)
#
# 库路径:默认自动探测 ~/AI/team-wiki 或 ~/AI/wiki;也可显式给:
#   ./install.sh ~/AI/team-wiki      或      WIKI_ROOT=/path ./install.sh
#
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# 找 Python:优先 python3,回退 python(部分系统/Git Bash 只有 python)
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "❌ 需要 python3(≥3.8)。macOS: brew install python3 / Ubuntu: sudo apt install python3" >&2
  exit 1
fi

ARGS=(--platform all --write)
if [ "${1:-}" != "" ]; then
  ARGS+=(--wiki-root "$1")
elif [ "${WIKI_ROOT:-}" != "" ]; then
  ARGS+=(--wiki-root "$WIKI_ROOT")
fi

exec "$PY" "$HERE/bin/wiki-init" "${ARGS[@]}"
