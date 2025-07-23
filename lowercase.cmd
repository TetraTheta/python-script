@REM Lowercase file/directory names
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\lowercase.py" %*
