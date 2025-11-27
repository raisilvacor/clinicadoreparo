# Como Configurar DATABASE_URL no Render

## Problema
Se você está recebendo a mensagem "Banco de dados não configurado. Configure DATABASE_URL no Render", significa que a variável de ambiente `DATABASE_URL` não está configurada no seu serviço web no Render.

## Solução

### Opção 1: Usando o Dashboard do Render (Recomendado)

1. Acesse o [Dashboard do Render](https://dashboard.render.com)
2. Vá para o seu serviço web (clinicadoreparo)
3. Clique em **Environment** (ou **Environment Variables**)
4. Procure por `DATABASE_URL`
5. Se não existir, clique em **Add Environment Variable**
6. Configure:
   - **Key**: `DATABASE_URL`
   - **Value**: Copie a **External Database URL** do seu banco de dados PostgreSQL
     - Vá para o banco de dados (clinicadoreparo-db)
     - Na aba **Info**, copie o **External Database URL**
     - Cole no campo **Value**
7. Clique em **Save Changes**
8. O Render irá reiniciar o serviço automaticamente

### Opção 2: Usando o render.yaml (Se você usa Blueprint)

Se você está usando o arquivo `render.yaml`, o `DATABASE_URL` deve ser configurado automaticamente. Verifique:

1. Se o banco de dados tem o nome correto: `clinicadoreparo-db`
2. Se o serviço web está vinculado ao banco corretamente
3. Se você fez o deploy usando o Blueprint

### Como verificar se está funcionando

1. Após configurar o `DATABASE_URL`, acesse os logs do serviço web no Render
2. Procure por mensagens como:
   - `DEBUG: ✅ Banco de dados configurado e conectado com sucesso!`
   - `DEBUG use_database: ✅ Conexão com banco de dados OK`
3. Se aparecer erros, verifique:
   - Se a URL do banco está correta
   - Se o banco está ativo (não suspenso)
   - Se a URL usa `postgresql://` (não `postgres://`)

### Formato da DATABASE_URL

A URL deve ter o formato:
```
postgresql://usuario:senha@host:porta/database?sslmode=require
```

Exemplo:
```
postgresql://clinicadoreparo_db_user:senha@dpg-xxxxx.oregon-postgres.render.com:5432/clinicadoreparo_db?sslmode=require
```

### Importante

- Use sempre a **External Database URL** (não a Internal)
- O Render adiciona automaticamente o `?sslmode=require` se necessário
- Após configurar, aguarde o serviço reiniciar (pode levar 1-2 minutos)

