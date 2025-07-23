@REM Renumber image files
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\renumber.py" %*
