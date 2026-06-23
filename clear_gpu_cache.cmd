@REM Clear GPU shader cache and PSO cache
@echo off
set "PATH=C:\bin;%PATH%"
gsudo status IsElevated >nul 2>&1
if %errorlevel% equ 0 goto ADMINTASKS

cd /d "%~dp0"
gsudo "%~f0"
exit /b

:ADMINTASKS
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\clear_gpu_cache.py"
