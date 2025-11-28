#!/usr/bin/env python3
"""
Script para criar todas as tabelas no banco de dados PostgreSQL
usando a External Database URL do Render.

Uso:
    python create_tables.py

Ou com a URL como variável de ambiente:
    set DATABASE_URL=postgresql://... python create_tables.py
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Importar os modelos
from models import db, Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom, Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Contato, Imagem, PDFDocument, Fornecedor

def corrigir_database_url(url):
    """Corrige a URL do banco de dados para o formato correto"""
    if not url:
        return None
    
    # Render usa postgres:// mas SQLAlchemy precisa postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    
    # Adicionar parâmetros SSL se necessário (para Render)
    if ('render.com' in url or 'dpg-' in url) and '?sslmode=' not in url:
        if '?' in url:
            url += '&sslmode=require'
        else:
            url += '?sslmode=require'
    
    return url

def criar_tabelas():
    """Cria todas as tabelas no banco de dados"""
    
    # Obter a URL do banco de dados
    database_url = os.environ.get('DATABASE_URL', '')
    
    if not database_url:
        print("❌ ERRO: DATABASE_URL não encontrada nas variáveis de ambiente.")
        print("\nPor favor, forneça a URL do banco de dados:")
        print("1. Como variável de ambiente: set DATABASE_URL=postgresql://...")
        print("2. Ou edite este script e adicione a URL diretamente")
        print("\nVocê pode encontrar a External Database URL no painel do Render:")
        print("   Database > Connections > External Database URL")
        return False
    
    # Corrigir a URL
    database_url = corrigir_database_url(database_url)
    
    if not database_url:
        print("❌ ERRO: URL do banco de dados inválida.")
        return False
    
    print(f"🔗 Conectando ao banco de dados...")
    print(f"   URL: {database_url[:50]}...")
    
    try:
        # Criar engine
        engine = create_engine(database_url, echo=False)
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text('SELECT version()'))
            version = result.scalar()
            print(f"✅ Conectado ao PostgreSQL: {version[:50]}...")
        
        # Configurar Flask app context (necessário para SQLAlchemy)
        from flask import Flask
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db.init_app(app)
        
        # Criar todas as tabelas
        print("\n📋 Criando tabelas...")
        with app.app_context():
            # Verificar tabelas existentes
            inspector = inspect(engine)
            tabelas_existentes = inspector.get_table_names()
            
            print(f"\n📊 Tabelas existentes: {len(tabelas_existentes)}")
            if tabelas_existentes:
                for tabela in sorted(tabelas_existentes):
                    print(f"   - {tabela}")
            
            # Criar todas as tabelas
            print("\n🔨 Criando/atualizando tabelas...")
            db.create_all()
            
            # Verificar tabelas criadas
            inspector = inspect(engine)
            tabelas_apos = inspector.get_table_names()
            
            print(f"\n✅ Tabelas após criação: {len(tabelas_apos)}")
            tabelas_esperadas = [
                'clientes', 'imagens', 'pdf_documents', 'servicos', 'tecnicos',
                'ordens_servico', 'comprovantes', 'cupons', 'slides', 'footer',
                'marcas', 'milestones', 'admin_users', 'agendamentos', 'contatos',
                'fornecedores', 'artigos'  # artigos pode não ser usado, mas está no modelo
            ]
            
            for tabela in sorted(tabelas_apos):
                status = "✅" if tabela in tabelas_esperadas else "⚠️"
                print(f"   {status} {tabela}")
            
            # Verificar tabelas esperadas que não foram criadas
            tabelas_faltando = [t for t in tabelas_esperadas if t not in tabelas_apos]
            if tabelas_faltando:
                print(f"\n⚠️  Tabelas esperadas que não foram criadas:")
                for tabela in tabelas_faltando:
                    print(f"   - {tabela}")
            
            # Verificar especificamente a tabela de fornecedores
            if 'fornecedores' in tabelas_apos:
                print("\n✅ Tabela 'fornecedores' criada com sucesso!")
                
                # Verificar estrutura
                columns = inspector.get_columns('fornecedores')
                print(f"   Colunas: {len(columns)}")
                for col in columns:
                    print(f"      - {col['name']} ({col['type']})")
            else:
                print("\n⚠️  Tabela 'fornecedores' não foi criada. Tentando criar manualmente...")
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS fornecedores (
                                id SERIAL PRIMARY KEY,
                                nome VARCHAR(200) NOT NULL,
                                contato VARCHAR(200),
                                telefone VARCHAR(20),
                                email VARCHAR(200),
                                endereco TEXT,
                                cnpj VARCHAR(18),
                                tipo_servico VARCHAR(200),
                                observacoes TEXT,
                                ativo BOOLEAN DEFAULT TRUE,
                                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """))
                    print("✅ Tabela 'fornecedores' criada manualmente!")
                except Exception as e:
                    print(f"❌ Erro ao criar tabela 'fornecedores' manualmente: {e}")
        
        print("\n🎉 Processo concluído!")
        return True
        
    except SQLAlchemyError as e:
        print(f"\n❌ ERRO ao conectar/criar tabelas: {e}")
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
    print("  CRIADOR DE TABELAS - Banco de Dados PostgreSQL")
    print("=" * 60)
    print()
    
    sucesso = criar_tabelas()
    
    if sucesso:
        print("\n✅ Todas as tabelas foram criadas com sucesso!")
        print("   Você pode agora usar o sistema normalmente.")
        sys.exit(0)
    else:
        print("\n❌ Falha ao criar tabelas. Verifique os erros acima.")
        sys.exit(1)

