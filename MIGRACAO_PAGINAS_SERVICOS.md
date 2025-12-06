# Migração: Adicionar coluna 'imagem' à tabela 'paginas_servicos'

## Problema
A coluna `imagem` não existe na tabela `paginas_servicos` no banco de dados, causando erros ao tentar acessar páginas de serviços.

## Solução
Execute o script SQL `migrate_paginas_servicos_imagem.sql` no banco de dados PostgreSQL do Render.

## Como executar a migração:

### Opção 1: Via Render Dashboard
1. Acesse o dashboard do Render
2. Vá para o seu banco de dados PostgreSQL
3. Clique em "Connect" ou "Query"
4. Cole e execute o conteúdo do arquivo `migrate_paginas_servicos_imagem.sql`

### Opção 2: Via psql (linha de comando)
```bash
psql <DATABASE_URL> -f migrate_paginas_servicos_imagem.sql
```

### Opção 3: Via Python (temporário)
Você pode executar este código Python uma vez para adicionar a coluna:

```python
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE paginas_servicos 
            ADD COLUMN IF NOT EXISTS imagem VARCHAR(500);
        """))
        db.session.commit()
        print("✅ Coluna 'imagem' adicionada com sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
        db.session.rollback()
```

## Após a migração
Após executar a migração, descomente a linha no arquivo `models.py`:
```python
imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
```

E faça um novo deploy.

