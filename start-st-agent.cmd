@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ST-Agent

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

curl.exe -fsS --max-time 2 http://127.0.0.1:8501/_stcore/health >nul 2>&1
if not errorlevel 1 (
  start "" "http://127.0.0.1:8501"
  exit /b 0
)

echo Starting ST-Agent. Close this window to stop the app.
echo.

if exist ".venv\Scripts\streamlit.exe" (
  ".venv\Scripts\streamlit.exe" run app.py --server.headless false
) else (
  where uv >nul 2>&1
  if errorlevel 1 (
    echo uv was not found. Install uv, then run: uv sync --group dev
    pause
    exit /b 1
  )
  uv run streamlit run app.py --server.headless false
)

if errorlevel 1 (
  echo ST-Agent failed to start.
  pause
)
