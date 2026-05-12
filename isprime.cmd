@REM Check if the given integer is prime number or not
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
start pythonw "%~dp0\script\is_prime.pyw" %1
