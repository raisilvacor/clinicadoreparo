# 🔄 Como Migrar Dados para o Banco de Dados Render

## ⚡ Passo a Passo Rápido

### 1. Configurar DATABASE_URL no Render

1. No seu serviço web Flask no Render
2. Vá em **"Environment"**
3. Adicione a variável:
   - **Key**: `DATABASE_URL`
   - **Value**: Cole a **Internal Database URL** do seu banco PostgreSQL
4. **Save Changes**

### 2. Executar Migração

**Opção A: Via Shell do Render (Recomendado)**

1. No Render, vá no seu serviço web
2. Clique em **"Shell"** (no menu lateral)
3. Execute:
   ```bash
   python migrate_to_db.py
   ```

**Opção B: Via Terminal Local**

1. Configure `DATABASE_URL` localmente:
   ```bash
   # Windows PowerShell
   $env:DATABASE_URL="postgresql://usuario:senha@host:porta/database"
   
   # Linux/Mac
   export DATABASE_URL="postgresql://usuario:senha@host:porta/database"
   ```

2. Execute a migração:
   ```bash
   python migrate_to_db.py
   ```

### 3. Verificar Migração

Após executar, você verá mensagens como:
```
✅ Migrados X clientes e suas ordens de serviço
✅ Migrados X serviços
✅ Migrados X técnicos
...
✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
```

### 4. Testar

1. Acesse seu site no Render
2. Verifique se os dados aparecem corretamente
3. Teste login admin
4. Verifique se consegue criar/editar registros

## 📋 O que será migrado

- ✅ Clientes (com todas as ordens de serviço)
- ✅ Serviços
- ✅ Técnicos
- ✅ Slides
- ✅ Footer (configurações)
- ✅ Marcas
- ✅ Milestones
- ✅ Usuários Admin
- ✅ Agendamentos
- ✅ Artigos do Blog
- ✅ Comprovantes
- ✅ Cupons de Fidelidade
- ✅ Contatos

## ⚠️ Importante

- Os arquivos JSON originais **NÃO serão deletados** (servem como backup)
- A migração é **idempotente** (pode executar várias vezes sem duplicar dados)
- Se um registro já existe no banco, ele será ignorado

## 🔍 Verificar Dados no Banco

No Render, você pode usar o **Shell** para verificar:

```python
from app import app, db
from models import Cliente, Servico

with app.app_context():
    # Contar registros
    print(f"Clientes: {Cliente.query.count()}")
    print(f"Serviços: {Servico.query.count()}")
```

## 🆘 Problemas

### Erro: "relation does not exist"
- Execute `db.create_all()` primeiro
- Ou execute a migração novamente (ela cria as tabelas automaticamente)

### Erro: "connection refused"
- Verifique se `DATABASE_URL` está correta
- Use **Internal Database URL** (não External)

### Dados duplicados
- A migração verifica se o registro já existe antes de inserir
- Se houver duplicatas, delete manualmente no banco ou ajuste o script

---

**Pronto!** Após a migração, todos os dados estarão no banco PostgreSQL do Render! 🎉

