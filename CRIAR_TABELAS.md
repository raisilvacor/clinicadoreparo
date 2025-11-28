# Como Criar as Tabelas no Banco de Dados

Este guia explica como criar todas as tabelas no banco de dados PostgreSQL usando a **External Database URL** do Render.

## Pré-requisitos

1. Python 3.7+ instalado
2. Todas as dependências instaladas (`pip install -r requirements.txt`)
3. A **External Database URL** do seu banco de dados no Render

## Passo 1: Obter a External Database URL

1. Acesse o painel do Render: https://dashboard.render.com
2. Vá até o seu banco de dados PostgreSQL
3. Na seção **Connections**, copie a **External Database URL**
   - Ela deve começar com `postgres://` ou `postgresql://`
   - Exemplo: `postgres://usuario:senha@host:porta/database`

## Passo 2: Executar o Script

### Opção 1: Usando variável de ambiente (Recomendado)

**Windows (PowerShell):**
```powershell
$env:DATABASE_URL="postgresql://usuario:senha@host:porta/database"
python create_tables.py
```

**Windows (CMD):**
```cmd
set DATABASE_URL=postgresql://usuario:senha@host:porta/database
python create_tables.py
```

**Linux/Mac:**
```bash
export DATABASE_URL="postgresql://usuario:senha@host:porta/database"
python create_tables.py
```

### Opção 2: Editar o script diretamente

1. Abra o arquivo `create_tables.py`
2. Encontre a linha: `database_url = os.environ.get('DATABASE_URL', '')`
3. Substitua por: `database_url = 'postgresql://usuario:senha@host:porta/database'`
4. Execute: `python create_tables.py`

## O que o Script Faz

1. ✅ Conecta ao banco de dados PostgreSQL
2. ✅ Verifica tabelas existentes
3. ✅ Cria todas as tabelas necessárias:
   - `clientes` - Clientes cadastrados
   - `imagens` - Imagens armazenadas no banco
   - `pdf_documents` - PDFs armazenados no banco
   - `servicos` - Serviços oferecidos
   - `tecnicos` - Técnicos cadastrados
   - `ordens_servico` - Ordens de serviço
   - `comprovantes` - Comprovantes de pagamento
   - `cupons` - Cupons de fidelidade
   - `slides` - Slides da homepage
   - `footer` - Dados do rodapé
   - `marcas` - Marcas atendidas
   - `milestones` - Marcos/conquistas
   - `admin_users` - Usuários administradores
   - `agendamentos` - Agendamentos de serviços
   - `contatos` - Mensagens de contato
   - `fornecedores` - Fornecedores cadastrados
   - `artigos` - Artigos do blog (se usado)

4. ✅ Verifica se todas as tabelas foram criadas corretamente
5. ✅ Mostra a estrutura da tabela `fornecedores` (se criada)

## Exemplo de Saída

```
============================================================
  CRIADOR DE TABELAS - Banco de Dados PostgreSQL
============================================================

🔗 Conectando ao banco de dados...
   URL: postgresql://usuario:senha@host:porta/database...
✅ Conectado ao PostgreSQL: PostgreSQL 15.0...

📋 Criando tabelas...

📊 Tabelas existentes: 0

🔨 Criando/atualizando tabelas...

✅ Tabelas após criação: 17
   ✅ admin_users
   ✅ agendamentos
   ✅ clientes
   ✅ comprovantes
   ✅ contatos
   ✅ cupons
   ✅ footer
   ✅ fornecedores
   ✅ imagens
   ✅ marcas
   ✅ milestones
   ✅ ordens_servico
   ✅ pdf_documents
   ✅ servicos
   ✅ slides
   ✅ tecnicos

✅ Tabela 'fornecedores' criada com sucesso!
   Colunas: 11
      - id (INTEGER)
      - nome (VARCHAR(200))
      - contato (VARCHAR(200))
      - telefone (VARCHAR(20))
      - email (VARCHAR(200))
      - endereco (TEXT)
      - cnpj (VARCHAR(18))
      - tipo_servico (VARCHAR(200))
      - observacoes (TEXT)
      - ativo (BOOLEAN)
      - data_cadastro (TIMESTAMP)

🎉 Processo concluído!

✅ Todas as tabelas foram criadas com sucesso!
   Você pode agora usar o sistema normalmente.
```

## Solução de Problemas

### Erro: "DATABASE_URL não encontrada"
- Certifique-se de que a variável de ambiente está configurada corretamente
- Ou edite o script para incluir a URL diretamente

### Erro: "connection refused" ou "timeout"
- Verifique se a External Database URL está correta
- Verifique se o firewall permite conexões externas
- No Render, certifique-se de que o banco está ativo (não hibernado)

### Erro: "permission denied"
- Verifique se o usuário do banco tem permissões para criar tabelas
- No Render, use o usuário principal do banco (não um usuário limitado)

### Tabelas não são criadas
- Verifique os logs do script para ver erros específicos
- Tente executar o script novamente
- Verifique se há conflitos de nomes de tabelas

## Notas Importantes

⚠️ **ATENÇÃO**: Este script cria tabelas, mas **NÃO** apaga dados existentes. Se uma tabela já existe, ela será mantida.

✅ O script é seguro e pode ser executado múltiplas vezes sem problemas.

✅ Após criar as tabelas, você pode usar o sistema normalmente. O botão "Criar Tabela no Banco" na interface admin também funciona, mas este script é mais completo e mostra mais informações.

