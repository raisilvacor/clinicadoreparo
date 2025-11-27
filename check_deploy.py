#!/usr/bin/env python3
"""
Script de verificação para deploy
Verifica se todos os arquivos e diretórios necessários existem
"""

import os
import sys

def check_file(filepath, required=True):
    """Verifica se um arquivo existe"""
    exists = os.path.exists(filepath)
    status = "[OK]" if exists else "[FALTANDO]"
    print(f"{status} {filepath}")
    if required and not exists:
        return False
    return True

def check_dir(dirpath, required=True):
    """Verifica se um diretório existe"""
    exists = os.path.isdir(dirpath)
    status = "[OK]" if exists else "[FALTANDO]"
    print(f"{status} {dirpath}/")
    if required and not exists:
        return False
    return True

def main():
    print("=" * 50)
    print("Verificação de Deploy - Clínica do Reparo")
    print("=" * 50)
    print()
    
    errors = []
    
    # Arquivos obrigatórios
    print("Arquivos obrigatórios:")
    print("-" * 50)
    if not check_file("app.py", required=True):
        errors.append("app.py não encontrado")
    if not check_file("requirements.txt", required=True):
        errors.append("requirements.txt não encontrado")
    if not check_file("Procfile", required=True):
        errors.append("Procfile não encontrado")
    if not check_file("runtime.txt", required=True):
        errors.append("runtime.txt não encontrado")
    print()
    
    # Diretórios obrigatórios
    print("Diretórios obrigatórios:")
    print("-" * 50)
    if not check_dir("templates", required=True):
        errors.append("templates/ não encontrado")
    if not check_dir("static", required=True):
        errors.append("static/ não encontrado")
    if not check_dir("data", required=True):
        errors.append("data/ não encontrado")
    print()
    
    # Subdiretórios estáticos
    print("Subdiretórios estáticos:")
    print("-" * 50)
    check_dir("static/css", required=False)
    check_dir("static/js", required=False)
    check_dir("static/img", required=False)
    check_dir("static/img/blog", required=False)
    check_dir("static/img/marcas", required=False)
    check_dir("static/img/milestones", required=False)
    check_dir("static/img/servicos", required=False)
    check_dir("static/img/slides", required=False)
    check_dir("static/pdfs", required=False)
    print()
    
    # Arquivos opcionais mas recomendados
    print("Arquivos recomendados:")
    print("-" * 50)
    check_file(".env.example", required=False)
    check_file("DEPLOY.md", required=False)
    check_file(".gitignore", required=False)
    print()
    
    # Verificar variáveis de ambiente
    print("Variáveis de ambiente:")
    print("-" * 50)
    secret_key = os.environ.get('SECRET_KEY', '')
    if secret_key and secret_key != 'sua_chave_secreta_aqui_altere_em_producao':
        print("[OK] SECRET_KEY configurada")
    else:
        print("[AVISO] SECRET_KEY não configurada ou usando valor padrão")
        errors.append("Configure SECRET_KEY antes do deploy")
    
    flask_env = os.environ.get('FLASK_ENV', '')
    if flask_env:
        print(f"[OK] FLASK_ENV={flask_env}")
    else:
        print("[AVISO] FLASK_ENV não configurado (usando padrão)")
    print()
    
    # Resultado final
    print("=" * 50)
    if errors:
        print("ERROS ENCONTRADOS:")
        for error in errors:
            print(f"  - {error}")
        print()
        print("Corrija os erros antes de fazer o deploy!")
        sys.exit(1)
    else:
        print("[SUCESSO] Verificação concluída com sucesso!")
        print("O projeto está pronto para deploy.")
        print()
        print("Próximos passos:")
        print("1. Configure as variáveis de ambiente na plataforma")
        print("2. Faça o push do código para o repositório")
        print("3. Siga as instruções em DEPLOY.md")
        sys.exit(0)

if __name__ == '__main__':
    main()

