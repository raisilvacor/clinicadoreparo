-- Migração para adicionar campos do Mercado Pago na tabela pedidos
-- Execute este script no banco de dados PostgreSQL do Render

BEGIN;

-- Adicionar coluna mercado_pago_payment_id se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='pedidos' AND column_name='mercado_pago_payment_id'
    ) THEN
        ALTER TABLE pedidos ADD COLUMN mercado_pago_payment_id VARCHAR(100);
    END IF;
END $$;

-- Adicionar coluna mercado_pago_preference_id se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='pedidos' AND column_name='mercado_pago_preference_id'
    ) THEN
        ALTER TABLE pedidos ADD COLUMN mercado_pago_preference_id VARCHAR(100);
    END IF;
END $$;

COMMIT;

