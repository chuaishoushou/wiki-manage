@echo off
REM ============================================================
REM  flux-wiki 一键安装(Windows)—— 对应 macOS/Linux 的 ./install.sh
REM
REM    git clone https://github.com/chuaishoushou/wiki-manage
REM    cd wiki-manage
REM    install.cmd
REM
REM  自动探测本机的 Claude / Codex / Cursor 并各自配好。
REM  Cursor 会打印一段 User Rules 文本,粘进 设置-Rules-User Rules 一次。
REM
REM  库路径:默认自动探测 %USERPROFILE%\AI\team-wiki 或 \AI\wiki;
REM  也可显式:install.cmd D:\path\to\team-wiki   或   set WIKI_ROOT=...
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

REM 选库路径:命令行参数优先，其次 WIKI_ROOT 环境变量，否则交给 wiki-init 自动探测
if not "%~1"=="" (
  %PY% "%HERE%bin\wiki-init" --platform all --write --wiki-root "%~1"
) else if defined WIKI_ROOT (
  %PY% "%HERE%bin\wiki-init" --platform all --write --wiki-root "%WIKI_ROOT%"
) else (
  %PY% "%HERE%bin\wiki-init" --platform all --write
)

endlocal
