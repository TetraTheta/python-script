@REM Compile Garry's Mod VMF map source
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\gmod_map_compile.py" %*
