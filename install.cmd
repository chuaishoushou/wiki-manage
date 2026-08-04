@echo off
REM ============================================================
REM  flux-wiki 一键安装(Windows)—— 对应 macOS/Linux 的 ./install.sh
REM
REM    git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
REM    cd %USERPROFILE%\AI\wiki-manage
REM    .\install.cmd
REM
REM  人和 AI 同一条命令。个人库与团队仓位置强制必填,且必须来自用户:
REM  终端里逐项必答(回车只能用明确显示的默认值);非终端(AI/CI)缺任一项
REM  报错退出 rc=2,绝不静默复用配置/默认值。AI 执行安装:先向用户【询问】
REM  两个位置再带参数重跑;已有配置也要向用户展示、确认沿用后才允许带
REM  --use-config;严禁照抄示例/占位路径或自行猜测。^<...^> 是占位符:
REM    .\install.cmd --personal-root ^<个人库路径^> --team-root ^<团队仓git克隆路径^>
REM  参数原样透传 bin\wiki-init。
REM ============================================================
setlocal
set "HERE=%~dp0"

REM 找 Python:优先 py 启动器(py -3),其次 python
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo [X] 未找到 Python。请装 Python 3.8+（python.org 勾选 Add to PATH,或 Microsoft Store）。
  exit /b 1
)

%PY% "%HERE%bin\wiki-init" %*
exit /b %ERRORLEVEL%
