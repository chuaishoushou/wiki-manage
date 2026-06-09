@echo off
REM ============================================================
REM  flux-wiki 一键安装(Windows)—— 对应 macOS/Linux 的 ./install.sh
REM
REM    git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
REM    cd %USERPROFILE%\AI\wiki-manage
REM    .\install.cmd
REM
REM  人工跑(无参):交互逐项询问 (1) 个人库 (2) 团队仓 的位置(回车用默认),
REM  写完三平台规则指针后,再问你是否现在初始化个人库(默认否)。
REM  Cursor 会打印一段 User Rules 文本,粘进 设置-Rules-User Rules 一次。
REM
REM  AI 助手勿裸跑本脚本(stdin 非终端,问不到用户)。见 README『给 AI 助手的执行指令』:
REM  先在对话里问用户,再用参数直接调 bin\wiki-init。
REM
REM  透传:本脚本把所有参数原样转交 bin\wiki-init;未给 --platform 补 all、未给 --write 补 --write。
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

REM 智能透传:缺 --platform 补 all、缺 --write 补 --write,其余参数原样传给 wiki-init。
set "EXTRA="
echo %* | findstr /C:"--platform" >nul || set "EXTRA=%EXTRA% --platform all"
echo %* | findstr /C:"--write" >nul || set "EXTRA=%EXTRA% --write"

%PY% "%HERE%bin\wiki-init"%EXTRA% %*
exit /b %ERRORLEVEL%
