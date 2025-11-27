from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_file, Response
from datetime import datetime
import json
import os
from functools import wraps
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models import db, Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom, Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Artigo, Contato, Imagem, PDFDocument

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sua_chave_secreta_aqui_altere_em_producao')

# Flag global para rastrear se o banco está disponível
DB_AVAILABLE = False

# Configuração do banco de dados (opcional)
database_url = os.environ.get('DATABASE_URL', '')
if database_url:
    try:
        # Render usa postgres:// mas SQLAlchemy precisa postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Corrigir URL do Render se necessário (adicionar porta padrão se faltar)
        if 'postgresql://' in database_url and '@' in database_url:
            # Verificar se tem porta
            parts = database_url.split('@')
            if len(parts) == 2:
                host_part = parts[1]
                # Se não tem porta e não tem / após o host, adicionar porta padrão
                if ':' not in host_part.split('/')[0] and not host_part.startswith('localhost'):
                    # Render usa porta 5432 por padrão
                    host_with_port = host_part.split('/')[0] + ':5432'
                    if '/' in host_part:
                        database_url = parts[0] + '@' + host_with_port + '/' + '/'.join(host_part.split('/')[1:])
                    else:
                        database_url = parts[0] + '@' + host_with_port
        
        # Adicionar parâmetros SSL se necessário (para Render)
        if ('render.com' in database_url or 'dpg-' in database_url) and '?sslmode=' not in database_url:
            if '?' in database_url:
                database_url += '&sslmode=require'
            else:
                database_url += '?sslmode=require'
        
        print(f"DEBUG: URL do banco configurada: {database_url[:50]}...")
        
        # IMPORTANTE: Configurar SQLALCHEMY_DATABASE_URI ANTES de db.init_app()
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        # Configurar SSL para conexões externas (Render)
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {
                'sslmode': 'require',
                'connect_timeout': 10
            },
            'pool_pre_ping': True,  # Verificar conexão antes de usar
            'pool_recycle': 300  # Reciclar conexões a cada 5 minutos
        }
        
        # Inicializar o banco de dados
        # IMPORTANTE: db.init_app() deve ser chamado DEPOIS de configurar SQLALCHEMY_DATABASE_URI
        db.init_app(app)
        
        # Criar tabelas se não existirem (apenas se conseguir conectar)
        try:
            with app.app_context():
                # Forçar criação do engine e tabelas
                db.create_all()
                # Testar conexão (mas não falhar se der erro temporário)
                try:
                    # Garantir que o engine está criado
                    engine = db.get_engine()
                    if engine:
                        with engine.connect() as conn:
                            conn.execute(db.text('SELECT 1'))
                        print("DEBUG: ✅ Banco de dados configurado e conectado com sucesso!")
                        DB_AVAILABLE = True
                    else:
                        print("DEBUG: ⚠️ Engine não pôde ser criado")
                        DB_AVAILABLE = False
                except Exception as conn_error:
                    print(f"DEBUG: ⚠️ Aviso ao testar conexão: {type(conn_error).__name__}: {str(conn_error)}")
                    print("DEBUG: O banco está configurado, mas a conexão pode estar temporariamente indisponível.")
                    print("DEBUG: O sistema tentará usar o banco quando necessário.")
                    DB_AVAILABLE = False
        except Exception as e:
            print(f"DEBUG: ⚠️ Erro ao inicializar banco de dados: {type(e).__name__}: {str(e)}")
            print("DEBUG: O sistema tentará usar o banco quando necessário.")
            DB_AVAILABLE = False
    except Exception as e:
        print(f"DEBUG: Erro ao configurar banco de dados: {type(e).__name__}: {str(e)}")
        print("O sistema continuará funcionando com arquivos JSON.")
        DB_AVAILABLE = False

# Credenciais de admin (em produção, use hash e variáveis de ambiente)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'  # Altere em produção!

# Caminhos para os arquivos de dados
DATA_FILE = 'data/services.json'
CLIENTS_FILE = 'data/clients.json'
COMPROVANTES_FILE = 'data/comprovantes.json'
FIDELIDADE_FILE = 'data/fidelidade.json'
TECNICOS_FILE = 'data/tecnicos.json'
SLIDES_FILE = 'data/slides.json'
FOOTER_FILE = 'data/footer.json'
MARCAS_FILE = 'data/marcas.json'
MILESTONES_FILE = 'data/milestones.json'
ADMIN_USERS_FILE = 'data/admin_users.json'
AGENDAMENTOS_FILE = 'data/agendamentos.json'
BLOG_FILE = 'data/blog.json'
# NOTA: NÃO criar diretórios para uploads - tudo vai direto para o banco PostgreSQL
# static/ deve conter APENAS arquivos estáticos do build (CSS, JS, imagens fixas)
# PDFs e imagens são salvos diretamente no banco de dados

# Configurações de upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== FUNÇÕES AUXILIARES ====================

def use_database():
    """Verifica se deve usar banco de dados - configuração direta com Render"""
    global DB_AVAILABLE
    
    # Se a flag indica que o banco não está disponível, retornar False imediatamente
    if not DB_AVAILABLE:
        return False
    
    # Verificar se DATABASE_URL existe nas variáveis de ambiente
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        return False
    
    # Verificar se o banco foi configurado no app
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        return False
    
    # Se chegou aqui, o banco está disponível
    return True

def get_proximo_numero_ordem():
    """Gera um número aleatório de 6 dígitos sem ser sequencial"""
    import random
    
    # Coletar todos os números de ordem existentes
    numeros_existentes = set()
    
    if use_database():
        # Usar banco de dados
        try:
            ordens = OrdemServico.query.all()
        except Exception as e:
            print(f"Erro ao carregar ordens do banco: {e}")
            ordens = []
        for ordem in ordens:
            if ordem.numero_ordem:
                try:
                    num = str(ordem.numero_ordem).replace('#', '').strip()
                    numeros_existentes.add(int(num))
                except:
                    pass
    else:
        # Usar arquivo JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for cliente in data['clients']:
            for ordem in cliente.get('ordens', []):
                if ordem.get('numero_ordem'):
                    try:
                        num = str(ordem['numero_ordem']).replace('#', '').strip()
                        numeros_existentes.add(int(num))
                    except:
                        pass
    
    def eh_sequencial(numero):
        """Verifica se o número é sequencial (crescente ou decrescente)"""
        str_num = str(numero)
        if len(str_num) != 6:
            return False
        
        # Verificar se é sequencial crescente (ex: 123456)
        crescente = True
        for i in range(len(str_num) - 1):
            if int(str_num[i+1]) != int(str_num[i]) + 1:
                crescente = False
                break
        
        # Verificar se é sequencial decrescente (ex: 654321)
        decrescente = True
        for i in range(len(str_num) - 1):
            if int(str_num[i+1]) != int(str_num[i]) - 1:
                decrescente = False
                break
        
        return crescente or decrescente
    
    def gerar_numero_aleatorio():
        """Gera um número aleatório de 6 dígitos (100000 a 999999)"""
        return random.randint(100000, 999999)
    
    # Tentar gerar um número único que não seja sequencial (máximo 10000 tentativas)
    max_tentativas = 10000
    for _ in range(max_tentativas):
        numero = gerar_numero_aleatorio()
        # Verificar se não é sequencial e se não existe
        if not eh_sequencial(numero) and numero not in numeros_existentes:
            return numero
    
    # Se não conseguir, tentar números não sequenciais de forma sistemática
    # Começar de 100000 e pular sequenciais
    numero_base = 100000
    tentativas_fallback = 0
    max_fallback = 100000
    while tentativas_fallback < max_fallback:
        if not eh_sequencial(numero_base) and numero_base not in numeros_existentes:
            return numero_base
        numero_base += 1
        tentativas_fallback += 1
        # Garantir que não ultrapasse 999999
        if numero_base > 999999:
            numero_base = 100000
    
    # Último recurso: número aleatório (pode ser sequencial, mas é raro)
    return random.randint(100000, 999999)

def atualizar_numeros_ordens():
    """Atualiza ordens existentes que não têm número de ordem (gera números aleatórios não sequenciais)"""
    import random
    
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    atualizado = False
    
    # Coletar todos os números existentes
    numeros_existentes = set()
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            if ordem.get('numero_ordem'):
                try:
                    # Converter para int, removendo # se houver
                    num = str(ordem['numero_ordem']).replace('#', '').strip()
                    numeros_existentes.add(int(num))
                except:
                    pass
    
    def eh_sequencial(numero):
        """Verifica se o número é sequencial (crescente ou decrescente)"""
        str_num = str(numero)
        if len(str_num) != 6:
            return False
        
        # Verificar se é sequencial crescente (ex: 123456)
        crescente = True
        for i in range(len(str_num) - 1):
            if int(str_num[i+1]) != int(str_num[i]) + 1:
                crescente = False
                break
        
        # Verificar se é sequencial decrescente (ex: 654321)
        decrescente = True
        for i in range(len(str_num) - 1):
            if int(str_num[i+1]) != int(str_num[i]) - 1:
                decrescente = False
                break
        
        return crescente or decrescente
    
    def gerar_numero_aleatorio():
        """Gera um número aleatório de 6 dígitos (100000 a 999999)"""
        return random.randint(100000, 999999)
    
    # Atribuir números aleatórios para ordens sem número
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            if not ordem.get('numero_ordem'):
                # Gerar número único que não seja sequencial
                max_tentativas = 10000
                numero_gerado = None
                for _ in range(max_tentativas):
                    numero = gerar_numero_aleatorio()
                    if not eh_sequencial(numero) and numero not in numeros_existentes:
                        numero_gerado = numero
                        break
                
                if numero_gerado:
                    ordem['numero_ordem'] = numero_gerado
                    numeros_existentes.add(numero_gerado)
                    atualizado = True
                else:
                    # Fallback: usar número não sequencial de forma sistemática
                    numero_base = 100000
                    tentativas = 0
                    while tentativas < 100000:
                        if not eh_sequencial(numero_base) and numero_base not in numeros_existentes:
                            ordem['numero_ordem'] = numero_base
                            numeros_existentes.add(numero_base)
                            atualizado = True
                            break
                        numero_base += 1
                        tentativas += 1
                        if numero_base > 999999:
                            numero_base = 100000
    
    if atualizado:
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Atualizar números de ordens existentes na inicialização
atualizar_numeros_ordens()

