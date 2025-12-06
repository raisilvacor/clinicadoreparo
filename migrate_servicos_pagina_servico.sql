-- Migração: Adicionar coluna pagina_servico_id à tabela servicos
-- Execute este script no banco de dados PostgreSQL do Render

ALTER TABLE servicos
ADD COLUMN IF NOT EXISTS pagina_servico_id INTEGER;

-- Adicionar foreign key constraint
ALTER TABLE servicos
ADD CONSTRAINT fk_servicos_pagina_servico
FOREIGN KEY (pagina_servico_id)
REFERENCES paginas_servicos(id)
ON DELETE SET NULL;

-- Criar índice para melhor performance
CREATE INDEX IF NOT EXISTS idx_servicos_pagina_servico_id ON servicos(pagina_servico_id);

