@REM Optimize Valve VMF file
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\source_vmf_sanitizer.py" %*
