# 📤 Comandos para Enviar Deploy ao GitHub

Repositório: https://github.com/raisilvacor/clinicadoreparo.git

## ⚠️ Situação Atual

Há um merge em andamento. Siga estes passos:

## 🔄 Passo 1: Concluir o Merge

```bash
# Finalizar o merge
git commit -m "Merge: Integrar alterações do repositório remoto"
```

## 📦 Passo 2: Adicionar Todos os Arquivos de Deploy

```bash
# Adicionar todos os arquivos novos e modificados
git add .

# Verificar o que será commitado
git status
```

## 💾 Passo 3: Fazer Commit

```bash
# Commit com mensagem descritiva
git commit -m "Adicionar arquivos de deploy e configurações de produção

- Adicionar Procfile para Railway/Heroku
- Adicionar runtime.txt com Python 3.12
- Adicionar gunicorn ao requirements.txt
- Atualizar app.py para usar variáveis de ambiente
- Adicionar guias de deploy (DEPLOY.md, DEPLOY_GITHUB.md)
- Adicionar script de verificação (check_deploy.py)
- Adicionar .env.example com variáveis necessárias
- Atualizar .gitignore para produção
- Adicionar todas as novas funcionalidades (blog, agendamentos, etc.)"
```

## 🚀 Passo 4: Enviar para GitHub

```bash
# Enviar para o repositório remoto
git push origin main
```

Se houver conflitos, use:

```bash
# Puxar alterações remotas primeiro
git pull origin main --rebase

# Resolver conflitos se houver
# Depois fazer push
git push origin main
```

## ✅ Verificação

Após o push, verifique no GitHub:
- https://github.com/raisilvacor/clinicadoreparo

Todos os arquivos devem estar presentes:
- ✅ Procfile
- ✅ runtime.txt
- ✅ requirements.txt (com gunicorn)
- ✅ DEPLOY.md
- ✅ DEPLOY_GITHUB.md
- ✅ check_deploy.py
- ✅ .env.example

## 🎯 Próximo Passo: Deploy

Após enviar para o GitHub, siga as instruções em `DEPLOY_GITHUB.md` para fazer o deploy na plataforma escolhida.

