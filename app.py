from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_file, Response
from datetime import datetime
import json
import os
import random
from functools import wraps
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models import db, Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom, Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Contato, Imagem, PDFDocument, Fornecedor, Categoria, Produto, Pedido, ItemPedido

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
                # Importar explicitamente todos os modelos para garantir que sejam registrados
                from models import Fornecedor  # Garantir que Fornecedor está importado
                db.create_all()
                print("DEBUG: ✅ Tabelas criadas/verificadas no banco de dados")
                # Nota: garantir_tabela_fornecedores() será chamada automaticamente quando necessário
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
            import traceback
            traceback.print_exc()
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
# NOTA: NÃO criar diretórios para uploads - tudo vai direto para o banco PostgreSQL
# static/ deve conter APENAS arquivos estáticos do build (CSS, JS, imagens fixas)
# PDFs e imagens são salvos diretamente no banco de dados

# Configurações de upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Lista fixa de tipos de serviço
TIPOS_SERVICO = [
    'Conserto de Celulares',
    'Conserto de Notebook',
    'Conserto de Computador',
    'Conserto de Video Game',
    'Conserto de Televisor',
    'Conserto de Microondas',
    'Conserto de Maquina de Lavar',
    'Conserto de Aparelhos de Som',
    'Outros Aparelhos Eletronicos'
]

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
    try:
        if hasattr(app, 'config') and app.config.get('SQLALCHEMY_DATABASE_URI'):
            return True
    except:
        pass
    
    return False

