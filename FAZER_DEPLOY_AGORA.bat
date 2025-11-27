@echo off
chcp 65001
cls
echo.
echo ============================================
echo    DEPLOY AUTOMATICO - EXECUTAR AGORA
echo ============================================
echo.
echo Este script vai:
echo 1. Adicionar todos os arquivos modificados
echo 2. Fazer commit das mudancas
echo 3. Enviar para o GitHub
echo.
pause
echo.
echo [1/3] Adicionando arquivos...
git add -A
if %errorlevel% neq 0 (
    echo ERRO ao adicionar!
    pause
    exit /b 1
)
echo OK!
echo.
echo [2/3] Fazendo commit...
git commit -m "Deploy: Melhorias na conexao do banco de dados"
if %errorlevel% neq 0 (
    echo AVISO: Nada para commitar ou erro
)
echo.
echo [3/3] Enviando para GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo ERRO ao enviar!
    echo.
    echo Verifique:
    echo - Conexao com internet
    echo - Credenciais do GitHub
    echo.
    pause
    exit /b 1
)
echo.
echo ============================================
echo    DEPLOY CONCLUIDO COM SUCESSO!
echo ============================================
echo.
echo O Render vai iniciar o deploy automaticamente.
echo.
pause

