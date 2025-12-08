-- Script RÁPIDO para deletar um cliente específico e todos os dados relacionados
-- Execute este script diretamente no PostgreSQL do Render
-- 
-- INSTRUÇÕES:
-- 1. Substitua o número 2 na linha abaixo pelo ID do cliente que você quer deletar
-- 2. Copie todo o conteúdo deste arquivo
-- 3. Cole no SQL Editor do Render PostgreSQL (Connect > Query)
-- 4. Execute

BEGIN;

DO $$
DECLARE
    -- ALTERE ESTE VALOR PARA O ID DO CLIENTE QUE VOCÊ QUER DELETAR
    v_cliente_id INTEGER := 2;  -- <-- ALTERE AQUI! (exemplo: 2, 5, 10, etc.)
    v_email TEXT;
    v_count INTEGER;
BEGIN
    RAISE NOTICE 'Deletando cliente ID: %', v_cliente_id;
    
    -- 1. Deletar itens_pedido relacionados aos pedidos do cliente (se tabela existir)
    BEGIN
        DELETE FROM itens_pedido 
        WHERE pedido_id IN (
            SELECT id FROM pedidos WHERE cliente_id = v_cliente_id
        );
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE 'Deletados % item(ns) de pedido(s)', v_count;
    EXCEPTION WHEN undefined_table THEN
        RAISE NOTICE 'Tabela itens_pedido não existe (ignorando)';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Erro ao deletar itens_pedido: %', SQLERRM;
    END;
    
    -- 2. Deletar pedidos do cliente (se tabela existir)
    BEGIN
        DELETE FROM pedidos WHERE cliente_id = v_cliente_id;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE 'Deletados % pedido(s) da loja antiga', v_count;
    EXCEPTION WHEN undefined_table THEN
        RAISE NOTICE 'Tabela pedidos não existe (ignorando)';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Erro ao deletar pedidos: %', SQLERRM;
    END;
    
    -- 3. Deletar PDFs de orçamentos de ar-condicionado
    DELETE FROM pdf_documents 
    WHERE id IN (
        SELECT pdf_id FROM orcamentos_ar_condicionado 
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de orçamentos', v_count;
    
    -- 4. Deletar orçamentos de ar-condicionado
    DELETE FROM orcamentos_ar_condicionado WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % orçamento(s) de ar-condicionado', v_count;
    
    -- 5. Deletar PDFs de comprovantes
    DELETE FROM pdf_documents 
    WHERE id IN (
        SELECT pdf_id FROM comprovantes 
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de comprovantes', v_count;
    
    -- 6. Deletar comprovantes
    DELETE FROM comprovantes WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % comprovante(s)', v_count;
    
    -- 7. Deletar cupons
    DELETE FROM cupons WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % cupom(ns)', v_count;
    
    -- 8. Deletar PDFs de ordens de serviço
    DELETE FROM pdf_documents 
    WHERE id IN (
        SELECT pdf_id FROM ordens_servico 
        WHERE cliente_id = v_cliente_id AND pdf_id IS NOT NULL
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % PDF(s) de ordens', v_count;
    
    -- 9. Deletar ordens de serviço
    DELETE FROM ordens_servico WHERE cliente_id = v_cliente_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Deletados % ordem(ns) de serviço', v_count;
    
    -- 10. Obter email do cliente e deletar agendamentos relacionados
    SELECT email INTO v_email FROM clientes WHERE id = v_cliente_id;
    IF v_email IS NOT NULL AND v_email != '' THEN
        DELETE FROM agendamentos WHERE email = v_email;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE 'Deletados % agendamento(s) relacionados', v_count;
    END IF;
    
    -- 11. Remover constraint de pedidos se existir (para clientes da loja antiga)
    BEGIN
        ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE;
        RAISE NOTICE 'Constraint de pedidos removida (se existia)';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Constraint não existe ou já foi removida';
    END;
    
    -- 12. Finalmente, deletar o cliente
    DELETE FROM clientes WHERE id = v_cliente_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    IF v_count > 0 THEN
        RAISE NOTICE '✅ Cliente ID % deletado com sucesso!', v_cliente_id;
    ELSE
        RAISE NOTICE '⚠️ Cliente ID % não encontrado', v_cliente_id;
    END IF;
    
END $$;

COMMIT;
