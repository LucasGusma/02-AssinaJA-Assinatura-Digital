@echo off
chcp 65001 >nul
echo ========================================================
echo   Assistente de Publicacao no GitHub - 02-AssinaJA-Assinatura-Digital
echo ========================================================
echo.
echo 1. Va ate https://github.com/new no seu navegador.
echo 2. Crie um repositorio vazio (SEM README, SEM .gitignore).
echo 3. Copie o link HTTPS do repositorio (ex: https://github.com/seu-usuario/seu-repo.git).
echo.
set /p REPO_URL="Cole o link do seu repositorio aqui: "

if "%REPO_URL%"=="" (
    echo.
    echo [ERRO] Nenhum link informado. Operacao cancelada.
    pause
    exit /b
)

echo.
echo [1/5] Inicializando Git...
git init

echo [2/5] Indexando arquivos sanitizados...
git add .

echo [3/5] Criando commit inicial seguro...
git commit -m "feat: initial commit - 02-AssinaJA-Assinatura-Digital portfolio release"

echo [4/5] Definindo branch main...
git branch -M main

echo [5/5] Vinculando ao seu GitHub e enviando...
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git push -u origin main

echo.
echo ========================================================
echo   Concluido! O projeto ja esta no seu GitHub!
echo ========================================================
pause
