# ✅ Checklist de Deploy

Use este checklist antes de fazer o deploy do projeto.

## 📋 Pré-Deploy

### Arquivos Criados
- [x] `Procfile` - Configuração para Heroku/Railway
- [x] `runtime.txt` - Versão do Python
- [x] `requirements.txt` - Inclui gunicorn
- [x] `.env.example` - Exemplo de variáveis
- [x] `DEPLOY.md` - Guia completo
- [x] `check_deploy.py` - Script de verificação

### Configurações do app.py
- [x] Usa `SECRET_KEY` de variável de ambiente
- [x] Usa `PORT` de variável de ambiente
- [x] Modo debug baseado em `FLASK_ENV`
- [x] Configurado para produção

## 🔐 Variáveis de Ambiente Obrigatórias

Configure estas variáveis na plataforma de deploy:

```bash
SECRET_KEY=sua_chave_secreta_super_segura_aqui
FLASK_ENV=production
```

### Gerar SECRET_KEY

Execute no terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 🚀 Passos para Deploy

### 1. Railway (Recomendado)

1. [ ] Criar conta no [Railway.app](https://railway.app)
2. [ ] Conectar repositório GitHub
3. [ ] Adicionar variáveis de ambiente:
   - `SECRET_KEY`
   - `FLASK_ENV=production`
4. [ ] Deploy automático acontece após push

### 2. Render

1. [ ] Criar conta no [Render.com](https://render.com)
2. [ ] Criar novo Web Service
3. [ ] Configurar:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
4. [ ] Adicionar variáveis de ambiente
5. [ ] Deploy

### 3. Heroku

1. [ ] Instalar Heroku CLI
2. [ ] `heroku login`
3. [ ] `heroku create nome-app`
4. [ ] `heroku config:set SECRET_KEY=...`
5. [ ] `heroku config:set FLASK_ENV=production`
6. [ ] `git push heroku main`

## ✅ Verificação Final

Execute o script de verificação:
```bash
python check_deploy.py
```

Deve mostrar:
- [OK] Todos os arquivos obrigatórios
- [OK] Todos os diretórios
- [AVISO] SECRET_KEY (normal em desenvolvimento)

## 🔍 Testes Pós-Deploy

Após o deploy, verifique:

- [ ] Site carrega corretamente
- [ ] Login admin funciona
- [ ] Upload de imagens funciona
- [ ] Formulários salvam dados
- [ ] PDFs são gerados corretamente
- [ ] WhatsApp float button funciona

## 📝 Notas Importantes

1. **SECRET_KEY**: NUNCA use a chave padrão em produção!
2. **Dados**: Os arquivos JSON em `data/` serão criados automaticamente
3. **Imagens**: Certifique-se de que os diretórios de upload existem
4. **SSL**: A maioria das plataformas fornece HTTPS automaticamente

## 🆘 Problemas Comuns

### Erro: "Module not found"
- Verifique se `requirements.txt` está completo
- Execute `pip install -r requirements.txt` localmente para testar

### Erro: "Port already in use"
- Configure `PORT` como variável de ambiente na plataforma

### Erro: "Permission denied"
- Verifique permissões dos diretórios `data/` e `static/`

### Site não carrega
- Verifique os logs da plataforma
- Confirme que `SECRET_KEY` está configurada
- Verifique se `FLASK_ENV=production`

## 📞 Suporte

Consulte `DEPLOY.md` para instruções detalhadas de cada plataforma.

