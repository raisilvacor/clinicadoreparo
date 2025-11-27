@echo off
git add templates/index.html static/js/main.js data/slides.json
git commit -m "Deploy: Ajustar altura do slide automaticamente e atualizar slides.json"
git push origin main
pause

