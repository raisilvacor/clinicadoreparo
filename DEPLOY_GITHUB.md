# 🚀 Guia de Deploy - Repositório GitHub

Repositório: [https://github.com/raisilvacor/clinicadoreparo.git](https://github.com/raisilvacor/clinicadoreparo.git)

## 📋 Pré-requisitos

- Conta no GitHub (já configurada)
- Conta em uma plataforma de deploy (Railway, Render, Heroku, etc.)
- Git instalado localmente

## 🔄 Sincronizar com o Repositório

### 1. Verificar repositório remoto

```bash
git remote -v
```

Se não estiver configurado, adicione:

```bash
git remote add origin https://github.com/raisilvacor/clinicadoreparo.git
```

### 2. Fazer commit dos arquivos de deploy

```bash
# Adicionar todos os arquivos novos
git add .

# Fazer commit
git commit -m "Adicionar arquivos de deploy e configurações de produção"

# Enviar para o GitHub
git push origin main
```

## 🚀 Deploy no Railway (Recomendado)

### Passo 1: Criar Projeto no Railway

1. Acesse [railway.app](https://railway.app)
2. Faça login com sua conta GitHub
3. Clique em **"New Project"**
4. Selecione **"Deploy from GitHub repo"**
5. Escolha o repositório: `raisilvacor/clinicadoreparo`

### Passo 2: Configurar Variáveis de Ambiente

1. No projeto Railway, vá em **"Variables"**
2. Adicione as seguintes variáveis:

```
SECRET_KEY=sua_chave_secreta_gerada_aqui
FLASK_ENV=production
PORT=5000
```

**Para gerar SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Passo 3: Deploy Automático

- O Railway detecta automaticamente o `Procfile`
- O deploy acontece automaticamente após cada push no GitHub
- A URL do site será fornecida pelo Railway

### Passo 4: Configurar Domínio (Opcional)

1. No projeto Railway, vá em **"Settings"**
2. Em **"Domains"**, adicione seu domínio personalizado

## 🚀 Deploy no Render

### Passo 1: Criar Web Service

1. Acesse [render.com](https://render.com)
2. Faça login com GitHub
3. Clique em **"New"** > **"Web Service"**
4. Conecte o repositório: `raisilvacor/clinicadoreparo`

### Passo 2: Configurações

- **Name**: `clinicadoreparo` (ou o nome que preferir)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

### Passo 3: Variáveis de Ambiente

Na seção **"Environment Variables"**, adicione:

```
SECRET_KEY=sua_chave_secreta_gerada_aqui
FLASK_ENV=production
```

### Passo 4: Deploy

- Clique em **"Create Web Service"**
- O deploy será iniciado automaticamente
- A URL será: `https://clinicadoreparo.onrender.com` (ou o nome escolhido)

## 🚀 Deploy no Heroku

### Passo 1: Instalar Heroku CLI

```bash
# Windows: Baixe do site https://devcenter.heroku.com/articles/heroku-cli
# Mac/Linux:
curl https://cli-assets.heroku.com/install.sh | sh
```

### Passo 2: Login e Criar App

```bash
# Login
heroku login

# Criar aplicação
heroku create clinicadoreparo

# Adicionar remote do Heroku
heroku git:remote -a clinicadoreparo
```

### Passo 3: Configurar Variáveis

```bash
# Gerar SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Configurar variáveis
heroku config:set SECRET_KEY=sua_chave_secreta_gerada
heroku config:set FLASK_ENV=production
```

### Passo 4: Deploy

```bash
# Enviar código para Heroku
git push heroku main
```

## ✅ Verificação Pós-Deploy

Após o deploy, verifique:

1. **Site carrega**: Acesse a URL fornecida pela plataforma
2. **Login admin**: `/admin/login`
   - Usuário: `admin`
   - Senha: `admin123`
3. **Funcionalidades**:
   - Upload de imagens funciona
   - Formulários salvam dados
   - PDFs são gerados
   - WhatsApp float button funciona

## 🔄 Atualizações Futuras

Para atualizar o site após fazer alterações:

```bash
# 1. Fazer alterações no código localmente

# 2. Commit e push para GitHub
git add .
git commit -m "Descrição das alterações"
git push origin main

# 3. O deploy automático será acionado (Railway/Render)
# Ou para Heroku:
git push heroku main
```

## 🔐 Segurança em Produção

⚠️ **IMPORTANTE**: Após o primeiro deploy:

1. **Altere a senha do admin**:
   - Acesse `/admin/usuarios`
   - Edite o usuário admin e altere a senha

2. **Gere uma SECRET_KEY segura**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Configure HTTPS**: A maioria das plataformas fornece automaticamente

## 📝 Checklist Final

- [ ] Código enviado para GitHub
- [ ] Variáveis de ambiente configuradas
- [ ] SECRET_KEY gerada e configurada
- [ ] FLASK_ENV=production configurado
- [ ] Deploy realizado com sucesso
- [ ] Site acessível e funcionando
- [ ] Login admin testado
- [ ] Senha do admin alterada

## 🆘 Troubleshooting

### Erro: "Module not found"
- Verifique se `requirements.txt` está completo
- Confirme que todas as dependências estão listadas

### Erro: "SECRET_KEY not set"
- Configure a variável `SECRET_KEY` na plataforma de deploy

### Site não carrega
- Verifique os logs da plataforma
- Confirme que o `Procfile` está correto
- Verifique se a porta está configurada corretamente

### Erro de permissão em arquivos
- Os diretórios `data/` e `static/` serão criados automaticamente
- Se necessário, verifique permissões na plataforma

## 📞 Links Úteis

- **Repositório**: https://github.com/raisilvacor/clinicadoreparo
- **Railway**: https://railway.app
- **Render**: https://render.com
- **Heroku**: https://heroku.com

---

**Pronto para deploy!** 🎉

