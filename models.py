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

# ==================== SERVIÇOS ====================
class Servico(db.Model):
    __tablename__ = 'servicos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    imagem = db.Column(db.String(500))
    ordem = db.Column(db.Integer, default=999)
    ativo = db.Column(db.Boolean, default=True)
    data = db.Column(db.DateTime, default=datetime.now)

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
    pdf_filename = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.now)

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
    pdf_filename = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.now)

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
    imagem = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500))
    link_target = db.Column(db.String(20), default='_self')
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)

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
    imagem = db.Column(db.String(500), nullable=False)
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)

# ==================== MILESTONES ====================
class Milestone(db.Model):
    __tablename__ = 'milestones'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    imagem = db.Column(db.String(500), nullable=False)
    ordem = db.Column(db.Integer, default=1)
    ativo = db.Column(db.Boolean, default=True)

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
    imagem_destaque = db.Column(db.String(500))
    data_publicacao = db.Column(db.DateTime, nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)

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

