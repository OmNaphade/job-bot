@echo off
rem Runs one job-alert pass and appends the output to data\run.log. Used by Windows Task Scheduler.
cd /d "%~dp0"
if not exist data mkdir data
".venv\Scripts\python.exe" -m jobalert run >> data\run.log 2>&1
