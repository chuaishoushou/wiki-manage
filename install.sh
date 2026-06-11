#!/usr/bin/env bash
#
# flux-wiki 一键安装(macOS / Linux)。人和 AI 同一条命令:
#
#   git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
#   cd ~/AI/wiki-manage && ./install.sh
#
# 安装强制要求提供个人库与团队仓位置,缺一不可:终端里逐项必答(回车只能用明确
# 显示的默认值,没有"跳过");AI/CI(非终端)必须带全两个参数,缺任一项报错退出
# (AI 应先向用户询问两个位置再重跑)。参数原样透传 bin/wiki-init,如:
#   ./install.sh --personal-root ~/AI/wiki --team-root ~/AI/team-wiki
#
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "❌ 需要 python3(≥3.8)。macOS: brew install python3 / Ubuntu: sudo apt install python3" >&2
  exit 1
fi

exec "$PY" "$HERE/bin/wiki-init" "$@"
