#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para fazer deploy automático"""
import subprocess
import sys
import os

def run_command(cmd, description):
    """Executa um comando e mostra o resultado"""
    print(f"\n{'='*50}")
    print(f"{description}")
    print(f"{'='*50}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"ERRO: {e}")
        return False

def main():
    print("Iniciando deploy completo...")
    
    # Verificar se estamos no diretório correto
    if not os.path.exists('app.py'):
        print("ERRO: app.py não encontrado. Execute este script na raiz do projeto.")
        return False
    
    # Adicionar todos os arquivos
    if not run_command("git add -A", "Adicionando arquivos ao git..."):
        print("ERRO ao adicionar arquivos!")
        return False
    
    # Verificar status
    run_command("git status --short", "Status do repositório:")
    
    # Fazer commit
    if not run_command('git commit -m "Deploy: Debug DATABASE_URL e melhorias"', "Fazendo commit..."):
        print("AVISO: Nenhuma mudança para commitar ou erro no commit.")
    
    # Fazer push
    if not run_command("git push origin main", "Fazendo push para origin/main..."):
        print("ERRO ao fazer push!")
        return False
    
    print("\n" + "="*50)
    print("Deploy concluído com sucesso!")
    print("="*50)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

