-- Migração: Adicionar coluna 'imagem' à tabela 'paginas_servicos'
-- Execute este script no banco de dados PostgreSQL do Render

-- Verificar se a coluna já existe antes de adicionar
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'paginas_servicos' 
        AND column_name = 'imagem'
    ) THEN
        ALTER TABLE paginas_servicos 
        ADD COLUMN imagem VARCHAR(500);
        
        RAISE NOTICE 'Coluna "imagem" adicionada com sucesso à tabela paginas_servicos';
    ELSE
        RAISE NOTICE 'Coluna "imagem" já existe na tabela paginas_servicos';
    END IF;
END $$;

