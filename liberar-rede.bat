@echo off
echo AssinaJA - permitir TCP 8765 apenas para a sub-rede local no perfil de dominio.
echo Execute este arquivo como administrador.
netsh advfirewall firewall show rule name="AssinaJA-Demo-LAN-8765" >nul 2>&1
if not errorlevel 1 (
  echo A regra ja existe. Solicite a TI a verificacao do escopo.
  pause
  exit /b 0
)
netsh advfirewall firewall add rule name="AssinaJA-Demo-LAN-8765" dir=in action=allow protocol=TCP localport=8765 remoteip=localsubnet profile=domain enable=yes
if errorlevel 1 (
  echo Nao foi possivel liberar a porta. Solicite a TI a execucao como administrador.
) else (
  echo Regra de rede local criada.
)
pause
