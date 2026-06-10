@echo off
REM ============================================================
REM  flux-wiki 一键安装(Windows)—— 对应 macOS/Linux 的 ./install.sh
REM
REM    git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
REM    cd %USERPROFILE%\AI\wiki-manage
REM    .\install.cmd
REM
REM  人和 AI 同一条命令:终端里逐项确认路径(回车用默认);
REM  非终端直接用默认/参数。可选参数原样透传 bin\wiki-init。
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
