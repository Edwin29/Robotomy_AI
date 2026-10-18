@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Robotomy YouTube - private upload of completed recordings
echo 1. Connect Google account
echo 2. Show status
echo 3. Pause uploader (NVIDIA recording stays on)
echo 4. Resume uploader
choice /c 1234 /n /m "Choose: "
if errorlevel 4 goto start
if errorlevel 3 goto stop
if errorlevel 2 goto status
if not exist ".robotomy\youtube\oauth-client.json" (
  echo Download a Google Desktop OAuth client JSON first.
  echo Save it to .robotomy\youtube\oauth-client.json
  echo See docs\youtube-auto-upload.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 scripts\youtube_upload.py connect
if errorlevel 1 goto end
:start
".venv\Scripts\python.exe" -X utf8 scripts\youtube_upload.py start
goto end
:stop
".venv\Scripts\python.exe" -X utf8 scripts\youtube_upload.py stop
goto end
:status
".venv\Scripts\python.exe" -X utf8 scripts\youtube_upload.py status
:end
pause
