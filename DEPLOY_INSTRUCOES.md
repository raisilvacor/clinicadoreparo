# Instruções para Deploy Manual

Como o sistema automático de deploy não está funcionando, siga estes passos:

## Método 1: Usando o Script Batch (Recomendado)

1. Abra o **Prompt de Comando** ou **PowerShell** na pasta do projeto
2. Execute:
   ```
   deploy_final.bat
   ```

## Método 2: Comandos Manuais

Abra o terminal na pasta do projeto e execute:

```bash
git add -A
git commit -m "Deploy: Melhorias na conexão do banco de dados"
git push origin main
```

## Método 3: Usando o Script Python

Execute no terminal:
```bash
python deploy_verificado.py
```

## Verificar se Funcionou

1. Acesse: https://github.com/raisilvacor/clinicadoreparo
2. Verifique se há um commit recente
3. O Render deve iniciar o deploy automaticamente

## Se o Push Falhar

Verifique:
- Se você está conectado à internet
- Se as credenciais do Git estão configuradas
- Se há algum problema com o repositório remoto

Para verificar o repositório:
```bash
git remote -v
```

Deve mostrar:
```
origin  https://github.com/raisilvacor/clinicadoreparo.git (fetch)
origin  https://github.com/raisilvacor/clinicadoreparo.git (push)
```

