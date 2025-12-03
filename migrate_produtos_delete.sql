-- Script de migração para permitir exclusão de produtos mesmo com itens de pedido
-- Execute este script no banco de dados PostgreSQL do Render

-- 1. Adicionar colunas para dados históricos na tabela itens_pedido
ALTER TABLE itens_pedido 
ADD COLUMN IF NOT EXISTS produto_nome VARCHAR(200),
ADD COLUMN IF NOT EXISTS produto_sku VARCHAR(100);

-- 2. Preencher dados históricos para itens existentes que têm produto
UPDATE itens_pedido ip
SET produto_nome = p.nome,
    produto_sku = p.sku
FROM produtos p
WHERE ip.produto_id = p.id 
  AND (ip.produto_nome IS NULL OR ip.produto_sku IS NULL);

-- 3. Modificar a foreign key para permitir NULL e usar ON DELETE SET NULL
-- Primeiro, remover a constraint existente
ALTER TABLE itens_pedido 
DROP CONSTRAINT IF EXISTS itens_pedido_produto_id_fkey;

-- Adicionar nova constraint com ON DELETE SET NULL
ALTER TABLE itens_pedido 
ADD CONSTRAINT itens_pedido_produto_id_fkey 
FOREIGN KEY (produto_id) 
REFERENCES produtos(id) 
ON DELETE SET NULL;

-- 4. Modificar produto_id para permitir NULL
ALTER TABLE itens_pedido 
ALTER COLUMN produto_id DROP NOT NULL;

-- Verificar se a migração foi bem-sucedida
SELECT 
    COUNT(*) as total_itens,
    COUNT(produto_id) as itens_com_produto,
    COUNT(*) - COUNT(produto_id) as itens_sem_produto,
    COUNT(produto_nome) as itens_com_nome_historico
FROM itens_pedido;

