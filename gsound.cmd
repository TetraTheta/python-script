@REM Convert Source Engine closed caption and soundscript to Lua script
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\gmod_map_scripts.py" %*
