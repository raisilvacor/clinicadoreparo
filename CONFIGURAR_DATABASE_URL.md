# Como Configurar DATABASE_URL no Render.com

## Passo 1: Criar o Banco de Dados PostgreSQL no Render

1. Acesse o painel do Render: https://dashboard.render.com
2. Clique em **"New +"** no canto superior direito
3. Selecione **"PostgreSQL"**
4. Preencha os dados:
   - **Name**: `clinicadoreparo-db` (ou outro nome de sua escolha)
   - **Database**: `clinicadoreparo` (ou outro nome)
   - **User**: Deixe o padrão ou escolha um nome
   - **Region**: Escolha a região mais próxima (ex: `Oregon (US West)`)
   - **PostgreSQL Version**: Deixe a versão mais recente
   - **Plan**: Escolha o plano (Free tier está disponível)
5. Clique em **"Create Database"**

## Passo 2: Obter a URL de Conexão

1. Após criar o banco, você será redirecionado para a página do banco
2. Na seção **"Connections"**, você verá a **"Internal Database URL"** ou **"External Database URL"**
3. A URL terá o formato:
   ```
   postgres://usuario:senha@host:porta/database
   ```
4. **Copie essa URL completa**

## Passo 3: Adicionar DATABASE_URL no Serviço Web

1. No painel do Render, vá para o seu serviço Web (aplicação Flask)
2. Clique em **"Environment"** no menu lateral
3. Clique em **"Add Environment Variable"**
4. Preencha:
   - **Key**: `DATABASE_URL`
   - **Value**: Cole a URL do banco de dados que você copiou
5. Clique em **"Save Changes"**

## Passo 4: Reiniciar o Serviço

1. Após salvar a variável, o Render reiniciará automaticamente o serviço
2. Aguarde alguns minutos para o deploy completar
3. Verifique os logs para confirmar que está funcionando

## Passo 5: Migrar os Dados

1. Acesse o painel admin do seu site: `https://seu-site.onrender.com/admin`
2. Faça login
3. Vá para **"Migrar Dados"** no dashboard
4. Clique em **"Executar Migração"**
5. Aguarde a conclusão da migração

## Verificação

Após configurar, você pode verificar se está funcionando:

1. Acesse o painel admin
2. Se a mensagem "Banco de dados não configurado" não aparecer mais, está funcionando!
3. Verifique os logs do Render para confirmar a conexão

## Formato da URL

A URL do Render geralmente vem no formato:
```
postgres://usuario:senha@dpg-xxxxx-a.oregon-postgres.render.com/database
```

O código já converte automaticamente `postgres://` para `postgresql://` se necessário.

## Problemas Comuns

### Erro: "ModuleNotFoundError: No module named 'psycopg2'"
- **Solução**: O `psycopg2-binary` já está no `requirements.txt`, mas se ainda der erro, verifique se o deploy foi feito corretamente.

### Erro: "Connection refused"
- **Solução**: Verifique se a URL está correta e se o banco de dados está ativo no Render.

### Erro: "Database does not exist"
- **Solução**: Verifique se o nome do banco na URL corresponde ao nome criado.

## Nota Importante

⚠️ **A URL do banco contém credenciais sensíveis. Nunca compartilhe ou commite essa URL no Git!**

O Render gerencia isso automaticamente através das variáveis de ambiente.

