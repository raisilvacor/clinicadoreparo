# 🚀 Instruções Rápidas - Migração para Banco de Dados

## ✅ O que foi feito

1. ✅ Modelos SQLAlchemy criados (`models.py`)
2. ✅ Script de migração criado (`migrate_to_db.py`)
3. ✅ `app.py` configurado para usar banco quando `DATABASE_URL` estiver definida
4. ✅ Rotas principais atualizadas (index, login admin)

## 📋 Próximos Passos

### 1. Configurar DATABASE_URL no Render

No seu serviço web Flask:
- **Environment** → Adicione: `DATABASE_URL` = Internal Database URL do seu banco

### 2. Executar Migração

**No Render Shell:**
```bash
python migrate_to_db.py
```

Isso migrará **TODOS** os dados dos arquivos JSON para o PostgreSQL:
- ✅ Clientes e ordens de serviço
- ✅ Serviços
- ✅ Técnicos
- ✅ Slides
- ✅ Footer
- ✅ Marcas
- ✅ Milestones
- ✅ Usuários admin
- ✅ Agendamentos
- ✅ Blog
- ✅ Comprovantes
- ✅ Cupons
- ✅ Contatos

### 3. Verificar

Após a migração, todos os dados estarão no banco e o site funcionará normalmente.

## ⚠️ Importante

- Os arquivos JSON **não serão deletados** (backup)
- A migração é segura (não duplica dados)
- O sistema usa banco quando `DATABASE_URL` existe, senão usa JSON

---

**Pronto para migrar!** Execute `python migrate_to_db.py` no Render Shell. 🎉

