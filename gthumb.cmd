@REM Cut and convert GMod screenshot to GMod map icon
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\gmod_map_thumb.py" %1
