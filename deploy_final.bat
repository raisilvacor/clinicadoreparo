@echo off
chcp 65001 >nul
echo ========================================
echo DEPLOY AUTOMATICO - SISTEMA VERIFICADO
echo ========================================
echo.

echo [1/6] Verificando diretorio...
if not exist "app.py" (
    echo ERRO: app.py nao encontrado!
    pause
    exit /b 1
)
echo OK: Diretorio correto
echo.

echo [2/6] Verificando status do git...
git status --short
echo.

echo [3/6] Adicionando todos os arquivos...
git add -A
if %errorlevel% neq 0 (
    echo ERRO ao adicionar arquivos!
    pause
    exit /b 1
)
echo OK: Arquivos adicionados
echo.

echo [4/6] Verificando o que sera commitado...
git status --short
echo.

echo [5/6] Fazendo commit...
git commit -m "Deploy: Melhorias na conexao do banco de dados"
if %errorlevel% neq 0 (
    echo AVISO: Nenhuma mudanca para commitar ou erro no commit
) else (
    echo OK: Commit realizado
)
echo.

echo [6/6] Fazendo push para origin/main...
git push origin main
if %errorlevel% neq 0 (
    echo ERRO ao fazer push!
    echo.
    echo Verificando se ha commits pendentes...
    git log origin/main..HEAD --oneline
    pause
    exit /b 1
)
echo OK: Push realizado com sucesso!
echo.

echo ========================================
echo DEPLOY CONCLUIDO!
echo ========================================
echo.
echo Verifique o GitHub para confirmar:
echo https://github.com/raisilvacor/clinicadoreparo
echo.
pause