def garantir_tabela_fornecedores():
    """Garante que a tabela de fornecedores existe no banco de dados - SOLUÇÃO DEFINITIVA"""
    if not use_database():
        print("DEBUG: Banco de dados não disponível")
        return False
    
    try:
        from sqlalchemy import text
        
        with app.app_context():
            # Método 1: Verificar se existe usando SQL direto (mais confiável)
            try:
                with db.engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'fornecedores'
                        )
                    """))
                    existe = result.scalar()
                    
                    if existe:
                        print("DEBUG: ✅ Tabela fornecedores já existe (verificado via SQL)")
                        return True
            except Exception as check_error:
                print(f"DEBUG: Erro ao verificar tabela: {check_error}")
            
            # Método 2: Criar tabela usando SQL direto (método mais confiável)
            print("DEBUG: Tabela não existe. Criando via SQL direto...")
            try:
                with db.engine.begin() as conn:
                    # Criar tabela diretamente
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS fornecedores (
                            id SERIAL PRIMARY KEY,
                            nome VARCHAR(200) NOT NULL,
                            contato VARCHAR(200),
                            telefone VARCHAR(20),
                            email VARCHAR(200),
                            endereco TEXT,
                            cnpj VARCHAR(18),
                            tipo_servico VARCHAR(200),
                            observacoes TEXT,
                            ativo BOOLEAN DEFAULT TRUE,
                            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    print("DEBUG: ✅ CREATE TABLE executado")
                
                # Verificar se foi criada
                with db.engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'fornecedores'
                        )
                    """))
                    existe = result.scalar()
                    
                    if existe:
                        print("DEBUG: ✅ Tabela fornecedores criada e verificada com sucesso!")
                        return True
                    else:
                        print("DEBUG: ⚠️ Tabela não foi criada mesmo após CREATE TABLE")
                        return False
            except Exception as sql_error:
                print(f"DEBUG: Erro ao criar tabela via SQL: {sql_error}")
                import traceback
                traceback.print_exc()
                # Tentar método alternativo: db.create_all()
                try:
                    db.create_all()
                    print("DEBUG: ✅ db.create_all() executado como fallback")
                    # Verificar novamente
                    with db.engine.connect() as conn:
                        result = conn.execute(text("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_name = 'fornecedores'
                            )
                        """))
                        if result.scalar():
                            print("DEBUG: ✅ Tabela criada via db.create_all()")
                            return True
                except Exception as fallback_error:
                    print(f"DEBUG: Erro no fallback db.create_all(): {fallback_error}")
                return False
    except Exception as e:
        print(f"DEBUG: Erro geral ao garantir tabela fornecedores: {e}")
        import traceback
        traceback.print_exc()
        return False


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
            # Garantir que contato e redes_sociais sejam dicionários
            contato = footer_obj.contato if footer_obj.contato else {}
            if not isinstance(contato, dict):
                contato = {}
            redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
            if not isinstance(redes_sociais, dict):
                redes_sociais = {}
            
            footer_data = {
                'descricao': footer_obj.descricao or '',
                'redes_sociais': redes_sociais,
                'contato': contato,
                'copyright': footer_obj.copyright or '',
                'whatsapp_float': footer_obj.whatsapp_float or ''
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
    
    # Carregar produtos em destaque
    produtos_destaque = []
    if use_database():
        try:
            produtos_db = Produto.query.filter_by(ativo=True, destaque=True).order_by(Produto.ordem, Produto.nome).limit(6).all()
            for p in produtos_db:
                if p.imagem_id:
                    imagem_url = f'/admin/produtos/imagem/{p.imagem_id}'
                elif p.imagem:
                    imagem_url = p.imagem
                else:
                    imagem_url = 'img/placeholder.png'
                
                produtos_destaque.append({
                    'id': p.id,
                    'nome': p.nome,
                    'slug': p.slug,
                    'descricao': p.descricao,
                    'preco': float(p.preco),
                    'preco_promocional': float(p.preco_promocional) if p.preco_promocional else None,
                    'imagem': imagem_url,
                    'categoria_id': p.categoria_id,
                    'categoria_nome': p.categoria.nome if p.categoria else None,
                    'marca': p.marca,
                    'modelo': p.modelo,
                    'estoque': p.estoque,
                    'sku': p.sku
                })
        except Exception as e:
            print(f"Erro ao carregar produtos em destaque do banco: {e}")
            produtos_destaque = []
    
    return render_template('index.html', slides=slides, footer=footer_data, marcas=marcas, milestones=milestones, servicos=servicos, produtos_destaque=produtos_destaque)

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
    
    # Carregar serviços do banco de dados ou JSON
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
    
    return render_template('servicos.html', footer=footer_data, servicos=servicos)

# ==================== ROTAS DA LOJA ====================
@app.route('/loja')
def loja():
    """Página principal da loja - lista todos os produtos"""
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    categoria_id = request.args.get('categoria', type=int)
    busca = request.args.get('busca', '').strip()
    
    # Carregar produtos do banco de dados
    produtos = []
    categorias = []
    
    if use_database():
        try:
            query = Produto.query.filter_by(ativo=True)
            
            if categoria_id:
                query = query.filter_by(categoria_id=categoria_id)
            
            if busca:
                query = query.filter(
                    db.or_(
                        Produto.nome.ilike(f'%{busca}%'),
                        Produto.descricao.ilike(f'%{busca}%'),
                        Produto.marca.ilike(f'%{busca}%')
                    )
                )
            
            produtos_db = query.order_by(Produto.ordem, Produto.nome).all()
            
            # Converter para formato de dicionário
            for p in produtos_db:
                if p.imagem_id:
                    imagem_url = f'/admin/produtos/imagem/{p.imagem_id}'
                elif p.imagem:
                    imagem_url = p.imagem
                else:
                    imagem_url = 'img/placeholder.png'
                
                produtos.append({
                    'id': p.id,
                    'nome': p.nome,
                    'slug': p.slug,
                    'descricao': p.descricao,
                    'preco': float(p.preco),
                    'preco_promocional': float(p.preco_promocional) if p.preco_promocional else None,
                    'imagem': imagem_url,
                    'categoria_id': p.categoria_id,
                    'categoria_nome': p.categoria.nome if p.categoria else None,
                    'marca': p.marca,
                    'estoque': p.estoque,
                    'destaque': p.destaque
                })
            
            # Carregar categorias
            categorias_db = Categoria.query.filter_by(ativo=True).order_by(Categoria.ordem, Categoria.nome).all()
            categorias = [{'id': c.id, 'nome': c.nome, 'slug': c.slug} for c in categorias_db]
            
        except Exception as e:
            print(f"Erro ao carregar produtos do banco: {e}")
            import traceback
            traceback.print_exc()
    
    categoria_selecionada = None
    if categoria_id:
        categoria_selecionada = next((c for c in categorias if c['id'] == categoria_id), None)
    
    return render_template('loja.html', footer=footer_data, produtos=produtos, categorias=categorias, 
                         categoria_selecionada=categoria_selecionada, busca=busca)

@app.route('/loja/produto/<slug>')
def produto_detalhes(slug):
    """Página de detalhes de um produto"""
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    produto = None
    
    if use_database():
        try:
            p = Produto.query.filter_by(slug=slug, ativo=True).first()
            if p:
                if p.imagem_id:
                    imagem_url = f'/admin/produtos/imagem/{p.imagem_id}'
                elif p.imagem:
                    imagem_url = p.imagem
                else:
                    imagem_url = 'img/placeholder.png'
                
                produto = {
                    'id': p.id,
                    'nome': p.nome,
                    'slug': p.slug,
                    'descricao': p.descricao,
                    'descricao_completa': p.descricao_completa,
                    'preco': float(p.preco),
                    'preco_promocional': float(p.preco_promocional) if p.preco_promocional else None,
                    'imagem': imagem_url,
                    'categoria_id': p.categoria_id,
                    'categoria_nome': p.categoria.nome if p.categoria else None,
                    'marca': p.marca,
                    'modelo': p.modelo,
                    'estoque': p.estoque,
                    'sku': p.sku,
                    'peso': float(p.peso) if p.peso else None,
                    'dimensoes': p.dimensoes
                }
        except Exception as e:
            print(f"Erro ao carregar produto do banco: {e}")
    
    if not produto:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('loja'))
    
    return render_template('produto.html', footer=footer_data, produto=produto)

@app.route('/loja/carrinho')
def carrinho():
    """Página do carrinho de compras"""
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    carrinho_itens = session.get('carrinho', [])
    produtos_carrinho = []
    total = 0
    
    if use_database() and carrinho_itens:
        try:
            for item in carrinho_itens:
                produto_id = item.get('produto_id')
                quantidade = item.get('quantidade', 1)
                
                p = Produto.query.get(produto_id)
                if p and p.ativo:
                    if p.imagem_id:
                        imagem_url = f'/admin/produtos/imagem/{p.imagem_id}'
                    elif p.imagem:
                        imagem_url = p.imagem
                    else:
                        imagem_url = 'img/placeholder.png'
                    
                    preco = float(p.preco_promocional if p.preco_promocional else p.preco)
                    subtotal = preco * quantidade
                    total += subtotal
                    
                    produtos_carrinho.append({
                        'id': p.id,
                        'nome': p.nome,
                        'slug': p.slug,
                        'imagem': imagem_url,
                        'preco': preco,
                        'quantidade': quantidade,
                        'subtotal': subtotal,
                        'estoque': p.estoque
                    })
        except Exception as e:
            print(f"Erro ao carregar produtos do carrinho: {e}")
    
    return render_template('carrinho.html', footer=footer_data, produtos=produtos_carrinho, total=total)

@app.route('/loja/adicionar-carrinho', methods=['POST'])
def adicionar_carrinho():
    """Adiciona produto ao carrinho"""
    produto_id = request.form.get('produto_id', type=int)
    quantidade = request.form.get('quantidade', type=int, default=1)
    
    if not produto_id or quantidade < 1:
        return jsonify({'success': False, 'message': 'Dados inválidos'})
    
    if use_database():
        try:
            produto = Produto.query.get(produto_id)
            if not produto or not produto.ativo:
                return jsonify({'success': False, 'message': 'Produto não encontrado'})
            
            if produto.estoque < quantidade:
                return jsonify({'success': False, 'message': f'Estoque insuficiente. Disponível: {produto.estoque}'})
            
            # Obter ou criar carrinho na sessão
            carrinho = session.get('carrinho', [])
            
            # Verificar se produto já está no carrinho
            item_existente = next((item for item in carrinho if item.get('produto_id') == produto_id), None)
            
            if item_existente:
                nova_quantidade = item_existente['quantidade'] + quantidade
                if produto.estoque < nova_quantidade:
                    return jsonify({'success': False, 'message': f'Estoque insuficiente. Disponível: {produto.estoque}'})
                item_existente['quantidade'] = nova_quantidade
            else:
                carrinho.append({
                    'produto_id': produto_id,
                    'quantidade': quantidade
                })
            
            session['carrinho'] = carrinho
            
            # Calcular total de itens
            total_itens = sum(item.get('quantidade', 0) for item in carrinho)
            
            return jsonify({
                'success': True,
                'message': 'Produto adicionado ao carrinho',
                'total_itens': total_itens
            })
        except Exception as e:
            print(f"Erro ao adicionar ao carrinho: {e}")
            return jsonify({'success': False, 'message': 'Erro ao adicionar produto'})
    
    return jsonify({'success': False, 'message': 'Banco de dados não disponível'})

@app.route('/loja/remover-carrinho', methods=['POST'])
def remover_carrinho():
    """Remove produto do carrinho"""
    produto_id = request.form.get('produto_id', type=int)
    
    if not produto_id:
        return jsonify({'success': False, 'message': 'Produto inválido'})
    
    carrinho = session.get('carrinho', [])
    carrinho = [item for item in carrinho if item.get('produto_id') != produto_id]
    session['carrinho'] = carrinho
    
    return jsonify({'success': True, 'message': 'Produto removido do carrinho'})

@app.route('/loja/atualizar-carrinho', methods=['POST'])
def atualizar_carrinho():
    """Atualiza quantidade de um item no carrinho"""
    produto_id = request.form.get('produto_id', type=int)
    quantidade = request.form.get('quantidade', type=int)
    
    if not produto_id or quantidade < 1:
        return jsonify({'success': False, 'message': 'Dados inválidos'})
    
    if use_database():
        try:
            produto = Produto.query.get(produto_id)
            if not produto or not produto.ativo:
                return jsonify({'success': False, 'message': 'Produto não encontrado'})
            
            if produto.estoque < quantidade:
                return jsonify({'success': False, 'message': f'Estoque insuficiente. Disponível: {produto.estoque}'})
            
            carrinho = session.get('carrinho', [])
            item = next((item for item in carrinho if item.get('produto_id') == produto_id), None)
            
            if item:
                item['quantidade'] = quantidade
                session['carrinho'] = carrinho
                
                # Recalcular total
                total = 0
                for item in carrinho:
                    p = Produto.query.get(item.get('produto_id'))
                    if p:
                        preco = float(p.preco_promocional if p.preco_promocional else p.preco)
                        total += preco * item.get('quantidade', 1)
                
                return jsonify({
                    'success': True,
                    'message': 'Quantidade atualizada',
                    'total': total
                })
            else:
                return jsonify({'success': False, 'message': 'Item não encontrado no carrinho'})
        except Exception as e:
            print(f"Erro ao atualizar carrinho: {e}")
            return jsonify({'success': False, 'message': 'Erro ao atualizar carrinho'})
    
    return jsonify({'success': False, 'message': 'Banco de dados não disponível'})

@app.route('/loja/checkout', methods=['GET', 'POST'])
def checkout():
    """Página de checkout/finalização do pedido"""
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    carrinho_itens = session.get('carrinho', [])
    
    if not carrinho_itens:
        flash('Seu carrinho está vazio.', 'warning')
        return redirect(url_for('loja'))
    
    if request.method == 'POST':
        # Processar pedido
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        cpf = request.form.get('cpf')
        endereco = request.form.get('endereco')
        cep = request.form.get('cep')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')
        forma_pagamento = request.form.get('forma_pagamento')
        observacoes = request.form.get('observacoes')
        
        if not all([nome, telefone, endereco, cidade, estado, forma_pagamento]):
            flash('Por favor, preencha todos os campos obrigatórios.', 'error')
            return redirect(url_for('checkout'))
        
        if use_database():
            try:
                # Calcular totais
                subtotal = 0
                itens_pedido = []
                
                for item in carrinho_itens:
                    produto = Produto.query.get(item.get('produto_id'))
                    if produto and produto.ativo:
                        quantidade = item.get('quantidade', 1)
                        preco = float(produto.preco_promocional if produto.preco_promocional else produto.preco)
                        subtotal_item = preco * quantidade
                        subtotal += subtotal_item
                        
                        itens_pedido.append({
                            'produto': produto,
                            'quantidade': quantidade,
                            'preco': preco,
                            'subtotal': subtotal_item
                        })
                
                if not itens_pedido:
                    flash('Nenhum produto válido no carrinho.', 'error')
                    return redirect(url_for('carrinho'))
                
                # Gerar número do pedido
                numero_pedido = f"PED{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
                
                # Criar pedido
                pedido = Pedido(
                    numero_pedido=numero_pedido,
                    cliente_nome=nome,
                    cliente_email=email,
                    cliente_telefone=telefone,
                    cliente_cpf=cpf,
                    endereco_entrega=endereco,
                    cep=cep,
                    cidade=cidade,
                    estado=estado,
                    subtotal=subtotal,
                    frete=0,  # Pode ser calculado depois
                    desconto=0,
                    total=subtotal,
                    forma_pagamento=forma_pagamento,
                    observacoes=observacoes,
                    status='pendente'
                )
                
                db.session.add(pedido)
                db.session.flush()  # Para obter o ID do pedido
                
                # Criar itens do pedido
                for item in itens_pedido:
                    item_pedido = ItemPedido(
                        pedido_id=pedido.id,
                        produto_id=item['produto'].id,
                        quantidade=item['quantidade'],
                        preco_unitario=item['preco'],
                        subtotal=item['subtotal']
                    )
                    db.session.add(item_pedido)
                    
                    # Atualizar estoque
                    item['produto'].estoque -= item['quantidade']
                
                db.session.commit()
                
                # Limpar carrinho
                session['carrinho'] = []
                
                flash(f'Pedido #{numero_pedido} realizado com sucesso!', 'success')
                return redirect(url_for('pedido_sucesso', numero=numero_pedido))
                
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao processar pedido: {e}")
                import traceback
                traceback.print_exc()
                flash('Erro ao processar pedido. Tente novamente.', 'error')
    
    # GET - mostrar formulário
    produtos_carrinho = []
    subtotal = 0
    
    if use_database():
        try:
            for item in carrinho_itens:
                produto = Produto.query.get(item.get('produto_id'))
                if produto and produto.ativo:
                    quantidade = item.get('quantidade', 1)
                    preco = float(produto.preco_promocional if produto.preco_promocional else produto.preco)
                    subtotal_item = preco * quantidade
                    subtotal += subtotal_item
                    
                    produtos_carrinho.append({
                        'nome': produto.nome,
                        'quantidade': quantidade,
                        'preco': preco,
                        'subtotal': subtotal_item
                    })
        except Exception as e:
            print(f"Erro ao carregar produtos do carrinho: {e}")
    
    return render_template('checkout.html', footer=footer_data, produtos=produtos_carrinho, subtotal=subtotal)

@app.route('/loja/pedido-sucesso/<numero>')
def pedido_sucesso(numero):
    """Página de confirmação do pedido"""
    init_footer_file()
    with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
        footer_data = json.load(f)
    
    pedido = None
    if use_database():
        try:
            p = Pedido.query.filter_by(numero_pedido=numero).first()
            if p:
                pedido = {
                    'numero': p.numero_pedido,
                    'data': p.data_pedido,
                    'total': float(p.total),
                    'status': p.status
                }
        except Exception as e:
            print(f"Erro ao carregar pedido: {e}")
    
    return render_template('pedido_sucesso.html', footer=footer_data, pedido=pedido)

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
        
        ordem_encontrada = None
        cliente_encontrado = None
        
        # Buscar no banco de dados se disponível
        if use_database():
            try:
                # Buscar ordem pelo número
                ordem_db = OrdemServico.query.filter_by(numero_ordem=str(codigo)).first()
                if ordem_db:
                    cliente_db = Cliente.query.get(ordem_db.cliente_id)
                    if cliente_db:
                        # Converter ordem do banco para formato esperado pelo template
                        ordem_encontrada = {
                            'id': ordem_db.id,
                            'numero_ordem': ordem_db.numero_ordem,
                            'servico': ordem_db.servico,
                            'tipo_aparelho': ordem_db.tipo_aparelho,
                            'marca': ordem_db.marca,
                            'modelo': ordem_db.modelo,
                            'numero_serie': ordem_db.numero_serie,
                            'defeitos_cliente': ordem_db.defeitos_cliente,
                            'diagnostico_tecnico': ordem_db.diagnostico_tecnico,
                            'pecas': ordem_db.pecas or [],
                            'custo_pecas': float(ordem_db.custo_pecas) if ordem_db.custo_pecas else 0.00,
                            'custo_mao_obra': float(ordem_db.custo_mao_obra) if ordem_db.custo_mao_obra else 0.00,
                            'subtotal': float(ordem_db.subtotal) if ordem_db.subtotal else 0.00,
                            'desconto_percentual': float(ordem_db.desconto_percentual) if ordem_db.desconto_percentual else 0.00,
                            'valor_desconto': float(ordem_db.valor_desconto) if ordem_db.valor_desconto else 0.00,
                            'total': float(ordem_db.total) if ordem_db.total else 0.00,
                            'status': ordem_db.status,
                            'prazo_estimado': ordem_db.prazo_estimado,
                            'tecnico_id': ordem_db.tecnico_id,
                            'data': ordem_db.data.strftime('%Y-%m-%d %H:%M:%S') if ordem_db.data else ''
                        }
                        cliente_encontrado = {
                            'id': cliente_db.id,
                            'nome': cliente_db.nome,
                            'email': cliente_db.email,
                            'telefone': cliente_db.telefone,
                            'cpf': cliente_db.cpf,
                            'endereco': cliente_db.endereco
                        }
            except Exception as e:
                print(f"Erro ao buscar ordem no banco: {e}")
                import traceback
                traceback.print_exc()
        
        # Fallback para JSON se não encontrou no banco
        if not ordem_encontrada:
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
                if use_database():
                    tecnico_db = Tecnico.query.get(tecnico_id)
                    if tecnico_db:
                        tecnico_encontrado = {
                            'id': tecnico_db.id,
                            'nome': tecnico_db.nome,
                            'especialidade': tecnico_db.especialidade,
                            'telefone': tecnico_db.telefone,
                            'email': tecnico_db.email
                        }
                else:
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
    # Calcular saldo (ordens com status "pago" ou com comprovante)
    saldo = 0.00
    ordens_pagas = []
    
    # Calcular a receber (ordens com status "concluido")
    a_receber = 0.00
    ordens_concluidas = []
    
    # Buscar do banco de dados se disponível
    if use_database():
        try:
            # Buscar todas as ordens
            ordens_db = OrdemServico.query.all()
            
            # Buscar todos os comprovantes para verificar quais ordens foram pagas
            comprovantes_db = Comprovante.query.all()
            ordens_com_comprovante = {c.ordem_id for c in comprovantes_db if c.ordem_id}
            
            for ordem in ordens_db:
                cliente = Cliente.query.get(ordem.cliente_id)
                cliente_nome = cliente.nome if cliente else 'Cliente não encontrado'
                total_ordem = float(ordem.total) if ordem.total else 0.00
                status = ordem.status or 'pendente'
                
                # Ordem está paga se tiver status "pago" ou se tiver comprovante
                if status == 'pago' or ordem.id in ordens_com_comprovante:
                    saldo += total_ordem
                    ordens_pagas.append({
                        'numero_ordem': ordem.numero_ordem or str(ordem.id),
                        'cliente_nome': cliente_nome,
                        'total': total_ordem,
                        'data': ordem.data.strftime('%Y-%m-%d %H:%M:%S') if ordem.data else '',
                        'servico': ordem.servico or ''
                    })
                elif status == 'concluido':
                    a_receber += total_ordem
                    ordens_concluidas.append({
                        'numero_ordem': ordem.numero_ordem or str(ordem.id),
                        'cliente_nome': cliente_nome,
                        'total': total_ordem,
                        'data': ordem.data.strftime('%Y-%m-%d %H:%M:%S') if ordem.data else '',
                        'servico': ordem.servico or ''
                    })
        except Exception as e:
            print(f"Erro ao buscar dados financeiros do banco: {e}")
            import traceback
            traceback.print_exc()
            # Continuar com fallback para JSON
    
    # Fallback para JSON
    if not use_database() or len(ordens_pagas) == 0 and len(ordens_concluidas) == 0:
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Buscar comprovantes para verificar quais ordens foram pagas
        comprovantes_data = {}
        if os.path.exists(COMPROVANTES_FILE):
            with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
                comprovantes_json = json.load(f)
            for comprovante in comprovantes_json.get('comprovantes', []):
                ordem_id = comprovante.get('ordem_id')
                cliente_id = comprovante.get('cliente_id')
                if ordem_id and cliente_id:
                    comprovantes_data[(cliente_id, ordem_id)] = comprovante
        
        # Processar todas as ordens de todos os clientes
        for cliente in data['clients']:
            cliente_id = cliente.get('id')
            for ordem in cliente.get('ordens', []):
                ordem_id = ordem.get('id')
                total_ordem = float(ordem.get('total', 0.00)) if ordem.get('total') else 0.00
                status = ordem.get('status', 'pendente')
                
                # Verificar se tem comprovante
                tem_comprovante = (cliente_id, ordem_id) in comprovantes_data
                
                # Ordem está paga se tiver status "pago" ou se tiver comprovante
                if status == 'pago' or tem_comprovante:
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
            if use_database():
                try:
                    cupom = Cupom.query.filter_by(id=cupom_id, cliente_id=cliente_id, usado=False).first()
                    if cupom:
                        desconto_percentual = float(cupom.desconto_percentual)
                        valor_desconto = subtotal * (desconto_percentual / 100)
                        cupom_usado = cupom
                except Exception as e:
                    print(f"Erro ao buscar cupom no banco: {e}")
            else:
                # Fallback para JSON
                with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
                    fidelidade_data = json.load(f)
                
                cupom = next((c for c in fidelidade_data['cupons'] if c.get('id') == cupom_id and c.get('cliente_id') == cliente_id and not c.get('usado', False)), None)
                if cupom:
                    desconto_percentual = cupom['desconto_percentual']
                    valor_desconto = subtotal * (desconto_percentual / 100)
                    cupom_usado = cupom
        
        total = subtotal - valor_desconto
        
        # Gerar número único da ordem
        numero_ordem = get_proximo_numero_ordem()
        
        # Salvar no banco de dados se disponível
        if use_database():
            try:
                # Garantir que as tabelas existem antes de salvar
                with app.app_context():
                    try:
                        db.create_all()
                    except Exception as create_error:
                        print(f"DEBUG: Aviso ao criar tabelas: {create_error}")
                
                # Verificar se cliente existe no banco
                cliente_db = Cliente.query.get(cliente_id)
                
                # Se não encontrou no banco, tentar buscar no JSON e criar no banco
                if not cliente_db:
                    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
                        data_json = json.load(f)
                    
                    cliente_json = next((c for c in data_json['clients'] if c.get('id') == cliente_id), None)
                    if cliente_json:
                        # Criar cliente no banco a partir do JSON
                        cliente_db = Cliente(
                            id=cliente_json['id'],
                            nome=cliente_json.get('nome', ''),
                            email=cliente_json.get('email', ''),
                            telefone=cliente_json.get('telefone', ''),
                            cpf=cliente_json.get('cpf', ''),
                            endereco=cliente_json.get('endereco', ''),
                            username=cliente_json.get('username', ''),
                            password=cliente_json.get('password', ''),
                            data_cadastro=datetime.strptime(cliente_json.get('data_cadastro', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S') if cliente_json.get('data_cadastro') else datetime.now()
                        )
                        db.session.add(cliente_db)
                        db.session.commit()
                    else:
                        flash('Cliente não encontrado!', 'error')
                        return redirect(url_for('add_ordem_servico'))
                
                # Criar ordem no banco
                nova_ordem_db = OrdemServico(
                    numero_ordem=str(numero_ordem),
                    cliente_id=cliente_id,
                    tecnico_id=int(tecnico_id) if tecnico_id and tecnico_id != '' else None,
                    servico=servico,
                    tipo_aparelho=tipo_aparelho,
                    marca=marca,
                    modelo=modelo,
                    numero_serie=numero_serie,
                    defeitos_cliente=defeitos_cliente,
                    diagnostico_tecnico=diagnostico_tecnico,
                    pecas=pecas,
                    custo_pecas=total_pecas,
                    custo_mao_obra=float(custo_mao_obra) if custo_mao_obra else 0.00,
                    subtotal=subtotal,
                    desconto_percentual=desconto_percentual,
                    valor_desconto=valor_desconto,
                    cupom_id=cupom_id if cupom_usado else None,
                    total=total,
                    status=status,
                    prazo_estimado=prazo_estimado if prazo_estimado else None,
                    data=datetime.now()
                )
                db.session.add(nova_ordem_db)
                db.session.commit()
                
                # Atualizar cupom se usado
                if cupom_usado and use_database():
                    try:
                        cupom_db = Cupom.query.get(cupom_id)
                        if cupom_db:
                            cupom_db.usado = True
                            cupom_db.ordem_id = nova_ordem_db.id
                            cupom_db.data_uso = datetime.now()
                            db.session.commit()
                    except Exception as e:
                        print(f"Erro ao atualizar cupom: {e}")
                        db.session.rollback()
                
                # Gerar PDF da ordem
                cliente_dict = {
                    'id': cliente_db.id,
                    'nome': cliente_db.nome,
                    'email': cliente_db.email,
                    'telefone': cliente_db.telefone,
                    'cpf': cliente_db.cpf,
                    'endereco': cliente_db.endereco
                }
                ordem_dict = {
                    'id': nova_ordem_db.id,
                    'numero_ordem': nova_ordem_db.numero_ordem,
                    'servico': nova_ordem_db.servico,
                    'marca': nova_ordem_db.marca,
                    'modelo': nova_ordem_db.modelo,
                    'numero_serie': nova_ordem_db.numero_serie,
                    'defeitos_cliente': nova_ordem_db.defeitos_cliente,
                    'diagnostico_tecnico': nova_ordem_db.diagnostico_tecnico,
                    'pecas': nova_ordem_db.pecas or [],
                    'custo_pecas': float(nova_ordem_db.custo_pecas) if nova_ordem_db.custo_pecas else 0.00,
                    'custo_mao_obra': float(nova_ordem_db.custo_mao_obra) if nova_ordem_db.custo_mao_obra else 0.00,
                    'subtotal': float(nova_ordem_db.subtotal) if nova_ordem_db.subtotal else 0.00,
                    'desconto_percentual': float(nova_ordem_db.desconto_percentual) if nova_ordem_db.desconto_percentual else 0.00,
                    'valor_desconto': float(nova_ordem_db.valor_desconto) if nova_ordem_db.valor_desconto else 0.00,
                    'total': float(nova_ordem_db.total) if nova_ordem_db.total else 0.00,
                    'status': nova_ordem_db.status,
                    'prazo_estimado': nova_ordem_db.prazo_estimado,
                    'data': nova_ordem_db.data.strftime('%Y-%m-%d %H:%M:%S') if nova_ordem_db.data else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                pdf_result = gerar_pdf_ordem(cliente_dict, ordem_dict)
                if isinstance(pdf_result, dict):
                    nova_ordem_db.pdf_filename = pdf_result.get('pdf_filename', '')
                    nova_ordem_db.pdf_id = pdf_result.get('pdf_id')
                    db.session.commit()
                
                flash('Ordem de serviço emitida com sucesso!', 'success')
                return redirect(url_for('admin_ordens'))
            except Exception as e:
                print(f"Erro ao salvar ordem no banco: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except:
                    pass
                
                # Verificar se o erro é relacionado à tabela não existir
                error_str = str(e).lower()
                if 'does not exist' in error_str or 'relation' in error_str or 'table' in error_str:
                    # Tentar criar a tabela e salvar novamente
                    try:
                        with app.app_context():
                            db.create_all()
                            print("DEBUG: ✅ Tabelas criadas/verificadas após erro")
                            
                            # Tentar salvar a ordem novamente após criar a tabela
                            try:
                                # Verificar se cliente existe no banco
                                cliente_db = Cliente.query.get(cliente_id)
                                
                                # Se não encontrou no banco, tentar buscar no JSON e criar no banco
                                if not cliente_db:
                                    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
                                        data_json = json.load(f)
                                    
                                    cliente_json = next((c for c in data_json['clients'] if c.get('id') == cliente_id), None)
                                    if cliente_json:
                                        # Criar cliente no banco a partir do JSON
                                        cliente_db = Cliente(
                                            id=cliente_json['id'],
                                            nome=cliente_json.get('nome', ''),
                                            email=cliente_json.get('email', ''),
                                            telefone=cliente_json.get('telefone', ''),
                                            cpf=cliente_json.get('cpf', ''),
                                            endereco=cliente_json.get('endereco', ''),
                                            username=cliente_json.get('username', ''),
                                            password=cliente_json.get('password', ''),
                                            data_cadastro=datetime.strptime(cliente_json.get('data_cadastro', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S') if cliente_json.get('data_cadastro') else datetime.now()
                                        )
                                        db.session.add(cliente_db)
                                        db.session.commit()
                                    else:
                                        flash('Cliente não encontrado!', 'error')
                                        return redirect(url_for('add_ordem_servico'))
                                
                                # Criar ordem no banco
                                nova_ordem_db = OrdemServico(
                                    numero_ordem=str(numero_ordem),
                                    cliente_id=cliente_id,
                                    tecnico_id=int(tecnico_id) if tecnico_id and tecnico_id != '' else None,
                                    servico=servico,
                                    tipo_aparelho=tipo_aparelho,
                                    marca=marca,
                                    modelo=modelo,
                                    numero_serie=numero_serie,
                                    defeitos_cliente=defeitos_cliente,
                                    diagnostico_tecnico=diagnostico_tecnico,
                                    pecas=pecas,
                                    custo_pecas=total_pecas,
                                    custo_mao_obra=float(custo_mao_obra) if custo_mao_obra else 0.00,
                                    subtotal=subtotal,
                                    desconto_percentual=desconto_percentual,
                                    valor_desconto=valor_desconto,
                                    cupom_id=cupom_id if cupom_usado else None,
                                    total=total,
                                    status=status,
                                    prazo_estimado=prazo_estimado if prazo_estimado else None,
                                    data=datetime.now()
                                )
                                db.session.add(nova_ordem_db)
                                db.session.commit()
                                
                                # Atualizar cupom se usado
                                if cupom_usado and use_database():
                                    try:
                                        cupom_db = Cupom.query.get(cupom_id)
                                        if cupom_db:
                                            cupom_db.usado = True
                                            cupom_db.ordem_id = nova_ordem_db.id
                                            cupom_db.data_uso = datetime.now()
                                            db.session.commit()
                                    except Exception as cupom_error:
                                        print(f"Erro ao atualizar cupom: {cupom_error}")
                                        db.session.rollback()
                                
                                # Gerar PDF da ordem
                                cliente_dict = {
                                    'id': cliente_db.id,
                                    'nome': cliente_db.nome,
                                    'email': cliente_db.email,
                                    'telefone': cliente_db.telefone,
                                    'cpf': cliente_db.cpf,
                                    'endereco': cliente_db.endereco
                                }
                                ordem_dict = {
                                    'id': nova_ordem_db.id,
                                    'numero_ordem': nova_ordem_db.numero_ordem,
                                    'servico': nova_ordem_db.servico,
                                    'marca': nova_ordem_db.marca,
                                    'modelo': nova_ordem_db.modelo,
                                    'numero_serie': nova_ordem_db.numero_serie,
                                    'defeitos_cliente': nova_ordem_db.defeitos_cliente,
                                    'diagnostico_tecnico': nova_ordem_db.diagnostico_tecnico,
                                    'pecas': nova_ordem_db.pecas or [],
                                    'custo_pecas': float(nova_ordem_db.custo_pecas) if nova_ordem_db.custo_pecas else 0.00,
                                    'custo_mao_obra': float(nova_ordem_db.custo_mao_obra) if nova_ordem_db.custo_mao_obra else 0.00,
                                    'subtotal': float(nova_ordem_db.subtotal) if nova_ordem_db.subtotal else 0.00,
                                    'desconto_percentual': float(nova_ordem_db.desconto_percentual) if nova_ordem_db.desconto_percentual else 0.00,
                                    'valor_desconto': float(nova_ordem_db.valor_desconto) if nova_ordem_db.valor_desconto else 0.00,
                                    'total': float(nova_ordem_db.total) if nova_ordem_db.total else 0.00,
                                    'status': nova_ordem_db.status,
                                    'prazo_estimado': nova_ordem_db.prazo_estimado,
                                    'data': nova_ordem_db.data.strftime('%Y-%m-%d %H:%M:%S') if nova_ordem_db.data else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                
                                pdf_result = gerar_pdf_ordem(cliente_dict, ordem_dict)
                                if isinstance(pdf_result, dict):
                                    nova_ordem_db.pdf_filename = pdf_result.get('pdf_filename', '')
                                    nova_ordem_db.pdf_id = pdf_result.get('pdf_id')
                                    db.session.commit()
                                
                                flash('Ordem de serviço emitida com sucesso!', 'success')
                                return redirect(url_for('admin_ordens'))
                            except Exception as retry_error:
                                print(f"Erro ao salvar ordem após criar tabela: {retry_error}")
                                import traceback
                                traceback.print_exc()
                                flash(f'Erro ao salvar ordem após criar tabela: {str(retry_error)[:200]}. Tente novamente.', 'error')
                                return redirect(url_for('add_ordem_servico'))
                    except Exception as create_error:
                        print(f"Erro ao criar tabelas: {create_error}")
                        flash(f'Erro: Tabela não existe. Execute db.create_all() no banco de dados. Detalhes: {str(e)[:200]}', 'error')
                        return redirect(url_for('add_ordem_servico'))
                else:
                    flash(f'Erro ao salvar ordem: {str(e)[:200]}. Tente novamente.', 'error')
                    return redirect(url_for('add_ordem_servico'))
        
        # Fallback para JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cliente = next((c for c in data['clients'] if c.get('id') == cliente_id), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('add_ordem_servico'))
        
        # Atualizar cupom se usado (JSON)
        if cupom_usado and not use_database():
            nova_ordem_id = len(cliente.get('ordens', [])) + 1
            cupom_usado['usado'] = True
            cupom_usado['ordem_id'] = nova_ordem_id
            cupom_usado['data_uso'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Salvar atualização do cupom
            with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
                fidelidade_data = json.load(f)
            
            for i, c in enumerate(fidelidade_data['cupons']):
                if c.get('id') == cupom_id:
                    fidelidade_data['cupons'][i] = cupom_usado
                    break
            
            with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
                json.dump(fidelidade_data, f, ensure_ascii=False, indent=2)
        
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
            comprovante['pdf_filename'] = str(pdf_result) if pdf_result else ''
        
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
        # Remover comprovante (PDF já está no banco de dados, não precisa deletar do filesystem)
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
    if request.method == 'POST':
        descricao = request.form.get('descricao', '').strip()
        facebook = request.form.get('facebook', '').strip()
        instagram = request.form.get('instagram', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        endereco = request.form.get('endereco', '').strip()
        copyright_text = request.form.get('copyright', '').strip()
        whatsapp_float = request.form.get('whatsapp_float', '').strip()
        
        # Salvar no banco de dados se disponível
        if use_database():
            try:
                footer_obj = Footer.query.first()
                if not footer_obj:
                    footer_obj = Footer()
                    db.session.add(footer_obj)
                
                footer_obj.descricao = descricao
                footer_obj.redes_sociais = {
                    'facebook': facebook,
                    'instagram': instagram,
                    'whatsapp': whatsapp
                }
                footer_obj.contato = {
                    'telefone': telefone,
                    'email': email,
                    'endereco': endereco
                }
                footer_obj.copyright = copyright_text
                footer_obj.whatsapp_float = whatsapp_float
                
                db.session.commit()
                flash('Rodapé atualizado com sucesso!', 'success')
                return redirect(url_for('admin_footer'))
            except Exception as e:
                print(f"Erro ao salvar footer no banco: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except:
                    pass
                flash('Erro ao salvar rodapé. Tente novamente.', 'error')
                return redirect(url_for('admin_footer'))
        
        # Fallback para JSON
        init_footer_file()
        with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Atualizar dados
        data['descricao'] = descricao
        data['redes_sociais']['facebook'] = facebook
        data['redes_sociais']['instagram'] = instagram
        data['redes_sociais']['whatsapp'] = whatsapp
        data['contato']['telefone'] = telefone
        data['contato']['email'] = email
        data['contato']['endereco'] = endereco
        data['copyright'] = copyright_text
        data['whatsapp_float'] = whatsapp_float
        
        with open(FOOTER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Rodapé atualizado com sucesso!', 'success')
        return redirect(url_for('admin_footer'))
    
    # GET - Carregar dados
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': footer_obj.redes_sociais or {
                        'facebook': '',
                        'instagram': '',
                        'whatsapp': ''
                    },
                    'contato': footer_obj.contato or {
                        'telefone': '',
                        'email': '',
                        'endereco': ''
                    },
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
            else:
                # Criar footer padrão se não existir
                footer_data = {
                    'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
                    'redes_sociais': {
                        'facebook': '',
                        'instagram': '',
                        'whatsapp': ''
                    },
                    'contato': {
                        'telefone': '',
                        'email': '',
                        'endereco': ''
                    },
                    'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
                    'whatsapp_float': ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
            footer_data = None
    
    # Fallback para JSON
    if not use_database() or footer_data is None:
        init_footer_file()
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
    footer_data = None
    
    # Tentar carregar do banco de dados primeiro
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': footer_obj.redes_sociais or {
                        'facebook': '',
                        'instagram': '',
                        'whatsapp': ''
                    },
                    'contato': footer_obj.contato or {
                        'telefone': '',
                        'email': '',
                        'endereco': ''
                    },
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco em inject_footer: {e}")
            footer_data = None
    
    # Fallback para JSON se não encontrou no banco
    if footer_data is None:
        init_footer_file()
        try:
            with open(FOOTER_FILE, 'r', encoding='utf-8') as f:
                footer_data = json.load(f)
        except:
            footer_data = None
    
    return {'footer': footer_data}

@app.context_processor
def inject_servicos():
    """Injeta serviços ativos em todos os templates"""
    servicos = []
    
    # Tentar carregar do banco de dados primeiro
    if use_database():
        try:
            servicos_db = Servico.query.filter_by(ativo=True).order_by(Servico.ordem).all()
            for s in servicos_db:
                servicos.append({
                    'id': s.id,
                    'nome': s.nome,
                    'descricao': s.descricao,
                    'imagem': f'/admin/servicos/imagem/{s.imagem_id}' if s.imagem_id else (s.imagem or 'img/placeholder.png'),
                    'ordem': s.ordem,
                    'ativo': s.ativo
                })
        except Exception as e:
            print(f"Erro ao carregar serviços do banco em inject_servicos: {e}")
            servicos = []
    
    # Fallback para JSON se não encontrou no banco
    if not servicos:
        init_data_file()
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                services_data = json.load(f)
            servicos = [s for s in services_data.get('services', []) if s.get('ativo', True)]
            servicos = sorted(servicos, key=lambda x: x.get('ordem', 999))
        except:
            servicos = []
    
    return {'servicos_footer': servicos}

@app.context_processor
def inject_tipos_servico():
    """Injeta lista fixa de tipos de serviço em todos os templates"""
    return {'tipos_servico': TIPOS_SERVICO}

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
                # pylint: disable=import-outside-toplevel
                from twilio.rest import Client  # type: ignore # noqa: F401
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

# ==================== FORNECEDORES ====================
@app.route('/admin/fornecedores')
@login_required
def admin_fornecedores():
    """Lista todos os fornecedores cadastrados"""
    busca = request.args.get('busca', '').strip()
    
    # Garantir que a tabela existe antes de listar
    if use_database():
        garantir_tabela_fornecedores()
    
    if use_database():
        try:
            query = Fornecedor.query
            
            # Aplicar filtro de busca se fornecido
            if busca:
                # Busca case-insensitive por nome ou tipo_servico
                from sqlalchemy import or_
                busca_pattern = f'%{busca}%'
                query = query.filter(
                    or_(
                        Fornecedor.nome.ilike(busca_pattern),
                        Fornecedor.tipo_servico.ilike(busca_pattern)
                    )
                )
            
            fornecedores_db = query.order_by(Fornecedor.nome).all()
            fornecedores = []
            for f in fornecedores_db:
                fornecedores.append({
                    'id': f.id,
                    'nome': f.nome,
                    'contato': f.contato or '',
                    'telefone': f.telefone or '',
                    'email': f.email or '',
                    'endereco': f.endereco or '',
                    'cnpj': f.cnpj or '',
                    'tipo_servico': f.tipo_servico or '',
                    'observacoes': f.observacoes or '',
                    'ativo': f.ativo,
                    'data_cadastro': f.data_cadastro.strftime('%d/%m/%Y') if f.data_cadastro else ''
                })
        except Exception as e:
            print(f"Erro ao buscar fornecedores do banco: {e}")
            fornecedores = []
    else:
        fornecedores = []
    
    return render_template('admin/fornecedores.html', fornecedores=fornecedores)

@app.route('/admin/fornecedores/add', methods=['GET', 'POST'])
@login_required
def add_fornecedor():
    """Adiciona um novo fornecedor"""
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        contato = request.form.get('contato', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        endereco = request.form.get('endereco', '').strip()
        cnpj = request.form.get('cnpj', '').strip()
        tipo_servico = request.form.get('tipo_servico', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        ativo = request.form.get('ativo') == 'on'
        
        if not nome:
            flash('Nome é obrigatório!', 'error')
            return redirect(url_for('add_fornecedor'))
        
        if use_database():
            # Garantir que a tabela existe antes de tentar adicionar
            if not garantir_tabela_fornecedores():
                flash('Não foi possível garantir que a tabela de fornecedores existe. Tente usar o botão "Criar Tabela no Banco".', 'error')
                return redirect(url_for('add_fornecedor'))
            
            try:
                fornecedor = Fornecedor(
                    nome=nome,
                    contato=contato if contato else None,
                    telefone=telefone if telefone else None,
                    email=email if email else None,
                    endereco=endereco if endereco else None,
                    cnpj=cnpj if cnpj else None,
                    tipo_servico=tipo_servico if tipo_servico else None,
                    observacoes=observacoes if observacoes else None,
                    ativo=ativo
                )
                db.session.add(fornecedor)
                db.session.commit()
                flash('Fornecedor cadastrado com sucesso!', 'success')
                return redirect(url_for('admin_fornecedores'))
            except Exception as e:
                print(f"Erro ao adicionar fornecedor no banco: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except:
                    pass
                
                error_msg = str(e)
                if 'relation' in error_msg.lower() and 'does not exist' in error_msg.lower():
                    # Tentar criar novamente e adicionar
                    if garantir_tabela_fornecedores():
                        try:
                            fornecedor = Fornecedor(
                                nome=nome,
                                contato=contato if contato else None,
                                telefone=telefone if telefone else None,
                                email=email if email else None,
                                endereco=endereco if endereco else None,
                                cnpj=cnpj if cnpj else None,
                                tipo_servico=tipo_servico if tipo_servico else None,
                                observacoes=observacoes if observacoes else None,
                                ativo=ativo
                            )
                            db.session.add(fornecedor)
                            db.session.commit()
                            flash('Tabela criada e fornecedor cadastrado com sucesso!', 'success')
                            return redirect(url_for('admin_fornecedores'))
                        except Exception as e2:
                            flash('Erro ao adicionar fornecedor após criar tabela. Tente novamente.', 'error')
                    else:
                        flash('Não foi possível criar a tabela. Use o botão "Criar Tabela no Banco" na página de fornecedores.', 'error')
                elif 'duplicate key' in error_msg.lower() or 'unique constraint' in error_msg.lower():
                    flash('Já existe um fornecedor com esses dados. Verifique os campos únicos.', 'error')
                else:
                    flash(f'Erro ao adicionar fornecedor: {error_msg[:150]}', 'error')
                return redirect(url_for('add_fornecedor'))
        else:
            flash('Banco de dados não disponível.', 'error')
            return redirect(url_for('add_fornecedor'))
    
    return render_template('admin/add_fornecedor.html')

@app.route('/admin/fornecedores/<int:fornecedor_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_fornecedor(fornecedor_id):
    """Edita um fornecedor existente"""
    if use_database():
        try:
            fornecedor = Fornecedor.query.get(fornecedor_id)
            if not fornecedor:
                flash('Fornecedor não encontrado!', 'error')
                return redirect(url_for('admin_fornecedores'))
            
            if request.method == 'POST':
                fornecedor.nome = request.form.get('nome', '').strip()
                fornecedor.contato = request.form.get('contato', '').strip() or None
                fornecedor.telefone = request.form.get('telefone', '').strip() or None
                fornecedor.email = request.form.get('email', '').strip() or None
                fornecedor.endereco = request.form.get('endereco', '').strip() or None
                fornecedor.cnpj = request.form.get('cnpj', '').strip() or None
                fornecedor.tipo_servico = request.form.get('tipo_servico', '').strip() or None
                fornecedor.observacoes = request.form.get('observacoes', '').strip() or None
                fornecedor.ativo = request.form.get('ativo') == 'on'
                
                db.session.commit()
                flash('Fornecedor atualizado com sucesso!', 'success')
                return redirect(url_for('admin_fornecedores'))
            
            fornecedor_dict = {
                'id': fornecedor.id,
                'nome': fornecedor.nome,
                'contato': fornecedor.contato or '',
                'telefone': fornecedor.telefone or '',
                'email': fornecedor.email or '',
                'endereco': fornecedor.endereco or '',
                'cnpj': fornecedor.cnpj or '',
                'observacoes': fornecedor.observacoes or '',
                'ativo': fornecedor.ativo,
                'data_cadastro': fornecedor.data_cadastro.strftime('%d/%m/%Y') if fornecedor.data_cadastro else ''
            }
            return render_template('admin/edit_fornecedor.html', fornecedor=fornecedor_dict)
        except Exception as e:
            print(f"Erro ao editar fornecedor no banco: {e}")
            flash('Erro ao editar fornecedor.', 'error')
            return redirect(url_for('admin_fornecedores'))
    
    flash('Banco de dados não disponível.', 'error')
    return redirect(url_for('admin_fornecedores'))

@app.route('/admin/fornecedores/<int:fornecedor_id>/delete', methods=['POST'])
@login_required
def delete_fornecedor(fornecedor_id):
    """Deleta um fornecedor"""
    if use_database():
        try:
            fornecedor = Fornecedor.query.get(fornecedor_id)
            if fornecedor:
                db.session.delete(fornecedor)
                db.session.commit()
                flash('Fornecedor excluído com sucesso!', 'success')
            else:
                flash('Fornecedor não encontrado!', 'error')
        except Exception as e:
            print(f"Erro ao deletar fornecedor: {e}")
            flash('Erro ao excluir fornecedor.', 'error')
    
    return redirect(url_for('admin_fornecedores'))

@app.route('/admin/fornecedores/create-table', methods=['POST'])
@login_required
def create_fornecedores_table():
    """Cria a tabela de fornecedores manualmente"""
    if use_database():
        if garantir_tabela_fornecedores():
            flash('Tabela de fornecedores criada/verificada com sucesso!', 'success')
        else:
            flash('Erro ao criar tabela de fornecedores. Verifique os logs do servidor.', 'error')
    else:
        flash('Banco de dados não disponível.', 'error')
    
    return redirect(url_for('admin_fornecedores'))

# ==================== FUNÇÕES AUXILIARES ====================

def slugify(text):
    """Converte texto para slug (URL-friendly)"""
    import re
    import unicodedata
    
    # Normalizar e remover acentos
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Converter para minúsculas e substituir espaços por hífens
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')
    
    return text

def salvar_imagem_banco(file):
    """Salva imagem no banco de dados e retorna objeto Imagem"""
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        return None
    
    # Verificar tamanho
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return None
    
    # Ler dados
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
    
    try:
        imagem = Imagem(
            nome=secure_filename(file.filename),
            dados=file_data,
            tipo_mime=imagem_tipo,
            tamanho=file_size,
            referencia=f'produto_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )
        db.session.add(imagem)
        db.session.commit()
        return imagem
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar imagem: {e}")
        return None

# ==================== ADMIN - LOJA ====================

@app.route('/admin/loja/produtos')
@login_required
def admin_produtos():
    """Lista todos os produtos"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        produtos = Produto.query.order_by(Produto.ordem, Produto.nome).all()
        categorias = Categoria.query.order_by(Categoria.nome).all()
        
        produtos_list = []
        for p in produtos:
            if p.imagem_id:
                imagem_url = f'/admin/produtos/imagem/{p.imagem_id}'
            elif p.imagem:
                imagem_url = p.imagem
            else:
                imagem_url = ''
            
            produtos_list.append({
                'id': p.id,
                'nome': p.nome,
                'slug': p.slug,
                'descricao': p.descricao,
                'preco': float(p.preco),
                'preco_promocional': float(p.preco_promocional) if p.preco_promocional else None,
                'estoque': p.estoque,
                'imagem': imagem_url,
                'categoria_id': p.categoria_id,
                'categoria_nome': p.categoria.nome if p.categoria else None,
                'marca': p.marca,
                'modelo': p.modelo,
                'sku': p.sku,
                'ativo': p.ativo,
                'destaque': p.destaque,
                'ordem': p.ordem
            })
        
        return render_template('admin/produtos.html', produtos=produtos_list, categorias=categorias)
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
        flash('Erro ao carregar produtos.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/loja/produtos/add', methods=['GET', 'POST'])
@login_required
def admin_add_produto():
    """Adicionar novo produto"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_produtos'))
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            slug = request.form.get('slug') or slugify(nome)
            descricao = request.form.get('descricao', '')
            descricao_completa = request.form.get('descricao_completa', '')
            categoria_id = request.form.get('categoria_id', type=int) or None
            preco = float(request.form.get('preco', 0))
            preco_promocional = request.form.get('preco_promocional')
            preco_promocional = float(preco_promocional) if preco_promocional else None
            estoque = int(request.form.get('estoque', 0))
            sku = request.form.get('sku', '')
            marca = request.form.get('marca', '')
            modelo = request.form.get('modelo', '')
            peso = request.form.get('peso')
            peso = float(peso) if peso else None
            dimensoes = request.form.get('dimensoes', '')
            ativo = request.form.get('ativo') == 'on'
            destaque = request.form.get('destaque') == 'on'
            ordem = int(request.form.get('ordem', 1))
            
            # Verificar se slug já existe
            produto_existente = Produto.query.filter_by(slug=slug).first()
            if produto_existente:
                flash('Já existe um produto com este slug. Use um slug diferente.', 'error')
                categorias = Categoria.query.order_by(Categoria.nome).all()
                return render_template('admin/add_produto.html', categorias=categorias)
            
            produto = Produto(
                nome=nome,
                slug=slug,
                descricao=descricao,
                descricao_completa=descricao_completa,
                categoria_id=categoria_id,
                preco=preco,
                preco_promocional=preco_promocional,
                estoque=estoque,
                sku=sku,
                marca=marca,
                modelo=modelo,
                peso=peso,
                dimensoes=dimensoes,
                ativo=ativo,
                destaque=destaque,
                ordem=ordem
            )
            
            # Upload de imagem
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename:
                    imagem = salvar_imagem_banco(file)
                    if imagem:
                        produto.imagem_id = imagem.id
            
            db.session.add(produto)
            db.session.commit()
            
            flash('Produto adicionado com sucesso!', 'success')
            return redirect(url_for('admin_produtos'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao adicionar produto: {e}")
            flash(f'Erro ao adicionar produto: {str(e)}', 'error')
    
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return render_template('admin/add_produto.html', categorias=categorias)

@app.route('/admin/loja/produtos/<int:produto_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_produto(produto_id):
    """Editar produto"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_produtos'))
    
    produto = Produto.query.get_or_404(produto_id)
    
    if request.method == 'POST':
        try:
            produto.nome = request.form.get('nome')
            slug = request.form.get('slug') or slugify(produto.nome)
            # Verificar se slug mudou e se já existe
            if slug != produto.slug:
                produto_existente = Produto.query.filter_by(slug=slug).first()
                if produto_existente and produto_existente.id != produto.id:
                    flash('Já existe um produto com este slug. Use um slug diferente.', 'error')
                    categorias = Categoria.query.order_by(Categoria.nome).all()
                    return render_template('admin/edit_produto.html', produto=produto, categorias=categorias)
                produto.slug = slug
            
            produto.descricao = request.form.get('descricao', '')
            produto.descricao_completa = request.form.get('descricao_completa', '')
            produto.categoria_id = request.form.get('categoria_id', type=int) or None
            produto.preco = float(request.form.get('preco', 0))
            preco_promocional = request.form.get('preco_promocional')
            produto.preco_promocional = float(preco_promocional) if preco_promocional else None
            produto.estoque = int(request.form.get('estoque', 0))
            produto.sku = request.form.get('sku', '')
            produto.marca = request.form.get('marca', '')
            produto.modelo = request.form.get('modelo', '')
            peso = request.form.get('peso')
            produto.peso = float(peso) if peso else None
            produto.dimensoes = request.form.get('dimensoes', '')
            produto.ativo = request.form.get('ativo') == 'on'
            produto.destaque = request.form.get('destaque') == 'on'
            produto.ordem = int(request.form.get('ordem', 1))
            
            # Upload de nova imagem
            if 'imagem' in request.files:
                file = request.files['imagem']
                if file and file.filename:
                    imagem = salvar_imagem_banco(file)
                    if imagem:
                        produto.imagem_id = imagem.id
            
            db.session.commit()
            flash('Produto atualizado com sucesso!', 'success')
            return redirect(url_for('admin_produtos'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao editar produto: {e}")
            flash(f'Erro ao editar produto: {str(e)}', 'error')
    
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return render_template('admin/edit_produto.html', produto=produto, categorias=categorias)

@app.route('/admin/loja/produtos/<int:produto_id>/delete', methods=['POST'])
@login_required
def admin_delete_produto(produto_id):
    """Excluir produto"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_produtos'))
    
    try:
        produto = Produto.query.get_or_404(produto_id)
        db.session.delete(produto)
        db.session.commit()
        flash('Produto excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir produto: {e}")
        flash('Erro ao excluir produto.', 'error')
    
    return redirect(url_for('admin_produtos'))

@app.route('/admin/produtos/imagem/<int:imagem_id>')
def produto_imagem(imagem_id):
    """Retorna imagem do produto"""
    if not use_database():
        return '', 404
    
    try:
        imagem = Imagem.query.get_or_404(imagem_id)
        return send_file(
            BytesIO(imagem.dados),
            mimetype=imagem.tipo_mime,
            download_name=imagem.nome or 'imagem.jpg'
        )
    except:
        return '', 404

@app.route('/admin/loja/categorias')
@login_required
def admin_categorias():
    """Lista todas as categorias"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        categorias = Categoria.query.order_by(Categoria.nome).all()
        return render_template('admin/categorias.html', categorias=categorias)
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        flash('Erro ao carregar categorias.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/loja/categorias/add', methods=['GET', 'POST'])
@login_required
def admin_add_categoria():
    """Adicionar nova categoria"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_categorias'))
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            slug = request.form.get('slug') or slugify(nome)
            descricao = request.form.get('descricao', '')
            ativo = request.form.get('ativo') == 'on'
            ordem = int(request.form.get('ordem', 1))
            
            # Verificar se slug já existe
            categoria_existente = Categoria.query.filter_by(slug=slug).first()
            if categoria_existente:
                flash('Já existe uma categoria com este slug.', 'error')
                return render_template('admin/add_categoria.html')
            
            categoria = Categoria(
                nome=nome,
                slug=slug,
                descricao=descricao,
                ativo=ativo,
                ordem=ordem
            )
            
            db.session.add(categoria)
            db.session.commit()
            
            flash('Categoria adicionada com sucesso!', 'success')
            return redirect(url_for('admin_categorias'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao adicionar categoria: {e}")
            flash(f'Erro ao adicionar categoria: {str(e)}', 'error')
    
    return render_template('admin/add_categoria.html')

@app.route('/admin/loja/categorias/<int:categoria_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_categoria(categoria_id):
    """Editar categoria"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_categorias'))
    
    categoria = Categoria.query.get_or_404(categoria_id)
    
    if request.method == 'POST':
        try:
            categoria.nome = request.form.get('nome')
            slug = request.form.get('slug') or slugify(categoria.nome)
            if slug != categoria.slug:
                categoria_existente = Categoria.query.filter_by(slug=slug).first()
                if categoria_existente and categoria_existente.id != categoria.id:
                    flash('Já existe uma categoria com este slug.', 'error')
                    return render_template('admin/edit_categoria.html', categoria=categoria)
                categoria.slug = slug
            
            categoria.descricao = request.form.get('descricao', '')
            categoria.ativo = request.form.get('ativo') == 'on'
            categoria.ordem = int(request.form.get('ordem', 1))
            
            db.session.commit()
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('admin_categorias'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao editar categoria: {e}")
            flash(f'Erro ao editar categoria: {str(e)}', 'error')
    
    return render_template('admin/edit_categoria.html', categoria=categoria)

@app.route('/admin/loja/categorias/<int:categoria_id>/delete', methods=['POST'])
@login_required
def admin_delete_categoria(categoria_id):
    """Excluir categoria"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_categorias'))
    
    try:
        categoria = Categoria.query.get_or_404(categoria_id)
        # Verificar se há produtos usando esta categoria
        produtos_count = Produto.query.filter_by(categoria_id=categoria_id).count()
        if produtos_count > 0:
            flash(f'Não é possível excluir esta categoria. Ela possui {produtos_count} produto(s) associado(s).', 'error')
            return redirect(url_for('admin_categorias'))
        
        db.session.delete(categoria)
        db.session.commit()
        flash('Categoria excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir categoria: {e}")
        flash('Erro ao excluir categoria.', 'error')
    
    return redirect(url_for('admin_categorias'))

@app.route('/admin/loja/pedidos')
@login_required
def admin_pedidos():
    """Lista todos os pedidos"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        pedidos = Pedido.query.order_by(Pedido.data_pedido.desc()).all()
        pedidos_list = []
        for p in pedidos:
            pedidos_list.append({
                'id': p.id,
                'numero': p.numero,
                'nome': p.nome,
                'email': p.email,
                'telefone': p.telefone,
                'status': p.status,
                'total': float(p.total),
                'data_pedido': p.data_pedido.strftime('%d/%m/%Y %H:%M') if p.data_pedido else '',
                'itens_count': len(p.itens)
            })
        return render_template('admin/pedidos.html', pedidos=pedidos_list)
    except Exception as e:
        print(f"Erro ao buscar pedidos: {e}")
        flash('Erro ao carregar pedidos.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/loja/pedidos/<int:pedido_id>')
@login_required
def admin_pedido_detalhes(pedido_id):
    """Detalhes de um pedido"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_pedidos'))
    
    try:
        pedido = Pedido.query.get_or_404(pedido_id)
        
        itens_list = []
        for item in pedido.itens:
            if item.produto:
                if item.produto.imagem_id:
                    imagem_url = f'/admin/produtos/imagem/{item.produto.imagem_id}'
                elif item.produto.imagem:
                    imagem_url = item.produto.imagem
                else:
                    imagem_url = ''
            else:
                imagem_url = ''
            
            itens_list.append({
                'id': item.id,
                'produto_nome': item.produto.nome if item.produto else 'Produto removido',
                'produto_imagem': imagem_url,
                'quantidade': item.quantidade,
                'preco_unitario': float(item.preco_unitario),
                'subtotal': float(item.subtotal)
            })
        
        pedido_dict = {
            'id': pedido.id,
            'numero': pedido.numero,
            'nome': pedido.nome,
            'email': pedido.email,
            'telefone': pedido.telefone,
            'cpf': pedido.cpf,
            'endereco': pedido.endereco,
            'cep': pedido.cep,
            'cidade': pedido.cidade,
            'estado': pedido.estado,
            'status': pedido.status,
            'total': float(pedido.total),
            'data_pedido': pedido.data_pedido.strftime('%d/%m/%Y %H:%M') if pedido.data_pedido else '',
            'itens': itens_list
        }
        
        return render_template('admin/pedido_detalhes.html', pedido=pedido_dict)
    except Exception as e:
        print(f"Erro ao buscar pedido: {e}")
        flash('Erro ao carregar pedido.', 'error')
        return redirect(url_for('admin_pedidos'))

@app.route('/admin/loja/pedidos/<int:pedido_id>/status', methods=['POST'])
@login_required
def admin_atualizar_status_pedido(pedido_id):
    """Atualizar status do pedido"""
    if not use_database():
        flash('Banco de dados não disponível.', 'error')
        return redirect(url_for('admin_pedidos'))
    
    try:
        pedido = Pedido.query.get_or_404(pedido_id)
        novo_status = request.form.get('status')
        
        if novo_status in ['pendente', 'processando', 'enviado', 'entregue', 'cancelado']:
            pedido.status = novo_status
            db.session.commit()
            flash('Status do pedido atualizado com sucesso!', 'success')
        else:
            flash('Status inválido.', 'error')
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar status: {e}")
        flash('Erro ao atualizar status do pedido.', 'error')
    
    return redirect(url_for('admin_pedido_detalhes', pedido_id=pedido_id))

@app.route('/sitemap.xml')
def sitemap():
    """Gera sitemap.xml dinâmico"""
    from flask import make_response
    
    base_url = request.url_root.rstrip('/')
    
    urls = [
        {'loc': f'{base_url}/', 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': f'{base_url}/servicos', 'changefreq': 'weekly', 'priority': '0.9'},
        {'loc': f'{base_url}/sobre', 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': f'{base_url}/contato', 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': f'{base_url}/agendamento', 'changefreq': 'weekly', 'priority': '0.8'},
        {'loc': f'{base_url}/rastrear', 'changefreq': 'weekly', 'priority': '0.7'},
    ]
    
    # Adicionar serviços dinâmicos se disponíveis
    if use_database():
        try:
            servicos = Servico.query.filter_by(ativo=True).all()
            for servico in servicos:
                urls.append({
                    'loc': f'{base_url}/servicos',
                    'changefreq': 'weekly',
                    'priority': '0.7'
                })
        except:
            pass
    
    sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
'''
    
    for url in urls:
        sitemap_xml += f'''  <url>
    <loc>{url['loc']}</loc>
    <changefreq>{url['changefreq']}</changefreq>
    <priority>{url['priority']}</priority>
  </url>
'''
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/robots.txt')
def robots():
    """Gera robots.txt"""
    from flask import make_response
    
    base_url = request.url_root.rstrip('/')
    
    robots_txt = f'''User-agent: *
Allow: /
Disallow: /admin/
Disallow: /client/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
'''
    
    response = make_response(robots_txt)
    response.headers['Content-Type'] = 'text/plain'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)

