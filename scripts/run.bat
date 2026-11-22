@echo off
REM Start the dashboard (Windows). Then open http://localhost:8000
cd /d %~dp0..
python -m factory.server
pause
