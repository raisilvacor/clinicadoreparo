# Migração - Correção do Sistema de Pedidos

## Problemas Corrigidos

Este script corrige vários problemas no sistema de pedidos:

1. **produto_id em itens_pedido**: Agora permite NULL para produtos removidos
2. **Foreign Key**: Atualizada para ON DELETE SET NULL
3. **Colunas Mercado Pago**: Adicionadas se não existirem
4. **Colunas históricas**: produto_nome e produto_sku adicionadas e preenchidas

## Como Executar

1. Acesse o dashboard do Render
2. Vá em seu banco de dados PostgreSQL
3. Execute o conteúdo do arquivo `migrate_pedidos_fix.sql`

## O que o Script Faz

1. Remove NOT NULL de produto_id em itens_pedido
2. Atualiza foreign key para ON DELETE SET NULL
3. Adiciona colunas do Mercado Pago (se não existirem)
4. Adiciona colunas produto_nome e produto_sku (se não existirem)
5. Preenche dados históricos dos produtos existentes

## Melhorias no Código

- Tratamento robusto de erros em todas as funções de pedidos
- Suporte a produtos removidos (produto_id NULL)
- Logs detalhados para debug
- Validação de dados antes de acessar
- Fallbacks para quando colunas não existem

