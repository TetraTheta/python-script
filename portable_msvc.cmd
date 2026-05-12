@REM Download Portable MSVC Toolchain (+CMake, Ninja)
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\portable_msvc.py" --location E:\ --msvc-version 14.50 --sdk-version 22621 --accept-license --target=x64,x86 --host=x64
