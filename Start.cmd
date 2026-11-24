@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if defined TEAM_EVAL_PORT set "WSLENV=%WSLENV%:TEAM_EVAL_PORT/u"
if defined TEAM_EVAL_PREFIX set "WSLENV=%WSLENV%:TEAM_EVAL_PREFIX/u"
if defined TEAM_EVAL_STATE set "WSLENV=%WSLENV%:TEAM_EVAL_STATE/u"
wsl.exe --cd "%CD%" --exec bash ./start.sh --open-windows
set "rc=%errorlevel%"
if not "%rc%"=="0" pause
popd
exit /b %rc%
