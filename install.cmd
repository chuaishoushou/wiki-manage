@echo off
REM ============================================================
REM  flux-wiki 一键安装(Windows)—— 对应 macOS/Linux 的 ./install.sh
REM
REM    git clone https://github.com/chuaishoushou/wiki-manage
REM    cd wiki-manage
REM    install.cmd
REM
REM  运行时会交互询问两个库的位置:
REM    (1) 个人库 —— 日常读写主库(不存在会自动建;默认 %USERPROFILE%\AI\wiki)
REM    (2) 团队仓 —— 团队知识源本地 clone(只读;默认 %USERPROFILE%\AI\team-wiki)
REM  自动探测本机的 Claude / Codex / Cursor 并各自配好。
REM  Cursor 会打印一段 User Rules 文本,粘进 设置-Rules-User Rules 一次。
REM
REM  不想交互?按顺序给路径(个人库 团队仓),或用环境变量:
REM    install.cmd D:\AI\wiki D:\AI\team-wiki
REM    set PERSONAL_ROOT=... ^& set TEAM_ROOT=... ^& install.cmd
REM ============================================================
setlocal
set "HERE=%~dp0"

REM 找 Python:优先 py 启动器,其次 python
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo [X] 未找到 Python。请装 Python 3.8+（python.org 或 Microsoft Store），勾选 Add to PATH。
  exit /b 1
)

REM 两个库位置:%1=个人库 %2=团队仓;或环境变量 PERSONAL_ROOT / TEAM_ROOT(兼容旧 WIKI_ROOT=个人库)。
REM 都不给时,wiki-init 在终端里逐项交互询问(回车用默认)。
set "ARGS=--platform all --write"
if not "%~1"=="" (
  set ARGS=%ARGS% --personal-root "%~1"
) else if defined PERSONAL_ROOT (
  set ARGS=%ARGS% --personal-root "%PERSONAL_ROOT%"
) else if defined WIKI_ROOT (
  set ARGS=%ARGS% --personal-root "%WIKI_ROOT%"
)
if not "%~2"=="" (
  set ARGS=%ARGS% --team-root "%~2"
) else if defined TEAM_ROOT (
  set ARGS=%ARGS% --team-root "%TEAM_ROOT%"
)
%PY% "%HERE%bin\wiki-init" %ARGS%

endlocal
