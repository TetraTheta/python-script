@REM Cleanup GMod Map Source file
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\gmod_map_source.py" %1
