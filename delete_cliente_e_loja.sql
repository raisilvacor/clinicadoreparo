-- Script para deletar cliente da loja antiga e todos os dados relacionados
-- Execute este script diretamente no PostgreSQL do Render
-- 
-- IMPORTANTE: Substitua CLIENTE_ID pelo ID do cliente que você quer deletar
-- Exemplo: Se o ID for 2, substitua todas as ocorrências de CLIENTE_ID por 2

BEGIN;

-- ============================================
-- PARTE 1: REMOVER CONSTRAINTS DA LOJA ANTIGA
-- ============================================

-- Remover constraint de pedidos se existir
DO $$
BEGIN
    ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE;
    RAISE NOTICE 'Constraint pedidos_cliente_id_fkey removida';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Constraint não existe ou já foi removida: %', SQLERRM;
END $$;

-- ============================================
-- PARTE 2: DELETAR TODOS OS REGISTROS RELACIONADOS AO CLIENTE
-- ============================================

-- DELETAR CLIENTE E TODOS OS DADOS RELACIONADOS
-- Substitua CLIENTE_ID pelo ID real do cliente (exemplo: 2)

DO $$
DECLARE
    v_cliente_id INTEGER := 2; -- ALTERE AQUI PARA O ID DO CLIENTE
    v_deleted_count INTEGER;
BEGIN
    RAISE NOTICE 'Iniciando exclusão do cliente ID: %', v_cliente_id;
    
    -- 1. Deletar PDFs de orçamentos de ar-condicionado
    DELETE FROM pdf_documents
    WHERE id IN (
        SELECT pdf_id FROM orcamentos_ar_condicionado
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de orçamentos de ar-condicionado', v_deleted_count;
    
    -- 2. Deletar orçamentos de ar-condicionado
    DELETE FROM orcamentos_ar_condicionado WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % orçamento(s) de ar-condicionado', v_deleted_count;
    
    -- 3. Deletar PDFs de comprovantes
    DELETE FROM pdf_documents
    WHERE id IN (
        SELECT pdf_id FROM comprovantes
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de comprovantes', v_deleted_count;
    
    -- 4. Deletar comprovantes
    DELETE FROM comprovantes WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % comprovante(s)', v_deleted_count;
    
    -- 5. Deletar cupons
    DELETE FROM cupons WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % cupom(ns)', v_deleted_count;
    
    -- 6. Deletar PDFs de ordens de serviço
    DELETE FROM pdf_documents
    WHERE id IN (
        SELECT pdf_id FROM ordens_servico
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de ordens de serviço', v_deleted_count;
    
    -- 7. Deletar ordens de serviço
    DELETE FROM ordens_servico WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % ordem(ns) de serviço', v_deleted_count;
    
    -- 8. Deletar agendamentos relacionados por email (se o cliente tiver email)
    DECLARE
        v_email TEXT;
    BEGIN
        SELECT email INTO v_email FROM clientes WHERE id = v_cliente_id;
        IF v_email IS NOT NULL AND v_email != '' THEN
            DELETE FROM agendamentos WHERE email = v_email;
            GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
            RAISE NOTICE 'Deletados % agendamento(s) relacionados por email', v_deleted_count;
        END IF;
    END;
    
    -- 9. Finalmente, deletar o cliente
    DELETE FROM clientes WHERE id = v_cliente_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    IF v_deleted_count > 0 THEN
        RAISE NOTICE 'Cliente ID % deletado com sucesso!', v_cliente_id;
    ELSE
        RAISE NOTICE 'Cliente ID % não encontrado', v_cliente_id;
    END IF;
    
END $$;

-- ============================================
-- PARTE 3: LIMPAR DADOS DA LOJA ANTIGA (OPCIONAL)
-- ============================================

-- Remover todas as foreign keys relacionadas à loja
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    -- Remover foreign keys de pedidos
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'pedidos'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE ' || constraint_record.table_name || ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname || ' CASCADE';
        RAISE NOTICE 'FK removida: %', constraint_record.conname;
    END LOOP;
    
    -- Remover foreign keys de itens_pedido
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'itens_pedido'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE ' || constraint_record.table_name || ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname || ' CASCADE';
        RAISE NOTICE 'FK removida: %', constraint_record.conname;
    END LOOP;
    
    -- Remover foreign keys de produtos
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'produtos'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE ' || constraint_record.table_name || ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname || ' CASCADE';
        RAISE NOTICE 'FK removida: %', constraint_record.conname;
    END LOOP;
END $$;

-- Deletar todas as tabelas da loja se existirem
DROP TABLE IF EXISTS itens_pedido CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS produtos CASCADE;
DROP TABLE IF EXISTS categorias CASCADE;
DROP TABLE IF EXISTS carrinho CASCADE;

RAISE NOTICE 'Tabelas da loja removidas (se existirem)';

-- Remover constraint final de clientes relacionada à loja
ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE;

COMMIT;

RAISE NOTICE '✅ Processo concluído!';

