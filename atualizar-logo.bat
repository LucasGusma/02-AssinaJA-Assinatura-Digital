@echo off
set "SRC=C:\Users\f015114\.gemini\antigravity\brain\4c42f1b7-1a09-4439-913b-076db36a5cf6\.user_uploaded\media_1794427999208_31839dac.png"
if exist "%SRC%" (
  copy /y "%SRC%" "%~dp0frontend\dist\logo-baleia-ia.png" >nul
  copy /y "%SRC%" "%~dp0frontend\public\logo-baleia-ia.png" >nul
  echo Logo BaleIA atualizada com sucesso!
) else (
  echo Arquivo de imagem nao encontrado.
)
