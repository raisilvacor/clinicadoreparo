-- Script para deletar TODOS os dados da loja antiga do banco de dados
-- Execute este script diretamente no PostgreSQL do Render
-- 
-- ATENÇÃO: Este script irá deletar:
-- - Todas as tabelas da loja (pedidos, itens_pedido, produtos, categorias, carrinho)
-- - Todos os clientes que foram cadastrados na loja
-- - Todas as constraints relacionadas à loja
--
-- Use com cuidado!

BEGIN;

RAISE NOTICE 'Iniciando limpeza completa da loja antiga...';

-- ============================================
-- PARTE 1: REMOVER CONSTRAINTS
-- ============================================

-- Remover todas as foreign keys relacionadas às tabelas da loja
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    -- Remover foreign keys que referenciam pedidos
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid IN (
            SELECT oid FROM pg_class WHERE relname IN ('pedidos', 'itens_pedido', 'produtos', 'categorias', 'carrinho')
        )
        AND contype = 'f'
    LOOP
        BEGIN
            EXECUTE 'ALTER TABLE ' || constraint_record.table_name || ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname || ' CASCADE';
            RAISE NOTICE 'FK removida: %', constraint_record.conname;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Erro ao remover FK %: %', constraint_record.conname, SQLERRM;
        END;
    END LOOP;
END $$;

-- Remover constraint específica de clientes relacionada a pedidos
DO $$
BEGIN
    ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE;
    RAISE NOTICE 'Constraint pedidos_cliente_id_fkey removida de clientes';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Constraint não existe ou já foi removida';
END $$;

-- ============================================
-- PARTE 2: DELETAR DADOS DAS TABELAS DA LOJA
-- ============================================

-- Deletar todos os dados das tabelas da loja (se existirem)
DELETE FROM itens_pedido WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'itens_pedido');
DELETE FROM pedidos WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pedidos');
DELETE FROM carrinho WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'carrinho');
DELETE FROM produtos WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'produtos');
DELETE FROM categorias WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'categorias');

-- ============================================
-- PARTE 3: DROPAR AS TABELAS DA LOJA
-- ============================================

DROP TABLE IF EXISTS itens_pedido CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS produtos CASCADE;
DROP TABLE IF EXISTS categorias CASCADE;
DROP TABLE IF EXISTS carrinho CASCADE;

RAISE NOTICE '✅ Tabelas da loja removidas!';

-- ============================================
-- PARTE 4: DELETAR CLIENTES DA LOJA
-- ============================================
-- 
-- ATENÇÃO: Esta parte deleta clientes que podem ter sido criados na loja
-- Se você quiser deletar apenas clientes específicos, comente esta seção
-- e use o script delete_cliente_e_loja.sql para clientes específicos

-- Opção 1: Deletar clientes que não têm relacionamentos (seguro)
-- Descomente as linhas abaixo se quiser usar esta opção:
/*
DO $$
DECLARE
    cliente_record RECORD;
    v_count INTEGER := 0;
BEGIN
    FOR cliente_record IN 
        SELECT id FROM clientes 
        WHERE id NOT IN (SELECT DISTINCT cliente_id FROM ordens_servico WHERE cliente_id IS NOT NULL)
        AND id NOT IN (SELECT DISTINCT cliente_id FROM comprovantes WHERE cliente_id IS NOT NULL)
        AND id NOT IN (SELECT DISTINCT cliente_id FROM cupons WHERE cliente_id IS NOT NULL)
        AND id NOT IN (SELECT DISTINCT cliente_id FROM orcamentos_ar_condicionado WHERE cliente_id IS NOT NULL)
    LOOP
        DELETE FROM agendamentos WHERE email = (SELECT email FROM clientes WHERE id = cliente_record.id);
        DELETE FROM clientes WHERE id = cliente_record.id;
        v_count := v_count + 1;
    END LOOP;
    RAISE NOTICE 'Deletados % cliente(s) sem relacionamentos', v_count;
END $$;
*/

COMMIT;

RAISE NOTICE '✅ Limpeza completa da loja concluída!';

