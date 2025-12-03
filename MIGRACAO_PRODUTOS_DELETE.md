# Migração: Permitir Exclusão de Produtos com Itens de Pedido

## O que foi alterado?

Agora é possível excluir produtos mesmo que tenham itens em pedidos. Os dados históricos são preservados:

1. **Campos adicionais em `itens_pedido`**:
   - `produto_nome`: Nome do produto no momento da compra
   - `produto_sku`: SKU do produto no momento da compra

2. **Foreign Key modificada**:
   - `produto_id` agora permite NULL
   - Usa `ON DELETE SET NULL` - quando produto é excluído, `produto_id` vira NULL mas os dados históricos são mantidos

## Como executar a migração?

### Opção 1: Via Render Dashboard (Recomendado)

1. Acesse o dashboard do Render
2. Vá em seu banco de dados PostgreSQL
3. Clique em "Connect" ou "Query"
4. Cole e execute o conteúdo do arquivo `migrate_produtos_delete.sql`

### Opção 2: Via psql (linha de comando)

```bash
psql $DATABASE_URL < migrate_produtos_delete.sql
```

### Opção 3: Via Python (se preferir)

Execute no console Python do Render ou localmente:

```python
from app import app, db
from sqlalchemy import text

with app.app_context():
    with open('migrate_produtos_delete.sql', 'r') as f:
        sql = f.read()
        db.session.execute(text(sql))
        db.session.commit()
```

## O que acontece após a migração?

- ✅ Produtos podem ser excluídos mesmo com itens em pedidos
- ✅ Dados históricos dos pedidos são preservados (nome, SKU, preço)
- ✅ Pedidos antigos continuam exibindo informações corretas
- ✅ Novos pedidos salvam automaticamente os dados históricos

## Verificação

Após executar a migração, você pode verificar se funcionou:

```sql
SELECT 
    COUNT(*) as total_itens,
    COUNT(produto_id) as itens_com_produto,
    COUNT(*) - COUNT(produto_id) as itens_sem_produto,
    COUNT(produto_nome) as itens_com_nome_historico
FROM itens_pedido;
```

## Importante

- Esta migração é **segura** e **reversível** (pode ser desfeita se necessário)
- Não perde dados existentes
- Funciona com pedidos antigos e novos

