#!/usr/bin/env bash
#
# flux-wiki 一键安装(macOS / Linux)。本仓不是原生插件,这是唯一安装入口。
#
#   git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
#   cd ~/AI/wiki-manage
#   ./install.sh
#
# 人工跑(无参):在终端里交互逐项询问 ① 个人库 ② 团队仓 的位置(回车用默认),
# 写完三平台规则指针后,再问你是否现在初始化个人库(默认否)。
#
# AI 助手请勿裸跑本脚本 —— 你执行命令时 stdin 不是终端,问不到用户。
# 正确做法见 README『给 AI 助手的执行指令』:先在对话里问用户,再用参数直接调 bin/wiki-init。
#
# 透传:本脚本把所有参数原样转交 bin/wiki-init;未给 --platform 时补 all、未给 --write 时补 --write。
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

# 智能透传:缺 --platform 补 all、缺 --write 补 --write,其余参数原样传给 wiki-init。
# (AI 若裸跑本脚本→补出 --write 但无库路径,wiki-init 在非 TTY 下会 exit 2 拦截,不会静默装错。)
EXTRA=()
case " $* " in *"--platform"*) ;; *) EXTRA+=(--platform all) ;; esac
case " $* " in *"--write"*) ;; *) EXTRA+=(--write) ;; esac

# 注:bash 3.2(macOS 自带)下,空数组 "${EXTRA[@]}" 在 set -u 会报 unbound;
# 用 ${arr[@]+"${arr[@]}"} 惯用法安全展开(空→什么都不加,非空→保留各元素)。
exec "$PY" "$HERE/bin/wiki-init" ${EXTRA[@]+"${EXTRA[@]}"} "$@"
