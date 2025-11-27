"""
Funções auxiliares para acesso ao banco de dados
Abstrai o acesso aos dados, usando banco de dados quando disponível
"""

from models import (
    Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom,
    Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Artigo, Contato
)
from app import db
import os
import json
from datetime import datetime

def use_database():
    """Verifica se deve usar banco de dados"""
    return bool(os.environ.get('DATABASE_URL'))

def parse_datetime(date_str):
    """Converte string de data para datetime"""
    if not date_str:
        return datetime.now()
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return datetime.now()

# ==================== CLIENTES ====================
def get_all_clientes():
    """Retorna todos os clientes"""
    if use_database():
        return Cliente.query.all()
    else:
        with open('data/clients.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('clients', [])

def get_cliente_by_id(cliente_id):
    """Retorna cliente por ID"""
    if use_database():
        return Cliente.query.get(cliente_id)
    else:
        with open('data/clients.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return next((c for c in data.get('clients', []) if c.get('id') == cliente_id), None)

def save_cliente(cliente_data):
    """Salva cliente"""
    if use_database():
        cliente = Cliente(**cliente_data)
        db.session.add(cliente)
        db.session.commit()
        return cliente
    else:
        # Implementação JSON (manter compatibilidade)
        with open('data/clients.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['clients'].append(cliente_data)
        with open('data/clients.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return cliente_data

# ==================== SERVIÇOS ====================
def get_all_servicos():
    """Retorna todos os serviços"""
    if use_database():
        return Servico.query.filter_by(ativo=True).order_by(Servico.ordem).all()
    else:
        with open('data/services.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [s for s in data.get('services', []) if s.get('ativo', True)]

def get_servico_by_id(servico_id):
    """Retorna serviço por ID"""
    if use_database():
        return Servico.query.get(servico_id)
    else:
        with open('data/services.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return next((s for s in data.get('services', []) if s.get('id') == servico_id), None)

# ==================== TÉCNICOS ====================
def get_all_tecnicos():
    """Retorna todos os técnicos"""
    if use_database():
        return Tecnico.query.filter_by(ativo=True).all()
    else:
        with open('data/tecnicos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [t for t in data.get('tecnicos', []) if t.get('ativo', True)]

def get_tecnico_by_id(tecnico_id):
    """Retorna técnico por ID"""
    if use_database():
        return Tecnico.query.get(tecnico_id)
    else:
        with open('data/tecnicos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return next((t for t in data.get('tecnicos', []) if t.get('id') == tecnico_id), None)

# ==================== SLIDES ====================
def get_all_slides():
    """Retorna todos os slides ativos"""
    if use_database():
        return Slide.query.filter_by(ativo=True).order_by(Slide.ordem).all()
    else:
        with open('data/slides.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [s for s in data.get('slides', []) if s.get('ativo', True)]

# ==================== FOOTER ====================
def get_footer():
    """Retorna configurações do footer"""
    if use_database():
        footer = Footer.query.first()
        if footer:
            return {
                'descricao': footer.descricao,
                'redes_sociais': footer.redes_sociais or {},
                'contato': footer.contato or {},
                'copyright': footer.copyright,
                'whatsapp_float': footer.whatsapp_float
            }
        return None
    else:
        if os.path.exists('data/footer.json'):
            with open('data/footer.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

# ==================== MARCAS ====================
def get_all_marcas():
    """Retorna todas as marcas ativas"""
    if use_database():
        return Marca.query.filter_by(ativo=True).order_by(Marca.ordem).all()
    else:
        with open('data/marcas.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [m for m in data.get('marcas', []) if m.get('ativo', True)]

# ==================== MILESTONES ====================
def get_all_milestones():
    """Retorna todos os milestones ativos"""
    if use_database():
        return Milestone.query.filter_by(ativo=True).order_by(Milestone.ordem).all()
    else:
        with open('data/milestones.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [m for m in data.get('milestones', []) if m.get('ativo', True)]

# ==================== ADMIN USERS ====================
def get_admin_user_by_username(username):
    """Retorna usuário admin por username"""
    if use_database():
        return AdminUser.query.filter_by(username=username, ativo=True).first()
    else:
        with open('data/admin_users.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return next((u for u in data.get('users', []) if u.get('username') == username and u.get('ativo')), None)

# ==================== AGENDAMENTOS ====================
def get_all_agendamentos():
    """Retorna todos os agendamentos"""
    if use_database():
        return Agendamento.query.order_by(Agendamento.data_criacao.desc()).all()
    else:
        with open('data/agendamentos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return sorted(data.get('agendamentos', []), key=lambda x: x.get('data_criacao', ''), reverse=True)

# ==================== BLOG ====================
def get_all_artigos():
    """Retorna todos os artigos ativos"""
    if use_database():
        return Artigo.query.filter_by(ativo=True).order_by(Artigo.data_publicacao.desc()).all()
    else:
        with open('data/blog.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [a for a in data.get('artigos', []) if a.get('ativo', True)]

def get_artigo_by_id(artigo_id):
    """Retorna artigo por ID"""
    if use_database():
        return Artigo.query.get(artigo_id)
    else:
        with open('data/blog.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return next((a for a in data.get('artigos', []) if a.get('id') == artigo_id), None)

