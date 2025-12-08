-- Script para remover todas as tabelas e vestígios da loja do banco de dados
-- Execute este script no banco de dados PostgreSQL do Render

BEGIN;

-- 1. Remover constraints de foreign key que referenciam pedidos/itens_pedido
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    -- Remover todas as foreign keys que referenciam pedidos
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE confrelid = 'pedidos'::regclass
        OR confrelid = 'itens_pedido'::regclass
        OR confrelid = 'produtos'::regclass
        OR confrelid = 'categorias'::regclass
    LOOP
        EXECUTE 'ALTER TABLE ' || constraint_record.table_name || ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        RAISE NOTICE 'Constraint removida: %', constraint_record.conname;
    END LOOP;
END $$;

-- 2. Remover todas as foreign keys da tabela pedidos
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN 
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'pedidos'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE pedidos DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        RAISE NOTICE 'FK removida de pedidos: %', constraint_record.conname;
    END LOOP;
END $$;

-- 3. Remover todas as foreign keys da tabela itens_pedido
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN 
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'itens_pedido'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE itens_pedido DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        RAISE NOTICE 'FK removida de itens_pedido: %', constraint_record.conname;
    END LOOP;
END $$;

-- 4. Remover todas as foreign keys da tabela produtos
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN 
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'produtos'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE produtos DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        RAISE NOTICE 'FK removida de produtos: %', constraint_record.conname;
    END LOOP;
END $$;

-- 5. Remover todas as foreign keys da tabela categorias
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN 
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'categorias'::regclass
        AND contype = 'f'
    LOOP
        EXECUTE 'ALTER TABLE categorias DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        RAISE NOTICE 'FK removida de categorias: %', constraint_record.conname;
    END LOOP;
END $$;

-- 6. Remover foreign key de clientes que referencia pedidos (se existir)
DO $$
BEGIN
    ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey;
    RAISE NOTICE 'FK pedidos_cliente_id_fkey removida de clientes';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'FK pedidos_cliente_id_fkey não existe ou já foi removida';
END $$;

-- 7. Dropar as tabelas da loja (se existirem)
DROP TABLE IF EXISTS itens_pedido CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS produtos CASCADE;
DROP TABLE IF EXISTS categorias CASCADE;
DROP TABLE IF EXISTS carrinho CASCADE;

-- 8. Remover a constraint específica de clientes se ainda existir
DO $$
BEGIN
    ALTER TABLE clientes DROP CONSTRAINT IF EXISTS pedidos_cliente_id_fkey CASCADE;
    RAISE NOTICE 'Constraint pedidos_cliente_id_fkey removida de clientes';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Constraint não existe ou já foi removida';
END $$;

RAISE NOTICE 'Tabelas da loja removidas com sucesso!';

COMMIT;

