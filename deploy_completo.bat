@echo off
echo ========================================
echo Iniciando deploy completo...
echo ========================================
echo.

echo Adicionando arquivos ao git...
git add -A
if %errorlevel% neq 0 (
    echo ERRO ao adicionar arquivos!
    pause
    exit /b 1
)

echo.
echo Verificando status...
git status --short

echo.
echo Fazendo commit...
git commit -m "Deploy completo: Debug DATABASE_URL e melhorias"
if %errorlevel% neq 0 (
    echo ERRO ao fazer commit!
    pause
    exit /b 1
)

echo.
echo Fazendo push para origin main...
git push origin main
if %errorlevel% neq 0 (
    echo ERRO ao fazer push!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Deploy concluido com sucesso!
echo ========================================
echo.
pause

