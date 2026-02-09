@REM Convert game screenshot with image manipulation
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\convert_screenshot_cli.py" %*
