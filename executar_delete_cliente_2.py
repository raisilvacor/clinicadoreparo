#!/usr/bin/env python3
"""
Script para deletar cliente ID 2 e todos os dados relacionados
Execute este script diretamente ou através da rota admin
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Converter postgres:// para postgresql:// se necessário
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

def deletar_cliente_2():
    """Deleta cliente ID 2 e todos os dados relacionados"""
    if not database_url:
        print("❌ DATABASE_URL não configurada!")
        return False
    
    try:
        engine = create_engine(database_url)
        
        with engine.begin() as conn:
            cliente_id = 2
            
            print(f"🗑️  Iniciando exclusão do cliente ID: {cliente_id}")
            
            # 1. Deletar PDFs de orçamentos de ar-condicionado
            result = conn.execute(text("""
                DELETE FROM pdf_documents 
                WHERE id IN (
                    SELECT pdf_id FROM orcamentos_ar_condicionado 
                    WHERE cliente_id = :cliente_id AND pdf_id IS NOT NULL
                )
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} PDF(s) de orçamentos")
            
            # 2. Deletar orçamentos de ar-condicionado
            result = conn.execute(text("""
                DELETE FROM orcamentos_ar_condicionado WHERE cliente_id = :cliente_id
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} orçamento(s) de ar-condicionado")
            
            # 3. Deletar PDFs de comprovantes
            result = conn.execute(text("""
                DELETE FROM pdf_documents 
                WHERE id IN (
                    SELECT pdf_id FROM comprovantes 
                    WHERE cliente_id = :cliente_id AND pdf_id IS NOT NULL
                )
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} PDF(s) de comprovantes")
            
            # 4. Deletar comprovantes
            result = conn.execute(text("""
                DELETE FROM comprovantes WHERE cliente_id = :cliente_id
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} comprovante(s)")
            
            # 5. Deletar cupons
            result = conn.execute(text("""
                DELETE FROM cupons WHERE cliente_id = :cliente_id
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} cupom(ns)")
            
            # 6. Deletar PDFs de ordens de serviço
            result = conn.execute(text("""
                DELETE FROM pdf_documents 
                WHERE id IN (
                    SELECT pdf_id FROM ordens_servico 
                    WHERE cliente_id = :cliente_id AND pdf_id IS NOT NULL
                )
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} PDF(s) de ordens")
            
            # 7. Deletar ordens de serviço
            result = conn.execute(text("""
                DELETE FROM ordens_servico WHERE cliente_id = :cliente_id
            """), {'cliente_id': cliente_id})
            print(f"✅ Deletados {result.rowcount} ordem(ns) de serviço")
            
            # 8. Obter email do cliente e deletar agendamentos relacionados
            email_result = conn.execute(text("""
                SELECT email FROM clientes WHERE id = :cliente_id
            """), {'cliente_id': cliente_id})
            email_row = email_result.fetchone()
            
            if email_row and email_row[0]:
                result = conn.execute(text("""
                    DELETE FROM agendamentos WHERE email = :email
                """), {'email': email_row[0]})
                print(f"✅ Deletados {result.rowcount} agendamento(s) relacionados")
            
            # 9. Remover constraint de pedidos se existir
            try:
                conn.execute(text("""
                    ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE
                """))
                print("✅ Constraint de pedidos removida (se existia)")
            except Exception as e:
                print(f"ℹ️  Constraint não existe ou já foi removida: {e}")
            
            # 10. Finalmente, deletar o cliente
            result = conn.execute(text("""
                DELETE FROM clientes WHERE id = :cliente_id
            """), {'cliente_id': cliente_id})
            
            if result.rowcount > 0:
                print(f"✅ Cliente ID {cliente_id} deletado com sucesso!")
                return True
            else:
                print(f"⚠️  Cliente ID {cliente_id} não encontrado")
                return False
                
    except SQLAlchemyError as e:
        print(f"❌ Erro ao deletar cliente: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Script de Exclusão de Cliente ID 2")
    print("=" * 50)
    sucesso = deletar_cliente_2()
    if sucesso:
        print("\n✅ Processo concluído com sucesso!")
    else:
        print("\n❌ Processo falhou. Verifique os erros acima.")
    print("=" * 50)

