# Migração: Adicionar pagina_servico_id à tabela servicos

## Problema
O código foi atualizado para usar `pagina_servico_id` na tabela `servicos`, mas a coluna ainda não existe no banco de dados, causando o erro:
```
column servicos.pagina_servico_id does not exist
```

## Solução Rápida (Temporária)
O código foi temporariamente comentado para permitir que o app funcione. Os serviços aparecerão, mas não terão links para páginas de serviços até a migração ser executada.

## Migração Permanente

### Passo 1: Execute o script SQL
Execute o script SQL `migrate_servicos_pagina_servico.sql` no banco de dados PostgreSQL do Render.

**Como executar:**
1. Acesse o painel do Render
2. Vá em "Dashboard" > Seu serviço > "PostgreSQL"
3. Clique em "Connect" ou use um cliente PostgreSQL (pgAdmin, DBeaver, etc.)
4. Execute o conteúdo do arquivo `migrate_servicos_pagina_servico.sql`

**Ou via terminal (se tiver acesso SSH):**
```bash
psql $DATABASE_URL -f migrate_servicos_pagina_servico.sql
```

### Passo 2: Descomente o código
Após executar a migração, descomente as seguintes linhas:

**Em `models.py`:**
- Linha 55: `pagina_servico_id = db.Column(...)`
- Linha 62: `pagina_servico = db.relationship(...)`

**Em `app.py`:**
- Linha ~1758: `pagina_servico_id = request.form.get(...)`
- Linhas ~1771-1774: Bloco de conversão de `pagina_servico_id`
- Linha ~1784: `pagina_servico_id=pagina_id,` no construtor de `Servico`
- Linha ~1843: `pagina_servico_id = request.form.get(...)`
- Linhas ~1847-1850: Bloco de atribuição de `servico.pagina_servico_id`
- Linha ~1884: `'pagina_servico_id': servico.pagina_servico_id,`

### Passo 3: Reinicie o serviço
Após descomentar o código, faça commit e push. O Render reiniciará automaticamente.

### Passo 4: Adicione `pagina_slug` às rotas
Nas rotas `index()` e `servicos()` em `app.py`, adicione `'pagina_slug': s.pagina_servico.slug if s.pagina_servico else None` ao dicionário `servicos.append({...})`.

