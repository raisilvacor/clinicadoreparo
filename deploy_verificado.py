#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para fazer deploy com verificação completa"""
import subprocess
import sys
import os

def run_command(cmd, description):
    """Executa um comando e mostra o resultado"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.stdout:
            print("SAÍDA:")
            print(result.stdout)
        if result.stderr:
            print("ERROS:")
            print(result.stderr)
        print(f"CÓDIGO DE SAÍDA: {result.returncode}")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"ERRO AO EXECUTAR COMANDO: {e}")
        return False, "", str(e)

def main():
    print("="*60)
    print("DEPLOY VERIFICADO - Sistema de Deploy Confiável")
    print("="*60)
    
    # Verificar se estamos no diretório correto
    if not os.path.exists('app.py'):
        print("ERRO: app.py não encontrado. Execute este script na raiz do projeto.")
        return False
    
    # 1. Verificar status atual
    success, stdout, stderr = run_command("git status --porcelain", "1. Verificando mudanças pendentes...")
    if stdout.strip():
        print(f"\nArquivos modificados encontrados:\n{stdout}")
    else:
        print("\nNenhuma mudança pendente encontrada.")
    
    # 2. Verificar último commit
    success, stdout, stderr = run_command("git log --oneline -1", "2. Último commit local:")
    if stdout:
        print(f"Último commit: {stdout.strip()}")
    
    # 3. Verificar commits não enviados
    success, stdout, stderr = run_command("git log origin/main..HEAD --oneline", "3. Commits não enviados:")
    if stdout.strip():
        print(f"Commits pendentes:\n{stdout}")
    else:
        print("Nenhum commit pendente.")
    
    # 4. Adicionar todos os arquivos
    print("\n" + "="*60)
    print("4. Adicionando arquivos ao git...")
    print("="*60)
    success, stdout, stderr = run_command("git add -A", "Adicionando arquivos...")
    if not success:
        print("ERRO ao adicionar arquivos!")
        return False
    
    # 5. Verificar o que foi adicionado
    success, stdout, stderr = run_command("git status --short", "5. Status após adicionar:")
    if stdout:
        print(f"Arquivos no stage:\n{stdout}")
    
    # 6. Fazer commit
    print("\n" + "="*60)
    print("6. Fazendo commit...")
    print("="*60)
    success, stdout, stderr = run_command('git commit -m "Deploy: Melhorias na conexão do banco de dados"', "Commit...")
    if not success and "nothing to commit" not in stderr.lower():
        print("AVISO: Nenhuma mudança para commitar ou erro no commit.")
        print(f"Stderr: {stderr}")
    else:
        if "nothing to commit" in stderr.lower():
            print("Nenhuma mudança para commitar.")
        else:
            print("Commit realizado com sucesso!")
    
    # 7. Verificar commits pendentes novamente
    success, stdout, stderr = run_command("git log origin/main..HEAD --oneline", "7. Commits pendentes após commit:")
    if stdout.strip():
        print(f"Commits para enviar:\n{stdout}")
    else:
        print("Nenhum commit para enviar.")
        return True
    
    # 8. Fazer push
    print("\n" + "="*60)
    print("8. Fazendo push para origin/main...")
    print("="*60)
    success, stdout, stderr = run_command("git push origin main", "Push...")
    if not success:
        print("ERRO ao fazer push!")
        print(f"Stderr: {stderr}")
        return False
    
    print("\n" + "="*60)
    print("DEPLOY CONCLUÍDO COM SUCESSO!")
    print("="*60)
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ Deploy realizado com sucesso!")
        else:
            print("\n❌ Deploy falhou. Verifique os erros acima.")
        input("\nPressione ENTER para sair...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nDeploy cancelado pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        input("\nPressione ENTER para sair...")
        sys.exit(1)

