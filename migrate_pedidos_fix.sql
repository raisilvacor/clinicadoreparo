-- Migração para corrigir problemas no sistema de pedidos
-- Execute este script no banco de dados PostgreSQL do Render

BEGIN;

-- 1. Corrigir produto_id em itens_pedido para permitir NULL
DO $$
BEGIN
    -- Verificar se a coluna existe e se é NOT NULL
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='itens_pedido' AND column_name='produto_id' AND is_nullable='NO'
    ) THEN
        -- Remover constraint NOT NULL se existir
        ALTER TABLE itens_pedido ALTER COLUMN produto_id DROP NOT NULL;
        RAISE NOTICE 'Coluna produto_id agora permite NULL';
    END IF;
END $$;

-- 2. Atualizar foreign key de produto_id para ON DELETE SET NULL
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    -- Encontrar e remover constraint antiga
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'itens_pedido'::regclass
    AND confrelid = 'produtos'::regclass
    AND contype = 'f'
    AND conname LIKE '%produto_id%';

    IF constraint_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE itens_pedido DROP CONSTRAINT ' || constraint_name;
        RAISE NOTICE 'Constraint antiga removida: %', constraint_name;
    END IF;
    
    -- Adicionar nova constraint com ON DELETE SET NULL
    ALTER TABLE itens_pedido
    ADD CONSTRAINT fk_itens_pedido_produto_id
    FOREIGN KEY (produto_id)
    REFERENCES produtos (id)
    ON DELETE SET NULL;
    
    RAISE NOTICE 'Nova constraint adicionada com ON DELETE SET NULL';
EXCEPTION
    WHEN duplicate_object THEN
        RAISE NOTICE 'Constraint já existe, pulando...';
END $$;

-- 3. Adicionar colunas do Mercado Pago se não existirem
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='pedidos' AND column_name='mercado_pago_payment_id'
    ) THEN
        ALTER TABLE pedidos ADD COLUMN mercado_pago_payment_id VARCHAR(100);
        RAISE NOTICE 'Coluna mercado_pago_payment_id adicionada';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='pedidos' AND column_name='mercado_pago_preference_id'
    ) THEN
        ALTER TABLE pedidos ADD COLUMN mercado_pago_preference_id VARCHAR(100);
        RAISE NOTICE 'Coluna mercado_pago_preference_id adicionada';
    END IF;
END $$;

-- 4. Adicionar colunas produto_nome e produto_sku em itens_pedido (se não existirem)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='itens_pedido' AND column_name='produto_nome'
    ) THEN
        ALTER TABLE itens_pedido ADD COLUMN produto_nome VARCHAR(200);
        RAISE NOTICE 'Coluna produto_nome adicionada';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='itens_pedido' AND column_name='produto_sku'
    ) THEN
        ALTER TABLE itens_pedido ADD COLUMN produto_sku VARCHAR(100);
        RAISE NOTICE 'Coluna produto_sku adicionada';
    END IF;
END $$;

-- 5. Preencher produto_nome e produto_sku com dados existentes dos produtos
UPDATE itens_pedido ip
SET
    produto_nome = p.nome,
    produto_sku = p.sku
FROM produtos p
WHERE ip.produto_id = p.id
AND (ip.produto_nome IS NULL OR ip.produto_sku IS NULL);

COMMIT;

