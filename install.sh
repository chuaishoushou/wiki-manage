#!/usr/bin/env bash
#
# flux-wiki 一键安装(macOS / Linux)。人和 AI 同一条命令:
#
#   git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
#   cd ~/AI/wiki-manage && ./install.sh
#
# 安装强制要求提供个人库与团队仓位置,缺一不可,且必须来自用户:
# - 终端:逐项必答(回车只能用明确显示的默认值,没有"跳过");
# - AI/CI(非终端):必须带全两个参数,缺任一项报错退出 rc=2。
#   AI 执行安装:先向用户【询问】两个位置再带参数重跑;已有配置(~/.flux-wiki.json)
#   也要向用户展示、由用户确认沿用后才允许带 --use-config 代替参数;
#   严禁照抄文档示例/占位路径,严禁自行猜测。下面 <...> 是占位符,不是可执行示例:
#   ./install.sh --personal-root <个人库路径> --team-root <团队仓git克隆路径>
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
