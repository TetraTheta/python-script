@REM Decode string encoded with Base64 and copy decoded string to clipboard
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\python-script\base64_encode_decode.py" %*
