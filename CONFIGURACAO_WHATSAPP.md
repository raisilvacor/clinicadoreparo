# Configuração de Notificações WhatsApp

## Opção 1: Evolution API (Recomendado - Gratuito)

1. Instale e configure a Evolution API: https://doc.evolution-api.com/
2. Configure as variáveis de ambiente:
   ```bash
   export EVOLUTION_API_URL="http://localhost:8080"
   export EVOLUTION_API_KEY="sua_chave_aqui"
   export EVOLUTION_INSTANCE="nome_da_instancia"
   ```

## Opção 2: Twilio

1. Crie uma conta no Twilio: https://www.twilio.com/
2. Configure as variáveis de ambiente:
   ```bash
   export TWILIO_ACCOUNT_SID="seu_account_sid"
   export TWILIO_AUTH_TOKEN="seu_auth_token"
   export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"
   ```

## Opção 3: Sem API (Manual)

Se nenhuma API estiver configurada, o sistema gerará uma URL do WhatsApp que pode ser aberta manualmente. A URL será exibida nos logs do servidor.

Para ver os logs, execute o servidor e verifique o console quando um agendamento for criado.

## Teste

Após configurar, teste criando um novo agendamento. A notificação será enviada automaticamente se a API estiver configurada corretamente.

