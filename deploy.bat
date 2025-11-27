@echo off
echo ========================================
echo DEPLOY AUTOMATICO
echo ========================================
echo.

echo [1/3] Adicionando arquivos...
git add -A
if %errorlevel% neq 0 (
    echo ERRO ao adicionar arquivos!
    pause
    exit /b 1
)

echo [2/3] Fazendo commit...
git commit -m "Deploy automatico - %date% %time%"
if %errorlevel% neq 0 (
    echo AVISO: Nenhuma alteracao para commitar ou commit ja existe
)

echo [3/3] Enviando para GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo ERRO ao fazer push!
    pause
    exit /b 1
)

echo.
echo ========================================
echo DEPLOY CONCLUIDO COM SUCESSO!
echo ========================================
echo O Render.com iniciara o deploy automaticamente.
timeout /t 3 >nul
