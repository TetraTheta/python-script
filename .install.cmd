@echo off
setlocal

set "SOURCE_DIR=%~dp0"
set "DEST_DIR=C:\bin"
set "SCRIPT_DIR=%SOURCE_DIR%script"
set "DEST_SCRIPT_DIR=%DEST_DIR%\script"

if not exist "%DEST_DIR%\" mkdir "%DEST_DIR%" || exit /b 1

for %%F in ("%SOURCE_DIR%*.cmd") do (
  if /I not "%%~fF"=="%~f0" copy /Y "%%~fF" "%DEST_DIR%\" >nul || exit /b 1
)

if exist "%SCRIPT_DIR%\" (
  robocopy "%SCRIPT_DIR%" "%DEST_SCRIPT_DIR%" *.py *.pyw *.csv /S /NFL /NDL /NJH /NJS /NP
  if errorlevel 8 exit /b 1
)

exit /b 0
