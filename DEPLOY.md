# Guia de Deploy - Clínica do Reparo

Este guia contém instruções para fazer deploy do projeto em diferentes plataformas.

## 📋 Pré-requisitos

- Python 3.12 ou superior
- Git instalado
- Conta na plataforma de deploy escolhida

## 🚀 Opções de Deploy

### 1. Railway (Recomendado - Grátis)

1. **Criar conta no Railway**
   - Acesse [railway.app](https://railway.app)
   - Faça login com GitHub

2. **Conectar repositório**
   - Clique em "New Project"
   - Selecione "Deploy from GitHub repo"
   - Escolha seu repositório

3. **Configurar variáveis de ambiente**
   - Vá em "Variables"
   - Adicione as variáveis do arquivo `.env.example`:
     ```
     SECRET_KEY=sua_chave_secreta_super_segura_aqui
     FLASK_ENV=production
     PORT=5000
     ```

4. **Deploy automático**
   - O Railway detecta automaticamente o `Procfile`
   - O deploy acontece automaticamente após push no GitHub

### 2. Render

1. **Criar conta no Render**
   - Acesse [render.com](https://render.com)
   - Faça login com GitHub

2. **Criar novo Web Service**
   - Clique em "New" > "Web Service"
   - Conecte seu repositório GitHub

3. **Configurações**
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3

4. **Variáveis de ambiente**
   - Adicione as variáveis do `.env.example` na seção "Environment"

### 3. Heroku

1. **Instalar Heroku CLI**
   ```bash
   # Windows
   # Baixe do site: https://devcenter.heroku.com/articles/heroku-cli
   
   # Mac/Linux
   curl https://cli-assets.heroku.com/install.sh | sh
   ```

2. **Login no Heroku**
   ```bash
   heroku login
   ```

3. **Criar aplicação**
   ```bash
   heroku create nome-da-sua-app
   ```

4. **Configurar variáveis de ambiente**
   ```bash
   heroku config:set SECRET_KEY=sua_chave_secreta_super_segura
   heroku config:set FLASK_ENV=production
   ```

5. **Deploy**
   ```bash
   git push heroku main
   ```

### 4. PythonAnywhere

1. **Criar conta no PythonAnywhere**
   - Acesse [pythonanywhere.com](https://www.pythonanywhere.com)
   - Crie uma conta gratuita

2. **Upload do código**
   - Use o console Bash para clonar seu repositório:
     ```bash
     git clone https://github.com/seu-usuario/seu-repositorio.git
     ```

3. **Configurar aplicação Web**
   - Vá em "Web" > "Add a new web app"
   - Escolha Flask e Python 3.12

4. **Configurar WSGI**
   - Edite o arquivo `wsgi.py`:
     ```python
     import sys
     path = '/home/seuusuario/seu-repositorio'
     if path not in sys.path:
         sys.path.append(path)
     
     from app import app as application
     ```

5. **Instalar dependências**
   - No console Bash:
     ```bash
     pip3.12 install --user -r requirements.txt
     ```

## 🔐 Configurações de Segurança

### Gerar SECRET_KEY

**Importante**: Nunca use a SECRET_KEY padrão em produção!

Para gerar uma SECRET_KEY segura:

```python
import secrets
print(secrets.token_hex(32))
```

Ou use:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Variáveis de Ambiente Obrigatórias

- `SECRET_KEY`: Chave secreta para sessões Flask (obrigatória)
- `FLASK_ENV`: `production` para produção, `development` para desenvolvimento

### Variáveis Opcionais

- `PORT`: Porta do servidor (padrão: 5000)
- `EVOLUTION_API_URL`: URL da API Evolution para WhatsApp
- `EVOLUTION_API_KEY`: Chave da API Evolution
- `EVOLUTION_INSTANCE`: Instância da Evolution API
- `TWILIO_ACCOUNT_SID`: Account SID do Twilio
- `TWILIO_AUTH_TOKEN`: Auth Token do Twilio
- `TWILIO_WHATSAPP_FROM`: Número WhatsApp do Twilio

## 📁 Estrutura de Arquivos

Certifique-se de que os seguintes diretórios existam:

```
data/
static/
  css/
  js/
  img/
    blog/
    marcas/
    milestones/
    servicos/
    slides/
  logos/
  pdfs/
templates/
```

## 🔧 Comandos Úteis

### Instalar dependências localmente
```bash
pip install -r requirements.txt
```

### Executar localmente
```bash
python app.py
```

### Executar com Gunicorn (produção)
```bash
gunicorn app:app
```

### Executar com Gunicorn (múltiplos workers)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📝 Checklist de Deploy

- [ ] Variável `SECRET_KEY` configurada e segura
- [ ] `FLASK_ENV=production` configurado
- [ ] Todos os diretórios necessários criados
- [ ] Dependências instaladas (`requirements.txt`)
- [ ] Testes locais realizados
- [ ] Variáveis de ambiente configuradas na plataforma
- [ ] Domínio personalizado configurado (opcional)
- [ ] SSL/HTTPS habilitado (geralmente automático)

## 🐛 Troubleshooting

### Erro: "Module not found"
- Verifique se todas as dependências estão no `requirements.txt`
- Execute `pip install -r requirements.txt`

### Erro: "Port already in use"
- Altere a porta no arquivo `.env` ou variável de ambiente `PORT`

### Erro: "SECRET_KEY not set"
- Configure a variável de ambiente `SECRET_KEY` na plataforma

### Erro: "Permission denied" em arquivos
- Verifique permissões dos diretórios `data/` e `static/`

## 📞 Suporte

Para mais informações sobre configuração de WhatsApp, consulte `CONFIGURACAO_WHATSAPP.md`

## 🔄 Atualizações

Após fazer alterações no código:

1. Commit as alterações:
   ```bash
   git add .
   git commit -m "Descrição das alterações"
   git push
   ```

2. O deploy automático será acionado (se configurado)
   - Ou faça deploy manual na plataforma escolhida

