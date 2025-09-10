@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Config ===
set VARS=HOME_ASSISTANT_BASE_URL HOME_ASSISTANT_TOKEN

echo.
echo === Home Assistant Environment Variable Setup (Permanent) ===
echo.

rem --- Detect admin for system scope option ---
net session >nul 2>&1
if %errorlevel%==0 (
  set IS_ADMIN=1
) else (
  set IS_ADMIN=0
)

echo Choose where to store the variables:
echo   [U] User scope
echo   [S] System-wide scope  (requires Administrator)
set "SCOPE_CHOICE="
set /p SCOPE_CHOICE=Enter choice (U/S) [U]: 
if /i "%SCOPE_CHOICE%"=="S" (
  if "%IS_ADMIN%"=="1" (
    set "SCOPE=Machine"
  ) else (
    echo.
    echo You chose System-wide but this session is not elevated. Falling back to User scope.
    set "SCOPE=User"
  )
) else (
  set "SCOPE=User"
)

echo.
echo Target scope: %SCOPE%
echo.

for %%V in (%VARS%) do (
  call :get_current_from_registry "%%V" "%SCOPE%" CURVAL
  if defined CURVAL (
    echo Current value for %%V:
    echo   !CURVAL!
    call :yesno "Do you want to override %%V" OVR
    if /i "!OVR!"=="Y" (
      set "NEWVAL="
      set /p NEWVAL=Enter new value for %%V: 
      call :set_env_var "%%V" "!NEWVAL!" "%SCOPE%"
    ) else (
      echo Keeping existing value for %%V.
    )
  ) else (
    echo %%V is not set.
    set "NEWVAL="
    set /p NEWVAL=Enter value for %%V: 
    call :set_env_var "%%V" "!NEWVAL!" "%SCOPE%"
  )
  echo.
)

call :broadcast_env_change

echo.
echo Done. Values are now stored permanently in %SCOPE% environment.
echo Open a new Command Prompt or PowerShell to see the changes.
echo.
echo Final values in %SCOPE%:
for %%V in (%VARS%) do (
  call :get_current_from_registry "%%V" "%SCOPE%" CURVAL
  echo   %%V=!CURVAL!
)
echo.
exit /b 0

:: ---------------- Functions ----------------

:get_current_from_registry
rem %1=VAR  %2=SCOPE(User|Machine)  %3=OUTVAR
setlocal
set "VAR=%~1"
set "SCOPE=%~2"

if /i "%SCOPE%"=="User" (
  set "REGPATH=HKCU\Environment"
) else (
  set "REGPATH=HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
)

rem Query the registry. Use carets to escape pipe and redirection inside FOR /F.
set "FOUND="
for /f "tokens=1,2,* skip=2" %%A in ('reg query "%REGPATH%" /v %VAR% 2^>nul ^| findstr /i /r "^%VAR%[ ]"') do (
  set "FOUND=1"
  set "VAL=%%C"
)
if defined FOUND (
  endlocal & set "%~3=%VAL%" & goto :eof
) else (
  endlocal & set "%~3=" & goto :eof
)

:set_env_var
rem %1=VAR  %2=VALUE  %3=SCOPE(User|Machine)
setlocal
set "VAR=%~1"
set "VAL=%~2"
set "SCOPE=%~3"
if /i "%SCO
