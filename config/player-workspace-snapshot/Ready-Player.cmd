@echo off
chcp 65001 >nul
"D:\Projects\Robotomy_AI\.venv\Scripts\python.exe" -X utf8 "D:\Projects\Robotomy_AI\scripts\prepare_player.py" --start-game --enable-input
if errorlevel 1 echo FAILED - review the error above.
pause
