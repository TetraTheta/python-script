@REM Download YouTube video thumbnail
@echo off
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%~dp0\script\library"
python "%~dp0\script\youtube_thumbnail_download.py" %1
