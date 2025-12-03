from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON

db = SQLAlchemy()

# ==================== CLIENTES ====================
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    cpf = db.Column(db.String(14))
    endereco = db.Column(db.Text)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    ordens = db.relationship('OrdemServico', backref='cliente', lazy=True, cascade='all, delete-orphan')

# ==================== IMAGENS ====================
class Imagem(db.Model):
    """Tabela para armazenar imagens no banco de dados"""
    __tablename__ = 'imagens'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    dados = db.Column(db.LargeBinary, nullable=False)  # Dados binários da imagem
    tipo_mime = db.Column(db.String(50), nullable=False)  # image/jpeg, image/png, etc
    tamanho = db.Column(db.Integer)  # Tamanho em bytes
    data_upload = db.Column(db.DateTime, default=datetime.now)
    referencia = db.Column(db.String(200))  # Referência (ex: 'servico_123')

# ==================== PDFs ====================
class PDFDocument(db.Model):
    """Tabela para armazenar PDFs no banco de dados"""
    __tablename__ = 'pdf_documents'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    dados = db.Column(db.LargeBinary, nullable=False)  # Dados binários do PDF
    tamanho = db.Column(db.Integer)  # Tamanho em bytes
    tipo_documento = db.Column(db.String(50))  # 'ordem_servico', 'comprovante'
    referencia_id = db.Column(db.Integer)  # ID do documento relacionado (ordem_id, comprovante_id)
    data_criacao = db.Column(db.DateTime, default=datetime.now)

# ==================== SERVIÇOS ====================
class Servico(db.Model):
    __tablename__ = 'servicos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    ordem = db.Column(db.Integer, default=999)
    ativo = db.Column(db.Boolean, default=True)
    data = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== TÉCNICOS ====================
class Tecnico(db.Model):
    __tablename__ = 'tecnicos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(200))
    especialidade = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    ordens = db.relationship('OrdemServico', backref='tecnico', lazy=True)

# ==================== ORDENS DE SERVIÇO ====================
class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'
    id = db.Column(db.Integer, primary_key=True)
    numero_ordem = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))
    servico = db.Column(db.String(200))
    tipo_aparelho = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    numero_serie = db.Column(db.String(100))
    defeitos_cliente = db.Column(db.Text)
    diagnostico_tecnico = db.Column(db.Text)
    pecas = db.Column(JSON)  # Lista de peças como JSON
    custo_pecas = db.Column(db.Numeric(10, 2), default=0)
    custo_mao_obra = db.Column(db.Numeric(10, 2), default=0)
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    desconto_percentual = db.Column(db.Numeric(5, 2), default=0)
    valor_desconto = db.Column(db.Numeric(10, 2), default=0)
    cupom_id = db.Column(db.Integer)
    total = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(50), default='pendente')
    prazo_estimado = db.Column(db.String(100))
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf_documents.id'))  # Referência ao PDF no banco
    pdf_filename = db.Column(db.String(200))  # Mantido para compatibilidade/fallback
    data = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    pdf_document = db.relationship('PDFDocument', foreign_keys=[pdf_id], lazy=True)

# ==================== COMPROVANTES ====================
class Comprovante(db.Model):
    __tablename__ = 'comprovantes'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, nullable=False)
    cliente_nome = db.Column(db.String(200))
    ordem_id = db.Column(db.Integer)
    numero_ordem = db.Column(db.Integer)
    valor_total = db.Column(db.Numeric(10, 2))
    valor_pago = db.Column(db.Numeric(10, 2))
    forma_pagamento = db.Column(db.String(50))
    parcelas = db.Column(db.Integer, default=1)
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf_documents.id'))  # Referência ao PDF no banco
    pdf_filename = db.Column(db.String(200))  # Mantido para compatibilidade/fallback
    data = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    pdf_document = db.relationship('PDFDocument', foreign_keys=[pdf_id], lazy=True)

# ==================== CUPONS DE FIDELIDADE ====================
class Cupom(db.Model):
    __tablename__ = 'cupons'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, nullable=False)
    cliente_nome = db.Column(db.String(200))
    desconto_percentual = db.Column(db.Numeric(5, 2), nullable=False)
    usado = db.Column(db.Boolean, default=False)
    ordem_id = db.Column(db.Integer)
    data_emissao = db.Column(db.DateTime, default=datetime.now)
    data_uso = db.Column(db.DateTime)

# ==================== SLIDES ====================
class Slide(db.Model):
    __tablename__ = 'slides'
    id = db.Column(db.Integer, primary_key=True)
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    link = db.Column(db.String(500))
    link_target = db.Column(db.String(20), default='_self')
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== FOOTER ====================
class Footer(db.Model):
    __tablename__ = 'footer'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.Text)
    redes_sociais = db.Column(JSON)  # {facebook, instagram, whatsapp}
    contato = db.Column(JSON)  # {telefone, email, endereco}
    copyright = db.Column(db.String(500))
    whatsapp_float = db.Column(db.String(500))

