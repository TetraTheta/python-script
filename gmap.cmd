@REM Remove files from SourceMod to allow it to be packed as GMod GMA
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\gmod_map_addon.py" %1
