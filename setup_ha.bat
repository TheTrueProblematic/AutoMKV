@echo off
setlocal EnableExtensions

rem =========================
rem Auto MKV HA Env Setup v3
rem =========================
set "VAR1=HOME_ASSISTANT_BASE_URL"
set "VAR2=HOME_ASSISTANT_TOKEN"

echo.
echo === Home Assistant Environment Variable Setup - Permanent ===
echo.

rem --- Detect admin (needed for System scope) ---
net session >nul 2>&1
if %errorlevel%==0 ( set "IS_ADMIN=1" ) else ( set "IS_ADMIN=0" )

echo Choose where to store the variables:
echo   [U] User scope     - no Administrator required
echo   [S] System scope   - requires Administrator
set "SCOPE_CHOICE="
set /p SCOPE_CHOICE=Enter choice (U/S) [U]: 
if /i "%SCOPE_CHOICE%"=="S" (
  if "%IS_ADMIN%"=="1" ( set "SCOPE=Machine" ) else (
    echo.
    echo You chose System scope but this session is not elevated. Falling back to User scope.
    set "SCOPE=User"
  )
) else (
  set "SCOPE=User"
)

echo.
echo Target scope: %SCOPE%
echo.

call :configure_var "%VAR1%" "%SCOPE%"
call :configure_var "%VAR2%" "%SCOPE%"

call :broadcast_env_change

echo.
echo Done. Values are now stored permanently in %SCOPE% environment.
echo Open a new Command Prompt or PowerShell to see the changes.
echo.
echo Final values:
call :print_current "%VAR1%" "%SCOPE%"
call :print_current "%VAR2%" "%SCOPE%"
echo.
exit /b 0

:: ---------------- Subroutines ----------------

:configure_var
rem %1=VAR  %2=SCOPE(User|Machine)
set "VAR=%~1"
set "SCOPE=%~2"

call :get_current_from_registry "%VAR%" "%SCOPE%" CURVAL
if defined CURVAL (
  echo Current value for %VAR%:
  echo   %CURVAL%
  call :yesno "Do you want to override %VAR%" OVR
  if /i "%OVR%"=="Y" goto setnew
  echo Keeping existing value.
  echo.
  goto :eof
) else (
  echo %VAR% is not set.
)

:setnew
set "NEWVAL="
set /p NEWVAL=Enter value for %VAR%: 
call :set_env_ps "%VAR%" "%NEWVAL%" "%SCOPE%"
echo.
goto :eof

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
set "VAL="
for /f "tokens=1,2,* skip=2" %%A in ('reg query "%REGPATH%" /v %VAR% 2^>nul ^| findstr /i /r "^%VAR%[ ]"') do set "VAL=%%C"
endlocal & set "%~3=%VAL%"
goto :eof

:set_env_ps
rem %1=VAR  %2=VALUE  %3=SCOPE(User|Machine)
setlocal
set "VAR=%~1"
set "VAL=%~2"
set "SCOPE=%~3"
rem Escape single quotes for PowerShell
set "VAL=%VAL:'=''%"
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('%VAR%','%VAL%','%SCOPE%')" >nul 2>&1
if errorlevel 1 ( echo Failed to set %VAR% in scope %SCOPE%. ) else ( echo Set %VAR% in scope %SCOPE%. )
endlocal & goto :eof

:print_current
rem %1=VAR  %2=SCOPE
setlocal
call :get_current_from_registry "%~1" "%~2" CUR
echo   %~1=%CUR%
endlocal & goto :eof

:yesno
rem %1=Prompt  %2=OUTVAR(Y/N)
set "PROMPT=%~1"
:askagain
set "ANS="
set /p ANS=%PROMPT% (Y/N): 
if /i "%ANS%"=="Y" ( set "%~2=Y" & goto :eof )
if /i "%ANS%"=="N" ( set "%~2=N" & goto :eof )
echo Please answer Y or N.
goto askagain

:broadcast_env_change
rem Notify apps that environment changed
powershell -NoProfile -Command ^
  "$sig='[DllImport(\"user32.dll\",CharSet=CharSet.Auto)]public static extern IntPtr SendMessageTimeout(IntPtr hWnd,int Msg,IntPtr wParam,string lParam,int fuFlags,int uTimeout,out IntPtr lpdwResult)';" ^
  "$t=Add-Type -Name 'Win32' -Namespace EnvNotify -MemberDefinition $sig -PassThru;" ^
  "$HWND_BROADCAST=[intptr]0xffff; $WM_SETTINGCHANGE=0x1A; $SMTO_ABORTIFHUNG=2; [intptr]$r=[intptr]::Zero;" ^
  "[void]$t::SendMessageTimeout($HWND_BROADCAST,$WM_SETTINGCHANGE,[intptr]0,'Environment',$SMTO_ABORTIFHUNG,5000,[ref]$r)" >nul 2>&1
goto :eof
