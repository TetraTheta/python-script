@REM Format and modify 'gameinfo.txt' of SourceMod
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\sourcemod_gameinfo.py" %*