# ==================== MARCAS ====================
class Marca(db.Model):
    __tablename__ = 'marcas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== MILESTONES ====================
class Milestone(db.Model):
    __tablename__ = 'milestones'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== ADMIN USERS ====================
class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(200))
    email = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)

# ==================== AGENDAMENTOS ====================
class Agendamento(db.Model):
    __tablename__ = 'agendamentos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    data_agendamento = db.Column(db.Date, nullable=False)
    hora_agendamento = db.Column(db.String(10), nullable=False)
    tipo_servico = db.Column(db.String(200))
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(50), default='pendente')
    data_criacao = db.Column(db.DateTime, default=datetime.now)

# ==================== BLOG ====================
class Artigo(db.Model):
    __tablename__ = 'artigos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(500), nullable=False)
    subtitulo = db.Column(db.String(500))
    slug = db.Column(db.String(500), unique=True)
    categoria = db.Column(db.String(100))
    autor = db.Column(db.String(200))
    resumo = db.Column(db.Text)
    conteudo = db.Column(db.Text)  # HTML do editor
    imagem_destaque = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
    imagem_destaque_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    data_publicacao = db.Column(db.DateTime, nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_destaque_id], lazy=True)

# ==================== CONTATOS ====================
class Contato(db.Model):
    __tablename__ = 'contatos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    servico = db.Column(db.String(200))
    mensagem = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.now)

# ==================== FORNECEDORES ====================
class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    contato = db.Column(db.String(200))  # Nome do contato
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(200))
    endereco = db.Column(db.Text)
    cnpj = db.Column(db.String(18))
    tipo_servico = db.Column(db.String(200))  # Tipo de serviço que o fornecedor oferece
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)

# ==================== LOJA - CATEGORIAS ====================
class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True)
    descricao = db.Column(db.Text)
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback)
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)
    produtos = db.relationship('Produto', backref='categoria', lazy=True)

# ==================== LOJA - PRODUTOS ====================
class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True)
    descricao = db.Column(db.Text)
    descricao_completa = db.Column(db.Text)  # Descrição detalhada
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'))
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    preco_promocional = db.Column(db.Numeric(10, 2))  # Preço com desconto
    estoque = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(100), unique=True)  # Código do produto
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem principal (fallback)
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    imagens_galeria = db.Column(JSON)  # Lista de IDs de imagens adicionais
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    peso = db.Column(db.Numeric(10, 2))  # Peso em kg
    dimensoes = db.Column(db.String(100))  # Ex: "10x20x5 cm"
    ativo = db.Column(db.Boolean, default=True)
    destaque = db.Column(db.Boolean, default=False)  # Produto em destaque
    ordem = db.Column(db.Integer, default=1)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamentos
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)
    itens_pedido = db.relationship('ItemPedido', backref='produto', lazy=True)

# ==================== LOJA - PEDIDOS ====================
class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))
    cliente_nome = db.Column(db.String(200), nullable=False)
    cliente_email = db.Column(db.String(200))
    cliente_telefone = db.Column(db.String(20), nullable=False)
    cliente_cpf = db.Column(db.String(14))
    endereco_entrega = db.Column(db.Text, nullable=False)
    cep = db.Column(db.String(10))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    frete = db.Column(db.Numeric(10, 2), default=0)
    desconto = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    forma_pagamento = db.Column(db.String(50))  # 'pix', 'cartao', 'boleto'
    status = db.Column(db.String(50), default='pendente')  # pendente, confirmado, em_preparacao, enviado, entregue, cancelado
    observacoes = db.Column(db.Text)
    data_pedido = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    mercado_pago_payment_id = db.Column(db.String(100))  # ID do pagamento no Mercado Pago
    mercado_pago_preference_id = db.Column(db.String(100))  # ID da preferência no Mercado Pago
    
    # Relacionamentos
    cliente = db.relationship('Cliente', foreign_keys=[cliente_id], lazy=True)
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True, cascade='all, delete-orphan')

# ==================== LOJA - ITENS DO PEDIDO ====================
class ItemPedido(db.Model):
    __tablename__ = 'itens_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id', ondelete='CASCADE'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id', ondelete='SET NULL'), nullable=True)  # Permite NULL para produtos removidos
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)  # Preço no momento da compra
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    # Campos opcionais para histórico (podem não existir no banco ainda)
    # produto_nome e produto_sku serão adicionados após executar migrate_produtos_delete.sql
    
    # NOTA: O relacionamento 'produto' é criado automaticamente via backref no modelo Produto
    # Não definir aqui para evitar conflito