# Inicializar arquivo de dados se não existir
def init_data_file():
    if not os.path.exists(DATA_FILE):
        data = {
            'services': [
                {
                    'id': 1,
                    'nome': 'Reparo de Celulares',
                    'descricao': 'Troca de tela, bateria, conectores e muito mais. Todas as marcas e modelos.',
                    'imagem': 'img/servico-celular.jpg',
                    'ordem': 1,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 2,
                    'nome': 'Eletrodomésticos',
                    'descricao': 'Geladeiras, máquinas de lavar, micro-ondas e todos os eletrodomésticos.',
                    'imagem': 'img/servico-eletrodomestico.jpg',
                    'ordem': 2,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 3,
                    'nome': 'Computadores e Notebook',
                    'descricao': 'Reparo e manutenção de computadores, notebooks e componentes.',
                    'imagem': 'img/servico-computador.jpg',
                    'ordem': 3,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            ],
            'contacts': []
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        # Verificar se precisa adicionar serviços padrão
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Se não houver serviços, adicionar os padrão
        if not data.get('services') or len(data['services']) == 0:
            data['services'] = [
                {
                    'id': 1,
                    'nome': 'Reparo de Celulares',
                    'descricao': 'Troca de tela, bateria, conectores e muito mais. Todas as marcas e modelos.',
                    'imagem': 'img/servico-celular.jpg',
                    'ordem': 1,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 2,
                    'nome': 'Eletrodomésticos',
                    'descricao': 'Geladeiras, máquinas de lavar, micro-ondas e todos os eletrodomésticos.',
                    'imagem': 'img/servico-eletrodomestico.jpg',
                    'ordem': 2,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 3,
                    'nome': 'Computadores e Notebook',
                    'descricao': 'Reparo e manutenção de computadores, notebooks e componentes.',
                    'imagem': 'img/servico-computador.jpg',
                    'ordem': 3,
                    'ativo': True,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            ]
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            # Atualizar serviços existentes para incluir novos campos se não existirem
            updated = False
            for servico in data.get('services', []):
                if 'imagem' not in servico:
                    servico['imagem'] = ''
                if 'ordem' not in servico:
                    servico['ordem'] = servico.get('id', 999)
                if 'ativo' not in servico:
                    servico['ativo'] = True
                if 'preco' in servico:
                    # Remover campo preco antigo
                    del servico['preco']
                    updated = True
            
            if updated:
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

init_data_file()

# ==================== ADMIN USERS ====================

def init_admin_users_file():
    """Inicializa arquivo de usuários admin se não existir"""
    if not os.path.exists(ADMIN_USERS_FILE):
        data_dir = os.path.dirname(ADMIN_USERS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {
            'users': [
                {
                    'id': 1,
                    'username': 'admin',
                    'password': 'admin123',
                    'nome': 'Administrador',
                    'email': 'admin@clinicadoreparo.com',
                    'ativo': True,
                    'data_criacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            ]
        }
        with open(ADMIN_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

init_admin_users_file()

# ==================== FOOTER ====================

def init_footer_file():
    """Inicializa arquivo de rodapé se não existir"""
    if not os.path.exists(FOOTER_FILE):
        data_dir = os.path.dirname(FOOTER_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {
                'facebook': '',
                'instagram': '',
                'whatsapp': 'https://wa.me/5586988959957'
            },
            'contato': {
                'telefone': '(11) 99999-9999',
                'email': 'contato@techassist.com.br',
                'endereco': 'São Paulo, SP'
            },
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': 'https://wa.me/5586988959957'
        }
        with open(FOOTER_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

init_footer_file()

# ==================== MARCAS ====================

def init_marcas_file():
    """Inicializa arquivo de marcas se não existir"""
    if not os.path.exists(MARCAS_FILE):
        data_dir = os.path.dirname(MARCAS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {
            'marcas': [
                {'id': i, 'nome': f'Marca {i}', 'imagem': f'logos/{i}.png', 'ordem': i, 'ativo': True}
                for i in range(1, 25)
            ]
        }
        with open(MARCAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

init_marcas_file()

# ==================== MILESTONES ====================

def init_milestones_file():
    """Inicializa arquivo de milestones se não existir"""
    if not os.path.exists(MILESTONES_FILE):
        data_dir = os.path.dirname(MILESTONES_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {
            'milestones': [
                {'id': 1, 'titulo': 'Diagnóstico Preciso', 'imagem': 'img/milestone1.png', 'ordem': 1, 'ativo': True},
                {'id': 2, 'titulo': 'Reparo Especializado', 'imagem': 'img/milestone2.png', 'ordem': 2, 'ativo': True},
                {'id': 3, 'titulo': 'Atendimento Rápido', 'imagem': 'img/milestone3.png', 'ordem': 3, 'ativo': True}
            ]
        }
        with open(MILESTONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

init_milestones_file()

# ==================== SLIDES ====================

def init_slides_file():
    """Inicializa arquivo de slides se não existir"""
    if not os.path.exists(SLIDES_FILE):
        data_dir = os.path.dirname(SLIDES_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {
            'slides': [
                {
                    'id': 1,
                    'imagem': 'img/milestone1.png',
                    'ordem': 1,
                    'ativo': True
                },
                {
                    'id': 2,
                    'imagem': 'img/milestone2.png',
                    'ordem': 2,
                    'ativo': True
                },
                {
                    'id': 3,
                    'imagem': 'img/milestone3.png',
                    'ordem': 3,
                    'ativo': True
                }
            ]
        }
        with open(SLIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

init_slides_file()

@app.route('/')
def index():
    # Carregar slides
    if use_database():
        try:
            slides_db = Slide.query.filter_by(ativo=True).order_by(Slide.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar slides do banco: {e}")
            slides_db = []
        slides = []
        for s in slides_db:
            # Se tem imagem_id, usar rota do banco, senão usar caminho estático
            if s.imagem_id:
                imagem_url = f'/admin/slides/imagem/{s.imagem_id}'
            elif s.imagem:
                imagem_url = s.imagem
            else:
                imagem_url = 'img/placeholder.png'
            
            slides.append({
                'id': s.id,
                'imagem': imagem_url,
                'link': s.link,
                'link_target': s.link_target or '_self',
                'ordem': s.ordem,
                'ativo': s.ativo
            })
    else:
        init_slides_file()
        with open(SLIDES_FILE, 'r', encoding='utf-8') as f:
            slides_data = json.load(f)
        slides = [s for s in slides_data.get('slides', []) if s.get('ativo', True)]
        slides = sorted(slides, key=lambda x: x.get('ordem', 999))
    
    # Carregar dados do rodapé
    if use_database():
        try:
            footer_obj = Footer.query.first()
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
            footer_obj = None
        if footer_obj:
            footer_data = {
                'descricao': footer_obj.descricao,
                'redes_sociais': footer_obj.redes_sociais or {},
                'contato': footer_obj.contato or {},
                'copyright': footer_obj.copyright,
                'whatsapp_float': footer_obj.whatsapp_float
            }
        else:
            footer_data = None
    else:
        init_footer_file()
        with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
            footer_data = json.load(f)
    
    # Carregar marcas
    if use_database():
        try:
            marcas_db = Marca.query.filter_by(ativo=True).order_by(Marca.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar marcas do banco: {e}")
            marcas_db = []
        marcas = []
        for m in marcas_db:
            if m.imagem_id:
                imagem_url = f'/admin/marcas/imagem/{m.imagem_id}'
            elif m.imagem:
                imagem_url = m.imagem
            else:
                imagem_url = 'img/placeholder.png'
            
            marcas.append({
                'id': m.id,
                'nome': m.nome,
                'imagem': imagem_url,
                'ordem': m.ordem,
                'ativo': m.ativo
            })
    else:
        init_marcas_file()
        with open(MARCAS_FILE, 'r', encoding='utf-8') as f:
            marcas_data = json.load(f)
        marcas = [m for m in marcas_data.get('marcas', []) if m.get('ativo', True)]
        marcas = sorted(marcas, key=lambda x: x.get('ordem', 999))
    
    # Carregar milestones
    if use_database():
        try:
            milestones_db = Milestone.query.filter_by(ativo=True).order_by(Milestone.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar milestones do banco: {e}")
            milestones_db = []
        milestones = []
        for m in milestones_db:
            if m.imagem_id:
                imagem_url = f'/admin/milestones/imagem/{m.imagem_id}'
            elif m.imagem:
                imagem_url = m.imagem
            else:
                imagem_url = 'img/placeholder.png'
            
            milestones.append({
                'id': m.id,
                'titulo': m.titulo,
                'imagem': imagem_url,
                'ordem': m.ordem,
                'ativo': m.ativo
            })
    else:
        init_milestones_file()
        with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
            milestones_data = json.load(f)
        milestones = [m for m in milestones_data.get('milestones', []) if m.get('ativo', True)]
        milestones = sorted(milestones, key=lambda x: x.get('ordem', 999))
    
    # Carregar serviços
    if use_database():
        try:
            servicos_db = Servico.query.filter_by(ativo=True).order_by(Servico.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar serviços do banco: {e}")
            servicos_db = []
        servicos = []
        for s in servicos_db:
            # Se tem imagem_id, usar rota do banco, senão usar caminho estático
            if s.imagem_id:
                imagem_url = f'/admin/servicos/imagem/{s.imagem_id}'
            elif s.imagem:
                imagem_url = s.imagem
            else:
                imagem_url = 'img/placeholder.png'
            
            servicos.append({
                'id': s.id,
                'nome': s.nome,
                'descricao': s.descricao,
                'imagem': imagem_url,
                'ordem': s.ordem,
                'ativo': s.ativo
            })
    else:
        init_data_file()
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            services_data = json.load(f)
        servicos = [s for s in services_data.get('services', []) if s.get('ativo', True)]
        servicos = sorted(servicos, key=lambda x: x.get('ordem', 999))
    
    return render_template('index.html', slides=slides, footer=footer_data, marcas=marcas, milestones=milestones, servicos=servicos)

@app.route('/sobre')
def sobre():
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    return render_template('sobre.html', footer=footer_data)

@app.route('/servicos')
def servicos():
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    return render_template('servicos.html', footer=footer_data)

@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        servico = request.form.get('servico')
        mensagem = request.form.get('mensagem')
        
        # Salvar contato
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        novo_contato = {
            'id': len(data['contacts']) + 1,
            'nome': nome,
            'email': email,
            'telefone': telefone,
            'servico': servico,
            'mensagem': mensagem,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        data['contacts'].append(novo_contato)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Mensagem enviada com sucesso! Entraremos em contato em breve.', 'success')
        return redirect(url_for('contato'))
    
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    return render_template('contato.html', footer=footer_data)

@app.route('/rastrear', methods=['GET', 'POST'])
def rastrear():
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        
        if not codigo:
            flash('Por favor, informe o código da ordem de serviço.', 'error')
            return render_template('rastrear.html')
        
        # Buscar ordem pelo número
        ordem_encontrada = None
        cliente_encontrado = None
        
        try:
            with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Buscar em todos os clientes
            for cliente in data.get('clients', []):
                for ordem in cliente.get('ordens', []):
                    if str(ordem.get('numero_ordem', '')) == str(codigo):
                        ordem_encontrada = ordem
                        cliente_encontrado = cliente
                        break
                if ordem_encontrada:
                    break
        except Exception as e:
            flash('Erro ao buscar ordem de serviço.', 'error')
            return render_template('rastrear.html')
        
        if not ordem_encontrada:
            flash('Ordem de serviço não encontrada. Verifique o código informado.', 'error')
            return render_template('rastrear.html')
        
        # Buscar técnico se houver tecnico_id na ordem
        tecnico_encontrado = None
        tecnico_id = ordem_encontrada.get('tecnico_id')
        if tecnico_id:
            try:
                init_tecnicos_file()
                with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
                    tecnicos_data = json.load(f)
                
                tecnico_encontrado = next((t for t in tecnicos_data.get('tecnicos', []) if t.get('id') == tecnico_id), None)
            except Exception as e:
                print(f"Erro ao buscar técnico: {str(e)}")
        
        # Usar prazo estimado da ordem se existir, caso contrário calcular baseado no status
        prazo_estimado = ordem_encontrada.get('prazo_estimado') or calcular_prazo_estimado(ordem_encontrada.get('status'))
        
        return render_template('rastreamento_resultado.html', 
                             ordem=ordem_encontrada, 
                             cliente=cliente_encontrado,
                             tecnico=tecnico_encontrado,
                             prazo_estimado=prazo_estimado)
    
    return render_template('rastrear.html')

def calcular_prazo_estimado(status):
    """Calcula prazo estimado baseado no status"""
    prazos = {
        'pendente': '3-5 dias úteis',
        'em_andamento': '2-4 dias úteis',
        'aguardando_pecas': '5-7 dias úteis',
        'pronto': 'Pronto para retirada',
        'pago': 'Pronto para retirada',
        'entregue': 'Entregue',
        'cancelado': 'Cancelado'
    }
    return prazos.get(status, 'A definir')

@app.route('/api/servicos', methods=['GET'])
def get_servicos():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data['services'])

@app.route('/api/servicos', methods=['POST'])
def add_servico():
    servico_data = request.json
    servico_data['id'] = datetime.now().timestamp()
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['services'].append(servico_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'servico': servico_data})

# ==================== ADMIN ROUTES ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Verificar usuário padrão (backward compatibility)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_user_id'] = 0  # ID 0 para usuário padrão
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # Verificar usuários no banco de dados ou JSON
        try:
            if use_database():
                try:
                    user = AdminUser.query.filter_by(username=username, ativo=True).first()
                except Exception as db_err:
                    print(f"Erro ao buscar usuário no banco: {db_err}")
                    user = None
                if user and user.password == password:
                    session['admin_logged_in'] = True
                    session['admin_username'] = username
                    session['admin_user_id'] = user.id
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('admin_dashboard'))
            else:
                init_admin_users_file()
                with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                
                user = next((u for u in users_data.get('users', []) if u.get('username') == username and u.get('ativo', True)), None)
                
                if user and user.get('password') == password:
                    session['admin_logged_in'] = True
                    session['admin_username'] = username
                    session['admin_user_id'] = user.get('id')
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('admin_dashboard'))
            
            flash('Usuário ou senha incorretos!', 'error')
        except Exception as e:
            flash('Erro ao verificar credenciais. Tente novamente.', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_user_id', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('admin_login'))

# Rota de migração removida - banco de dados agora funciona diretamente com o Render
# Quando DATABASE_URL estiver configurado, o sistema usa o banco automaticamente

@app.route('/admin')
@login_required
def admin_dashboard():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_contatos = len(data['contacts'])
    total_servicos = len(data['services'])
    contatos_recentes = sorted(data['contacts'], key=lambda x: x['data'], reverse=True)[:5]
    
    stats = {
        'total_contatos': total_contatos,
        'total_servicos': total_servicos,
        'contatos_recentes': contatos_recentes
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/contatos')
@login_required
def admin_contatos():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    contatos = sorted(data['contacts'], key=lambda x: x['data'], reverse=True)
    return render_template('admin/contatos.html', contatos=contatos)

@app.route('/admin/contatos/<int:contato_id>/delete', methods=['POST'])
@login_required
def delete_contato(contato_id):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['contacts'] = [c for c in data['contacts'] if c.get('id') != contato_id]
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Contato excluído com sucesso!', 'success')
    return redirect(url_for('admin_contatos'))

@app.route('/admin/servicos')
@login_required
def admin_servicos():
    if use_database():
        try:
            servicos = Servico.query.order_by(Servico.ordem).all()
            # Converter para formato compatível com template
            servicos_list = []
            for s in servicos:
                    # Determinar URL da imagem
                    if s.imagem_id:
                        imagem_url = f'/admin/servicos/imagem/{s.imagem_id}'
                    elif s.imagem:
                        imagem_url = s.imagem
                    else:
                        imagem_url = ''
                    
                    servico_dict = {
                        'id': s.id,
                        'nome': s.nome,
                        'descricao': s.descricao,
                        'imagem': imagem_url,
                        'ordem': s.ordem,
                        'ativo': s.ativo,
                        'data': s.data.strftime('%Y-%m-%d %H:%M:%S') if s.data else ''
                    }
                    servicos_list.append(servico_dict)
            return render_template('admin/servicos.html', servicos=servicos_list)
        except Exception as e:
            print(f"Erro ao buscar serviços do banco: {e}")
            flash('Erro ao carregar serviços do banco. Usando arquivos JSON.', 'warning')
    
    # Fallback para JSON
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    servicos = sorted(data['services'], key=lambda x: x.get('ordem', 999))
    return render_template('admin/servicos.html', servicos=servicos)

@app.route('/admin/servicos/upload', methods=['POST'])
@login_required
def upload_servico_imagem():
    """Rota para upload de imagem de serviço - salva no banco de dados"""
    if 'imagem' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP'}), 400
    
    # Verificar tamanho do arquivo
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'Arquivo muito grande. Tamanho máximo: 5MB'}), 400
    
    # Ler dados do arquivo
    file_data = file.read()
    
    # Determinar tipo MIME
    ext = os.path.splitext(file.filename)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    imagem_tipo = mime_types.get(ext, 'image/jpeg')
    
    # Se usar banco de dados, salvar no banco
    if use_database():
        try:
            # Em rotas Flask, já estamos em um contexto de aplicação
            # Criar registro de imagem no banco
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'servico_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            # Usar db.session diretamente - Flask-SQLAlchemy gerencia o contexto
            db.session.add(imagem)
            db.session.commit()
            
            # Retornar ID da imagem para usar no serviço
            return jsonify({
                'success': True, 
                'path': f'/admin/servicos/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem no banco: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass
            # Retornar erro mais detalhado para debug
            error_msg = str(e)
            if 'Bind key' in error_msg:
                return jsonify({
                    'success': False, 
                    'error': 'Erro de configuração do banco. Verifique se DATABASE_URL está configurado corretamente no Render.'
                }), 500
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {error_msg}'}), 500
    
    # Se chegou aqui, o banco não está disponível
    # Em produção (Render), isso NÃO deve acontecer - retornar erro
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/servicos/imagem/<int:image_id>')
def servir_imagem_servico(image_id):
    """Rota para servir imagens do banco de dados"""
    if use_database():
        try:
            # Não usar app.app_context() aqui - já estamos em uma rota Flask
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime or 'image/jpeg',
                    headers={
                        'Content-Disposition': f'inline; filename={imagem.nome or "imagem.jpg"}',
                        'Cache-Control': 'public, max-age=31536000'  # Cache por 1 ano
                    }
                )
        except Exception as e:
            print(f"Erro ao buscar imagem: {e}")
            import traceback
            traceback.print_exc()
    
    # Fallback: retornar placeholder
    return redirect(url_for('static', filename='img/placeholder.png'))

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
                        'Cache-Control': 'public, max-age=31536000'  # Cache por 1 ano
                    }
                )
        except Exception as e:
            print(f"Erro ao buscar PDF: {e}")
            import traceback
            traceback.print_exc()
    
    # Fallback: retornar erro 404
    return "PDF não encontrado", 404

@app.route('/admin/servicos/add', methods=['GET', 'POST'])
@login_required
def add_servico_admin():
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        imagem = request.form.get('imagem', '').strip()
        ordem = request.form.get('ordem', '999')
        ativo = request.form.get('ativo') == 'on'
        
        # Extrair image_id se a imagem veio do banco (formato: /admin/servicos/imagem/123)
        imagem_id = None
        if imagem.startswith('/admin/servicos/imagem/'):
            try:
                imagem_id = int(imagem.split('/')[-1])
            except:
                pass
        
        if use_database():
            try:
                # Em rotas Flask, já estamos em um contexto de aplicação
                servico = Servico(
                    nome=nome,
                    descricao=descricao,
                    imagem=imagem,
                    imagem_id=imagem_id,
                    ordem=int(ordem) if ordem.isdigit() else 999,
                    ativo=ativo,
                    data=datetime.now()
                )
                db.session.add(servico)
                db.session.commit()
                flash('Serviço adicionado com sucesso!', 'success')
                return redirect(url_for('admin_servicos'))
            except Exception as e:
                print(f"Erro ao adicionar serviço no banco: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except:
                    pass
                flash(f'Erro ao adicionar serviço: {str(e)}', 'error')
                return redirect(url_for('add_servico_admin'))
        else:
            # Fallback para JSON
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            max_id = max([s.get('id', 0) for s in data['services']], default=0)
            
            novo_servico = {
                'id': max_id + 1,
                'nome': nome,
                'descricao': descricao,
                'imagem': imagem,
                'ordem': int(ordem) if ordem.isdigit() else 999,
                'ativo': ativo,
                'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            data['services'].append(novo_servico)
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            flash('Serviço adicionado com sucesso!', 'success')
            return redirect(url_for('admin_servicos'))
    
    return render_template('admin/add_servico.html')

@app.route('/admin/servicos/<int:servico_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_servico(servico_id):
    if use_database():
        try:
            servico = Servico.query.get(servico_id)
            if not servico:
                flash('Serviço não encontrado!', 'error')
                return redirect(url_for('admin_servicos'))
            
            if request.method == 'POST':
                servico.nome = request.form.get('nome')
                servico.descricao = request.form.get('descricao')
                imagem_nova = request.form.get('imagem', '').strip()
                if imagem_nova:
                    servico.imagem = imagem_nova
                    # Extrair image_id se veio do banco
                    if imagem_nova.startswith('/admin/servicos/imagem/'):
                        try:
                            servico.imagem_id = int(imagem_nova.split('/')[-1])
                        except:
                            pass
                    else:
                        servico.imagem_id = None
                servico.ordem = int(request.form.get('ordem', '999')) if request.form.get('ordem', '999').isdigit() else 999
                servico.ativo = request.form.get('ativo') == 'on'
                
                db.session.commit()
                flash('Serviço atualizado com sucesso!', 'success')
                return redirect(url_for('admin_servicos'))
            
            # Converter para formato compatível com template
            if servico.imagem_id:
                imagem_url = f'/admin/servicos/imagem/{servico.imagem_id}'
            elif servico.imagem:
                imagem_url = servico.imagem
            else:
                imagem_url = ''
            
            servico_dict = {
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao,
                'imagem': imagem_url,
                'ordem': servico.ordem,
                'ativo': servico.ativo,
                'data': servico.data.strftime('%Y-%m-%d %H:%M:%S') if servico.data else ''
            }
            return render_template('admin/edit_servico.html', servico=servico_dict)
        except Exception as e:
            print(f"Erro ao editar serviço no banco: {e}")
            flash('Erro ao editar serviço. Usando arquivos JSON.', 'warning')
    
    # Fallback para JSON
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    servico = next((s for s in data['services'] if s.get('id') == servico_id), None)
    if not servico:
        flash('Serviço não encontrado!', 'error')
        return redirect(url_for('admin_servicos'))
    
    if request.method == 'POST':
        servico['nome'] = request.form.get('nome')
        servico['descricao'] = request.form.get('descricao')
        imagem_nova = request.form.get('imagem', '').strip()
        if imagem_nova:
            servico['imagem'] = imagem_nova
        servico['ordem'] = int(request.form.get('ordem', '999')) if request.form.get('ordem', '999').isdigit() else 999
        servico['ativo'] = request.form.get('ativo') == 'on'
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Serviço atualizado com sucesso!', 'success')
        return redirect(url_for('admin_servicos'))
    
    return render_template('admin/edit_servico.html', servico=servico)

@app.route('/admin/servicos/<int:servico_id>/delete', methods=['POST'])
@login_required
def delete_servico(servico_id):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['services'] = [s for s in data['services'] if s.get('id') != servico_id]
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Serviço excluído com sucesso!', 'success')
    return redirect(url_for('admin_servicos'))

# ==================== CLIENT MANAGEMENT (ADMIN) ====================

def init_clients_file():
    if not os.path.exists(CLIENTS_FILE):
        data = {
            'clients': [],
            'orders': []
        }
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

init_clients_file()

@app.route('/admin/clientes')
@login_required
def admin_clientes():
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return render_template('admin/clientes_gerenciar.html', clientes=data['clients'])

@app.route('/admin/clientes/add', methods=['GET', 'POST'])
@login_required
def add_cliente_admin():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        cpf = request.form.get('cpf')
        endereco = request.form.get('endereco')
        username = request.form.get('username')
        password = request.form.get('password')
        
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verificar se username já existe
        if any(c.get('username') == username for c in data['clients']):
            flash('Este nome de usuário já está em uso!', 'error')
            return render_template('admin/add_cliente.html')
        
        novo_cliente = {
            'id': len(data['clients']) + 1,
            'nome': nome,
            'email': email,
            'telefone': telefone,
            'cpf': cpf,
            'endereco': endereco,
            'username': username,
            'password': password,  # Em produção, usar hash!
            'data_cadastro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ordens': []
        }
        
        data['clients'].append(novo_cliente)
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_clientes'))
    
    return render_template('admin/add_cliente.html')

@app.route('/admin/clientes/<int:cliente_id>')
@login_required
def view_cliente(cliente_id):
    """Visualiza detalhes de um cliente"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('admin_clientes'))
    
    return render_template('admin/view_cliente.html', cliente=cliente)

@app.route('/admin/clientes/<int:cliente_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cliente(cliente_id):
    """Edita um cliente existente"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('admin_clientes'))
    
    if request.method == 'POST':
        # Verificar se username foi alterado e se já existe
        novo_username = request.form.get('username')
        if novo_username != cliente.get('username'):
            if any(c.get('username') == novo_username and c.get('id') != cliente_id for c in data['clients']):
                flash('Este nome de usuário já está em uso!', 'error')
                return render_template('admin/edit_cliente.html', cliente=cliente)
        
        # Atualizar dados do cliente
        cliente['nome'] = request.form.get('nome')
        cliente['email'] = request.form.get('email')
        cliente['telefone'] = request.form.get('telefone')
        cliente['cpf'] = request.form.get('cpf')
        cliente['endereco'] = request.form.get('endereco')
        cliente['username'] = novo_username
        
        # Atualizar senha apenas se fornecida
        nova_senha = request.form.get('password')
        if nova_senha and nova_senha.strip():
            cliente['password'] = nova_senha  # Em produção, usar hash!
        
        # Atualizar na lista
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('admin_clientes'))
    
    return render_template('admin/edit_cliente.html', cliente=cliente)

@app.route('/admin/clientes/<int:cliente_id>/delete', methods=['POST'])
@login_required
def delete_cliente(cliente_id):
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['clients'] = [c for c in data['clients'] if c.get('id') != cliente_id]
    
    with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Cliente excluído com sucesso!', 'success')
    return redirect(url_for('admin_clientes'))

@app.route('/admin/financeiro')
@login_required
def admin_financeiro():
    """Página financeira com saldo e valores a receber"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Calcular saldo (ordens com status "pago")
    saldo = 0.00
    ordens_pagas = []
    
    # Calcular a receber (ordens com status "concluido")
    a_receber = 0.00
    ordens_concluidas = []
    
    # Processar todas as ordens de todos os clientes
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            total_ordem = ordem.get('total', 0.00)
            status = ordem.get('status', 'pendente')
            
            if status == 'pago':
                saldo += total_ordem
                ordens_pagas.append({
                    'numero_ordem': ordem.get('numero_ordem', ordem.get('id', 'N/A')),
                    'cliente_nome': cliente['nome'],
                    'total': total_ordem,
                    'data': ordem.get('data', ''),
                    'servico': ordem.get('servico', '')
                })
            elif status == 'concluido':
                a_receber += total_ordem
                ordens_concluidas.append({
                    'numero_ordem': ordem.get('numero_ordem', ordem.get('id', 'N/A')),
                    'cliente_nome': cliente['nome'],
                    'total': total_ordem,
                    'data': ordem.get('data', ''),
                    'servico': ordem.get('servico', '')
                })
    
    # Ordenar por data (mais recentes primeiro)
    ordens_pagas = sorted(ordens_pagas, key=lambda x: x.get('data', ''), reverse=True)
    ordens_concluidas = sorted(ordens_concluidas, key=lambda x: x.get('data', ''), reverse=True)
    
    return render_template('admin/financeiro.html', 
                         saldo=saldo, 
                         a_receber=a_receber,
                         ordens_pagas=ordens_pagas,
                         ordens_concluidas=ordens_concluidas)

@app.route('/admin/ordens')
@login_required
def admin_ordens():
    if use_database():
        try:
            # Buscar todas as ordens do banco
            ordens_db = OrdemServico.query.order_by(OrdemServico.data.desc()).all()
            todas_ordens = []
            for ordem in ordens_db:
                cliente = Cliente.query.get(ordem.cliente_id)
                ordem_dict = {
                    'id': ordem.id,
                    'numero_ordem': ordem.numero_ordem,
                    'cliente_id': ordem.cliente_id,
                    'cliente_nome': cliente.nome if cliente else 'Cliente não encontrado',
                    'servico': ordem.servico,
                    'marca': ordem.marca,
                    'modelo': ordem.modelo,
                    'status': ordem.status,
                    'total': float(ordem.total) if ordem.total else 0.00,
                    'data': ordem.data.strftime('%Y-%m-%d %H:%M:%S') if ordem.data else '',
                    'pdf_filename': ordem.pdf_filename if ordem.pdf_filename else None,
                    'pdf_id': ordem.pdf_id
                }
                todas_ordens.append(ordem_dict)
            return render_template('admin/ordens.html', ordens=todas_ordens)
        except Exception as e:
            print(f"Erro ao buscar ordens do banco: {e}")
            import traceback
            traceback.print_exc()
    
    # Fallback para JSON
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Coletar todas as ordens de todos os clientes
    todas_ordens = []
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            ordem_completa = ordem.copy()
            ordem_completa['cliente_nome'] = cliente['nome']
            ordem_completa['cliente_id'] = cliente['id']
            # Garantir que pdf_filename seja string, não dict
            if isinstance(ordem_completa.get('pdf_filename'), dict):
                ordem_completa['pdf_filename'] = ordem_completa['pdf_filename'].get('pdf_filename', '')
            todas_ordens.append(ordem_completa)
    
    # Ordenar por data (mais recente primeiro)
    todas_ordens = sorted(todas_ordens, key=lambda x: x.get('data', ''), reverse=True)
    
    return render_template('admin/ordens.html', ordens=todas_ordens)

@app.route('/admin/ordens/add', methods=['GET', 'POST'])
@login_required
def add_ordem_servico():
    if request.method == 'POST':
        cliente_id = int(request.form.get('cliente_id'))
        servico = request.form.get('servico')
        tipo_aparelho = request.form.get('tipo_aparelho')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        numero_serie = request.form.get('numero_serie')
        defeitos_cliente = request.form.get('defeitos_cliente')
        diagnostico_tecnico = request.form.get('diagnostico_tecnico')
        custo_mao_obra = request.form.get('custo_mao_obra', '0.00')
        status = request.form.get('status', 'pendente')
        tecnico_id = request.form.get('tecnico_id')
        prazo_estimado = request.form.get('prazo_estimado', '').strip()
        
        # Coletar peças
        pecas = []
        total_pecas = 0.00
        for i in range(10):
            nome_peca = request.form.get(f'peca_nome_{i}', '').strip()
            custo_peca = request.form.get(f'peca_custo_{i}', '0.00')
            
            if nome_peca:  # Só adicionar se tiver nome
                try:
                    custo_valor = float(custo_peca) if custo_peca else 0.00
                    total_pecas += custo_valor
                    pecas.append({
                        'nome': nome_peca,
                        'custo': custo_valor
                    })
                except:
                    pass
        
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('add_ordem_servico'))
        
        # Calcular total
        try:
            custo_mao_obra_valor = float(custo_mao_obra) if custo_mao_obra else 0.00
            subtotal = total_pecas + custo_mao_obra_valor
        except:
            subtotal = 0.00
        
        # Aplicar cupom de desconto se selecionado
        cupom_id = request.form.get('cupom_id')
        desconto_percentual = 0.00
        valor_desconto = 0.00
        cupom_usado = None
        
        if cupom_id and cupom_id != '':
            cupom_id = int(cupom_id)
            # Buscar cupom
            with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
                fidelidade_data = json.load(f)
            
            cupom = next((c for c in fidelidade_data['cupons'] if c.get('id') == cupom_id and c.get('cliente_id') == cliente_id and not c.get('usado', False)), None)
            if cupom:
                desconto_percentual = cupom['desconto_percentual']
                valor_desconto = subtotal * (desconto_percentual / 100)
                cupom_usado = cupom
                # Obter o ID da ordem que será criada (antes de adicionar à lista)
                nova_ordem_id = len(cliente.get('ordens', [])) + 1
                cupom['usado'] = True
                cupom['ordem_id'] = nova_ordem_id
                cupom['data_uso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Salvar atualização do cupom
                with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(fidelidade_data, f, ensure_ascii=False, indent=2)
        
        total = subtotal - valor_desconto
        
        # Gerar número único da ordem
        numero_ordem = get_proximo_numero_ordem()
        
        # ID da ordem (usado para vincular com cupom)
        nova_ordem_id = len(cliente.get('ordens', [])) + 1
        
        nova_ordem = {
            'id': nova_ordem_id,
            'numero_ordem': numero_ordem,
            'servico': servico,
            'tipo_aparelho': tipo_aparelho,
            'marca': marca,
            'modelo': modelo,
            'numero_serie': numero_serie,
            'defeitos_cliente': defeitos_cliente,
            'diagnostico_tecnico': diagnostico_tecnico,
            'pecas': pecas,
            'custo_pecas': total_pecas,
            'custo_mao_obra': float(custo_mao_obra) if custo_mao_obra else 0.00,
            'subtotal': subtotal,
            'desconto_percentual': desconto_percentual,
            'valor_desconto': valor_desconto,
            'cupom_id': cupom_id if cupom_usado else None,
            'tecnico_id': int(tecnico_id) if tecnico_id and tecnico_id != '' else None,
            'total': total,
            'status': status,
            'prazo_estimado': prazo_estimado if prazo_estimado else None,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if 'ordens' not in cliente:
            cliente['ordens'] = []
        
        cliente['ordens'].append(nova_ordem)
        
        # Atualizar cliente na lista
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Gerar PDF da ordem
        pdf_result = gerar_pdf_ordem(cliente, nova_ordem)
        if isinstance(pdf_result, dict):
            # Salvar apenas o nome do arquivo, não o dicionário inteiro
            nova_ordem['pdf_filename'] = pdf_result.get('pdf_filename', '')
            nova_ordem['pdf_id'] = pdf_result.get('pdf_id')
        else:
            # Fallback para compatibilidade
            nova_ordem['pdf_filename'] = str(pdf_result) if pdf_result else ''
        
        # Atualizar ordem com nome do PDF
        for i, o in enumerate(cliente['ordens']):
            if o.get('id') == nova_ordem['id']:
                cliente['ordens'][i] = nova_ordem
                break
        
        # Atualizar cliente na lista novamente
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Ordem de serviço emitida com sucesso!', 'success')
        return redirect(url_for('admin_ordens'))
    
    init_tecnicos_file()
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        services_data = json.load(f)
    
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
        tecnicos_data = json.load(f)
    
    # Buscar cupons disponíveis para cada cliente
    cupons_por_cliente = {}
    if os.path.exists(FIDELIDADE_FILE):
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            fidelidade_data = json.load(f)
        
        for cupom in fidelidade_data['cupons']:
            if not cupom.get('usado', False):
                cliente_id = cupom.get('cliente_id')
                if cliente_id not in cupons_por_cliente:
                    cupons_por_cliente[cliente_id] = []
                cupons_por_cliente[cliente_id].append(cupom)
    
    return render_template('admin/add_ordem.html', 
                         clientes=clients_data['clients'], 
                         servicos=services_data['services'],
                         tecnicos=tecnicos_data.get('tecnicos', []),
                         cupons_por_cliente=cupons_por_cliente)

@app.route('/admin/clientes/<int:cliente_id>/ordens/<int:ordem_id>')
@login_required
def view_ordem_detalhes(cliente_id, ordem_id):
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    if not cliente:
        return jsonify({'error': 'Cliente não encontrado'}), 404
    
    ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == ordem_id), None)
    if not ordem:
        return jsonify({'error': 'Ordem não encontrada'}), 404
    
    ordem_completa = ordem.copy()
    ordem_completa['cliente_nome'] = cliente['nome']
    ordem_completa['cliente_id'] = cliente['id']
    
    return jsonify(ordem_completa)

@app.route('/admin/clientes/<int:cliente_id>/ordens/<int:ordem_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ordem_servico(cliente_id, ordem_id):
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('admin_ordens'))
    
    ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == ordem_id), None)
    if not ordem:
        flash('Ordem não encontrada!', 'error')
        return redirect(url_for('admin_ordens'))
    
    if request.method == 'POST':
        servico = request.form.get('servico')
        tipo_aparelho = request.form.get('tipo_aparelho')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        numero_serie = request.form.get('numero_serie')
        defeitos_cliente = request.form.get('defeitos_cliente')
        diagnostico_tecnico = request.form.get('diagnostico_tecnico')
        custo_mao_obra = request.form.get('custo_mao_obra', '0.00')
        status = request.form.get('status', 'pendente')
        prazo_estimado = request.form.get('prazo_estimado', '').strip()
        tecnico_id = request.form.get('tecnico_id')
        
        # Coletar peças
        pecas = []
        total_pecas = 0.00
        for i in range(10):
            nome_peca = request.form.get(f'peca_nome_{i}', '').strip()
            custo_peca = request.form.get(f'peca_custo_{i}', '0.00')
            
            if nome_peca:  # Só adicionar se tiver nome
                try:
                    custo_valor = float(custo_peca) if custo_peca else 0.00
                    total_pecas += custo_valor
                    pecas.append({
                        'nome': nome_peca,
                        'custo': custo_valor
                    })
                except:
                    pass
        
        # Calcular total
        try:
            custo_mao_obra_valor = float(custo_mao_obra) if custo_mao_obra else 0.00
            total = total_pecas + custo_mao_obra_valor
        except:
            total = 0.00
        
        # Atualizar ordem (manter número da ordem original e campos de desconto)
        ordem_atualizada = {
            'id': ordem_id,
            'numero_ordem': ordem.get('numero_ordem', get_proximo_numero_ordem()),
            'servico': servico,
            'tipo_aparelho': tipo_aparelho,
            'marca': marca,
            'modelo': modelo,
            'numero_serie': numero_serie,
            'defeitos_cliente': defeitos_cliente,
            'diagnostico_tecnico': diagnostico_tecnico,
            'pecas': pecas,
            'custo_pecas': total_pecas,
            'custo_mao_obra': float(custo_mao_obra) if custo_mao_obra else 0.00,
            'subtotal': ordem.get('subtotal', total),
            'desconto_percentual': ordem.get('desconto_percentual', 0.00),
            'valor_desconto': ordem.get('valor_desconto', 0.00),
            'cupom_id': ordem.get('cupom_id'),
            'total': total,
            'status': status,
            'prazo_estimado': prazo_estimado if prazo_estimado else ordem.get('prazo_estimado'),
            'tecnico_id': int(tecnico_id) if tecnico_id and tecnico_id != '' else ordem.get('tecnico_id'),
            'data': ordem.get('data', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'pdf_filename': ordem.get('pdf_filename')
        }
        
        # Atualizar ordem no cliente
        for i, o in enumerate(cliente['ordens']):
            if o.get('id') == ordem_id:
                cliente['ordens'][i] = ordem_atualizada
                break
        
        # Atualizar cliente na lista
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Regenerar PDF da ordem atualizada
        # Gerar novo PDF
        pdf_result = gerar_pdf_ordem(cliente, ordem_atualizada)
        if isinstance(pdf_result, dict):
            # Salvar apenas o nome do arquivo, não o dicionário inteiro
            ordem_atualizada['pdf_filename'] = pdf_result.get('pdf_filename', '')
            ordem_atualizada['pdf_id'] = pdf_result.get('pdf_id')
        else:
            # Fallback para compatibilidade
            ordem_atualizada['pdf_filename'] = str(pdf_result) if pdf_result else ''
        
        # Atualizar ordem com novo PDF
        for i, o in enumerate(cliente['ordens']):
            if o.get('id') == ordem_id:
                cliente['ordens'][i] = ordem_atualizada
                break
        
        # Atualizar cliente na lista novamente
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Ordem de serviço atualizada com sucesso!', 'success')
        return redirect(url_for('admin_ordens'))
    
    # GET - Exibir formulário de edição
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        services_data = json.load(f)
    
    init_tecnicos_file()
    with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
        tecnicos_data = json.load(f)
    
    return render_template('admin/edit_ordem.html', 
                         cliente=cliente, 
                         ordem=ordem, 
                         servicos=services_data['services'],
                         tecnicos=tecnicos_data.get('tecnicos', []))

@app.route('/admin/clientes/<int:cliente_id>/ordens/<int:ordem_id>/delete', methods=['POST'])
@login_required
def delete_ordem_servico(cliente_id, ordem_id):
    if use_database():
        try:
            # Buscar ordem no banco
            ordem = OrdemServico.query.filter_by(id=ordem_id, cliente_id=cliente_id).first()
            if not ordem:
                flash('Ordem de serviço não encontrada!', 'error')
                return redirect(url_for('admin_ordens'))
            
            # Se a ordem tiver cupom aplicado, reverter o cupom para disponível
            if ordem.cupom_id:
                try:
                    cupom = Cupom.query.get(ordem.cupom_id)
                    if cupom and cupom.ordem_id == ordem_id:
                        cupom.usado = False
                        cupom.ordem_id = None
                        cupom.data_uso = None
                        db.session.commit()
                except Exception as e:
                    print(f"Erro ao reverter cupom: {e}")
                    db.session.rollback()
            
            # Deletar PDF do banco se existir
            if ordem.pdf_id:
                try:
                    pdf_doc = PDFDocument.query.get(ordem.pdf_id)
                    if pdf_doc:
                        db.session.delete(pdf_doc)
                except Exception as e:
                    print(f"Erro ao deletar PDF: {e}")
            
            # Deletar ordem
            db.session.delete(ordem)
            db.session.commit()
            
            flash('Ordem de serviço excluída com sucesso!', 'success')
            return redirect(url_for('admin_ordens'))
        except Exception as e:
            print(f"Erro ao excluir ordem do banco: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass
            flash('Erro ao excluir ordem. Tente novamente.', 'error')
            return redirect(url_for('admin_ordens'))
    
    # Fallback para JSON (apenas se banco não estiver disponível)
    try:
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('admin_ordens'))
        
        # Buscar ordem antes de excluir
        ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == ordem_id), None)
        
        # Se a ordem tiver cupom aplicado, reverter o cupom para disponível
        if ordem and ordem.get('cupom_id'):
            cupom_id_ordem_excluida = ordem['cupom_id']
            if os.path.exists(FIDELIDADE_FILE):
                with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
                    fidelidade_data = json.load(f)
                
                # Buscar cupom e reverter apenas se estiver vinculado à ordem que está sendo excluída
                cupom = next((c for c in fidelidade_data['cupons'] if c.get('id') == cupom_id_ordem_excluida), None)
                if cupom:
                    # Verificar se o cupom está realmente vinculado à ordem que está sendo excluída
                    if cupom.get('ordem_id') == ordem_id:
                        cupom['usado'] = False
                        cupom['ordem_id'] = None
                        cupom['data_uso'] = None
                        
                        # Salvar alterações do cupom
                        with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
                            json.dump(fidelidade_data, f, ensure_ascii=False, indent=2)
        
        # Remover ordem
        cliente['ordens'] = [o for o in cliente.get('ordens', []) if o.get('id') != ordem_id]
        
        # Atualizar cliente na lista
        for i, c in enumerate(data['clients']):
            if c.get('id') == cliente_id:
                data['clients'][i] = cliente
                break
        
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Ordem de serviço excluída com sucesso!', 'success')
        return redirect(url_for('admin_ordens'))
    except Exception as e:
        print(f"Erro ao excluir ordem (JSON): {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao excluir ordem. Tente novamente.', 'error')
        return redirect(url_for('admin_ordens'))

# ==================== PDF GENERATION ====================

def salvar_pdf_no_banco(pdf_data, nome, tipo_documento, referencia_id):
    """Salva PDF no banco de dados e retorna o ID"""
    if use_database():
        try:
            pdf_doc = PDFDocument(
                nome=nome,
                dados=pdf_data,
                tamanho=len(pdf_data),
                tipo_documento=tipo_documento,
                referencia_id=referencia_id
            )
            db.session.add(pdf_doc)
            db.session.commit()
            return pdf_doc.id
        except Exception as e:
            print(f"Erro ao salvar PDF no banco: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass
    return None

def gerar_pdf_ordem(cliente, ordem):
    """Gera PDF da ordem de serviço e salva no banco de dados"""
    # Nome do arquivo PDF
    pdf_filename = f"ordem_{cliente['id']}_{ordem['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Criar buffer em memória para o PDF
    buffer = BytesIO()
    
    # Criar documento PDF em memória
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Logo e Título
    logo_path = os.path.join('static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        try:
            # Proporção da logo original: 838x322 = 2.60:1
            # Definindo largura e calculando altura para manter proporção
            logo_width = 4.5*cm
            logo_height = logo_width / 2.60  # Mantém proporção original
            logo = Image(logo_path, width=logo_width, height=logo_height)
            # Centralizar logo
            logo_table = Table([[logo]], colWidths=[17*cm])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(logo_table)
            story.append(Spacer(1, 0.2*cm))
        except:
            pass
    
    # Título principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#215f97'),
        spaceAfter=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("ORDEM DE SERVIÇO", title_style))
    
    # Subtítulo
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        spaceAfter=12,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Clínica do Reparo - Assistência Técnica Especializada", subtitle_style))
    story.append(Spacer(1, 0.4*cm))
    
    # Informações da Ordem (Nº da OS, Data, Status)
    numero_ordem = ordem.get('numero_ordem', ordem.get('id', 100000))
    try:
        # Formatar sem zeros à esquerda e sem #
        numero_formatado = str(int(numero_ordem))
    except:
        # Se não conseguir converter, usar o valor original sem #
        numero_formatado = str(numero_ordem).replace('#', '').strip()
    
    # Formatar data
    try:
        data_obj = datetime.strptime(ordem['data'], '%Y-%m-%d %H:%M:%S')
        data_formatada = data_obj.strftime('%d/%m/%Y')
    except:
        data_formatada = ordem['data']
    
    status_text = ordem['status'].upper().replace('_', ' ')
    ordem_info_data = [
        ['Nº da OS:', numero_formatado, 'Data:', data_formatada, 'Status:', status_text]
    ]
    ordem_info_table = Table(ordem_info_data, colWidths=[2.8*cm, 3.2*cm, 2.5*cm, 3.2*cm, 2.5*cm, 3.2*cm])
    ordem_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTNAME', (4, 0), (4, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(ordem_info_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Dados do Cliente
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#215f97'),
        spaceAfter=8,
        spaceBefore=0,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("DADOS DO CLIENTE", heading_style))
    
    # Formatar telefone
    telefone = cliente.get('telefone', '')
    if telefone and len(telefone) >= 10:
        telefone_formatado = f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}" if len(telefone) == 11 else f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}" if len(telefone) == 10 else telefone
    else:
        telefone_formatado = telefone
    
    # Formatar CPF
    cpf = cliente.get('cpf', '')
    if cpf and len(cpf) == 11:
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    else:
        cpf_formatado = cpf
    
    cliente_data = [
        ['Nome:', cliente['nome']],
        ['E-mail:', cliente.get('email', '')],
        ['Telefone:', telefone_formatado],
        ['CPF:', cpf_formatado],
        ['Endereço:', cliente.get('endereco', '')],
    ]
    cliente_table = Table(cliente_data, colWidths=[4.5*cm, 12.5*cm])
    cliente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(cliente_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Dados do Equipamento
    story.append(Paragraph("DADOS DO EQUIPAMENTO", heading_style))
    
    # Montar aparelho completo
    aparelho_completo = f"{ordem.get('marca', '')} {ordem.get('modelo', '')}".strip()
    
    aparelho_data = [
        ['Tipo de Serviço:', ordem.get('servico', '')],
        ['Aparelho:', aparelho_completo],
        ['Número de Série:', ordem.get('numero_serie', 'N/A')],
        ['Defeito Informado:', ordem.get('defeitos_cliente', '')],
        ['Diagnóstico Técnico:', ordem.get('diagnostico_tecnico', '')],
    ]
    aparelho_table = Table(aparelho_data, colWidths=[4.5*cm, 12.5*cm])
    aparelho_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(aparelho_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Custos
    story.append(Paragraph("CUSTOS", heading_style))
    
    # Tabela de custos
    custos_header = [['Descrição', 'Valor (R$)']]
    
    # Adicionar peças se existirem
    custos_rows = []
    if ordem.get('pecas') and len(ordem['pecas']) > 0:
        for peca in ordem['pecas']:
            custos_rows.append([peca['nome'], f"{peca['custo']:.2f}".replace('.', ',')])
        custos_rows.append(['Subtotal Peças', f"{ordem.get('custo_pecas', 0):.2f}".replace('.', ',')])
    
    custos_rows.append(['Mão de Obra', f"{ordem.get('custo_mao_obra', 0):.2f}".replace('.', ',')])
    
    # Adicionar desconto se houver
    subtotal = ordem.get('custo_pecas', 0) + ordem.get('custo_mao_obra', 0)
    if ordem.get('desconto_percentual', 0) > 0:
        custos_rows.append(['Subtotal', f"{subtotal:.2f}".replace('.', ',')])
        custos_rows.append([f'Desconto ({ordem.get("desconto_percentual", 0):.2f}%)', f"-{ordem.get('valor_desconto', 0):.2f}".replace('.', ',')])
    
    custos_rows.append(['TOTAL', f"{ordem.get('total', 0):.2f}".replace('.', ',')])
    
    custos_data = custos_header + custos_rows
    custos_table = Table(custos_data, colWidths=[13*cm, 4*cm])
    custos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#215f97')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#215f97')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#215f97')),
    ]))
    story.append(custos_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Condições Gerais de Serviço
    story.append(Paragraph("CONDIÇÕES GERAIS DE SERVIÇO", heading_style))
    
    condicoes_texto = """1. O prazo de execução do serviço será informado ao cliente no momento da avaliação.
2. O cliente será notificado quando o serviço estiver concluído.
3. A garantia do serviço é de 30 dias para peças e mão de obra.
4. Em caso de não retirada do aparelho em até 30 dias após a conclusão, serão cobradas taxas de armazenamento.
5. Peças substituídas tornam-se propriedade da oficina, exceto se solicitado pelo cliente no ato do orçamento.
6. O cliente deve comparecer pessoalmente para retirada do aparelho ou autorizar por escrito outra pessoa.
7. A oficina não se responsabiliza por dados perdidos durante o reparo.
8. Em caso de reparo não autorizado, será cobrado apenas o valor da avaliação."""
    
    condicoes_style = ParagraphStyle(
        'Condicoes',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        spaceAfter=12,
        alignment=TA_LEFT,
        leftIndent=0,
        rightIndent=0
    )
    story.append(Paragraph(condicoes_texto, condicoes_style))
    story.append(Spacer(1, 1*cm))
    
    # Assinaturas
    story.append(Paragraph("ASSINATURAS", heading_style))
    story.append(Spacer(1, 0.3*cm))
    
    assinaturas_data = [
        ['Assinatura do Cliente:', '___________________________', 'Assinatura do Técnico:', '___________________________'],
        ['Data da Retirada:', '__ / __ / __', '', ''],
    ]
    assinaturas_table = Table(assinaturas_data, colWidths=[4*cm, 6*cm, 4*cm, 6*cm])
    assinaturas_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(assinaturas_table)
    
    # Construir PDF
    doc.build(story)
    
    # Obter dados do PDF do buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Salvar no banco de dados
    if use_database():
        pdf_id = salvar_pdf_no_banco(
            pdf_data=pdf_data,
            nome=pdf_filename,
            tipo_documento='ordem_servico',
            referencia_id=ordem.get('id')
        )
        if pdf_id:
            return {'pdf_id': pdf_id, 'pdf_filename': pdf_filename, 'url': f'/media/pdf/{pdf_id}'}
    
    # Fallback: salvar em arquivo (apenas para desenvolvimento local sem banco)
    pdf_path = os.path.join('static', 'pdfs', pdf_filename)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, 'wb') as f:
        f.write(pdf_data)
    
    return {'pdf_filename': pdf_filename, 'url': f'/static/pdfs/{pdf_filename}'}

@app.route('/admin/download-pdf/<path:filename>')
@login_required
def download_pdf(filename):
    """Download do PDF da ordem (admin)"""
    # Se o filename for um dicionário (erro de serialização), tentar extrair o pdf_id
    if filename.startswith("{'pdf_id'") or filename.startswith('{"pdf_id"'):
        try:
            import ast
            # Tentar parsear como dict Python
            pdf_info = ast.literal_eval(filename)
            if 'pdf_id' in pdf_info:
                return redirect(f"/media/pdf/{pdf_info['pdf_id']}")
            elif 'url' in pdf_info:
                return redirect(pdf_info['url'])
        except:
            pass
    
    # Se o filename contém /media/pdf/, redirecionar diretamente
    if '/media/pdf/' in filename:
        pdf_id = filename.split('/media/pdf/')[-1].split("'")[0].split('}')[0]
        try:
            return redirect(f"/media/pdf/{int(pdf_id)}")
        except:
            pass
    
    # Tentar buscar no banco de dados primeiro
    if use_database():
        try:
            # Tentar encontrar ordem pelo pdf_filename
            ordem = OrdemServico.query.filter_by(pdf_filename=filename).first()
            if ordem and ordem.pdf_id:
                pdf_doc = PDFDocument.query.get(ordem.pdf_id)
                if pdf_doc and pdf_doc.dados:
                    return Response(
                        pdf_doc.dados,
                        mimetype='application/pdf',
                        headers={
                            'Content-Disposition': f'attachment; filename={pdf_doc.nome}'
                        }
                    )
        except Exception as e:
            print(f"Erro ao buscar PDF no banco: {e}")
    
    # Fallback: tentar arquivo estático (apenas para desenvolvimento local)
    pdf_path = os.path.join('static', 'pdfs', filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    
    flash('Arquivo PDF não encontrado!', 'error')
    return redirect(url_for('admin_ordens'))

# ==================== CLIENT AREA ====================

def client_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'client_logged_in' not in session:
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/cliente/login', methods=['GET', 'POST'])
def client_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cliente = next((c for c in data['clients'] if c.get('username') == username and c.get('password') == password), None)
        
        if cliente:
            session['client_logged_in'] = True
            session['client_id'] = cliente['id']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('client_dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('client/login.html')

@app.route('/cliente/logout')
def client_logout():
    session.pop('client_logged_in', None)
    session.pop('client_id', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('client_login'))

@app.route('/cliente')
@client_login_required
def client_dashboard():
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente_id = session.get('client_id')
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('client_logout'))
    
    ordens = cliente.get('ordens', [])
    ordens_ordenadas = sorted(ordens, key=lambda x: x.get('data', ''), reverse=True)
    
    # Buscar comprovantes do cliente
    comprovantes = []
    if os.path.exists(COMPROVANTES_FILE):
        with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
            comprovantes_data = json.load(f)
        
        comprovantes = [c for c in comprovantes_data['comprovantes'] if c.get('cliente_id') == cliente_id]
        comprovantes = sorted(comprovantes, key=lambda x: x.get('data', ''), reverse=True)
    
    # Buscar cupons de desconto do cliente
    cupons = []
    if os.path.exists(FIDELIDADE_FILE):
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            fidelidade_data = json.load(f)
        
        cupons = [c for c in fidelidade_data['cupons'] if c.get('cliente_id') == cliente_id]
        cupons = sorted(cupons, key=lambda x: x.get('data_emissao', ''), reverse=True)
    
    return render_template('client/dashboard.html', cliente=cliente, ordens=ordens_ordenadas, comprovantes=comprovantes, cupons=cupons)

@app.route('/cliente/download-pdf/<path:filename>')
@client_login_required
def client_download_pdf(filename):
    """Download do PDF da ordem (cliente) - com verificação de segurança"""
    cliente_id = session.get('client_id')
    
    # Verificar se o PDF pertence ao cliente logado
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('client_dashboard'))
    
    # Verificar se a ordem pertence ao cliente
    ordem_encontrada = False
    for ordem in cliente.get('ordens', []):
        if ordem.get('pdf_filename') == filename:
            ordem_encontrada = True
            break
    
    if not ordem_encontrada:
        flash('Você não tem permissão para baixar este arquivo!', 'error')
        return redirect(url_for('client_dashboard'))
    
    # Tentar buscar no banco de dados primeiro
    if use_database():
        try:
            # Buscar ordem pelo pdf_filename e cliente_id
            ordem = OrdemServico.query.filter_by(pdf_filename=filename, cliente_id=cliente_id).first()
            if ordem and ordem.pdf_id:
                pdf_doc = PDFDocument.query.get(ordem.pdf_id)
                if pdf_doc and pdf_doc.dados:
                    return Response(
                        pdf_doc.dados,
                        mimetype='application/pdf',
                        headers={
                            'Content-Disposition': f'attachment; filename={pdf_doc.nome}'
                        }
                    )
        except Exception as e:
            print(f"Erro ao buscar PDF no banco: {e}")
    
    # Fallback: tentar arquivo estático (apenas para desenvolvimento local)
    pdf_path = os.path.join('static', 'pdfs', filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    
    flash('Arquivo PDF não encontrado!', 'error')
    return redirect(url_for('client_dashboard'))

@app.route('/cliente/comprovantes/download/<path:filename>')
@client_login_required
def client_download_comprovante_pdf(filename):
    """Download do PDF do comprovante (cliente) - com verificação de segurança"""
    cliente_id = session.get('client_id')
    
    # Verificar se o comprovante pertence ao cliente logado
    if not os.path.exists(COMPROVANTES_FILE):
        flash('Comprovante não encontrado!', 'error')
        return redirect(url_for('client_dashboard'))
    
    with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
        comprovantes_data = json.load(f)
    
    # Tentar buscar no banco de dados primeiro
    if use_database():
        try:
            comprovante = Comprovante.query.filter_by(pdf_filename=filename, cliente_id=cliente_id).first()
            if comprovante and comprovante.pdf_id:
                pdf_doc = PDFDocument.query.get(comprovante.pdf_id)
                if pdf_doc and pdf_doc.dados:
                    return Response(
                        pdf_doc.dados,
                        mimetype='application/pdf',
                        headers={
                            'Content-Disposition': f'attachment; filename={pdf_doc.nome}'
                        }
                    )
        except Exception as e:
            print(f"Erro ao buscar PDF no banco: {e}")
    
    # Fallback para JSON
    comprovante = next((c for c in comprovantes_data['comprovantes'] if c.get('pdf_filename') == filename and c.get('cliente_id') == cliente_id), None)
    
    if not comprovante:
        flash('Você não tem permissão para baixar este arquivo!', 'error')
        return redirect(url_for('client_dashboard'))
    
    # Tentar arquivo estático (apenas para desenvolvimento local)
    pdf_path = os.path.join('static', 'pdfs', filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    
    flash('Arquivo PDF não encontrado!', 'error')
    return redirect(url_for('client_dashboard'))

# ==================== COMPROVANTES ====================

def init_comprovantes_file():
    """Inicializa arquivo de comprovantes se não existir"""
    if not os.path.exists(COMPROVANTES_FILE):
        data_dir = os.path.dirname(COMPROVANTES_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        with open(COMPROVANTES_FILE, 'w', encoding='utf-8') as f:
            json.dump({'comprovantes': []}, f, ensure_ascii=False, indent=2)

init_comprovantes_file()

@app.route('/admin/comprovantes')
@login_required
def admin_comprovantes():
    """Lista todos os comprovantes emitidos"""
    with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    comprovantes = sorted(data['comprovantes'], key=lambda x: x.get('data', ''), reverse=True)
    return render_template('admin/comprovantes.html', comprovantes=comprovantes)

@app.route('/admin/comprovantes/add', methods=['GET', 'POST'])
@login_required
def emitir_comprovante():
    """Emitir novo comprovante de pagamento"""
    if request.method == 'POST':
        cliente_id = int(request.form.get('cliente_id'))
        ordem_id = int(request.form.get('ordem_id'))
        valor_pago = float(request.form.get('valor_pago'))
        forma_pagamento = request.form.get('forma_pagamento')
        parcelas = request.form.get('parcelas', '1')
        
        # Buscar cliente e ordem
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        cliente = next((c for c in clients_data['clients'] if c.get('id') == cliente_id), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('emitir_comprovante'))
        
        ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == ordem_id), None)
        if not ordem:
            flash('Ordem de serviço não encontrada!', 'error')
            return redirect(url_for('emitir_comprovante'))
        
        # Criar comprovante
        with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
            comprovantes_data = json.load(f)
        
        novo_comprovante = {
            'id': len(comprovantes_data['comprovantes']) + 1,
            'cliente_id': cliente_id,
            'cliente_nome': cliente['nome'],
            'ordem_id': ordem_id,
            'numero_ordem': ordem.get('numero_ordem', ordem_id),
            'valor_total': ordem.get('total', 0.00),
            'valor_pago': valor_pago,
            'forma_pagamento': forma_pagamento,
            'parcelas': int(parcelas) if forma_pagamento == 'cartao_credito' else 1,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pdf_filename': None
        }
        
        # Gerar PDF do comprovante
        pdf_result = gerar_pdf_comprovante(cliente, ordem, novo_comprovante)
        if isinstance(pdf_result, dict):
            novo_comprovante['pdf_filename'] = pdf_result.get('pdf_filename', '')
            novo_comprovante['pdf_id'] = pdf_result.get('pdf_id')
        else:
            # Fallback para compatibilidade
            novo_comprovante['pdf_filename'] = pdf_result
        
        # Salvar comprovante
        comprovantes_data['comprovantes'].append(novo_comprovante)
        with open(COMPROVANTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(comprovantes_data, f, ensure_ascii=False, indent=2)
        
        flash('Comprovante emitido com sucesso!', 'success')
        return redirect(url_for('admin_comprovantes'))
    
    # GET - Exibir formulário
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    return render_template('admin/emitir_comprovante.html', clientes=clients_data['clients'])

@app.route('/admin/comprovantes/<int:cliente_id>/ordens')
@login_required
def get_ordens_cliente(cliente_id):
    """Retorna ordens de um cliente em JSON"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
    if not cliente:
        return jsonify({'error': 'Cliente não encontrado'}), 404
    
    ordens = cliente.get('ordens', [])
    ordens_data = []
    for ordem in ordens:
        ordens_data.append({
            'id': ordem.get('id'),
            'numero_ordem': ordem.get('numero_ordem', ordem.get('id')),
            'servico': ordem.get('servico', ''),
            'total': ordem.get('total', 0.00),
            'status': ordem.get('status', 'pendente')
        })
    
    return jsonify({'ordens': ordens_data})

def gerar_pdf_comprovante(cliente, ordem, comprovante):
    """Gera PDF do comprovante de pagamento e salva no banco de dados"""
    pdf_filename = f"comprovante_{comprovante['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Criar buffer em memória para o PDF
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Logo
    logo_path = os.path.join('static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo_width = 4.5*cm
            logo_height = logo_width / 2.60
            logo = Image(logo_path, width=logo_width, height=logo_height)
            logo_table = Table([[logo]], colWidths=[17*cm])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(logo_table)
            story.append(Spacer(1, 0.2*cm))
        except:
            pass
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#215f97'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("COMPROVANTE DE PAGAMENTO", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informações do Comprovante
    data_formatada = datetime.strptime(comprovante['data'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    
    info_data = [
        ['Número do Comprovante:', f"#{comprovante['id']:04d}"],
        ['Data:', data_formatada],
        ['Número da Ordem:', str(comprovante['numero_ordem'])],
    ]
    info_table = Table(info_data, colWidths=[5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Dados do Cliente
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#215f97'),
        spaceAfter=8,
        spaceBefore=0,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("DADOS DO CLIENTE", heading_style))
    
    # Formatar telefone e CPF
    telefone = cliente.get('telefone', '')
    if telefone and len(telefone) == 11:
        telefone_formatado = f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    elif telefone and len(telefone) == 10:
        telefone_formatado = f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    else:
        telefone_formatado = telefone
    
    cpf = cliente.get('cpf', '')
    if cpf and len(cpf) == 11:
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    else:
        cpf_formatado = cpf
    
    cliente_data = [
        ['Nome:', cliente['nome']],
        ['E-mail:', cliente.get('email', '')],
        ['Telefone:', telefone_formatado],
        ['CPF:', cpf_formatado],
    ]
    cliente_table = Table(cliente_data, colWidths=[4.5*cm, 12.5*cm])
    cliente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(cliente_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Informações de Pagamento
    story.append(Paragraph("INFORMAÇÕES DE PAGAMENTO", heading_style))
    
    formas_pagamento = {
        'dinheiro': 'Dinheiro',
        'cartao_debito': 'Cartão de Débito',
        'cartao_credito': 'Cartão de Crédito',
        'pix': 'PIX'
    }
    
    forma_pagamento_texto = formas_pagamento.get(comprovante['forma_pagamento'], comprovante['forma_pagamento'])
    if comprovante['forma_pagamento'] == 'cartao_credito' and comprovante['parcelas'] > 1:
        forma_pagamento_texto += f" ({comprovante['parcelas']}x)"
    
    pagamento_data = [
        ['Valor Total da Ordem:', f"R$ {comprovante['valor_total']:.2f}".replace('.', ',')],
        ['Valor Pago:', f"R$ {comprovante['valor_pago']:.2f}".replace('.', ',')],
        ['Forma de Pagamento:', forma_pagamento_texto],
    ]
    
    if comprovante['forma_pagamento'] == 'cartao_credito' and comprovante['parcelas'] > 1:
        valor_parcela = comprovante['valor_pago'] / comprovante['parcelas']
        pagamento_data.append(['Valor por Parcela:', f"R$ {valor_parcela:.2f}".replace('.', ',')])
    
    pagamento_table = Table(pagamento_data, colWidths=[5*cm, 12*cm])
    pagamento_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(pagamento_table)
    story.append(Spacer(1, 1*cm))
    
    # Assinatura
    story.append(Paragraph("ASSINATURA", heading_style))
    story.append(Spacer(1, 0.3*cm))
    
    assinatura_data = [
        ['Assinatura:', '___________________________'],
    ]
    assinatura_table = Table(assinatura_data, colWidths=[4*cm, 13*cm])
    assinatura_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(assinatura_table)
    
    doc.build(story)
    
    # Obter dados do PDF do buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Salvar no banco de dados
    if use_database():
        pdf_id = salvar_pdf_no_banco(
            pdf_data=pdf_data,
            nome=pdf_filename,
            tipo_documento='comprovante',
            referencia_id=comprovante.get('id')
        )
        if pdf_id:
            return {'pdf_id': pdf_id, 'pdf_filename': pdf_filename, 'url': f'/media/pdf/{pdf_id}'}
    
    # Fallback: salvar em arquivo (apenas para desenvolvimento local sem banco)
    pdf_path = os.path.join('static', 'pdfs', pdf_filename)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, 'wb') as f:
        f.write(pdf_data)
    
    return {'pdf_filename': pdf_filename, 'url': f'/static/pdfs/{pdf_filename}'}

@app.route('/admin/comprovantes/<int:comprovante_id>')
@login_required
def view_comprovante_detalhes(comprovante_id):
    """Retorna detalhes do comprovante em JSON"""
    with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    comprovante = next((c for c in data['comprovantes'] if c.get('id') == comprovante_id), None)
    if not comprovante:
        return jsonify({'error': 'Comprovante não encontrado'}), 404
    
    return jsonify(comprovante)

@app.route('/admin/comprovantes/<int:comprovante_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_comprovante(comprovante_id):
    """Editar comprovante existente"""
    with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
        comprovantes_data = json.load(f)
    
    comprovante = next((c for c in comprovantes_data['comprovantes'] if c.get('id') == comprovante_id), None)
    if not comprovante:
        flash('Comprovante não encontrado!', 'error')
        return redirect(url_for('admin_comprovantes'))
    
    if request.method == 'POST':
        valor_pago = float(request.form.get('valor_pago'))
        forma_pagamento = request.form.get('forma_pagamento')
        parcelas = request.form.get('parcelas', '1')
        
        # Buscar cliente e ordem para regenerar PDF
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        cliente = next((c for c in clients_data['clients'] if c.get('id') == comprovante['cliente_id']), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('admin_comprovantes'))
        
        ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == comprovante['ordem_id']), None)
        if not ordem:
            flash('Ordem de serviço não encontrada!', 'error')
            return redirect(url_for('admin_comprovantes'))
        
        # Atualizar comprovante
        comprovante['valor_pago'] = valor_pago
        comprovante['forma_pagamento'] = forma_pagamento
        comprovante['parcelas'] = int(parcelas) if forma_pagamento == 'cartao_credito' else 1
        comprovante['data'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Deletar PDF antigo
        if comprovante.get('pdf_filename'):
            old_pdf = os.path.join('static', 'pdfs', comprovante['pdf_filename'])
            if os.path.exists(old_pdf):
                os.remove(old_pdf)
        
        # Regenerar PDF
        pdf_result = gerar_pdf_comprovante(cliente, ordem, comprovante)
        if isinstance(pdf_result, dict):
            comprovante['pdf_filename'] = pdf_result.get('pdf_filename', '')
            comprovante['pdf_id'] = pdf_result.get('pdf_id')
        else:
            # Fallback para compatibilidade
            comprovante['pdf_filename'] = pdf_result
        comprovante['pdf_filename'] = pdf_filename
        
        # Salvar alterações
        with open(COMPROVANTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(comprovantes_data, f, ensure_ascii=False, indent=2)
        
        flash('Comprovante atualizado com sucesso!', 'success')
        return redirect(url_for('admin_comprovantes'))
    
    # GET - Exibir formulário de edição
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    cliente = next((c for c in clients_data['clients'] if c.get('id') == comprovante['cliente_id']), None)
    ordem = None
    if cliente:
        ordem = next((o for o in cliente.get('ordens', []) if o.get('id') == comprovante['ordem_id']), None)
    
    return render_template('admin/edit_comprovante.html', comprovante=comprovante, cliente=cliente, ordem=ordem, clientes=clients_data['clients'])

@app.route('/admin/comprovantes/<int:comprovante_id>/delete', methods=['POST'])
@login_required
def delete_comprovante(comprovante_id):
    """Excluir comprovante"""
    with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    comprovante = next((c for c in data['comprovantes'] if c.get('id') == comprovante_id), None)
    if comprovante:
        # Deletar PDF
        if comprovante.get('pdf_filename'):
            pdf_path = os.path.join(PDFS_DIR, comprovante['pdf_filename'])
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        
        # Remover comprovante
        data['comprovantes'] = [c for c in data['comprovantes'] if c.get('id') != comprovante_id]
        
        with open(COMPROVANTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Comprovante excluído com sucesso!', 'success')
    else:
        flash('Comprovante não encontrado!', 'error')
    
    return redirect(url_for('admin_comprovantes'))

@app.route('/admin/comprovantes/download/<path:filename>')
@login_required
def download_comprovante_pdf(filename):
    """Download do PDF do comprovante"""
    # Tentar buscar no banco de dados primeiro
    if use_database():
        try:
            # Tentar encontrar comprovante pelo pdf_filename
            comprovante = Comprovante.query.filter_by(pdf_filename=filename).first()
            if comprovante and comprovante.pdf_id:
                pdf_doc = PDFDocument.query.get(comprovante.pdf_id)
                if pdf_doc and pdf_doc.dados:
                    return Response(
                        pdf_doc.dados,
                        mimetype='application/pdf',
                        headers={
                            'Content-Disposition': f'attachment; filename={pdf_doc.nome}'
                        }
                    )
        except Exception as e:
            print(f"Erro ao buscar PDF no banco: {e}")
    
    # Fallback: tentar arquivo estático (apenas para desenvolvimento local)
    pdf_path = os.path.join('static', 'pdfs', filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    
    flash('Arquivo PDF não encontrado!', 'error')
    return redirect(url_for('admin_comprovantes'))

# ==================== PROGRAMA DE FIDELIDADE ====================

def init_fidelidade_file():
    """Inicializa arquivo de fidelidade se não existir"""
    if not os.path.exists(FIDELIDADE_FILE):
        data_dir = os.path.dirname(FIDELIDADE_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'cupons': []}, f, ensure_ascii=False, indent=2)

init_fidelidade_file()

@app.route('/admin/fidelidade')
@login_required
def admin_fidelidade():
    """Página do Clube Clínica do Reparo"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        fidelidade_data = json.load(f)
    
    cupons = sorted(fidelidade_data['cupons'], key=lambda x: x.get('data_emissao', ''), reverse=True)
    
    # Adicionar nome do cliente em cada cupom
    for cupom in cupons:
        cliente = next((c for c in clients_data['clients'] if c.get('id') == cupom.get('cliente_id')), None)
        if cliente:
            cupom['cliente_nome'] = cliente['nome']
        else:
            cupom['cliente_nome'] = 'Cliente não encontrado'
    
    return render_template('admin/fidelidade.html', clientes=clients_data['clients'], cupons=cupons)

@app.route('/admin/fidelidade/emitir', methods=['POST'])
@login_required
def emitir_cupom_desconto():
    """Emitir cupom de desconto para um cliente"""
    cliente_id = int(request.form.get('cliente_id'))
    desconto_percentual = float(request.form.get('desconto_percentual'))
    
    # Validar desconto
    if desconto_percentual <= 0 or desconto_percentual > 100:
        flash('Desconto deve ser entre 1% e 100%!', 'error')
        return redirect(url_for('admin_fidelidade'))
    
    # Buscar cliente
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    cliente = next((c for c in clients_data['clients'] if c.get('id') == cliente_id), None)
    if not cliente:
        flash('Cliente não encontrado!', 'error')
        return redirect(url_for('admin_fidelidade'))
    
    # Criar cupom
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        fidelidade_data = json.load(f)
    
    novo_cupom = {
        'id': len(fidelidade_data['cupons']) + 1,
        'cliente_id': cliente_id,
        'cliente_nome': cliente['nome'],
        'desconto_percentual': desconto_percentual,
        'usado': False,
        'ordem_id': None,
        'data_emissao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_uso': None
    }
    
    fidelidade_data['cupons'].append(novo_cupom)
    
    with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fidelidade_data, f, ensure_ascii=False, indent=2)
    
    flash(f'Cupom de {desconto_percentual}% de desconto emitido para {cliente["nome"]} com sucesso!', 'success')
    return redirect(url_for('admin_fidelidade'))

@app.route('/admin/fidelidade/<int:cupom_id>')
@login_required
def view_cupom_detalhes(cupom_id):
    """Retorna detalhes do cupom em JSON para modal"""
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cupom = next((c for c in data['cupons'] if c.get('id') == cupom_id), None)
    if not cupom:
        return jsonify({'error': 'Cupom não encontrado'}), 404
    
    # Buscar dados do cliente
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    cliente = next((c for c in clients_data['clients'] if c.get('id') == cupom.get('cliente_id')), None)
    if cliente:
        cupom['cliente_nome'] = cliente['nome']
        cupom['cliente_email'] = cliente.get('email', '')
    
    return jsonify(cupom)

@app.route('/admin/fidelidade/<int:cupom_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cupom(cupom_id):
    """Editar cupom de desconto"""
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cupom = next((c for c in data['cupons'] if c.get('id') == cupom_id), None)
    if not cupom:
        flash('Cupom não encontrado!', 'error')
        return redirect(url_for('admin_fidelidade'))
    
    if cupom.get('usado'):
        flash('Não é possível editar um cupom já utilizado!', 'error')
        return redirect(url_for('admin_fidelidade'))
    
    if request.method == 'POST':
        desconto_percentual = float(request.form.get('desconto_percentual'))
        
        # Validar desconto
        if desconto_percentual <= 0 or desconto_percentual > 100:
            flash('Desconto deve ser entre 1% e 100%!', 'error')
            return redirect(url_for('edit_cupom', cupom_id=cupom_id))
        
        # Atualizar cupom
        cupom['desconto_percentual'] = desconto_percentual
        
        with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Cupom atualizado com sucesso!', 'success')
        return redirect(url_for('admin_fidelidade'))
    
    # GET - Exibir formulário
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
    cliente = next((c for c in clients_data['clients'] if c.get('id') == cupom.get('cliente_id')), None)
    
    return render_template('admin/edit_cupom.html', cupom=cupom, cliente=cliente, clientes=clients_data['clients'])

@app.route('/admin/fidelidade/<int:cupom_id>/delete', methods=['POST'])
@login_required
def delete_cupom(cupom_id):
    """Excluir cupom de desconto"""
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cupom = next((c for c in data['cupons'] if c.get('id') == cupom_id), None)
    if cupom:
        if cupom.get('usado'):
            flash('Não é possível excluir um cupom já utilizado!', 'error')
        else:
            data['cupons'] = [c for c in data['cupons'] if c.get('id') != cupom_id]
            with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            flash('Cupom excluído com sucesso!', 'success')
    else:
        flash('Cupom não encontrado!', 'error')
    
    return redirect(url_for('admin_fidelidade'))

@app.route('/admin/fidelidade/<int:cliente_id>/cupons')
@login_required
def get_cupons_cliente(cliente_id):
    """Retorna cupons disponíveis de um cliente em JSON"""
    with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cupons = [c for c in data['cupons'] if c.get('cliente_id') == cliente_id and not c.get('usado', False)]
    return jsonify({'cupons': cupons})


# ==================== TÉCNICOS ====================

def init_tecnicos_file():
    """Inicializa arquivo de técnicos se não existir"""
    if not os.path.exists(TECNICOS_FILE):
        data_dir = os.path.dirname(TECNICOS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_data = {'tecnicos': []}
        with open(TECNICOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

@app.route('/admin/tecnicos', methods=['GET'])
@login_required
def admin_tecnicos():
    """Lista todos os técnicos cadastrados"""
    init_tecnicos_file()
    
    with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tecnicos = data.get('tecnicos', [])
    return render_template('admin/tecnicos.html', tecnicos=tecnicos)

@app.route('/admin/tecnicos/add', methods=['GET', 'POST'])
@login_required
def add_tecnico():
    """Adiciona um novo técnico"""
    init_tecnicos_file()
    
    if request.method == 'POST':
        with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Obter próximo ID
        tecnicos = data.get('tecnicos', [])
        novo_id = max([t.get('id', 0) for t in tecnicos], default=0) + 1
        
        novo_tecnico = {
            'id': novo_id,
            'nome': request.form.get('nome', '').strip(),
            'cpf': request.form.get('cpf', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'especialidade': request.form.get('especialidade', '').strip(),
            'data_cadastro': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        tecnicos.append(novo_tecnico)
        data['tecnicos'] = tecnicos
        
        with open(TECNICOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Técnico cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_tecnicos'))
    
    return render_template('admin/add_tecnico.html')

@app.route('/admin/tecnicos/<int:tecnico_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_tecnico(tecnico_id):
    """Edita um técnico existente"""
    init_tecnicos_file()
    
    with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tecnicos = data.get('tecnicos', [])
    tecnico = next((t for t in tecnicos if t.get('id') == tecnico_id), None)
    
    if not tecnico:
        flash('Técnico não encontrado!', 'error')
        return redirect(url_for('admin_tecnicos'))
    
    if request.method == 'POST':
        tecnico['nome'] = request.form.get('nome', '').strip()
        tecnico['cpf'] = request.form.get('cpf', '').strip()
        tecnico['telefone'] = request.form.get('telefone', '').strip()
        tecnico['email'] = request.form.get('email', '').strip()
        tecnico['especialidade'] = request.form.get('especialidade', '').strip()
        
        with open(TECNICOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Técnico atualizado com sucesso!', 'success')
        return redirect(url_for('admin_tecnicos'))
    
    return render_template('admin/edit_tecnico.html', tecnico=tecnico)

@app.route('/admin/tecnicos/<int:tecnico_id>/delete', methods=['POST'])
@login_required
def delete_tecnico(tecnico_id):
    """Exclui um técnico"""
    init_tecnicos_file()
    
    with open(TECNICOS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tecnicos = data.get('tecnicos', [])
    data['tecnicos'] = [t for t in tecnicos if t.get('id') != tecnico_id]
    
    with open(TECNICOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Técnico excluído com sucesso!', 'success')
    return redirect(url_for('admin_tecnicos'))

@app.route('/admin/slides', methods=['GET'])
@login_required
def admin_slides():
    """Lista todos os slides cadastrados"""
    if use_database():
        try:
            slides_db = Slide.query.order_by(Slide.ordem).all()
            slides = []
            for s in slides_db:
                    # Se tem imagem_id, usar rota do banco, senão usar caminho estático
                    if s.imagem_id:
                        imagem_url = f'/admin/slides/imagem/{s.imagem_id}'
                    elif s.imagem:
                        imagem_url = s.imagem
                    else:
                        imagem_url = 'img/placeholder.png'
                    
                    slides.append({
                        'id': s.id,
                        'imagem': imagem_url,
                        'link': s.link,
                        'link_target': s.link_target or '_self',
                        'ordem': s.ordem,
                        'ativo': s.ativo
                    })
        except Exception as e:
            print(f"Erro ao buscar slides do banco: {e}")
            slides = []
    else:
        init_slides_file()
        with open(SLIDES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        slides = sorted(data.get('slides', []), key=lambda x: x.get('ordem', 999))
    
    return render_template('admin/slides.html', slides=slides)

@app.route('/admin/slides/add', methods=['GET', 'POST'])
@login_required
def add_slide():
    """Adiciona um novo slide"""
    if request.method == 'POST':
        imagem_path_or_id = request.form.get('imagem', '').strip()
        link = request.form.get('link', '').strip()
        link_target = request.form.get('link_target', '_self').strip()
        ordem = request.form.get('ordem', '1')
        ativo = request.form.get('ativo') == 'on'
        
        if use_database():
            try:
                with app.app_context():
                    slide = Slide(
                        link=link if link else None,
                        link_target=link_target,
                        ordem=int(ordem) if ordem.isdigit() else 1,
                        ativo=ativo
                    )
                    
                    if imagem_path_or_id.startswith('/admin/slides/imagem/'):
                        try:
                            slide.imagem_id = int(imagem_path_or_id.split('/')[-1])
                        except ValueError:
                            slide.imagem = imagem_path_or_id  # Fallback se ID inválido
                    else:
                        slide.imagem = imagem_path_or_id
                    
                    db.session.add(slide)
                    db.session.commit()
                    flash('Slide cadastrado com sucesso!', 'success')
                    return redirect(url_for('admin_slides'))
            except Exception as e:
                print(f"Erro ao adicionar slide no banco: {e}")
                flash('Erro ao adicionar slide. Tente novamente.', 'error')
                return redirect(url_for('add_slide'))
        else:
            # Fallback para JSON
            init_slides_file()
            with open(SLIDES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            slides = data.get('slides', [])
            novo_id = max([s.get('id', 0) for s in slides], default=0) + 1
            proxima_ordem = max([s.get('ordem', 0) for s in slides], default=0) + 1
            
            novo_slide = {
                'id': novo_id,
                'imagem': imagem_path_or_id,
                'link': link,
                'link_target': link_target,
                'ordem': proxima_ordem,
                'ativo': ativo
            }
            
            slides.append(novo_slide)
            data['slides'] = slides
            
            with open(SLIDES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            flash('Slide cadastrado com sucesso!', 'success')
            return redirect(url_for('admin_slides'))
    
    return render_template('admin/add_slide.html')

@app.route('/admin/slides/<int:slide_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_slide(slide_id):
    """Edita um slide existente"""
    if use_database():
        try:
            slide = Slide.query.get(slide_id)
            if not slide:
                flash('Slide não encontrado!', 'error')
                return redirect(url_for('admin_slides'))
            
            if request.method == 'POST':
                slide.link = request.form.get('link', '').strip() or None
                slide.link_target = request.form.get('link_target', '_self').strip()
                slide.ordem = int(request.form.get('ordem', '1')) if request.form.get('ordem', '1').isdigit() else 1
                slide.ativo = request.form.get('ativo') == 'on'
                
                imagem_nova = request.form.get('imagem', '').strip()
                if imagem_nova:
                    if imagem_nova.startswith('/admin/slides/imagem/'):
                        try:
                            slide.imagem_id = int(imagem_nova.split('/')[-1])
                            slide.imagem = None  # Limpar caminho se usar ID
                        except ValueError:
                            slide.imagem_id = None
                            slide.imagem = imagem_nova
                    else:
                        slide.imagem_id = None  # Reset se não for imagem do banco
                        slide.imagem = imagem_nova
                
                db.session.commit()
                flash('Slide atualizado com sucesso!', 'success')
                return redirect(url_for('admin_slides'))
            
            # Converter para formato compatível com template
            if slide.imagem_id:
                imagem_url = f'/admin/slides/imagem/{slide.imagem_id}'
            elif slide.imagem:
                imagem_url = slide.imagem
            else:
                imagem_url = ''
            
            slide_dict = {
                'id': slide.id,
                'imagem': imagem_url,
                'link': slide.link or '',
                'link_target': slide.link_target or '_self',
                'ordem': slide.ordem,
                'ativo': slide.ativo
            }
            return render_template('admin/edit_slide.html', slide=slide_dict)
        except Exception as e:
            print(f"Erro ao editar slide no banco: {e}")
            flash('Erro ao editar slide. Usando arquivos JSON.', 'warning')
    
    # Fallback para JSON
    init_slides_file()
    with open(SLIDES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    slides = data.get('slides', [])
    slide = next((s for s in slides if s.get('id') == slide_id), None)
    
    if not slide:
        flash('Slide não encontrado!', 'error')
        return redirect(url_for('admin_slides'))
    
    if request.method == 'POST':
        slide['imagem'] = request.form.get('imagem', '').strip()
        slide['link'] = request.form.get('link', '').strip()
        slide['link_target'] = request.form.get('link_target', '_self').strip()
        slide['ordem'] = int(request.form.get('ordem', 1))
        slide['ativo'] = request.form.get('ativo') == 'on'
        
        with open(SLIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Slide atualizado com sucesso!', 'success')
        return redirect(url_for('admin_slides'))
    
    return render_template('admin/edit_slide.html', slide=slide)

@app.route('/admin/slides/<int:slide_id>/delete', methods=['POST'])
@login_required
def delete_slide(slide_id):
    """Exclui um slide"""
    if use_database():
        try:
            slide = Slide.query.get(slide_id)
            if slide:
                db.session.delete(slide)
                db.session.commit()
                flash('Slide excluído com sucesso!', 'success')
            else:
                flash('Slide não encontrado!', 'error')
        except Exception as e:
            print(f"Erro ao excluir slide do banco: {e}")
            flash('Erro ao excluir slide. Tente novamente.', 'error')
    else:
        init_slides_file()
        with open(SLIDES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        slides = data.get('slides', [])
        data['slides'] = [s for s in slides if s.get('id') != slide_id]
        
        with open(SLIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Slide excluído com sucesso!', 'success')
    
    return redirect(url_for('admin_slides'))

# ==================== FOOTER MANAGEMENT ====================

@app.route('/admin/footer', methods=['GET', 'POST'])
@login_required
def admin_footer():
    """Gerencia o rodapé do site"""
    init_footer_file()
    
    if request.method == 'POST':
        with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Atualizar dados
        data['descricao'] = request.form.get('descricao', '').strip()
        data['redes_sociais']['facebook'] = request.form.get('facebook', '').strip()
        data['redes_sociais']['instagram'] = request.form.get('instagram', '').strip()
        data['redes_sociais']['whatsapp'] = request.form.get('whatsapp', '').strip()
        data['contato']['telefone'] = request.form.get('telefone', '').strip()
        data['contato']['email'] = request.form.get('email', '').strip()
        data['contato']['endereco'] = request.form.get('endereco', '').strip()
        data['copyright'] = request.form.get('copyright', '').strip()
        data['whatsapp_float'] = request.form.get('whatsapp_float', '').strip()
        
        with open(FOOTER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Rodapé atualizado com sucesso!', 'success')
        return redirect(url_for('admin_footer'))
    
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    return render_template('admin/footer.html', footer=footer_data)

# ==================== MARCAS MANAGEMENT ====================

@app.route('/admin/marcas', methods=['GET'])
@login_required
def admin_marcas():
    """Lista todas as marcas cadastradas"""
    if use_database():
        try:
            marcas_db = Marca.query.order_by(Marca.ordem).all()
            marcas = []
            for m in marcas_db:
                    if m.imagem_id:
                        imagem_url = f'/admin/marcas/imagem/{m.imagem_id}'
                    elif m.imagem:
                        imagem_url = m.imagem
                    else:
                        imagem_url = 'img/placeholder.png'
                    
                    marcas.append({
                        'id': m.id,
                        'nome': m.nome,
                        'imagem': imagem_url,
                        'ordem': m.ordem,
                        'ativo': m.ativo
                    })
        except Exception as e:
            print(f"Erro ao buscar marcas do banco: {e}")
            marcas = []
    else:
        init_marcas_file()
        with open(MARCAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        marcas = sorted(data.get('marcas', []), key=lambda x: x.get('ordem', 999))
    
    return render_template('admin/marcas.html', marcas=marcas)

@app.route('/admin/marcas/add', methods=['GET', 'POST'])
@login_required
def add_marca():
    """Adiciona uma nova marca"""
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        imagem_path_or_id = request.form.get('imagem', '').strip()
        ordem = request.form.get('ordem', '1')
        ativo = request.form.get('ativo') == 'on'
        
        if use_database():
            try:
                marca = Marca(
                    nome=nome,
                    ordem=int(ordem) if ordem.isdigit() else 1,
                    ativo=ativo
                )
                
                if imagem_path_or_id.startswith('/admin/marcas/imagem/'):
                    try:
                        marca.imagem_id = int(imagem_path_or_id.split('/')[-1])
                    except ValueError:
                        marca.imagem = imagem_path_or_id
                else:
                    marca.imagem = imagem_path_or_id
                
                db.session.add(marca)
                db.session.commit()
                flash('Marca cadastrada com sucesso!', 'success')
                return redirect(url_for('admin_marcas'))
            except Exception as e:
                print(f"Erro ao adicionar marca no banco: {e}")
                flash('Erro ao adicionar marca. Tente novamente.', 'error')
                return redirect(url_for('add_marca'))
        else:
            # Fallback para JSON
            init_marcas_file()
            with open(MARCAS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            marcas = data.get('marcas', [])
            novo_id = max([m.get('id', 0) for m in marcas], default=0) + 1
            proxima_ordem = max([m.get('ordem', 0) for m in marcas], default=0) + 1
            
            nova_marca = {
                'id': novo_id,
                'nome': nome,
                'imagem': imagem_path_or_id,
                'ordem': proxima_ordem,
                'ativo': ativo
            }
            
            marcas.append(nova_marca)
            data['marcas'] = marcas
            
            with open(MARCAS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            flash('Marca cadastrada com sucesso!', 'success')
            return redirect(url_for('admin_marcas'))
    
    return render_template('admin/add_marca.html')

@app.route('/admin/marcas/<int:marca_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_marca(marca_id):
    """Edita uma marca existente"""
    if use_database():
        try:
            marca = Marca.query.get(marca_id)
            if not marca:
                flash('Marca não encontrada!', 'error')
                return redirect(url_for('admin_marcas'))
            
            if request.method == 'POST':
                marca.nome = request.form.get('nome', '').strip()
                marca.ordem = int(request.form.get('ordem', '1')) if request.form.get('ordem', '1').isdigit() else 1
                marca.ativo = request.form.get('ativo') == 'on'
                
                imagem_nova = request.form.get('imagem', '').strip()
                if imagem_nova:
                    if imagem_nova.startswith('/admin/marcas/imagem/'):
                        try:
                            marca.imagem_id = int(imagem_nova.split('/')[-1])
                            marca.imagem = None
                        except ValueError:
                            marca.imagem_id = None
                            marca.imagem = imagem_nova
                    else:
                        marca.imagem_id = None
                        marca.imagem = imagem_nova
                
                db.session.commit()
                flash('Marca atualizada com sucesso!', 'success')
                return redirect(url_for('admin_marcas'))
            
            if marca.imagem_id:
                imagem_url = f'/admin/marcas/imagem/{marca.imagem_id}'
            elif marca.imagem:
                imagem_url = marca.imagem
            else:
                imagem_url = ''
            
            marca_dict = {
                'id': marca.id,
                'nome': marca.nome,
                'imagem': imagem_url,
                'ordem': marca.ordem,
                'ativo': marca.ativo
            }
            return render_template('admin/edit_marca.html', marca=marca_dict)
        except Exception as e:
            print(f"Erro ao editar marca no banco: {e}")
            flash('Erro ao editar marca. Usando arquivos JSON.', 'warning')
    
    # Fallback para JSON
    init_marcas_file()
    with open(MARCAS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    marcas = data.get('marcas', [])
    marca = next((m for m in marcas if m.get('id') == marca_id), None)
    
    if not marca:
        flash('Marca não encontrada!', 'error')
        return redirect(url_for('admin_marcas'))
    
    if request.method == 'POST':
        marca['nome'] = request.form.get('nome', '').strip()
        marca['imagem'] = request.form.get('imagem', '').strip()
        marca['ordem'] = int(request.form.get('ordem', 1))
        marca['ativo'] = request.form.get('ativo') == 'on'
        
        with open(MARCAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Marca atualizada com sucesso!', 'success')
        return redirect(url_for('admin_marcas'))
    
    return render_template('admin/edit_marca.html', marca=marca)

@app.route('/admin/marcas/<int:marca_id>/delete', methods=['POST'])
@login_required
def delete_marca(marca_id):
    """Exclui uma marca"""
    if use_database():
        try:
            marca = Marca.query.get(marca_id)
            if marca:
                db.session.delete(marca)
                db.session.commit()
                flash('Marca excluída com sucesso!', 'success')
            else:
                flash('Marca não encontrada!', 'error')
        except Exception as e:
            print(f"Erro ao excluir marca do banco: {e}")
            flash('Erro ao excluir marca. Tente novamente.', 'error')
    else:
        init_marcas_file()
        with open(MARCAS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        marcas = data.get('marcas', [])
        data['marcas'] = [m for m in marcas if m.get('id') != marca_id]
        
        with open(MARCAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Marca excluída com sucesso!', 'success')
    
    return redirect(url_for('admin_marcas'))

# ==================== MILESTONES MANAGEMENT ====================

@app.route('/admin/milestones', methods=['GET'])
@login_required
def admin_milestones():
    """Lista todos os milestones cadastrados"""
    init_milestones_file()
    
    with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    milestones = sorted(data.get('milestones', []), key=lambda x: x.get('ordem', 999))
    return render_template('admin/milestones.html', milestones=milestones)

@app.route('/admin/milestones/add', methods=['GET', 'POST'])
@login_required
def add_milestone():
    """Adiciona um novo milestone"""
    init_milestones_file()
    
    if request.method == 'POST':
        with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Obter próximo ID
        milestones = data.get('milestones', [])
        novo_id = max([m.get('id', 0) for m in milestones], default=0) + 1
        
        # Obter próxima ordem
        proxima_ordem = max([m.get('ordem', 0) for m in milestones], default=0) + 1
        
        novo_milestone = {
            'id': novo_id,
            'titulo': request.form.get('titulo', '').strip(),
            'imagem': request.form.get('imagem', '').strip(),
            'ordem': proxima_ordem,
            'ativo': request.form.get('ativo') == 'on'
        }
        
        milestones.append(novo_milestone)
        data['milestones'] = milestones
        
        with open(MILESTONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Milestone cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_milestones'))
    
    return render_template('admin/add_milestone.html')

@app.route('/admin/milestones/<int:milestone_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_milestone(milestone_id):
    """Edita um milestone existente"""
    init_milestones_file()
    
    with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    milestones = data.get('milestones', [])
    milestone = next((m for m in milestones if m.get('id') == milestone_id), None)
    
    if not milestone:
        flash('Milestone não encontrado!', 'error')
        return redirect(url_for('admin_milestones'))
    
    if request.method == 'POST':
        milestone['titulo'] = request.form.get('titulo', '').strip()
        milestone['imagem'] = request.form.get('imagem', '').strip()
        milestone['ordem'] = int(request.form.get('ordem', 1))
        milestone['ativo'] = request.form.get('ativo') == 'on'
        
        with open(MILESTONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Milestone atualizado com sucesso!', 'success')
        return redirect(url_for('admin_milestones'))
    
    return render_template('admin/edit_milestone.html', milestone=milestone)

@app.route('/admin/milestones/<int:milestone_id>/delete', methods=['POST'])
@login_required
def delete_milestone(milestone_id):
    """Exclui um milestone"""
    init_milestones_file()
    
    with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    milestones = data.get('milestones', [])
    data['milestones'] = [m for m in milestones if m.get('id') != milestone_id]
    
    with open(MILESTONES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Milestone excluído com sucesso!', 'success')
    return redirect(url_for('admin_milestones'))

# ==================== ADMIN USERS MANAGEMENT ====================

@app.route('/admin/usuarios')
@login_required
def admin_usuarios():
    init_admin_users_file()
    with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    usuarios = sorted(data.get('users', []), key=lambda x: x.get('id', 0))
    return render_template('admin/usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/add', methods=['GET', 'POST'])
@login_required
def add_usuario_admin():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        ativo = request.form.get('ativo') == 'on'
        
        if not username or not password:
            flash('Usuário e senha são obrigatórios!', 'error')
            return render_template('admin/add_usuario.html')
        
        init_admin_users_file()
        with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verificar se username já existe
        if any(u.get('username') == username for u in data.get('users', [])):
            flash('Este nome de usuário já está em uso!', 'error')
            return render_template('admin/add_usuario.html')
        
        # Obter próximo ID
        max_id = max([u.get('id', 0) for u in data.get('users', [])], default=0)
        
        novo_usuario = {
            'id': max_id + 1,
            'username': username,
            'password': password,
            'nome': nome,
            'email': email,
            'ativo': ativo,
            'data_criacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        data.setdefault('users', []).append(novo_usuario)
        
        with open(ADMIN_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Usuário adicionado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('admin/add_usuario.html')

@app.route('/admin/usuarios/<int:usuario_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_usuario_admin(usuario_id):
    init_admin_users_file()
    with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    usuario = next((u for u in data.get('users', []) if u.get('id') == usuario_id), None)
    if not usuario:
        flash('Usuário não encontrado!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    # Não permitir editar o próprio usuário se for o usuário padrão (id 0)
    current_user_id = session.get('admin_user_id', 0)
    if usuario_id == current_user_id and current_user_id == 0:
        flash('Não é possível editar o usuário padrão através desta interface!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        ativo = request.form.get('ativo') == 'on'
        
        if not username:
            flash('Nome de usuário é obrigatório!', 'error')
            return render_template('admin/edit_usuario.html', usuario=usuario)
        
        # Verificar se username já existe (exceto o próprio usuário)
        if any(u.get('username') == username and u.get('id') != usuario_id for u in data.get('users', [])):
            flash('Este nome de usuário já está em uso!', 'error')
            return render_template('admin/edit_usuario.html', usuario=usuario)
        
        usuario['username'] = username
        if password:  # Só atualiza senha se foi informada
            usuario['password'] = password
        usuario['nome'] = nome
        usuario['email'] = email
        usuario['ativo'] = ativo
        
        with open(ADMIN_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('admin/edit_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/<int:usuario_id>/delete', methods=['POST'])
@login_required
def delete_usuario_admin(usuario_id):
    # Não permitir excluir o próprio usuário
    current_user_id = session.get('admin_user_id', 0)
    if usuario_id == current_user_id:
        flash('Você não pode excluir seu próprio usuário!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    init_admin_users_file()
    with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['users'] = [u for u in data.get('users', []) if u.get('id') != usuario_id]
    
    with open(ADMIN_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('admin_usuarios'))

@app.context_processor
def inject_footer():
    """Injeta dados do rodapé em todos os templates"""
    init_footer_file()
    try:
        with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
            footer_data = json.load(f)
        return {'footer': footer_data}
    except:
        return {'footer': None}

@app.context_processor
def inject_servicos():
    """Injeta serviços ativos em todos os templates"""
    init_data_file()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            services_data = json.load(f)
        servicos = [s for s in services_data.get('services', []) if s.get('ativo', True)]
        servicos = sorted(servicos, key=lambda x: x.get('ordem', 999))
        return {'servicos_footer': servicos}
    except:
        return {'servicos_footer': []}

@app.template_filter('get_status_label')
def get_status_label(status):
    """Traduz o status para português"""
    status_labels = {
        'pendente': 'Pendente',
        'em_andamento': 'Em Andamento',
        'aguardando_pecas': 'Aguardando Peças',
        'pronto': 'Pronto',
        'pago': 'Pago',
        'entregue': 'Entregue',
        'cancelado': 'Cancelado'
    }
    return status_labels.get(status, status.capitalize())

# ==================== SISTEMA DE AGENDAMENTO ====================

def init_agendamentos_file():
    """Inicializa arquivo de agendamentos se não existir"""
    if not os.path.exists(AGENDAMENTOS_FILE):
        data_dir = os.path.dirname(AGENDAMENTOS_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        with open(AGENDAMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'agendamentos': []}, f, ensure_ascii=False, indent=2)

init_agendamentos_file()

def enviar_notificacao_whatsapp(mensagem):
    """Envia notificação via WhatsApp"""
    try:
        import requests
        from urllib.parse import quote
        import re
        
        # Buscar número do WhatsApp do footer
        with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
            footer_data = json.load(f)
        
        whatsapp_link = footer_data.get('whatsapp_float') or footer_data.get('redes_sociais', {}).get('whatsapp', '')
        
        if not whatsapp_link:
            print("WhatsApp não configurado no footer")
            return None
        
        # Extrair número do link (formato: https://wa.me/5586988959957)
        numero_match = re.search(r'wa\.me/(\d+)', whatsapp_link)
        if not numero_match:
            print("Número do WhatsApp não encontrado no link")
            return None
        
        numero_destino = numero_match.group(1)
        
        # Tentar enviar via API Evolution API (se configurada)
        # Você pode configurar a URL da sua API Evolution API aqui
        evolution_api_url = os.environ.get('EVOLUTION_API_URL', '')
        evolution_api_key = os.environ.get('EVOLUTION_API_KEY', '')
        evolution_instance = os.environ.get('EVOLUTION_INSTANCE', '')
        
        if evolution_api_url and evolution_api_key and evolution_instance:
            try:
                url = f"{evolution_api_url}/message/sendText/{evolution_instance}"
                headers = {
                    'Content-Type': 'application/json',
                    'apikey': evolution_api_key
                }
                payload = {
                    "number": numero_destino,
                    "text": mensagem
                }
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    print(f"Notificação WhatsApp enviada via Evolution API para {numero_destino}")
                    return True
                else:
                    print(f"Erro ao enviar via Evolution API: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Erro ao enviar via Evolution API: {str(e)}")
        
        # Tentar enviar via Twilio (se configurado)
        twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
        twilio_whatsapp_from = os.environ.get('TWILIO_WHATSAPP_FROM', '')
        
        if twilio_account_sid and twilio_auth_token and twilio_whatsapp_from:
            try:
                from twilio.rest import Client
                client = Client(twilio_account_sid, twilio_auth_token)
                message = client.messages.create(
                    body=mensagem,
                    from_=twilio_whatsapp_from,
                    to=f'whatsapp:+{numero_destino}'
                )
                print(f"Notificação WhatsApp enviada via Twilio para {numero_destino}. SID: {message.sid}")
                return True
            except Exception as e:
                print(f"Erro ao enviar via Twilio: {str(e)}")
        
        # Se nenhuma API configurada, gerar URL e fazer log detalhado
        mensagem_codificada = quote(mensagem)
        url_whatsapp = f"https://wa.me/{numero_destino}?text={mensagem_codificada}"
        
        print("=" * 60)
        print("NOTIFICAÇÃO WHATSAPP - NENHUMA API CONFIGURADA")
        print("=" * 60)
        print(f"URL do WhatsApp: {url_whatsapp}")
        print("\nMensagem que seria enviada:")
        print("-" * 60)
        print(mensagem)
        print("-" * 60)
        print("\nPara configurar envio automático, consulte CONFIGURACAO_WHATSAPP.md")
        print("=" * 60)
        
        # Tentar abrir a URL automaticamente (funciona apenas em ambiente local/desenvolvimento)
        try:
            import webbrowser
            webbrowser.open(url_whatsapp)
            print("✓ URL do WhatsApp aberta no navegador")
        except Exception as e:
            print(f"⚠ Não foi possível abrir o navegador automaticamente: {str(e)}")
            print(f"   Abra manualmente: {url_whatsapp}")
        
        return url_whatsapp
        
    except Exception as e:
        print(f"Erro ao enviar notificação WhatsApp: {str(e)}")
        import traceback
        traceback.print_exc()
    return None

@app.route('/agendamento', methods=['GET', 'POST'])
def agendamento():
    """Página de agendamento de serviços"""
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        data_agendamento = request.form.get('data_agendamento', '').strip()
        hora_agendamento = request.form.get('hora_agendamento', '').strip()
        tipo_servico = request.form.get('tipo_servico', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Validações
        if not nome or not telefone or not data_agendamento or not hora_agendamento or not tipo_servico:
            flash('Por favor, preencha todos os campos obrigatórios!', 'error')
            return redirect(url_for('agendamento'))
        
        # Salvar agendamento
        init_agendamentos_file()
        with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
            agendamentos_data = json.load(f)
        
        novo_agendamento = {
            'id': len(agendamentos_data['agendamentos']) + 1,
            'nome': nome,
            'telefone': telefone,
            'email': email,
            'data_agendamento': data_agendamento,
            'hora_agendamento': hora_agendamento,
            'tipo_servico': tipo_servico,
            'observacoes': observacoes,
            'status': 'pendente',
            'data_criacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        agendamentos_data['agendamentos'].append(novo_agendamento)
        
        with open(AGENDAMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(agendamentos_data, f, ensure_ascii=False, indent=2)
        
        # Enviar notificação WhatsApp
        mensagem = f"🔔 *NOVO AGENDAMENTO*\n\n"
        mensagem += f"👤 *Cliente:* {nome}\n"
        mensagem += f"📞 *Telefone:* {telefone}\n"
        if email:
            mensagem += f"📧 *E-mail:* {email}\n"
        mensagem += f"📅 *Data:* {data_agendamento}\n"
        mensagem += f"⏰ *Hora:* {hora_agendamento}\n"
        mensagem += f"🔧 *Serviço:* {tipo_servico}\n"
        if observacoes:
            mensagem += f"📝 *Observações:* {observacoes}\n"
        mensagem += f"\n_Agendamento criado em {novo_agendamento['data_criacao']}_"
        
        resultado = enviar_notificacao_whatsapp(mensagem)
        
        if resultado:
            print(f"Notificação WhatsApp processada: {resultado}")
        else:
            print("Aviso: Notificação WhatsApp não foi enviada. Verifique as configurações.")
        
        flash('Agendamento solicitado com sucesso! Entraremos em contato em breve para confirmar.', 'success')
        return redirect(url_for('agendamento'))
    
    # GET - Exibir formulário
    init_data_file()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        services_data = json.load(f)
    
    servicos = [s for s in services_data.get('services', []) if s.get('ativo', True)]
    
    return render_template('agendamento.html', servicos=servicos)

@app.route('/admin/agendamentos')
@login_required
def admin_agendamentos():
    """Lista todos os agendamentos"""
    init_agendamentos_file()
    with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
        agendamentos_data = json.load(f)
    
    agendamentos = sorted(agendamentos_data.get('agendamentos', []), 
                         key=lambda x: x.get('data_criacao', ''), reverse=True)
    
    return render_template('admin/agendamentos.html', agendamentos=agendamentos)

@app.route('/admin/agendamentos/<int:agendamento_id>/status', methods=['POST'])
@login_required
def atualizar_status_agendamento(agendamento_id):
    """Atualiza status do agendamento"""
    novo_status = request.form.get('status', 'pendente')
    
    init_agendamentos_file()
    with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
        agendamentos_data = json.load(f)
    
    agendamento = next((a for a in agendamentos_data['agendamentos'] if a.get('id') == agendamento_id), None)
    if agendamento:
        agendamento['status'] = novo_status
        agendamento['data_atualizacao'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(AGENDAMENTOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(agendamentos_data, f, ensure_ascii=False, indent=2)
        
        flash('Status do agendamento atualizado com sucesso!', 'success')
    else:
        flash('Agendamento não encontrado!', 'error')
    
    return redirect(url_for('admin_agendamentos'))

@app.route('/admin/agendamentos/<int:agendamento_id>/reenviar', methods=['POST'])
@login_required
def reenviar_notificacao_agendamento(agendamento_id):
    """Reenvia notificação WhatsApp de um agendamento"""
    init_agendamentos_file()
    with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
        agendamentos_data = json.load(f)
    
    agendamento = next((a for a in agendamentos_data['agendamentos'] if a.get('id') == agendamento_id), None)
    if not agendamento:
        return jsonify({'success': False, 'error': 'Agendamento não encontrado'}), 404
    
    # Montar mensagem
    mensagem = f"🔔 *NOVO AGENDAMENTO*\n\n"
    mensagem += f"👤 *Cliente:* {agendamento['nome']}\n"
    mensagem += f"📞 *Telefone:* {agendamento['telefone']}\n"
    if agendamento.get('email'):
        mensagem += f"📧 *E-mail:* {agendamento['email']}\n"
    mensagem += f"📅 *Data:* {agendamento['data_agendamento']}\n"
    mensagem += f"⏰ *Hora:* {agendamento['hora_agendamento']}\n"
    mensagem += f"🔧 *Serviço:* {agendamento['tipo_servico']}\n"
    if agendamento.get('observacoes'):
        mensagem += f"📝 *Observações:* {agendamento['observacoes']}\n"
    mensagem += f"\n_Agendamento criado em {agendamento['data_criacao']}_"
    
    resultado = enviar_notificacao_whatsapp(mensagem)
    
    if resultado and resultado is not True:
        # Se retornou URL, significa que não foi enviado automaticamente
        return jsonify({'success': False, 'error': 'API não configurada', 'url': resultado})
    elif resultado:
        return jsonify({'success': True, 'message': 'Notificação enviada com sucesso'})
    else:
        return jsonify({'success': False, 'error': 'Erro ao enviar notificação'})

@app.route('/admin/agendamentos/<int:agendamento_id>/delete', methods=['POST'])
@login_required
def delete_agendamento(agendamento_id):
    """Exclui um agendamento"""
    init_agendamentos_file()
    with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
        agendamentos_data = json.load(f)
    
    agendamentos_data['agendamentos'] = [a for a in agendamentos_data['agendamentos'] if a.get('id') != agendamento_id]
    
    with open(AGENDAMENTOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(agendamentos_data, f, ensure_ascii=False, indent=2)
    
    flash('Agendamento excluído com sucesso!', 'success')
    return redirect(url_for('admin_agendamentos'))

# ==================== BLOG ====================

def init_blog_file():
    """Inicializa arquivo de blog se não existir"""
    if not os.path.exists(BLOG_FILE):
        data_dir = os.path.dirname(BLOG_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        with open(BLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'artigos': []}, f, ensure_ascii=False, indent=2)

init_blog_file()

@app.route('/blog')
def blog():
    """Página principal do blog"""
    init_blog_file()
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_data = json.load(f)
    
    artigos = sorted([a for a in blog_data.get('artigos', []) if a.get('ativo', True)], 
                    key=lambda x: x.get('data_publicacao', ''), reverse=True)
    
    return render_template('blog.html', artigos=artigos)

@app.route('/blog/<int:artigo_id>')
def artigo(artigo_id):
    """Página individual do artigo"""
    init_blog_file()
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_data = json.load(f)
    
    artigo_encontrado = next((a for a in blog_data.get('artigos', []) if a.get('id') == artigo_id and a.get('ativo', True)), None)
    
    if not artigo_encontrado:
        flash('Artigo não encontrado!', 'error')
        return redirect(url_for('blog'))
    
    # Buscar artigos relacionados (mesma categoria)
    artigos_relacionados = [a for a in blog_data.get('artigos', []) 
                           if a.get('id') != artigo_id 
                           and a.get('ativo', True)
                           and a.get('categoria') == artigo_encontrado.get('categoria')][:3]
    
    return render_template('artigo.html', artigo=artigo_encontrado, artigos_relacionados=artigos_relacionados)

@app.route('/admin/blog')
@login_required
def admin_blog():
    """Lista todos os artigos do blog"""
    init_blog_file()
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_data = json.load(f)
    
    artigos = sorted(blog_data.get('artigos', []), 
                    key=lambda x: x.get('data_publicacao', ''), reverse=True)
    
    return render_template('admin/blog.html', artigos=artigos)

@app.route('/admin/blog/add', methods=['GET', 'POST'])
@login_required
def add_artigo():
    """Adicionar novo artigo"""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        subtitulo = request.form.get('subtitulo', '').strip()
        slug = request.form.get('slug', '').strip()
        resumo = request.form.get('resumo', '').strip()
        conteudo = request.form.get('conteudo', '').strip()
        autor = request.form.get('autor', '').strip()
        categoria = request.form.get('categoria', '').strip()
        imagem_destaque = request.form.get('imagem_destaque', '').strip()
        data_publicacao = request.form.get('data_publicacao', '').strip()
        hora_publicacao = request.form.get('hora_publicacao', '').strip()
        ativo = request.form.get('ativo') == 'on'
        
        if not titulo or not conteudo or not data_publicacao or not hora_publicacao:
            flash('Título, conteúdo, data e hora são obrigatórios!', 'error')
            return redirect(url_for('add_artigo'))
        
        # Gerar slug se não fornecido
        if not slug:
            import re
            slug = re.sub(r'[^a-z0-9]+', '-', titulo.lower())
            slug = re.sub(r'^-+|-+$', '', slug)
        
        # Combinar data e hora
        data_hora_publicacao = f"{data_publicacao} {hora_publicacao}:00"
        
        init_blog_file()
        with open(BLOG_FILE, 'r', encoding='utf-8') as f:
            blog_data = json.load(f)
        
        novo_id = max([a.get('id', 0) for a in blog_data.get('artigos', [])], default=0) + 1
        
        novo_artigo = {
            'id': novo_id,
            'titulo': titulo,
            'subtitulo': subtitulo,
            'slug': slug,
            'resumo': resumo,
            'conteudo': conteudo,
            'autor': autor or 'Equipe Clínica do Reparo',
            'categoria': categoria or 'Geral',
            'imagem_destaque': imagem_destaque,
            'ativo': ativo,
            'data_publicacao': data_hora_publicacao,
            'hora_publicacao': hora_publicacao,
            'data_criacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        blog_data['artigos'].append(novo_artigo)
        
        with open(BLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(blog_data, f, ensure_ascii=False, indent=2)
        
        flash('Artigo criado com sucesso!', 'success')
        return redirect(url_for('admin_blog'))
    
    return render_template('admin/add_artigo.html')

@app.route('/admin/blog/<int:artigo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_artigo(artigo_id):
    """Editar artigo"""
    init_blog_file()
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_data = json.load(f)
    
    artigo_encontrado = next((a for a in blog_data.get('artigos', []) if a.get('id') == artigo_id), None)
    
    if not artigo_encontrado:
        flash('Artigo não encontrado!', 'error')
        return redirect(url_for('admin_blog'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        subtitulo = request.form.get('subtitulo', '').strip()
        slug = request.form.get('slug', '').strip()
        resumo = request.form.get('resumo', '').strip()
        conteudo = request.form.get('conteudo', '').strip()
        autor = request.form.get('autor', '').strip()
        categoria = request.form.get('categoria', '').strip()
        imagem_destaque = request.form.get('imagem_destaque', '').strip()
        data_publicacao = request.form.get('data_publicacao', '').strip()
        hora_publicacao = request.form.get('hora_publicacao', '').strip()
        ativo = request.form.get('ativo') == 'on'
        
        if not titulo or not conteudo or not data_publicacao or not hora_publicacao:
            flash('Título, conteúdo, data e hora são obrigatórios!', 'error')
            return redirect(url_for('edit_artigo', artigo_id=artigo_id))
        
        # Gerar slug se não fornecido
        if not slug:
            import re
            slug = re.sub(r'[^a-z0-9]+', '-', titulo.lower())
            slug = re.sub(r'^-+|-+$', '', slug)
        
        # Combinar data e hora
        data_hora_publicacao = f"{data_publicacao} {hora_publicacao}:00"
        
        artigo_encontrado.update({
            'titulo': titulo,
            'subtitulo': subtitulo,
            'slug': slug,
            'resumo': resumo,
            'conteudo': conteudo,
            'autor': autor or 'Equipe Clínica do Reparo',
            'categoria': categoria or 'Geral',
            'imagem_destaque': imagem_destaque,
            'ativo': ativo,
            'data_publicacao': data_hora_publicacao,
            'hora_publicacao': hora_publicacao,
            'data_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Atualizar na lista
        for i, artigo in enumerate(blog_data['artigos']):
            if artigo.get('id') == artigo_id:
                blog_data['artigos'][i] = artigo_encontrado
                break
        
        with open(BLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(blog_data, f, ensure_ascii=False, indent=2)
        
        flash('Artigo atualizado com sucesso!', 'success')
        return redirect(url_for('admin_blog'))
    
    return render_template('admin/edit_artigo.html', artigo=artigo_encontrado)

@app.route('/admin/blog/<int:artigo_id>/delete', methods=['POST'])
@login_required
def delete_artigo(artigo_id):
    """Excluir artigo"""
    init_blog_file()
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        blog_data = json.load(f)
    
    blog_data['artigos'] = [a for a in blog_data['artigos'] if a.get('id') != artigo_id]
    
    with open(BLOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(blog_data, f, ensure_ascii=False, indent=2)
    
    flash('Artigo excluído com sucesso!', 'success')
    return redirect(url_for('admin_blog'))

@app.route('/admin/blog/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_blog():
    """Upload de imagem para o blog - salva no banco de dados ou sistema de arquivos"""
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Tipo de arquivo não permitido'}), 400
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'Arquivo muito grande. Tamanho máximo: 5MB'}), 400
    
    file_data = file.read()
    imagem_tipo = file.mimetype
    
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'blog_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            db.session.add(imagem)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'path': f'/admin/blog/imagem/{imagem.id}',
                'url': f'/admin/blog/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem de blog no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500
    
    # Se chegou aqui, o banco não está disponível
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/blog/imagem/<int:image_id>')
def servir_imagem_blog(image_id):
    """Rota para servir imagens de blog do banco de dados"""
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime,
                    headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
                )
        except Exception as e:
            print(f"Erro ao buscar imagem de blog: {e}")
    
    return redirect(url_for('static', filename='img/placeholder.png'))

@app.route('/admin/slides/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_slide():
    """Upload de imagem para slides - salva no banco de dados ou sistema de arquivos"""
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP'}), 400
    
    # Verificar tamanho do arquivo
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'Arquivo muito grande. Tamanho máximo: 5MB'}), 400
    
    file_data = file.read()
    imagem_tipo = file.mimetype
    
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'slide_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            db.session.add(imagem)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'path': f'/admin/slides/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem de slide no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500
    
    # Se chegou aqui, o banco não está disponível
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/slides/imagem/<int:image_id>')
def servir_imagem_slide(image_id):
    """Rota para servir imagens de slides do banco de dados"""
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime,
                    headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
                )
        except Exception as e:
            print(f"Erro ao buscar imagem de slide: {e}")
    
    # Fallback: retornar placeholder
    return redirect(url_for('static', filename='img/placeholder.png'))

@app.route('/admin/marcas/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_marca():
    """Upload de imagem para marcas - salva no banco de dados ou sistema de arquivos"""
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP'}), 400
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'Arquivo muito grande. Tamanho máximo: 5MB'}), 400
    
    file_data = file.read()
    imagem_tipo = file.mimetype
    
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'marca_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            db.session.add(imagem)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'path': f'/admin/marcas/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem de marca no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500
    
    # Se chegou aqui, o banco não está disponível
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/marcas/imagem/<int:image_id>')
def servir_imagem_marca(image_id):
    """Rota para servir imagens de marcas do banco de dados"""
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime,
                    headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
                )
        except Exception as e:
            print(f"Erro ao buscar imagem de marca: {e}")
    
    return redirect(url_for('static', filename='img/placeholder.png'))

@app.route('/admin/milestones/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_milestone():
    """Upload de imagem para milestones - salva no banco de dados ou sistema de arquivos"""
    if 'imagem' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['imagem']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF ou WEBP'}), 400
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'Arquivo muito grande. Tamanho máximo: 5MB'}), 400
    
    file_data = file.read()
    imagem_tipo = file.mimetype
    
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'milestone_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            db.session.add(imagem)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'path': f'/admin/milestones/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem de milestone no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500
    
    # Se chegou aqui, o banco não está disponível
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/milestones/imagem/<int:image_id>')
def servir_imagem_milestone(image_id):
    """Rota para servir imagens de milestones do banco de dados"""
    if use_database():
        try:
            # Não usar app.app_context() - já estamos em uma rota Flask
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime,
                    headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
                )
        except Exception as e:
            print(f"Erro ao buscar imagem de milestone: {e}")
    
    return redirect(url_for('static', filename='img/placeholder.png'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)

