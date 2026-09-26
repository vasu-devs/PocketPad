@echo off
title PocketPad host
cd /d "%~dp0"
python -c "import aiohttp" 2>nul || (
  echo Installing dependencies...
  python -m pip install --user -q -r requirements.txt
)
python -m host %*
if errorlevel 1 pause
