@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Config ===
set VARS=HOME_ASSISTANT_BASE_URL HOME_ASSISTANT_TOKEN

echo.
echo === Home Assistant Environment Variable Setup (Permanent) ===
echo.

rem --- Check admin (for system-wide) ---
net session >nul 2>&1
if %errorlevel%==0 (
  set IS_ADMIN=1
) else (
  set IS_ADMIN=0
)

echo Choose where to store the variables:
echo   [U] User (current account)  - no admin required
echo   [S] System-wide             - admin required
set "SCOPE_CHOICE="
set /p SCOPE_CHOICE=Enter choice (U/S) [U]: 
if /i "%SCOPE_CHOICE%"=="S" (
  if "%IS_ADMIN%"=="1" (
    set SCOPE=Machine
  ) else (
    echo.
    echo You chose System-wide, but this script is not running as Administrator.
    echo Falling back to User scope.
    set SCOPE=User
  )
) else (
  set SCOPE=User
)

echo.
echo Target scope: %SCOPE%
echo.

rem --- For each variable: show current (from registry for scope), prompt to override ---
for %%V in (%VARS%) do (
  call :get_current_from_registry "%%V" "%SCOPE%" CURVAL
  if defined CURVAL (
    echo Current value for %%V (scope=%SCOPE%):
    echo   !CURVAL!
    call :yesno "Do you want to override %%V?" OVR
    if /i "!OVR!"=="Y" (
      set "NEWVAL="
      set /p NEWVAL=Enter new value for %%V: 
      call :set_env_var "%%V" "!NEWVAL!" "%SCOPE%"
    ) else (
      echo Keeping existing value.
    )
  ) else (
    echo %%V is not set in %SCOPE% scope.
    set "NEWVAL="
    set /p NEWVAL=Enter value for %%V: 
    call :set_env_var "%%V" "!NEWVAL!" "%SCOPE%"
  )
  echo.
)

rem --- Broadcast environment change so many apps pick it up immediately ---
call :broadcast_env_change

echo.
echo Done. Values are now stored permanently under %SCOPE% environment.
echo Notes:
echo   - New Command Prompt / PowerShell windows will see the new values.
echo   - Some running apps may need to be restarted to pick up changes.
echo.
echo Final values (effective for %SCOPE%):
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
set "OUTVAR=%~3"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command ^
  "[Environment]::GetEnvironmentVariable('%VAR%','%SCOPE%')"`) do (
  endlocal & set "%OUTVAR%=%%A" & goto :eof
)
endlocal & set "%OUTVAR%=" & goto :eof

:set_env_var
rem %1=VAR  %2=VALUE  %3=SCOPE(User|Machine)
setlocal
set "VAR=%~1"
set "VAL=%~2"
set "SCOPE=%~3"
powershell -NoProfile -Command ^
  "[Environment]::SetEnvironmentVariable('%VAR%','%VAL%','%SCOPE%')" >nul 2>&1
if errorlevel 1 (
  echo Failed to set %VAR% in scope %SCOPE%.
) else (
  echo Set %VAR% in scope %SCOPE%.
)
endlocal & goto :eof

:yesno
rem %1=Prompt  %2=OUTVAR(Y/N)
setlocal
set "PROMPT=%~1"
:askagain
set "ANS="
set /p ANS=%PROMPT% (Y/N): 
if /i "%ANS%"=="Y" ( endlocal & set "%~2=Y" & goto :eof )
if /i "%ANS%"=="N" ( endlocal & set "%~2=N" & goto :eof )
echo Please answer Y or N.
goto askagain

:broadcast_env_change
rem Broadcast WM_SETTINGCHANGE so many apps refresh environment (no guarantees)
powershell -NoProfile -Command ^
  "$sig='[DllImport(\"user32.dll\",CharSet=CharSet.Auto)]public static extern IntPtr SendMessageTimeout(IntPtr hWnd,int Msg,IntPtr wParam,string lParam,int fuFlags,int uTimeout,out IntPtr lpdwResu
