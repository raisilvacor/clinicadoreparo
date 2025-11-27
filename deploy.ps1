Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOY AUTOMATICO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Adicionando arquivos..." -ForegroundColor Yellow
git add -A
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO ao adicionar arquivos!" -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

Write-Host "[2/3] Fazendo commit..." -ForegroundColor Yellow
$commitMsg = "Deploy automatico - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git commit -m $commitMsg
if ($LASTEXITCODE -ne 0) {
    Write-Host "AVISO: Nenhuma alteracao para commitar" -ForegroundColor Yellow
}

Write-Host "[3/3] Enviando para GitHub..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO ao fazer push!" -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOY CONCLUIDO COM SUCESSO!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "O Render.com iniciara o deploy automaticamente." -ForegroundColor Green
Read-Host "Pressione Enter para sair"

