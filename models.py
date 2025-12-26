from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
import os

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
    descricao = db.Column(db.Text)  # Mantido para compatibilidade, mas não será usado
    imagem = db.Column(db.String(500))  # Caminho ou ID da imagem
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Referência à tabela de imagens
    # pagina_servico_id = db.Column(db.Integer, db.ForeignKey('paginas_servicos.id'))  # TEMPORARIAMENTE COMENTADO - Descomente após executar migrate_servicos_pagina_servico.sql
    ordem = db.Column(db.Integer, default=999)
    ativo = db.Column(db.Boolean, default=True)
    data = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)
    # pagina_servico = db.relationship('PaginaServico', foreign_keys=[pagina_servico_id], lazy=True)  # TEMPORARIAMENTE COMENTADO - Descomente após executar migrate_servicos_pagina_servico.sql

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

# Modelos da loja removidos - sistema de loja removido

# ==================== REPAROS REALIZADOS ====================
class ReparoRealizado(db.Model):
    """Galeria de fotos de reparos realizados"""
    __tablename__ = 'reparos_realizados'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))  # Título opcional para a foto
    descricao = db.Column(db.Text)  # Descrição opcional
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'), nullable=False)
    ordem = db.Column(db.Integer, default=1)  # Ordem de exibição
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== VÍDEOS ====================
class Video(db.Model):
    """Vídeos do YouTube cadastrados usando código embed"""
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    embed_code = db.Column(db.Text, nullable=False)  # Código embed do YouTube
    ordem = db.Column(db.Integer, default=1)  # Ordem de exibição
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    def get_video_id(self):
        """Extrai o ID do vídeo do YouTube do código embed"""
        import re
        # Tenta extrair o ID de diferentes formatos de embed
        # Formato 1: src="https://www.youtube.com/embed/VIDEO_ID"
        # Formato 2: src="https://youtu.be/VIDEO_ID"
        # Formato 3: VIDEO_ID direto
        if not self.embed_code:
            return None
        
        # Procurar por /embed/VIDEO_ID
        match = re.search(r'/embed/([a-zA-Z0-9_-]{11})', self.embed_code)
        if match:
            return match.group(1)
        
        # Procurar por youtu.be/VIDEO_ID
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', self.embed_code)
        if match:
            return match.group(1)
        
        # Procurar por ID direto (11 caracteres)
        match = re.search(r'([a-zA-Z0-9_-]{11})', self.embed_code)
        if match and len(match.group(1)) == 11:
            return match.group(1)
        
        return None
    
    def get_embed_url(self):
        """Retorna a URL embed do YouTube"""
        video_id = self.get_video_id()
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}'
        return None
    
    def get_thumbnail_url(self):
        """Retorna a URL da thumbnail automática do YouTube"""
        video_id = self.get_video_id()
        if video_id:
            return f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
        return None
    
    def get_embed_html(self):
        """Retorna o HTML do iframe embed"""
        video_id = self.get_video_id()
        if video_id:
            return f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
        return self.embed_code  # Fallback: retorna o código original

# ==================== MANUAIS ====================
class Manual(db.Model):
    """Manuais em PDF cadastrados no sistema"""
    __tablename__ = 'manuais'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    pdf_data = db.Column(db.LargeBinary, nullable=False)  # Dados binários do PDF
    pdf_filename = db.Column(db.String(200), nullable=False)  # Nome do arquivo original
    pdf_size = db.Column(db.Integer, nullable=False)  # Tamanho em bytes
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def get_pdf_url(self):
        """Retorna a URL para servir o PDF"""
        return f'/media/manual/{self.id}'
    
    def get_download_url(self):
        """Retorna a URL para download do PDF"""
        return f'/admin/manuais/{self.id}/download'

# ==================== PÁGINAS DE SERVIÇOS ====================
class PaginaServico(db.Model):
    """Páginas individuais de serviços (Máquina de Lavar, Microondas, etc.)"""
    __tablename__ = 'paginas_servicos'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)  # URL amigável (ex: maquina-de-lavar)
    titulo = db.Column(db.String(200), nullable=False)  # Título exibido no menu (ex: Máquina de Lavar)
    descricao = db.Column(db.Text)  # Descrição da página
    conteudo = db.Column(db.Text)  # Conteúdo HTML da página
    # imagem = db.Column(db.String(500))  # Caminho ou ID da imagem (fallback) - Desabilitado temporariamente até migração
    imagem_id = db.Column(db.Integer, db.ForeignKey('imagens.id'))  # Imagem principal
    ordem = db.Column(db.Integer, default=1)  # Ordem no menu
    ativo = db.Column(db.Boolean, default=True)  # Se aparece no menu
    meta_titulo = db.Column(db.String(200))  # SEO: meta title
    meta_descricao = db.Column(db.Text)  # SEO: meta description
    meta_keywords = db.Column(db.String(500))  # SEO: meta keywords
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamento
    imagem_obj = db.relationship('Imagem', foreign_keys=[imagem_id], lazy=True)

# ==================== ORÇAMENTO AR-CONDICIONADO ====================
class OrcamentoArCondicionado(db.Model):
    __tablename__ = 'orcamentos_ar_condicionado'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))
    tipo_servico = db.Column(db.String(100), nullable=False)  # Instalação, Limpeza Evaporadora, Limpeza Completa, Remoção
    potencia_btu = db.Column(db.Integer, nullable=False)  # 9000, 12000, 18000, etc
    tipo_acesso = db.Column(db.String(50), nullable=False)  # Fácil, Moderado, Difícil
    marca_aparelho = db.Column(db.String(100))
    modelo_aparelho = db.Column(db.String(100))
    material_adicional = db.Column(db.String(100))  # Kit Convencional, Tubulação extra
    valor_material_adicional = db.Column(db.Numeric(10, 2), default=0)
    custos_adicionais = db.Column(JSON)  # Lista de custos adicionais: [{"item": "Nome", "valor": 100.00}, ...]
    valor_base = db.Column(db.Numeric(10, 2), nullable=False)
    valor_acesso = db.Column(db.Numeric(10, 2), default=0)  # Valor do acréscimo por acesso
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), default='pendente')
    prazo_estimado = db.Column(db.String(100))
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf_documents.id'))
    pdf_filename = db.Column(db.String(200))
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamentos
    cliente = db.relationship('Cliente', foreign_keys=[cliente_id], lazy=True)
    tecnico = db.relationship('Tecnico', foreign_keys=[tecnico_id], lazy=True)
    pdf_document = db.relationship('PDFDocument', foreign_keys=[pdf_id], lazy=True)

# ==================== LINKS DO MENU ====================
class LinkMenu(db.Model):
    """Links gerenciáveis do menu principal"""
    __tablename__ = 'links_menu'
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(200), nullable=False)  # Texto exibido no menu (ex: "Celulares")
    url = db.Column(db.String(500), nullable=False)  # URL do link (ex: "/celulares" ou "https://...")
    ordem = db.Column(db.Integer, default=1)  # Ordem no menu
    ativo = db.Column(db.Boolean, default=True)  # Se aparece no menu
    abrir_nova_aba = db.Column(db.Boolean, default=True)  # Se deve abrir em nova aba
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

