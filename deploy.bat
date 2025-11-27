@echo off
echo ========================================
echo DEPLOY AUTOMATICO
echo ========================================
echo.

git add -A
if %errorlevel% neq 0 (
    echo ERRO ao adicionar arquivos!
    pause
    exit /b 1
)

git commit -m "Deploy automatico - %date% %time%"
if %errorlevel% neq 0 (
    echo AVISO: Nenhuma alteracao para commitar
)

git push origin main
if %errorlevel% neq 0 (
    echo ERRO ao fazer push!
    pause
    exit /b 1
)

echo.
echo ========================================
echo DEPLOY CONCLUIDO!
echo ========================================
pause
