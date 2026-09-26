@echo off
title PocketPad host
cd /d "%~dp0"
python -c "import aiohttp, qrcode" 2>nul || (
  echo Installing dependencies...
  python -m pip install --user -q -r requirements.txt
)
python -m pocketpad %*
if errorlevel 1 pause
