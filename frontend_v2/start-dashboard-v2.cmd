@echo off
setlocal
set "NODE_BIN=C:\Users\sasir\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
set "PNPM_CMD=C:\Users\sasir\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd"
set "FRONTEND_DIR=%~dp0."
set "PATH=%NODE_BIN%;%PATH%"
"%PNPM_CMD%" --dir "%FRONTEND_DIR%" run dev
exit /b %ERRORLEVEL%
