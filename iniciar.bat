@echo off
cd /d "%~dp0"
set "NEW_LOGO=C:\Users\f015114\.gemini\antigravity\brain\4c42f1b7-1a09-4439-913b-076db36a5cf6\.user_uploaded\media_1794427999208_31839dac.png"
if exist "%NEW_LOGO%" (
  copy /y "%NEW_LOGO%" "%~dp0frontend\dist\logo-baleia-ia.png" >nul 2>&1
  copy /y "%NEW_LOGO%" "%~dp0frontend\public\logo-baleia-ia.png" >nul 2>&1
)
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0iniciar.py"
) else (
  start "" pythonw.exe "%~dp0iniciar.py"
)
