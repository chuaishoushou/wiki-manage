#!/usr/bin/env bash
#
# flux-wiki 一键安装 —— 团队成员只需要这一条命令(三平台统一,自动探测):
#
#   git clone https://github.com/chuaishoushou/wiki-manage && cd wiki-manage && ./install.sh
#
# 运行时会(在终端里)交互询问两个库的位置:
#   ① 个人库 —— 你日常读写/入库的主库(不存在会自动建;默认 ~/AI/wiki)
#   ② 团队仓 —— 团队知识源的本地 git clone(只读;默认 ~/AI/team-wiki;还没 clone 会提示你 clone)
#
# 脚本会自动认出本机装了 Claude Code / Codex / Cursor,挨个配好:
#   - Claude Code : 写 ~/.claude/CLAUDE.md 指针 + 软链 skills/命令(全局,自动)
#   - Codex       : 写 ~/.codex/AGENTS.md 指针(全局,自动)
#   - Cursor      : 打印一段规则文本,你粘进 设置→Rules→User Rules 一次(全局,手动一步)
#
# 不想交互?直接按顺序给路径(个人库 团队仓),或用环境变量:
#   ./install.sh ~/AI/wiki ~/AI/team-wiki
#   PERSONAL_ROOT=~/AI/wiki TEAM_ROOT=~/AI/team-wiki ./install.sh
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

# 两个库位置:位置参数 $1=个人库 $2=团队仓;或环境变量 PERSONAL_ROOT / TEAM_ROOT
# (兼容旧 WIKI_ROOT=个人库)。都不给时,wiki-init 在终端里逐项交互询问(回车用默认)。
ARGS=(--platform all --write)
if [ "${1:-}" != "" ]; then
  ARGS+=(--personal-root "$1")
elif [ "${PERSONAL_ROOT:-}" != "" ]; then
  ARGS+=(--personal-root "$PERSONAL_ROOT")
elif [ "${WIKI_ROOT:-}" != "" ]; then
  ARGS+=(--personal-root "$WIKI_ROOT")
fi
if [ "${2:-}" != "" ]; then
  ARGS+=(--team-root "$2")
elif [ "${TEAM_ROOT:-}" != "" ]; then
  ARGS+=(--team-root "$TEAM_ROOT")
fi

exec "$PY" "$HERE/bin/wiki-init" "${ARGS[@]}"
