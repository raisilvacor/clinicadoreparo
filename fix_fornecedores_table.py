#!/usr/bin/env python3
"""
Script para verificar e corrigir a tabela fornecedores
adicionando a coluna tipo_servico se ela estiver faltando.
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

def corrigir_database_url(url):
    """Corrige a URL do banco de dados para o formato correto"""
    if not url:
        return None
    
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    
    if ('render.com' in url or 'dpg-' in url) and '?sslmode=' not in url:
        if '?' in url:
            url += '&sslmode=require'
        else:
            url += '?sslmode=require'
    
    return url

def verificar_e_corrigir_tabela():
    """Verifica e corrige a tabela fornecedores"""
    
    database_url = os.environ.get('DATABASE_URL', '')
    
    if not database_url:
        print("❌ ERRO: DATABASE_URL não encontrada.")
        return False
    
    database_url = corrigir_database_url(database_url)
    
    print(f"🔗 Conectando ao banco de dados...")
    
    try:
        engine = create_engine(database_url, echo=False)
        
        with engine.connect() as conn:
            result = conn.execute(text('SELECT version()'))
            version = result.scalar()
            print(f"✅ Conectado ao PostgreSQL")
        
        inspector = inspect(engine)
        
        # Verificar se a tabela existe
        if not inspector.has_table('fornecedores'):
            print("❌ Tabela 'fornecedores' não existe!")
            return False
        
        print("✅ Tabela 'fornecedores' existe")
        
        # Verificar colunas existentes
        columns = inspector.get_columns('fornecedores')
        column_names = [col['name'] for col in columns]
        
        print(f"\n📋 Colunas existentes ({len(column_names)}):")
        for col in columns:
            print(f"   - {col['name']} ({col['type']})")
        
        # Verificar se tipo_servico existe
        if 'tipo_servico' not in column_names:
            print("\n⚠️  Coluna 'tipo_servico' não encontrada!")
            print("🔨 Adicionando coluna 'tipo_servico'...")
            
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        ALTER TABLE fornecedores 
                        ADD COLUMN IF NOT EXISTS tipo_servico VARCHAR(200)
                    """))
                print("✅ Coluna 'tipo_servico' adicionada com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao adicionar coluna: {e}")
                return False
        else:
            print("\n✅ Coluna 'tipo_servico' já existe!")
        
        # Verificar novamente após adicionar
        inspector = inspect(engine)
        columns_after = inspector.get_columns('fornecedores')
        column_names_after = [col['name'] for col in columns_after]
        
        print(f"\n📋 Colunas após correção ({len(column_names_after)}):")
        for col in columns_after:
            print(f"   - {col['name']} ({col['type']})")
        
        # Verificar se todas as colunas esperadas estão presentes
        colunas_esperadas = [
            'id', 'nome', 'contato', 'telefone', 'email', 'endereco',
            'cnpj', 'tipo_servico', 'observacoes', 'ativo', 'data_cadastro'
        ]
        
        colunas_faltando = [col for col in colunas_esperadas if col not in column_names_after]
        
        if colunas_faltando:
            print(f"\n⚠️  Colunas esperadas que não foram encontradas:")
            for col in colunas_faltando:
                print(f"   - {col}")
        else:
            print("\n✅ Todas as colunas esperadas estão presentes!")
        
        print("\n🎉 Verificação concluída!")
        return True
        
    except SQLAlchemyError as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ ERRO inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("  VERIFICADOR E CORRETOR - Tabela Fornecedores")
    print("=" * 60)
    print()
    
    sucesso = verificar_e_corrigir_tabela()
    
    if sucesso:
        print("\n✅ Tabela 'fornecedores' está correta!")
        sys.exit(0)
    else:
        print("\n❌ Falha ao verificar/corrigir tabela.")
        sys.exit(1)

