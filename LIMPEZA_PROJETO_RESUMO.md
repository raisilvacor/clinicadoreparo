# Resumo da Limpeza e Reorganização do Projeto

## ✅ Mudanças Realizadas

### 1. Dependências Limpas
- **Removido**: `Flask-Migrate==4.0.5` (não utilizado)
- **Mantido**: Apenas dependências essenciais

### 2. Modelo PDFDocument Criado
- Novo modelo `PDFDocument` em `models.py` para armazenar PDFs no banco
- Campos: `id`, `nome`, `dados` (LargeBinary), `tamanho`, `tipo_documento`, `referencia_id`, `data_criacao`
- Relacionamentos adicionados em `OrdemServico` e `Comprovante` com campo `pdf_id`

### 3. Rotas de Servir Arquivos
- **Imagens**: `/admin/{entity}/imagem/<image_id>` (já existia)
- **PDFs**: `/media/pdf/<pdf_id>` (NOVO)

### 4. Funções de Geração de PDF Atualizadas
- `gerar_pdf_ordem()`: Agora gera PDF em memória (BytesIO) e salva no banco
- `gerar_pdf_comprovante()`: Agora gera PDF em memória (BytesIO) e salva no banco
- Função auxiliar `salvar_pdf_no_banco()` criada

### 5. Remoção de Criação de Diretórios
- Removido `os.makedirs(PDFS_DIR)` na inicialização
- PDFs agora são salvos apenas no banco (com fallback para arquivo apenas em desenvolvimento local)

## 📋 Arquivos Modificados

1. **models.py**
   - Adicionado modelo `PDFDocument`
   - Adicionado campo `pdf_id` em `OrdemServico` e `Comprovante`

2. **app.py**
   - Adicionado import `BytesIO`
   - Adicionado import `PDFDocument`
   - Removido `PDFS_DIR` e criação de diretórios
   - Criada função `salvar_pdf_no_banco()`
   - Atualizada função `gerar_pdf_ordem()`
   - Atualizada função `gerar_pdf_comprovante()`
   - Criada rota `/media/pdf/<pdf_id>`

3. **requirements.txt**
   - Removido `Flask-Migrate==4.0.5`

## ⚠️ Pendências

### 1. Atualizar Chamadas de Funções de PDF
As funções `gerar_pdf_ordem()` e `gerar_pdf_comprovante()` agora retornam um dicionário:
```python
{
    'pdf_id': 123,  # Se salvo no banco
    'pdf_filename': 'ordem_1_1_20251127.pdf',
    'url': '/media/pdf/123'  # ou '/static/pdfs/...' se fallback
}
```

**Locais que precisam ser atualizados:**
- Linha ~1613: `pdf_filename = gerar_pdf_ordem(cliente, nova_ordem)`
- Linha ~1786: `pdf_filename = gerar_pdf_ordem(cliente, ordem_atualizada)`
- Linha ~2404: `pdf_filename = gerar_pdf_comprovante(cliente, ordem, novo_comprovante)`
- Linha ~2670: `pdf_filename = gerar_pdf_comprovante(cliente, ordem, comprovante)`

### 2. Remover Escritas de Arquivos JSON
Há **119 ocorrências** de escrita de arquivos JSON (`with open(..., 'w')` e `json.dump`).

**Estratégia recomendada:**
- Manter leitura de JSON como fallback apenas
- Remover TODAS as escritas de JSON
- Garantir que o sistema funcione APENAS com banco de dados em produção

### 3. Atualizar Rotas de Download de PDF
As rotas que usam `send_file()` com PDFs precisam ser atualizadas para usar `/media/pdf/<pdf_id>` quando disponível.

## 📄 Código das Rotas de Servir Arquivos

### Rota de Servir Imagens (já existia)
```python
@app.route('/admin/servicos/imagem/<int:image_id>')
def servir_imagem_servico(image_id):
    """Rota para servir imagens do banco de dados"""
    if use_database():
        try:
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime or 'image/jpeg',
                    headers={
                        'Content-Disposition': f'inline; filename={imagem.nome or "imagem.jpg"}',
                        'Cache-Control': 'public, max-age=31536000'
                    }
                )
        except Exception as e:
            print(f"Erro ao buscar imagem: {e}")
    
    return redirect(url_for('static', filename='img/placeholder.png'))
```

### Rota de Servir PDFs (NOVO)
```python
@app.route('/media/pdf/<int:pdf_id>')
def servir_pdf(pdf_id):
    """Rota para servir PDFs do banco de dados"""
    if use_database():
        try:
            pdf_doc = PDFDocument.query.get(pdf_id)
            if pdf_doc and pdf_doc.dados:
                return Response(
                    pdf_doc.dados,
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'inline; filename={pdf_doc.nome or "documento.pdf"}',
                        'Cache-Control': 'public, max-age=31536000'
                    }
                )
        except Exception as e:
            print(f"Erro ao buscar PDF: {e}")
    
    return "PDF não encontrado", 404
```

## 🔄 Próximos Passos

1. Atualizar todas as chamadas de `gerar_pdf_*` para usar o novo formato de retorno
2. Atualizar rotas de download para usar `/media/pdf/<pdf_id>`
3. Remover todas as escritas de arquivos JSON (119 ocorrências)
4. Testar sistema completo com banco de dados
5. Remover fallbacks de arquivo (opcional, apenas para desenvolvimento local)

