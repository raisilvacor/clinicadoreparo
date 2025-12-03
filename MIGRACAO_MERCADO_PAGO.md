# Migração - Integração Mercado Pago

## O que foi implementado

A integração com Mercado Pago foi adicionada ao checkout da loja. Agora todos os pagamentos são processados através do Mercado Pago.

## Configurações

As credenciais do Mercado Pago estão configuradas no código:
- **Access Token**: APP_USR-76423944696406-120317-e90c1e5d3cd966a580b8ac832fcf4d32-3038587256
- **Public Key**: APP_USR-f1ed3d57-6c67-417b-89a6-2750b70ca3f7

## Como funciona

1. Cliente preenche dados no checkout
2. Sistema cria pedido no banco com status "pendente"
3. Sistema cria preferência de pagamento no Mercado Pago
4. Cliente é redirecionado para o Mercado Pago
5. Após pagamento, cliente retorna para o site
6. Webhook atualiza status do pedido automaticamente

## Migração do Banco de Dados

Execute o script `migrate_mercado_pago.sql` no banco de dados PostgreSQL do Render:

1. Acesse o dashboard do Render
2. Vá em seu banco de dados PostgreSQL
3. Execute o conteúdo do arquivo `migrate_mercado_pago.sql`

Isso adicionará as colunas:
- `mercado_pago_payment_id` - ID do pagamento no Mercado Pago
- `mercado_pago_preference_id` - ID da preferência de pagamento

## Rotas criadas

- `/loja/pagamento/sucesso` - Callback de pagamento aprovado
- `/loja/pagamento/falha` - Callback de pagamento rejeitado
- `/loja/pagamento/pendente` - Callback de pagamento pendente
- `/loja/pagamento/webhook` - Webhook para notificações do Mercado Pago

## Instalação de dependências

O pacote `mercadopago==2.2.0` foi adicionado ao `requirements.txt`. O Render instalará automaticamente na próxima atualização.

