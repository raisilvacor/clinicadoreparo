from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_file, Response
from datetime import datetime
import json
import os
import random
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models import db, Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom, Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Contato, Imagem, PDFDocument, Fornecedor, ReparoRealizado, Video, PaginaServico, OrcamentoArCondicionado, OrcamentoArCondicionado

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sua_chave_secreta_aqui_altere_em_producao')

# Configurações do Mercado Pago (REMOVIDO - sistema de loja removido)

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
                'connect_timeout': 5  # Reduzido de 10 para 5 segundos
            },
            'pool_pre_ping': True,  # Verificar conexão antes de usar
            'pool_recycle': 300,  # Reciclar conexões a cada 5 minutos
            'pool_timeout': 5,  # Timeout para obter conexão do pool
            'max_overflow': 0  # Não criar conexões extras
        }
        
        # Inicializar o banco de dados
        # IMPORTANTE: db.init_app() deve ser chamado DEPOIS de configurar SQLALCHEMY_DATABASE_URI
        db.init_app(app)
        
        # Criar tabelas se não existirem (apenas se conseguir conectar) - com timeout
        try:
            with app.app_context():
                # Forçar criação do engine e tabelas
                # Importar explicitamente todos os modelos para garantir que sejam registrados
                from models import Fornecedor, Video, PaginaServico  # Garantir que todos os modelos estão importados
                
                # Apenas criar tabelas, sem queries pesadas
                try:
                    db.create_all()
                    print("DEBUG: ✅ Tabelas criadas/verificadas no banco de dados")
                    
                    # Garantir que a coluna pagina_servico_id existe (importante para funcionalidade completa)
                    try:
                        garantir_coluna_pagina_servico_id()
                    except Exception as col_error:
                        print(f"DEBUG: ⚠️ Aviso ao criar coluna pagina_servico_id (não crítico): {col_error}")
                except Exception as create_error:
                    print(f"DEBUG: ⚠️ Aviso ao criar tabelas (não crítico): {create_error}")
                    # Continuar mesmo se der erro
                
                # Criar dados padrão de forma assíncrona/não-bloqueante (apenas tentar, não bloquear)
                # Essas operações serão feitas sob demanda quando necessário
                print("DEBUG: ✅ Inicialização do banco concluída (dados padrão serão criados sob demanda)")
                DB_AVAILABLE = True
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
    'Ar-condicionado',
    'Geladeira',
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

# Cache para verificar se a coluna existe (evita múltiplas queries)
_pagina_servico_id_column_exists = None

def garantir_coluna_pagina_servico_id():
    """Garante que a coluna pagina_servico_id existe na tabela servicos, criando se necessário (otimizado)"""
    global _pagina_servico_id_column_exists
    
    # Se já verificamos antes e existe, retornar True (cache)
    if _pagina_servico_id_column_exists is True:
        return True
    
    if not use_database():
        _pagina_servico_id_column_exists = False
        return False
    
    try:
        # Verificação rápida usando SQL direto (mais eficiente que inspect)
        engine = db.engine
        try:
            with engine.connect() as conn:
                result = conn.execute(db.text("""
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'servicos' 
                    AND column_name = 'pagina_servico_id'
                    LIMIT 1
                """))
                if result.fetchone():
                    _pagina_servico_id_column_exists = True
                    return True
        except Exception as check_error:
            # Se der erro na verificação, tentar criar (pode ser que não exista)
            print(f"Aviso ao verificar coluna: {check_error}")
        
        # Coluna não existe, criar agora (com timeout implícito via pool)
        print("Coluna pagina_servico_id não existe. Criando...")
        try:
            # Usar uma transação simples e rápida
            with engine.begin() as conn:
                # Adicionar coluna (IF NOT EXISTS evita erro se já existir)
                conn.execute(db.text("""
                    ALTER TABLE servicos
                    ADD COLUMN IF NOT EXISTS pagina_servico_id INTEGER
                """))
                # Adicionar foreign key constraint apenas se não existir
                conn.execute(db.text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'fk_servicos_pagina_servico'
                        ) THEN
                            ALTER TABLE servicos
                            ADD CONSTRAINT fk_servicos_pagina_servico
                            FOREIGN KEY (pagina_servico_id)
                            REFERENCES paginas_servicos(id)
                            ON DELETE SET NULL;
                        END IF;
                    EXCEPTION WHEN OTHERS THEN
                        -- Ignorar se já existe
                        NULL;
                    END $$;
                """))
                # Criar índice (IF NOT EXISTS evita erro se já existir)
                conn.execute(db.text("""
                    CREATE INDEX IF NOT EXISTS idx_servicos_pagina_servico_id 
                    ON servicos(pagina_servico_id)
                """))
            print("✅ Coluna pagina_servico_id criada com sucesso!")
            _pagina_servico_id_column_exists = True
            return True
        except Exception as create_error:
            # Se der erro, pode ser que já exista ou houve problema de permissão
            error_str = str(create_error).lower()
            if 'already exists' in error_str or 'duplicate' in error_str or 'exists' in error_str:
                # Se já existe, marcar como True
                _pagina_servico_id_column_exists = True
                return True
            print(f"Erro ao criar coluna pagina_servico_id: {create_error}")
            _pagina_servico_id_column_exists = False
            return False
    except Exception as e:
        print(f"Erro ao verificar/criar coluna pagina_servico_id: {e}")
        _pagina_servico_id_column_exists = False
        return False

def coluna_pagina_servico_id_existe():
    """Verifica se a coluna pagina_servico_id existe (cria se não existir)"""
    return garantir_coluna_pagina_servico_id()

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

@app.route('/favicon.ico')
def favicon():
    """Serve o favicon do site"""
    try:
        return send_file('static/img/favi.ico', mimetype='image/x-icon')
    except Exception as e:
        # Se não encontrar, retornar 404
        return '', 404

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
        # Se não usar banco, criar footer padrão (não usar JSON)
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
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
            
            # Buscar pagina_slug usando SQL direto
            pagina_slug = None
            global _pagina_servico_id_column_exists
            
            # Garantir que a coluna existe (apenas se ainda não soubermos que não existe)
            if _pagina_servico_id_column_exists is not False:
                if _pagina_servico_id_column_exists is not True:
                    garantir_coluna_pagina_servico_id()
                
                # Tentar buscar apenas se a coluna existe ou pode existir
                if _pagina_servico_id_column_exists is True:
                    try:
                        result = db.session.execute(
                            db.text("SELECT pagina_servico_id FROM servicos WHERE id = :servico_id"),
                            {'servico_id': s.id}
                        ).fetchone()
                        if result and result[0]:
                            pagina_servico_id = result[0]
                            pagina_result = db.session.execute(
                                db.text("SELECT slug FROM paginas_servicos WHERE id = :pagina_id AND ativo = true"),
                                {'pagina_id': pagina_servico_id}
                            ).fetchone()
                            if pagina_result:
                                pagina_slug = pagina_result[0]
                    except Exception as e:
                        # Se der erro, fazer rollback e verificar se é problema de coluna
                        error_str = str(e).lower()
                        try:
                            db.session.rollback()
                        except:
                            pass
                        if 'column' in error_str and ('does not exist' in error_str or 'undefined column' in error_str):
                            # Se a coluna realmente não existe, resetar cache e tentar criar uma última vez
                            _pagina_servico_id_column_exists = None
                            if garantir_coluna_pagina_servico_id():
                                # Tentar ler novamente
                                try:
                                    result = db.session.execute(
                                        db.text("SELECT pagina_servico_id FROM servicos WHERE id = :servico_id"),
                                        {'servico_id': s.id}
                                    ).fetchone()
                                    if result and result[0]:
                                        pagina_servico_id = result[0]
                                        pagina_result = db.session.execute(
                                            db.text("SELECT slug FROM paginas_servicos WHERE id = :pagina_id AND ativo = true"),
                                            {'pagina_id': pagina_servico_id}
                                        ).fetchone()
                                        if pagina_result:
                                            pagina_slug = pagina_result[0]
                                except:
                                    pass
            
            servicos.append({
                'id': s.id,
                'nome': s.nome,
                'descricao': s.descricao,
                'imagem': imagem_url,
                'ordem': s.ordem,
                'ativo': s.ativo,
                'pagina_slug': pagina_slug
            })
    else:
        init_data_file()
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            services_data = json.load(f)
        servicos = [s for s in services_data.get('services', []) if s.get('ativo', True)]
        servicos = sorted(servicos, key=lambda x: x.get('ordem', 999))
    
    # Carregar reparos realizados (galeria)
    if use_database():
        try:
            reparos_db = ReparoRealizado.query.filter_by(ativo=True).order_by(ReparoRealizado.ordem).limit(6).all()
        except Exception as e:
            print(f"Erro ao carregar reparos realizados do banco: {e}")
            reparos_db = []
        reparos = []
        for r in reparos_db:
            if r.imagem_obj:
                imagem_url = f'/admin/reparos/imagem/{r.imagem_id}'
            else:
                imagem_url = 'img/placeholder.png'
            
            reparos.append({
                'id': r.id,
                'titulo': r.titulo or '',
                'descricao': r.descricao or '',
                'imagem_url': imagem_url,
                'imagem_id': r.imagem_id
            })
    else:
        reparos = []
    
    # Carregar vídeos do YouTube (últimos 6)
    if use_database():
        try:
            videos_db = Video.query.filter_by(ativo=True).order_by(Video.ordem, Video.data_criacao.desc()).limit(6).all()
        except Exception as e:
            print(f"Erro ao carregar vídeos do banco: {e}")
            videos_db = []
        videos = []
        for v in videos_db:
            videos.append({
                'id': v.id,
                'titulo': v.titulo,
                'link_youtube': v.link_youtube,
                'video_id': v.get_video_id(),
                'embed_url': v.get_embed_url(),
                'thumbnail_url': v.get_thumbnail_url(),
                'ordem': v.ordem
            })
    else:
        videos = []
    
    return render_template('index.html', slides=slides, footer=footer_data, marcas=marcas, milestones=milestones, servicos=servicos, reparos=reparos, videos=videos)

@app.route('/reparos')
def todos_reparos():
    """Página que exibe todos os reparos realizados"""
    # Carregar footer do banco de dados
    footer_data = None
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                contato = footer_obj.contato if footer_obj.contato else {}
                redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': redes_sociais,
                    'contato': contato,
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
    
    if not footer_data:
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
    # Carregar todos os reparos realizados
    if use_database():
        try:
            reparos_db = ReparoRealizado.query.filter_by(ativo=True).order_by(ReparoRealizado.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar reparos realizados do banco: {e}")
            reparos_db = []
        reparos = []
        for r in reparos_db:
            if r.imagem_id:
                imagem_url = f'/admin/reparos/imagem/{r.imagem_id}'
            else:
                imagem_url = 'img/placeholder.png'
            
            reparos.append({
                'id': r.id,
                'titulo': r.titulo or '',
                'descricao': r.descricao or '',
                'imagem_url': imagem_url,
                'ordem': r.ordem
            })
    else:
        reparos = []
    
    return render_template('reparos.html', footer=footer_data, reparos=reparos)

@app.route('/sobre')
def sobre():
    # Carregar footer do banco de dados
    footer_data = None
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                contato = footer_obj.contato if footer_obj.contato else {}
                redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': redes_sociais,
                    'contato': contato,
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
    
    if not footer_data:
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
    return render_template('sobre.html', footer=footer_data)

@app.route('/servicos')
def servicos():
    """Redireciona para a primeira página de serviço disponível ou para a home"""
    # Tentar encontrar a primeira página de serviço ativa (ordenada por ordem)
    if use_database():
        try:
            primeira_pagina = PaginaServico.query.filter_by(ativo=True).order_by(PaginaServico.ordem).first()
            if primeira_pagina:
                return redirect(url_for('pagina_servico', slug=primeira_pagina.slug))
        except Exception as e:
            print(f"Erro ao buscar primeira página de serviço: {e}")
    
    # Se não encontrar nenhuma página, redirecionar para a home
    return redirect(url_for('index'))

@app.route('/servico/<slug>')
def pagina_servico(slug):
    """Rota dinâmica para páginas de serviços individuais"""
    # SEMPRE usar banco de dados - não há fallback para JSON
    if not use_database():
        flash('Sistema de páginas de serviços não disponível. Configure DATABASE_URL no Render.', 'error')
        return redirect(url_for('index'))
    
    try:
        pagina = PaginaServico.query.filter_by(slug=slug, ativo=True).first()
        if not pagina:
            flash('Página de serviço não encontrada.', 'error')
            # Redirecionar para a primeira página disponível ou home
            primeira_pagina = PaginaServico.query.filter_by(ativo=True).order_by(PaginaServico.ordem).first()
            if primeira_pagina:
                return redirect(url_for('pagina_servico', slug=primeira_pagina.slug))
            return redirect(url_for('index'))
    except Exception as e:
        print(f"Erro ao buscar página de serviço: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar página.', 'error')
        return redirect(url_for('index'))
    
    # Carregar footer
    footer_data = None
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                contato = footer_obj.contato if footer_obj.contato else {}
                redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': redes_sociais,
                    'contato': contato,
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer: {e}")
    
    if not footer_data:
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
    # Preparar dados da página
    imagem_url = None
    if pagina.imagem_id:
        imagem_url = f'/admin/paginas-servicos/imagem/{pagina.imagem_id}'
    elif hasattr(pagina, 'imagem') and pagina.imagem:
        imagem_url = pagina.imagem if pagina.imagem.startswith('/') or pagina.imagem.startswith('http') else url_for('static', filename=pagina.imagem)
    
    pagina_data = {
        'id': pagina.id,
        'slug': pagina.slug,
        'titulo': pagina.titulo,
        'descricao': pagina.descricao or '',
        'conteudo': pagina.conteudo or '',
        'imagem': imagem_url,
        'meta_titulo': pagina.meta_titulo or pagina.titulo,
        'meta_descricao': pagina.meta_descricao or pagina.descricao or '',
        'meta_keywords': pagina.meta_keywords or ''
    }
    
    return render_template('pagina_servico.html', pagina=pagina_data, footer=footer_data)

# ==================== ROTAS DA LOJA (REMOVIDO) ====================
@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        servico = request.form.get('servico')
        mensagem = request.form.get('mensagem')
        
        # Salvar contato no banco de dados
        if use_database():
            try:
                novo_contato = Contato(
                    nome=nome,
                    email=email if email else None,
                    telefone=telefone if telefone else None,
                    servico=servico if servico else None,
                    mensagem=mensagem if mensagem else None
                )
                
                db.session.add(novo_contato)
                db.session.commit()
                
                flash('Mensagem enviada com sucesso! Entraremos em contato em breve.', 'success')
                return redirect(url_for('contato'))
            except Exception as e:
                print(f"Erro ao salvar contato no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash('Erro ao enviar mensagem. Tente novamente.', 'error')
        else:
            # Fallback para JSON
            init_data_file()
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            novo_contato = {
                'id': len(data.get('contacts', [])) + 1,
                'nome': nome,
                'email': email,
                'telefone': telefone,
                'servico': servico,
                'mensagem': mensagem,
                'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if 'contacts' not in data:
                data['contacts'] = []
            data['contacts'].append(novo_contato)
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            flash('Mensagem enviada com sucesso! Entraremos em contato em breve.', 'success')
            return redirect(url_for('contato'))
    
    # Carregar footer do banco de dados
    footer_data = None
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                contato = footer_obj.contato if footer_obj.contato else {}
                redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': redes_sociais,
                    'contato': contato,
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
    
    if not footer_data:
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
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
                if user and check_password_hash(user.password, password):
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
                
                if user:
                    # Verificar senha (pode estar hasheada ou não)
                    user_password = user.get('password', '')
                    if user_password.startswith('pbkdf2:') or user_password.startswith('scrypt:'):
                        # Senha hasheada
                        if check_password_hash(user_password, password):
                            session['admin_logged_in'] = True
                            session['admin_username'] = username
                            session['admin_user_id'] = user.get('id')
                            flash('Login realizado com sucesso!', 'success')
                            return redirect(url_for('admin_dashboard'))
                    else:
                        # Senha em texto plano (backward compatibility)
                        if user_password == password:
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
    if use_database():
        try:
            # Contatos do banco
            total_contatos = Contato.query.count()
            contatos_recentes_db = Contato.query.order_by(Contato.data.desc()).limit(5).all()
            contatos_recentes = []
            for c in contatos_recentes_db:
                contatos_recentes.append({
                    'id': c.id,
                    'nome': c.nome,
                    'email': c.email or '',
                    'telefone': c.telefone or '',
                    'servico': c.servico or '',
                    'mensagem': c.mensagem or '',
                    'data': c.data.strftime('%Y-%m-%d %H:%M:%S') if c.data else ''
                })
            
            # Serviços do banco
            total_servicos = Servico.query.count()
        except Exception as e:
            print(f"Erro ao buscar estatísticas do banco: {e}")
            total_contatos = 0
            total_servicos = 0
            contatos_recentes = []
    else:
        # Fallback para JSON
        init_data_file()
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total_contatos = len(data.get('contacts', []))
        total_servicos = len(data.get('services', []))
        contatos_recentes = sorted(data.get('contacts', []), key=lambda x: x.get('data', ''), reverse=True)[:5]
    
    stats = {
        'total_contatos': total_contatos,
        'total_servicos': total_servicos,
        'contatos_recentes': contatos_recentes
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/contatos')
@login_required
def admin_contatos():
    if use_database():
        try:
            contatos_db = Contato.query.order_by(Contato.data.desc()).all()
            contatos = []
            for c in contatos_db:
                contatos.append({
                    'id': c.id,
                    'nome': c.nome,
                    'email': c.email or '',
                    'telefone': c.telefone or '',
                    'servico': c.servico or '',
                    'mensagem': c.mensagem or '',
                    'data': c.data.strftime('%Y-%m-%d %H:%M:%S') if c.data else ''
                })
        except Exception as e:
            print(f"Erro ao buscar contatos do banco: {e}")
            contatos = []
    else:
        # Fallback para JSON
        init_data_file()
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        contatos = sorted(data.get('contacts', []), key=lambda x: x.get('data', ''), reverse=True)
    
    return render_template('admin/contatos.html', contatos=contatos)

@app.route('/admin/contatos/<int:contato_id>/delete', methods=['POST'])
@login_required
def delete_contato(contato_id):
    if use_database():
        try:
            contato = Contato.query.get(contato_id)
            if not contato:
                flash('Contato não encontrado!', 'error')
                return redirect(url_for('admin_contatos'))
            
            db.session.delete(contato)
            db.session.commit()
            
            flash('Contato excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir contato do banco: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir contato: {str(e)}', 'error')
    else:
        # Fallback para JSON
        init_data_file()
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['contacts'] = [c for c in data.get('contacts', []) if c.get('id') != contato_id]
        
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
                        'descricao': s.descricao or '',  # Garantir que nunca seja None
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
        pagina_servico_id = request.form.get('pagina_servico_id', '').strip()
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
        
        # Converter pagina_servico_id para int se fornecido
        pagina_id = None
        if pagina_servico_id and pagina_servico_id.isdigit():
            pagina_id = int(pagina_servico_id)
        
        if use_database():
            try:
                # Em rotas Flask, já estamos em um contexto de aplicação
                servico = Servico(
                    nome=nome,
                    descricao=None,  # Não usar mais descrição
                    imagem=imagem if not imagem_id else None,
                    imagem_id=imagem_id,
                    ordem=int(ordem) if ordem.isdigit() else 999,
                    ativo=ativo,
                    data=datetime.now()
                )
                # Garantir que a coluna existe ANTES de fazer commit (mais eficiente)
                coluna_existe = garantir_coluna_pagina_servico_id()
                
                db.session.add(servico)
                db.session.flush()  # Obter o ID sem fazer commit ainda
                
                # Atualizar pagina_servico_id usando SQL direto (já que o campo está comentado no modelo)
                if pagina_id and coluna_existe:
                    try:
                        db.session.execute(
                            db.text("UPDATE servicos SET pagina_servico_id = :pagina_id WHERE id = :servico_id"),
                            {'pagina_id': pagina_id, 'servico_id': servico.id}
                        )
                        print(f"✅ pagina_servico_id {pagina_id} salvo para serviço {servico.id}")
                    except Exception as e:
                        print(f"Erro ao atualizar pagina_servico_id: {e}")
                        try:
                            db.session.rollback()
                        except:
                            pass
                
                # Fazer commit de tudo de uma vez
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
                'descricao': None,  # Não usar mais descrição, usar pagina_servico_id
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
    
    # Buscar páginas de serviços ativas para o dropdown
    paginas_servicos = []
    if use_database():
        try:
            paginas_servicos = PaginaServico.query.filter_by(ativo=True).order_by(PaginaServico.ordem).all()
        except Exception as e:
            print(f"Erro ao carregar páginas de serviços: {e}")
            # Fazer rollback explícito para evitar InFailedSqlTransaction
            try:
                db.session.rollback()
            except:
                pass
    
    return render_template('admin/add_servico.html', paginas_servicos=paginas_servicos)

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
                servico.descricao = None  # Não usar mais descrição
                pagina_servico_id = request.form.get('pagina_servico_id', '').strip()
                imagem_nova = request.form.get('imagem', '').strip()
                
                # Converter pagina_servico_id para int se fornecido
                pagina_id = None
                if pagina_servico_id and pagina_servico_id.isdigit():
                    pagina_id = int(pagina_servico_id)
                
                if imagem_nova:
                    servico.imagem = imagem_nova if not imagem_nova.startswith('/admin/servicos/imagem/') else None
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
                
                # Garantir que a coluna existe ANTES de fazer commit (mais eficiente)
                coluna_existe = garantir_coluna_pagina_servico_id()
                
                # Atualizar pagina_servico_id usando SQL direto (já que o campo está comentado no modelo)
                if coluna_existe:
                    try:
                        if pagina_id:
                            db.session.execute(
                                db.text("UPDATE servicos SET pagina_servico_id = :pagina_id WHERE id = :servico_id"),
                                {'pagina_id': pagina_id, 'servico_id': servico.id}
                            )
                            print(f"✅ pagina_servico_id {pagina_id} atualizado para serviço {servico.id}")
                        else:
                            db.session.execute(
                                db.text("UPDATE servicos SET pagina_servico_id = NULL WHERE id = :servico_id"),
                                {'servico_id': servico.id}
                            )
                            print(f"✅ pagina_servico_id removido do serviço {servico.id}")
                    except Exception as e:
                        print(f"Erro ao atualizar pagina_servico_id: {e}")
                        try:
                            db.session.rollback()
                        except:
                            pass
                
                # Fazer commit de tudo de uma vez
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
            
            # Buscar pagina_servico_id usando SQL direto
            pagina_servico_id = None
            # Garantir que a coluna existe antes de tentar ler
            global _pagina_servico_id_column_exists
            
            # Se não sabemos se a coluna existe, ou sabemos que não existe, tentar criar
            if _pagina_servico_id_column_exists is not True:
                garantir_coluna_pagina_servico_id()
            
            # Tentar buscar o valor
            if _pagina_servico_id_column_exists is True:
                try:
                    result = db.session.execute(
                        db.text("SELECT pagina_servico_id FROM servicos WHERE id = :servico_id"),
                        {'servico_id': servico.id}
                    ).fetchone()
                    if result and result[0]:
                        pagina_servico_id = result[0]
                except Exception as e:
                    error_str = str(e).lower()
                    # Fazer rollback IMEDIATAMENTE para evitar InFailedSqlTransaction
                    try:
                        db.session.rollback()
                    except:
                        pass
                    # Se ainda der erro mesmo após garantir, pode ser outro problema
                    if 'column' in error_str and ('does not exist' in error_str or 'undefined column' in error_str):
                        # Resetar cache e tentar criar novamente
                        _pagina_servico_id_column_exists = None
                        if garantir_coluna_pagina_servico_id():
                            # Tentar ler novamente
                            try:
                                result = db.session.execute(
                                    db.text("SELECT pagina_servico_id FROM servicos WHERE id = :servico_id"),
                                    {'servico_id': servico.id}
                                ).fetchone()
                                if result and result[0]:
                                    pagina_servico_id = result[0]
                            except:
                                pass
                    else:
                        print(f"Erro ao buscar pagina_servico_id: {e}")
            
            servico_dict = {
                'id': servico.id,
                'nome': servico.nome,
                'descricao': servico.descricao or '',  # Mantido para compatibilidade
                'imagem': imagem_url,
                'ordem': servico.ordem,
                'ativo': servico.ativo,
                'pagina_servico_id': pagina_servico_id,
                'data': servico.data.strftime('%Y-%m-%d %H:%M:%S') if servico.data else ''
            }
            
            # Buscar páginas de serviços ativas para o dropdown
            paginas_servicos = []
            try:
                paginas_servicos = PaginaServico.query.filter_by(ativo=True).order_by(PaginaServico.ordem).all()
            except Exception as e:
                print(f"Erro ao carregar páginas de serviços: {e}")
                # Fazer rollback explícito para evitar InFailedSqlTransaction
                try:
                    db.session.rollback()
                except:
                    pass
            
            return render_template('admin/edit_servico.html', servico=servico_dict, paginas_servicos=paginas_servicos)
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
    if use_database():
        try:
            # Buscar serviço no banco
            servico = Servico.query.get(servico_id)
            if not servico:
                flash('Serviço não encontrado!', 'error')
                return redirect(url_for('admin_servicos'))
            
            # Deletar imagem do banco se existir e estiver associada apenas a este serviço
            if servico.imagem_id:
                try:
                    imagem = Imagem.query.get(servico.imagem_id)
                    if imagem:
                        # Verificar se a imagem não está sendo usada por outros serviços
                        outros_servicos = Servico.query.filter(
                            Servico.imagem_id == servico.imagem_id,
                            Servico.id != servico_id
                        ).count()
                        
                        # Se não há outros serviços usando esta imagem, deletar
                        if outros_servicos == 0:
                            db.session.delete(imagem)
                            print(f"✅ Imagem {servico.imagem_id} deletada (não usada por outros serviços)")
                except Exception as e:
                    print(f"Erro ao deletar imagem: {e}")
                    # Continuar mesmo se der erro ao deletar imagem
            
            # Deletar serviço
            db.session.delete(servico)
            db.session.commit()
            
            flash('Serviço excluído com sucesso!', 'success')
            return redirect(url_for('admin_servicos'))
        except Exception as e:
            print(f"Erro ao excluir serviço do banco: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass
            flash('Erro ao excluir serviço. Tente novamente.', 'error')
            return redirect(url_for('admin_servicos'))
    
    # Fallback para JSON (apenas se banco não estiver disponível)
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['services'] = [s for s in data['services'] if s.get('id') != servico_id]
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Serviço excluído com sucesso!', 'success')
    except Exception as e:
        print(f"Erro ao excluir serviço do JSON: {e}")
        flash('Erro ao excluir serviço. Tente novamente.', 'error')
    
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
    
    # Fallback para JSON - só usar se não estiver usando banco
    if not use_database():
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
        if 'client_logged_in' not in session and 'cliente_logado' not in session:
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/cliente/login', methods=['GET', 'POST'])
def client_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('client/login.html')
        
        if use_database():
            try:
                # Buscar cliente por username ou email
                cliente = Cliente.query.filter(
                    db.or_(Cliente.username == username, Cliente.email == username)
                ).first()
                
                if cliente and cliente.password:
                    # Verificar senha (pode estar hasheada ou em texto plano para compatibilidade)
                    senha_valida = False
                    try:
                        # Tentar verificar como hash primeiro
                        if check_password_hash(cliente.password, password):
                            senha_valida = True
                    except:
                        # Se falhar, pode ser que a senha esteja em texto plano
                        pass
                    
                    # Se não passou no hash, verificar como texto plano (compatibilidade)
                    if not senha_valida and cliente.password == password:
                        # Senha em texto plano - hashear e atualizar no banco
                        try:
                            cliente.password = generate_password_hash(password)
                            db.session.commit()
                            senha_valida = True
                        except Exception as hash_err:
                            print(f"Erro ao hashear senha: {hash_err}")
                    
                    if senha_valida:
                        session['client_logged_in'] = True
                        session['cliente_logado'] = True
                        session['client_id'] = cliente.id
                        session['cliente_id'] = cliente.id
                        session['cliente_nome'] = cliente.nome
                        session['cliente_email'] = cliente.email
                        flash('Login realizado com sucesso!', 'success')
                        return redirect(url_for('client_dashboard'))
                
                flash('Usuário ou senha incorretos!', 'error')
            except Exception as e:
                print(f"Erro ao fazer login do cliente: {e}")
                flash('Erro ao fazer login. Tente novamente.', 'error')
        else:
            # Fallback para JSON (se necessário)
            try:
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
            except:
                flash('Erro ao fazer login. Tente novamente.', 'error')
    
    return render_template('client/login.html')

@app.route('/cliente/logout')
def client_logout():
    session.pop('client_logged_in', None)
    session.pop('client_id', None)
    session.pop('cliente_logado', None)
    session.pop('cliente_id', None)
    session.pop('cliente_nome', None)
    session.pop('cliente_email', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('client_login'))

@app.route('/cliente')
@client_login_required
def client_dashboard():
    cliente_id = session.get('client_id') or session.get('cliente_id')
    
    if not cliente_id:
        flash('Sessão expirada. Faça login novamente.', 'error')
        return redirect(url_for('client_login'))
    
    if use_database():
        try:
            cliente = Cliente.query.get(cliente_id)
            
            if not cliente:
                flash('Cliente não encontrado!', 'error')
                return redirect(url_for('client_logout'))
            
            # Buscar ordens de serviço do cliente
            ordens_db = OrdemServico.query.filter_by(cliente_id=cliente_id).order_by(OrdemServico.data.desc()).all()
            ordens = []
            for ordem in ordens_db:
                ordens.append({
                    'id': ordem.id,
                    'numero_ordem': ordem.numero_ordem,
                    'servico': ordem.servico.nome if ordem.servico else 'Serviço',
                    'tipo_aparelho': ordem.tipo_aparelho,
                    'marca': ordem.marca,
                    'modelo': ordem.modelo,
                    'numero_serie': ordem.numero_serie,
                    'defeitos_cliente': ordem.defeitos_cliente,
                    'diagnostico_tecnico': ordem.diagnostico_tecnico,
                    'status': ordem.status,
                    'custo_pecas': float(ordem.custo_pecas) if ordem.custo_pecas else 0,
                    'custo_mao_obra': float(ordem.custo_mao_obra) if ordem.custo_mao_obra else 0,
                    'total': float(ordem.valor_total) if ordem.valor_total else 0,
                    'data': ordem.data.strftime('%d/%m/%Y %H:%M') if ordem.data else '',
                    'pdf_filename': ordem.pdf_filename
                })
            
            # Buscar comprovantes do cliente
            comprovantes_db = Comprovante.query.filter_by(cliente_id=cliente_id).order_by(Comprovante.data.desc()).all()
            comprovantes = []
            for comp in comprovantes_db:
                comprovantes.append({
                    'id': comp.id,
                    'numero_ordem': comp.numero_ordem,
                    'valor_total': float(comp.valor_total),
                    'valor_pago': float(comp.valor_pago),
                    'forma_pagamento': comp.forma_pagamento,
                    'parcelas': comp.parcelas,
                    'data': comp.data.strftime('%d/%m/%Y %H:%M') if comp.data else '',
                    'pdf_filename': comp.pdf_filename
                })
            
            # Buscar cupons de desconto do cliente
            cupons_db = Cupom.query.filter_by(cliente_id=cliente_id).order_by(Cupom.data_emissao.desc()).all()
            cupons = []
            for cupom in cupons_db:
                cupons.append({
                    'id': cupom.id,
                    'desconto_percentual': float(cupom.desconto_percentual),
                    'usado': cupom.usado,
                    'ordem_id': cupom.ordem_id,
                    'data_emissao': cupom.data_emissao.strftime('%d/%m/%Y') if cupom.data_emissao else '',
                    'data_uso': cupom.data_uso.strftime('%d/%m/%Y') if cupom.data_uso else None
                })
            
            # Preparar dados do cliente para o template
            cliente_dict = {
                'id': cliente.id,
                'nome': cliente.nome,
                'email': cliente.email,
                'telefone': cliente.telefone,
                'cpf': cliente.cpf,
                'endereco': cliente.endereco,
                'data_cadastro': cliente.data_cadastro.strftime('%d/%m/%Y') if cliente.data_cadastro else ''
            }
            
            return render_template('client/dashboard.html', 
                                 cliente=cliente_dict, 
                                 ordens=ordens, 
                                 pedidos=[],
                                 comprovantes=comprovantes, 
                                 cupons=cupons)
        except Exception as e:
            print(f"Erro ao carregar dashboard do cliente: {e}")
            import traceback
            traceback.print_exc()
            flash('Erro ao carregar seus dados. Tente novamente.', 'error')
            return redirect(url_for('client_login'))
    else:
        # Fallback para JSON (se necessário)
        try:
            with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
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
            
            return render_template('client/dashboard.html', 
                                 cliente=cliente, 
                                 ordens=ordens_ordenadas, 
                                 pedidos=[],
                                 comprovantes=comprovantes, 
                                 cupons=cupons)
        except Exception as e:
            print(f"Erro ao carregar dashboard: {e}")
            flash('Erro ao carregar seus dados.', 'error')
            return redirect(url_for('client_login'))

# Rotas de pedidos da loja removidas

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
    if use_database():
        try:
            comprovantes_db = Comprovante.query.order_by(Comprovante.data.desc()).all()
            comprovantes = []
            for c in comprovantes_db:
                comprovantes.append({
                    'id': c.id,
                    'cliente_id': c.cliente_id,
                    'cliente_nome': c.cliente_nome or '',
                    'ordem_id': c.ordem_id,
                    'numero_ordem': c.numero_ordem or '',
                    'valor_total': float(c.valor_total) if c.valor_total else 0.00,
                    'valor_pago': float(c.valor_pago) if c.valor_pago else 0.00,
                    'forma_pagamento': c.forma_pagamento or '',
                    'parcelas': c.parcelas or 1,
                    'data': c.data.strftime('%Y-%m-%d %H:%M:%S') if c.data else '',
                    'pdf_filename': c.pdf_filename or ''
                })
        except Exception as e:
            print(f"Erro ao listar comprovantes do banco: {e}")
            import traceback
            traceback.print_exc()
            comprovantes = []
    else:
        # Fallback para JSON
        with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        comprovantes = sorted(data.get('comprovantes', []), key=lambda x: x.get('data', ''), reverse=True)
    
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
        
        if use_database():
            try:
                # Buscar cliente e ordem do banco
                cliente = Cliente.query.get(cliente_id)
                if not cliente:
                    flash('Cliente não encontrado!', 'error')
                    return redirect(url_for('emitir_comprovante'))
                
                ordem = OrdemServico.query.filter_by(id=ordem_id, cliente_id=cliente_id).first()
                if not ordem:
                    flash('Ordem de serviço não encontrada!', 'error')
                    return redirect(url_for('emitir_comprovante'))
                
                # Preparar dados para gerar PDF
                cliente_dict = {
                    'nome': cliente.nome,
                    'email': cliente.email or '',
                    'telefone': cliente.telefone or '',
                    'cpf': cliente.cpf or '',
                    'endereco': cliente.endereco or ''
                }
                
                ordem_dict = {
                    'id': ordem.id,
                    'numero_ordem': ordem.numero_ordem or str(ordem.id),
                    'servico': ordem.servico or '',
                    'total': float(ordem.total) if ordem.total else 0.00,
                    'status': ordem.status or 'pendente'
                }
                
                # Criar comprovante temporário para gerar PDF
                novo_comprovante_temp = {
                    'id': 0,  # Será atualizado após salvar
                    'cliente_id': cliente_id,
                    'cliente_nome': cliente.nome,
                    'ordem_id': ordem_id,
                    'numero_ordem': ordem.numero_ordem or str(ordem_id),
                    'valor_total': float(ordem.total) if ordem.total else 0.00,
                    'valor_pago': valor_pago,
                    'forma_pagamento': forma_pagamento,
                    'parcelas': int(parcelas) if forma_pagamento == 'cartao_credito' else 1,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'pdf_filename': None
                }
                
                # Gerar PDF do comprovante
                pdf_result = gerar_pdf_comprovante(cliente_dict, ordem_dict, novo_comprovante_temp)
                
                # Criar comprovante no banco
                novo_comprovante = Comprovante(
                    cliente_id=cliente_id,
                    cliente_nome=cliente.nome,
                    ordem_id=ordem_id,
                    numero_ordem=ordem.numero_ordem or str(ordem_id),
                    valor_total=float(ordem.total) if ordem.total else 0.00,
                    valor_pago=valor_pago,
                    forma_pagamento=forma_pagamento,
                    parcelas=int(parcelas) if forma_pagamento == 'cartao_credito' else 1,
                    data=datetime.now()
                )
                
                # Atualizar PDF se gerado
                if isinstance(pdf_result, dict):
                    novo_comprovante.pdf_filename = pdf_result.get('pdf_filename', '')
                    novo_comprovante.pdf_id = pdf_result.get('pdf_id')
                elif pdf_result:
                    novo_comprovante.pdf_filename = pdf_result
                
                db.session.add(novo_comprovante)
                db.session.commit()
                
                # Atualizar ID do comprovante temporário para caso precise regerar PDF
                novo_comprovante_temp['id'] = novo_comprovante.id
                
                flash('Comprovante emitido com sucesso!', 'success')
                return redirect(url_for('admin_comprovantes'))
            except Exception as e:
                print(f"Erro ao emitir comprovante no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash('Erro ao emitir comprovante. Tente novamente.', 'error')
                return redirect(url_for('emitir_comprovante'))
        else:
            # Fallback para JSON
            with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
                clients_data = json.load(f)
            
            cliente = next((c for c in clients_data.get('clients', []) if c.get('id') == cliente_id), None)
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
                'id': len(comprovantes_data.get('comprovantes', [])) + 1,
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
            if 'comprovantes' not in comprovantes_data:
                comprovantes_data['comprovantes'] = []
            comprovantes_data['comprovantes'].append(novo_comprovante)
            with open(COMPROVANTES_FILE, 'w', encoding='utf-8') as f:
                json.dump(comprovantes_data, f, ensure_ascii=False, indent=2)
            
            flash('Comprovante emitido com sucesso!', 'success')
            return redirect(url_for('admin_comprovantes'))
    
    # GET - Exibir formulário
    if use_database():
        try:
            clientes_db = Cliente.query.all()
            clientes = []
            for c in clientes_db:
                clientes.append({
                    'id': c.id,
                    'nome': c.nome,
                    'email': c.email or '',
                    'telefone': c.telefone or '',
                    'cpf': c.cpf or '',
                    'username': c.username or '',
                    'ordens': []  # Será carregado via AJAX
                })
        except Exception as e:
            print(f"Erro ao buscar clientes do banco: {e}")
            clientes = []
    else:
        # Fallback para JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        clientes = clients_data.get('clients', [])
    
    return render_template('admin/emitir_comprovante.html', clientes=clientes)

@app.route('/admin/comprovantes/<int:cliente_id>/ordens')
@login_required
def get_ordens_cliente(cliente_id):
    """Retorna ordens de um cliente em JSON"""
    if use_database():
        try:
            cliente = Cliente.query.get(cliente_id)
            if not cliente:
                return jsonify({'error': 'Cliente não encontrado'}), 404
            
            ordens_db = OrdemServico.query.filter_by(cliente_id=cliente_id).all()
            ordens_data = []
            for ordem in ordens_db:
                ordens_data.append({
                    'id': ordem.id,
                    'numero_ordem': ordem.numero_ordem or str(ordem.id),
                    'servico': ordem.servico or '',
                    'total': float(ordem.total) if ordem.total else 0.00,
                    'status': ordem.status or 'pendente'
                })
            
            return jsonify({'ordens': ordens_data})
        except Exception as e:
            print(f"Erro ao buscar ordens do cliente: {e}")
            return jsonify({'error': 'Erro ao buscar ordens'}), 500
    else:
        # Fallback para JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cliente = next((c for c in data.get('clients', []) if c.get('id') == cliente_id), None)
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
    if use_database():
        try:
            comprovante = Comprovante.query.get(comprovante_id)
            if not comprovante:
                flash('Comprovante não encontrado!', 'error')
                return redirect(url_for('admin_comprovantes'))
            
            # Deletar PDF do banco se existir
            if comprovante.pdf_id:
                try:
                    pdf_doc = PDFDocument.query.get(comprovante.pdf_id)
                    if pdf_doc:
                        db.session.delete(pdf_doc)
                except Exception as e:
                    print(f"Erro ao deletar PDF: {e}")
            
            # Deletar comprovante
            db.session.delete(comprovante)
            db.session.commit()
            
            flash('Comprovante excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir comprovante do banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao excluir comprovante: {str(e)}', 'error')
    else:
        # Fallback para JSON
        with open(COMPROVANTES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        comprovante = next((c for c in data.get('comprovantes', []) if c.get('id') == comprovante_id), None)
        if comprovante:
            # Remover comprovante (PDF já está no banco de dados, não precisa deletar do filesystem)
            data['comprovantes'] = [c for c in data.get('comprovantes', []) if c.get('id') != comprovante_id]
            
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
    if use_database():
        try:
            # Buscar cupons do banco
            cupons_db = Cupom.query.order_by(Cupom.data_emissao.desc()).all()
            cupons = []
            for c in cupons_db:
                cupons.append({
                    'id': c.id,
                    'cliente_id': c.cliente_id,
                    'cliente_nome': c.cliente_nome or 'Cliente não encontrado',
                    'desconto_percentual': float(c.desconto_percentual) if c.desconto_percentual else 0,
                    'usado': c.usado or False,
                    'ordem_id': c.ordem_id,
                    'data_emissao': c.data_emissao.strftime('%Y-%m-%d %H:%M:%S') if c.data_emissao else '',
                    'data_uso': c.data_uso.strftime('%Y-%m-%d %H:%M:%S') if c.data_uso else None
                })
            
            # Buscar clientes do banco
            clientes_db = Cliente.query.all()
            clientes = []
            for c in clientes_db:
                clientes.append({
                    'id': c.id,
                    'nome': c.nome,
                    'email': c.email or '',
                    'telefone': c.telefone or '',
                    'cpf': c.cpf or '',
                    'username': c.username or ''
                })
        except Exception as e:
            print(f"Erro ao buscar cupons/clientes do banco: {e}")
            import traceback
            traceback.print_exc()
            cupons = []
            clientes = []
    else:
        # Fallback para JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            fidelidade_data = json.load(f)
        
        cupons = sorted(fidelidade_data.get('cupons', []), key=lambda x: x.get('data_emissao', ''), reverse=True)
        
        # Adicionar nome do cliente em cada cupom
        for cupom in cupons:
            cliente = next((c for c in clients_data.get('clients', []) if c.get('id') == cupom.get('cliente_id')), None)
            if cliente:
                cupom['cliente_nome'] = cliente['nome']
            else:
                cupom['cliente_nome'] = 'Cliente não encontrado'
        
        clientes = clients_data.get('clients', [])
    
    return render_template('admin/fidelidade.html', clientes=clientes, cupons=cupons)

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
    
    if use_database():
        try:
            # Buscar cliente no banco
            cliente = Cliente.query.get(cliente_id)
            if not cliente:
                flash('Cliente não encontrado!', 'error')
                return redirect(url_for('admin_fidelidade'))
            
            # Criar cupom no banco
            novo_cupom = Cupom(
                cliente_id=cliente_id,
                cliente_nome=cliente.nome,
                desconto_percentual=desconto_percentual,
                usado=False,
                ordem_id=None,
                data_emissao=datetime.now(),
                data_uso=None
            )
            db.session.add(novo_cupom)
            db.session.commit()
            
            flash(f'Cupom de {desconto_percentual}% de desconto emitido para {cliente.nome} com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao emitir cupom no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash('Erro ao emitir cupom. Tente novamente.', 'error')
    else:
        # Fallback para JSON
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        cliente = next((c for c in clients_data.get('clients', []) if c.get('id') == cliente_id), None)
        if not cliente:
            flash('Cliente não encontrado!', 'error')
            return redirect(url_for('admin_fidelidade'))
        
        # Criar cupom
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            fidelidade_data = json.load(f)
        
        novo_cupom = {
            'id': len(fidelidade_data.get('cupons', [])) + 1,
            'cliente_id': cliente_id,
            'cliente_nome': cliente['nome'],
            'desconto_percentual': desconto_percentual,
            'usado': False,
            'ordem_id': None,
            'data_emissao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_uso': None
        }
        
        if 'cupons' not in fidelidade_data:
            fidelidade_data['cupons'] = []
        fidelidade_data['cupons'].append(novo_cupom)
        
        with open(FIDELIDADE_FILE, 'w', encoding='utf-8') as f:
            json.dump(fidelidade_data, f, ensure_ascii=False, indent=2)
        
        flash(f'Cupom de {desconto_percentual}% de desconto emitido para {cliente["nome"]} com sucesso!', 'success')
    
    return redirect(url_for('admin_fidelidade'))

@app.route('/admin/fidelidade/<int:cupom_id>')
@login_required
def view_cupom_detalhes(cupom_id):
    """Retorna detalhes do cupom em JSON para modal"""
    if use_database():
        try:
            cupom = Cupom.query.get(cupom_id)
            if not cupom:
                return jsonify({'error': 'Cupom não encontrado'}), 404
            
            cupom_dict = {
                'id': cupom.id,
                'cliente_id': cupom.cliente_id,
                'cliente_nome': cupom.cliente_nome or '',
                'desconto_percentual': float(cupom.desconto_percentual) if cupom.desconto_percentual else 0,
                'usado': cupom.usado or False,
                'ordem_id': cupom.ordem_id,
                'data_emissao': cupom.data_emissao.strftime('%Y-%m-%d %H:%M:%S') if cupom.data_emissao else '',
                'data_uso': cupom.data_uso.strftime('%Y-%m-%d %H:%M:%S') if cupom.data_uso else None
            }
            
            # Buscar dados do cliente
            cliente = Cliente.query.get(cupom.cliente_id)
            if cliente:
                cupom_dict['cliente_nome'] = cliente.nome
                cupom_dict['cliente_email'] = cliente.email or ''
            
            return jsonify(cupom_dict)
        except Exception as e:
            print(f"Erro ao buscar cupom: {e}")
            return jsonify({'error': 'Erro ao buscar cupom'}), 500
    else:
        # Fallback para JSON
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cupom = next((c for c in data.get('cupons', []) if c.get('id') == cupom_id), None)
        if not cupom:
            return jsonify({'error': 'Cupom não encontrado'}), 404
        
        # Buscar dados do cliente
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            clients_data = json.load(f)
        
        cliente = next((c for c in clients_data.get('clients', []) if c.get('id') == cupom.get('cliente_id')), None)
        if cliente:
            cupom['cliente_nome'] = cliente['nome']
            cupom['cliente_email'] = cliente.get('email', '')
        
        return jsonify(cupom)

@app.route('/admin/fidelidade/<int:cupom_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cupom(cupom_id):
    """Editar cupom de desconto"""
    if use_database():
        try:
            cupom = Cupom.query.get(cupom_id)
            if not cupom:
                flash('Cupom não encontrado!', 'error')
                return redirect(url_for('admin_fidelidade'))
            
            if cupom.usado:
                flash('Não é possível editar um cupom já utilizado!', 'error')
                return redirect(url_for('admin_fidelidade'))
            
            if request.method == 'POST':
                desconto_percentual = float(request.form.get('desconto_percentual'))
                
                # Validar desconto
                if desconto_percentual <= 0 or desconto_percentual > 100:
                    flash('Desconto deve ser entre 1% e 100%!', 'error')
                    return redirect(url_for('edit_cupom', cupom_id=cupom_id))
                
                # Atualizar cupom
                cupom.desconto_percentual = desconto_percentual
                db.session.commit()
                
                flash('Cupom atualizado com sucesso!', 'success')
                return redirect(url_for('admin_fidelidade'))
            
            # GET - Exibir formulário
            cupom_dict = {
                'id': cupom.id,
                'cliente_id': cupom.cliente_id,
                'cliente_nome': cupom.cliente_nome or '',
                'desconto_percentual': float(cupom.desconto_percentual) if cupom.desconto_percentual else 0,
                'usado': cupom.usado or False,
                'ordem_id': cupom.ordem_id,
                'data_emissao': cupom.data_emissao.strftime('%Y-%m-%d %H:%M:%S') if cupom.data_emissao else '',
                'data_uso': cupom.data_uso.strftime('%Y-%m-%d %H:%M:%S') if cupom.data_uso else None
            }
            
            # Buscar clientes do banco
            clientes_db = Cliente.query.all()
            clientes = []
            for c in clientes_db:
                clientes.append({
                    'id': c.id,
                    'nome': c.nome,
                    'email': c.email or ''
                })
            
            cliente = next((c for c in clientes if c.get('id') == cupom.cliente_id), None)
            
            return render_template('admin/edit_cupom.html', cupom=cupom_dict, cliente=cliente, clientes=clientes)
        except Exception as e:
            print(f"Erro ao editar cupom: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash('Erro ao editar cupom. Tente novamente.', 'error')
            return redirect(url_for('admin_fidelidade'))
    else:
        # Fallback para JSON
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cupom = next((c for c in data.get('cupons', []) if c.get('id') == cupom_id), None)
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
        
        cliente = next((c for c in clients_data.get('clients', []) if c.get('id') == cupom.get('cliente_id')), None)
        
        return render_template('admin/edit_cupom.html', cupom=cupom, cliente=cliente, clientes=clients_data.get('clients', []))

@app.route('/admin/fidelidade/<int:cupom_id>/delete', methods=['POST'])
@login_required
def delete_cupom(cupom_id):
    """Excluir cupom de desconto"""
    if use_database():
        try:
            cupom = Cupom.query.get(cupom_id)
            if not cupom:
                flash('Cupom não encontrado!', 'error')
                return redirect(url_for('admin_fidelidade'))
            
            if cupom.usado:
                flash('Não é possível excluir um cupom já utilizado!', 'error')
            else:
                db.session.delete(cupom)
                db.session.commit()
                flash('Cupom excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir cupom do banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao excluir cupom: {str(e)}', 'error')
    else:
        # Fallback para JSON
        with open(FIDELIDADE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        cupom = next((c for c in data.get('cupons', []) if c.get('id') == cupom_id), None)
        if cupom:
            if cupom.get('usado'):
                flash('Não é possível excluir um cupom já utilizado!', 'error')
            else:
                data['cupons'] = [c for c in data.get('cupons', []) if c.get('id') != cupom_id]
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
                flash('Rodapé atualizado com sucesso no banco de dados!', 'success')
                return redirect(url_for('admin_footer'))
            except Exception as e:
                print(f"Erro ao salvar footer no banco: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except:
                    pass
                flash(f'Erro ao salvar rodapé no banco de dados: {str(e)}. Verifique a conexão.', 'error')
                return redirect(url_for('admin_footer'))
        
        # Se não usar banco, mostrar erro
        flash('Banco de dados não configurado. Configure DATABASE_URL no Render para salvar os dados permanentemente.', 'error')
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
    
    # Se não usar banco ou não encontrou, criar footer padrão
    if not use_database() or footer_data is None:
        if not use_database():
            flash('Banco de dados não configurado. Configure DATABASE_URL no Render.', 'warning')
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
    if use_database():
        try:
            milestones_db = Milestone.query.order_by(Milestone.ordem).all()
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
        except Exception as e:
            print(f"Erro ao buscar milestones do banco: {e}")
            milestones = []
    else:
        # Fallback para JSON
        init_milestones_file()
        with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        milestones = sorted(data.get('milestones', []), key=lambda x: x.get('ordem', 999))
    
    return render_template('admin/milestones.html', milestones=milestones)

@app.route('/admin/milestones/add', methods=['GET', 'POST'])
@login_required
def add_milestone():
    """Adiciona um novo milestone"""
    if request.method == 'POST':
        if use_database():
            try:
                titulo = request.form.get('titulo', '').strip()
                imagem_path = request.form.get('imagem', '').strip()
                ordem = request.form.get('ordem', '1')
                ativo = request.form.get('ativo') == 'on'
                
                if not titulo:
                    flash('Por favor, informe o título do milestone.', 'error')
                    return redirect(url_for('add_milestone'))
                
                # Extrair image_id do path se for do banco
                imagem_id = None
                if imagem_path.startswith('/admin/milestones/imagem/'):
                    try:
                        imagem_id = int(imagem_path.split('/')[-1])
                    except:
                        pass
                
                # Obter próxima ordem se não fornecida
                if not ordem or not ordem.isdigit():
                    ultimo_milestone = Milestone.query.order_by(Milestone.ordem.desc()).first()
                    ordem = (ultimo_milestone.ordem + 1) if ultimo_milestone else 1
                else:
                    ordem = int(ordem)
                
                novo_milestone = Milestone(
                    titulo=titulo,
                    imagem=imagem_path if not imagem_id else None,
                    imagem_id=imagem_id,
                    ordem=ordem,
                    ativo=ativo
                )
                
                db.session.add(novo_milestone)
                db.session.commit()
                
                flash('Milestone cadastrado com sucesso!', 'success')
                return redirect(url_for('admin_milestones'))
            except Exception as e:
                print(f"Erro ao salvar milestone no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash(f'Erro ao salvar milestone: {str(e)}', 'error')
        else:
            # Fallback para JSON
            init_milestones_file()
            with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            milestones = data.get('milestones', [])
            novo_id = max([m.get('id', 0) for m in milestones], default=0) + 1
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
    if use_database():
        try:
            milestone = Milestone.query.get(milestone_id)
            if not milestone:
                flash('Milestone não encontrado!', 'error')
                return redirect(url_for('admin_milestones'))
            
            if request.method == 'POST':
                milestone.titulo = request.form.get('titulo', '').strip()
                imagem_path = request.form.get('imagem', '').strip()
                ordem = request.form.get('ordem', '1')
                milestone.ativo = request.form.get('ativo') == 'on'
                
                if not milestone.titulo:
                    flash('Por favor, informe o título do milestone.', 'error')
                    return redirect(url_for('edit_milestone', milestone_id=milestone_id))
                
                # Extrair image_id do path se for do banco
                imagem_id = None
                if imagem_path.startswith('/admin/milestones/imagem/'):
                    try:
                        imagem_id = int(imagem_path.split('/')[-1])
                    except:
                        pass
                
                if imagem_id:
                    milestone.imagem_id = imagem_id
                    milestone.imagem = None
                else:
                    milestone.imagem = imagem_path
                    milestone.imagem_id = None
                
                if ordem and ordem.isdigit():
                    milestone.ordem = int(ordem)
                
                db.session.commit()
                
                flash('Milestone atualizado com sucesso!', 'success')
                return redirect(url_for('admin_milestones'))
            
            # Preparar dados para o template
            if milestone.imagem_id:
                imagem_url = f'/admin/milestones/imagem/{milestone.imagem_id}'
            elif milestone.imagem:
                imagem_url = milestone.imagem
            else:
                imagem_url = 'img/placeholder.png'
            
            milestone_data = {
                'id': milestone.id,
                'titulo': milestone.titulo,
                'imagem': imagem_url,
                'ordem': milestone.ordem,
                'ativo': milestone.ativo
            }
            
            return render_template('admin/edit_milestone.html', milestone=milestone_data)
        except Exception as e:
            print(f"Erro ao editar milestone no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao editar milestone: {str(e)}', 'error')
            return redirect(url_for('admin_milestones'))
    else:
        # Fallback para JSON
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
    if use_database():
        try:
            milestone = Milestone.query.get(milestone_id)
            if not milestone:
                flash('Milestone não encontrado!', 'error')
                return redirect(url_for('admin_milestones'))
            
            db.session.delete(milestone)
            db.session.commit()
            
            flash('Milestone excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir milestone do banco: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir milestone: {str(e)}', 'error')
    else:
        # Fallback para JSON
        init_milestones_file()
        with open(MILESTONES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        milestones = data.get('milestones', [])
        data['milestones'] = [m for m in milestones if m.get('id') != milestone_id]
        
        with open(MILESTONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Milestone excluído com sucesso!', 'success')
    
    return redirect(url_for('admin_milestones'))

# ==================== REPAROS REALIZADOS ====================

@app.route('/admin/reparos')
@login_required
def admin_reparos():
    """Lista todos os reparos realizados cadastrados"""
    if use_database():
        try:
            reparos_db = ReparoRealizado.query.order_by(ReparoRealizado.ordem).all()
            reparos = []
            for r in reparos_db:
                if r.imagem_obj:
                    imagem_url = f'/admin/reparos/imagem/{r.imagem_id}'
                else:
                    imagem_url = 'img/placeholder.png'
                
                reparos.append({
                    'id': r.id,
                    'titulo': r.titulo or '',
                    'descricao': r.descricao or '',
                    'imagem_url': imagem_url,
                    'imagem_id': r.imagem_id,
                    'ordem': r.ordem,
                    'ativo': r.ativo,
                    'data_criacao': r.data_criacao
                })
        except Exception as e:
            print(f"Erro ao buscar reparos do banco: {e}")
            reparos = []
    else:
        reparos = []
    
    return render_template('admin/reparos.html', reparos=reparos)

@app.route('/admin/reparos/add', methods=['GET', 'POST'])
@login_required
def add_reparo():
    """Adiciona um novo reparo realizado"""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        imagem_id = request.form.get('imagem_id', '').strip()
        ordem = request.form.get('ordem', '1')
        ativo = request.form.get('ativo') == 'on'
        
        if not imagem_id or not imagem_id.isdigit():
            flash('Por favor, faça upload de uma imagem antes de salvar.', 'error')
            return redirect(url_for('add_reparo'))
        
        if use_database():
            try:
                # Verificar se a imagem existe
                imagem = Imagem.query.get(int(imagem_id))
                if not imagem:
                    flash('Imagem não encontrada. Por favor, faça upload novamente.', 'error')
                    return redirect(url_for('add_reparo'))
                
                # Obter próxima ordem se não especificada
                if not ordem or not ordem.isdigit():
                    ultimo_reparo = ReparoRealizado.query.order_by(ReparoRealizado.ordem.desc()).first()
                    ordem = (ultimo_reparo.ordem + 1) if ultimo_reparo else 1
                else:
                    ordem = int(ordem)
                
                novo_reparo = ReparoRealizado(
                    titulo=titulo if titulo else None,
                    descricao=descricao if descricao else None,
                    imagem_id=int(imagem_id),
                    ordem=ordem,
                    ativo=ativo
                )
                
                db.session.add(novo_reparo)
                db.session.commit()
                
                flash('Reparo cadastrado com sucesso!', 'success')
                return redirect(url_for('admin_reparos'))
            except Exception as e:
                print(f"Erro ao salvar reparo no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash(f'Erro ao salvar reparo: {str(e)}', 'error')
        else:
            flash('Banco de dados não configurado. Configure DATABASE_URL no Render.', 'error')
            return redirect(url_for('admin_reparos'))
    
    return render_template('admin/add_reparo.html')

@app.route('/admin/reparos/<int:reparo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_reparo(reparo_id):
    """Edita um reparo existente"""
    if use_database():
        try:
            reparo = ReparoRealizado.query.get(reparo_id)
            if not reparo:
                flash('Reparo não encontrado!', 'error')
                return redirect(url_for('admin_reparos'))
            
            if request.method == 'POST':
                reparo.titulo = request.form.get('titulo', '').strip() or None
                reparo.descricao = request.form.get('descricao', '').strip() or None
                reparo.ordem = int(request.form.get('ordem', '1')) if request.form.get('ordem', '1').isdigit() else 1
                reparo.ativo = request.form.get('ativo') == 'on'
                
                # Atualizar imagem se uma nova foi enviada
                nova_imagem_id = request.form.get('imagem_id', '').strip()
                if nova_imagem_id and nova_imagem_id.isdigit():
                    imagem = Imagem.query.get(int(nova_imagem_id))
                    if imagem:
                        reparo.imagem_id = int(nova_imagem_id)
                
                db.session.commit()
                
                flash('Reparo atualizado com sucesso!', 'success')
                return redirect(url_for('admin_reparos'))
            
            # Preparar dados para o template
            if reparo.imagem_obj:
                imagem_url = f'/admin/reparos/imagem/{reparo.imagem_id}'
            else:
                imagem_url = 'img/placeholder.png'
            
            reparo_dict = {
                'id': reparo.id,
                'titulo': reparo.titulo or '',
                'descricao': reparo.descricao or '',
                'imagem_url': imagem_url,
                'imagem_id': reparo.imagem_id,
                'ordem': reparo.ordem,
                'ativo': reparo.ativo
            }
            
            return render_template('admin/edit_reparo.html', reparo=reparo_dict)
        except Exception as e:
            print(f"Erro ao editar reparo: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Erro ao editar reparo: {str(e)}', 'error')
            return redirect(url_for('admin_reparos'))
    else:
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_reparos'))

@app.route('/admin/reparos/<int:reparo_id>/delete', methods=['POST'])
@login_required
def delete_reparo(reparo_id):
    """Exclui um reparo"""
    if use_database():
        try:
            reparo = ReparoRealizado.query.get(reparo_id)
            if not reparo:
                flash('Reparo não encontrado!', 'error')
                return redirect(url_for('admin_reparos'))
            
            db.session.delete(reparo)
            db.session.commit()
            
            flash('Reparo excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir reparo: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir reparo: {str(e)}', 'error')
    else:
        flash('Banco de dados não configurado.', 'error')
    
    return redirect(url_for('admin_reparos'))

@app.route('/admin/reparos/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_reparo():
    """Upload de imagem para reparos - salva no banco de dados"""
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
            imagem = Imagem(
                nome=secure_filename(file.filename),
                dados=file_data,
                tipo_mime=imagem_tipo,
                tamanho=file_size,
                referencia=f'reparo_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            db.session.add(imagem)
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'path': f'/admin/reparos/imagem/{imagem.id}',
                'image_id': imagem.id
            })
        except Exception as e:
            print(f"Erro ao salvar imagem de reparo no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500
    
    return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render.'}), 500

@app.route('/admin/reparos/imagem/<int:image_id>')
def servir_imagem_reparo(image_id):
    """Rota para servir imagens de reparos do banco de dados"""
    if use_database():
        try:
            imagem = Imagem.query.get(image_id)
            if imagem and imagem.dados:
                return Response(
                    imagem.dados,
                    mimetype=imagem.tipo_mime,
                    headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
                )
        except Exception as e:
            print(f"Erro ao buscar imagem de reparo: {e}")
    
    # Fallback: retornar placeholder
    return redirect(url_for('static', filename='img/placeholder.png'))

# ==================== VÍDEOS ====================

@app.route('/admin/videos')
@login_required
def admin_videos():
    """Lista todos os vídeos cadastrados"""
    if use_database():
        try:
            videos_db = Video.query.order_by(Video.ordem, Video.data_criacao.desc()).all()
            videos = []
            for v in videos_db:
                videos.append({
                    'id': v.id,
                    'titulo': v.titulo,
                    'link_youtube': v.link_youtube,
                    'video_id': v.get_video_id(),
                    'thumbnail_url': v.get_thumbnail_url(),
                    'ordem': v.ordem,
                    'ativo': v.ativo,
                    'data_criacao': v.data_criacao
                })
        except Exception as e:
            print(f"Erro ao buscar vídeos do banco: {e}")
            videos = []
    else:
        videos = []
    
    return render_template('admin/videos.html', videos=videos)

@app.route('/admin/videos/add', methods=['GET', 'POST'])
@login_required
def add_video():
    """Adiciona um novo vídeo"""
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        link_youtube = request.form.get('link_youtube', '').strip()
        ordem = request.form.get('ordem', '1')
        ativo = request.form.get('ativo') == 'on'
        
        if not titulo:
            flash('Por favor, informe o título do vídeo.', 'error')
            return redirect(url_for('add_video'))
        
        if not link_youtube:
            flash('Por favor, informe o link do YouTube.', 'error')
            return redirect(url_for('add_video'))
        
        if use_database():
            try:
                # Validar se o link é válido
                video_temp = Video()
                video_temp.link_youtube = link_youtube
                if not video_temp.get_video_id():
                    flash('Link do YouTube inválido. Use um link válido do YouTube.', 'error')
                    return redirect(url_for('add_video'))
                
                # Obter próxima ordem se não especificada
                if not ordem or not ordem.isdigit():
                    ultimo_video = Video.query.order_by(Video.ordem.desc()).first()
                    ordem = (ultimo_video.ordem + 1) if ultimo_video else 1
                else:
                    ordem = int(ordem)
                
                novo_video = Video(
                    titulo=titulo,
                    link_youtube=link_youtube,
                    ordem=ordem,
                    ativo=ativo
                )
                
                db.session.add(novo_video)
                db.session.commit()
                
                flash('Vídeo cadastrado com sucesso!', 'success')
                return redirect(url_for('admin_videos'))
            except Exception as e:
                print(f"Erro ao salvar vídeo no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash(f'Erro ao salvar vídeo: {str(e)}', 'error')
        else:
            flash('Banco de dados não configurado. Configure DATABASE_URL no Render.', 'error')
            return redirect(url_for('admin_videos'))
    
    return render_template('admin/add_video.html')

@app.route('/admin/videos/<int:video_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_video(video_id):
    """Edita um vídeo existente"""
    if use_database():
        try:
            video = Video.query.get(video_id)
            if not video:
                flash('Vídeo não encontrado!', 'error')
                return redirect(url_for('admin_videos'))
            
            if request.method == 'POST':
                video.titulo = request.form.get('titulo', '').strip()
                link_youtube = request.form.get('link_youtube', '').strip()
                ordem = request.form.get('ordem', '1')
                video.ativo = request.form.get('ativo') == 'on'
                
                if not video.titulo:
                    flash('Por favor, informe o título do vídeo.', 'error')
                    return redirect(url_for('edit_video', video_id=video_id))
                
                if not link_youtube:
                    flash('Por favor, informe o link do YouTube.', 'error')
                    return redirect(url_for('edit_video', video_id=video_id))
                
                # Validar link
                video_temp = Video()
                video_temp.link_youtube = link_youtube
                if not video_temp.get_video_id():
                    flash('Link do YouTube inválido. Use um link válido do YouTube.', 'error')
                    return redirect(url_for('edit_video', video_id=video_id))
                
                video.link_youtube = link_youtube
                
                if ordem and ordem.isdigit():
                    video.ordem = int(ordem)
                
                db.session.commit()
                
                flash('Vídeo atualizado com sucesso!', 'success')
                return redirect(url_for('admin_videos'))
            
            video_data = {
                'id': video.id,
                'titulo': video.titulo,
                'link_youtube': video.link_youtube,
                'video_id': video.get_video_id(),
                'thumbnail_url': video.get_thumbnail_url(),
                'ordem': video.ordem,
                'ativo': video.ativo
            }
        except Exception as e:
            print(f"Erro ao buscar vídeo: {e}")
            flash('Erro ao carregar vídeo.', 'error')
            return redirect(url_for('admin_videos'))
    else:
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_videos'))
    
    return render_template('admin/edit_video.html', video=video_data)

@app.route('/admin/videos/<int:video_id>/delete', methods=['POST'])
@login_required
def delete_video(video_id):
    """Exclui um vídeo"""
    if use_database():
        try:
            video = Video.query.get(video_id)
            if not video:
                flash('Vídeo não encontrado!', 'error')
                return redirect(url_for('admin_videos'))
            
            db.session.delete(video)
            db.session.commit()
            
            flash('Vídeo excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir vídeo: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir vídeo: {str(e)}', 'error')
    else:
        flash('Banco de dados não configurado.', 'error')
    
    return redirect(url_for('admin_videos'))

@app.route('/videos')
def todos_videos():
    """Página que exibe todos os vídeos"""
    # Carregar footer do banco de dados
    footer_data = None
    if use_database():
        try:
            footer_obj = Footer.query.first()
            if footer_obj:
                contato = footer_obj.contato if footer_obj.contato else {}
                redes_sociais = footer_obj.redes_sociais if footer_obj.redes_sociais else {}
                footer_data = {
                    'descricao': footer_obj.descricao or '',
                    'redes_sociais': redes_sociais,
                    'contato': contato,
                    'copyright': footer_obj.copyright or '',
                    'whatsapp_float': footer_obj.whatsapp_float or ''
                }
        except Exception as e:
            print(f"Erro ao carregar footer do banco: {e}")
    
    if not footer_data:
        footer_data = {
            'descricao': 'Sua assistência técnica de confiança para eletrodomésticos, celulares, computadores e notebooks.',
            'redes_sociais': {'facebook': '', 'instagram': '', 'whatsapp': ''},
            'contato': {'telefone': '', 'email': '', 'endereco': ''},
            'copyright': '© 2026 Clínica do Reparo. Todos os direitos reservados.',
            'whatsapp_float': ''
        }
    
    # Carregar todos os vídeos
    if use_database():
        try:
            videos_db = Video.query.filter_by(ativo=True).order_by(Video.ordem, Video.data_criacao.desc()).all()
        except Exception as e:
            print(f"Erro ao carregar vídeos do banco: {e}")
            videos_db = []
        videos = []
        for v in videos_db:
            videos.append({
                'id': v.id,
                'titulo': v.titulo,
                'link_youtube': v.link_youtube,
                'video_id': v.get_video_id(),
                'embed_url': v.get_embed_url(),
                'thumbnail_url': v.get_thumbnail_url(),
                'ordem': v.ordem
            })
    else:
        videos = []
    
    return render_template('videos.html', footer=footer_data, videos=videos)

# ==================== ADMIN USERS MANAGEMENT ====================

@app.route('/admin/usuarios')
@login_required
def admin_usuarios():
    if use_database():
        try:
            usuarios_db = AdminUser.query.order_by(AdminUser.id).all()
            usuarios = []
            for u in usuarios_db:
                usuarios.append({
                    'id': u.id,
                    'username': u.username,
                    'nome': u.nome,
                    'email': u.email,
                    'ativo': u.ativo,
                    'data_criacao': u.data_criacao.strftime('%Y-%m-%d %H:%M:%S') if u.data_criacao else '-'
                })
        except Exception as e:
            print(f"Erro ao buscar usuários do banco: {e}")
            usuarios = []
    else:
        # Fallback para JSON
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
        
        if use_database():
            try:
                # Verificar se username já existe
                usuario_existente = AdminUser.query.filter_by(username=username).first()
                if usuario_existente:
                    flash('Este nome de usuário já está em uso!', 'error')
                    return render_template('admin/add_usuario.html')
                
                novo_usuario = AdminUser(
                    username=username,
                    password=generate_password_hash(password),
                    nome=nome if nome else None,
                    email=email if email else None,
                    ativo=ativo
                )
                
                db.session.add(novo_usuario)
                db.session.commit()
                
                flash('Usuário adicionado com sucesso!', 'success')
                return redirect(url_for('admin_usuarios'))
            except Exception as e:
                print(f"Erro ao adicionar usuário no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash(f'Erro ao adicionar usuário: {str(e)}', 'error')
                return render_template('admin/add_usuario.html')
        else:
            # Fallback para JSON
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
                'password': generate_password_hash(password),
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
    if use_database():
        try:
            usuario = AdminUser.query.get(usuario_id)
            if not usuario:
                flash('Usuário não encontrado!', 'error')
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
                usuario_existente = AdminUser.query.filter(
                    AdminUser.username == username,
                    AdminUser.id != usuario_id
                ).first()
                
                if usuario_existente:
                    flash('Este nome de usuário já está em uso!', 'error')
                    return render_template('admin/edit_usuario.html', usuario=usuario)
                
                usuario.username = username
                if password:  # Só atualiza senha se foi informada
                    usuario.password = generate_password_hash(password)
                usuario.nome = nome if nome else None
                usuario.email = email if email else None
                usuario.ativo = ativo
                
                db.session.commit()
                
                flash('Usuário atualizado com sucesso!', 'success')
                return redirect(url_for('admin_usuarios'))
            
            return render_template('admin/edit_usuario.html', usuario=usuario)
        except Exception as e:
            print(f"Erro ao editar usuário no banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao editar usuário: {str(e)}', 'error')
            return redirect(url_for('admin_usuarios'))
    else:
        # Fallback para JSON (não recomendado)
        init_admin_users_file()
        with open(ADMIN_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        usuario = next((u for u in data.get('users', []) if u.get('id') == usuario_id), None)
        if not usuario:
            flash('Usuário não encontrado!', 'error')
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
                usuario['password'] = generate_password_hash(password)
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
    current_user_id = session.get('admin_user_id')
    if current_user_id and usuario_id == current_user_id:
        flash('Você não pode excluir seu próprio usuário!', 'error')
        return redirect(url_for('admin_usuarios'))
    
    if use_database():
        try:
            usuario = AdminUser.query.get(usuario_id)
            if not usuario:
                flash('Usuário não encontrado!', 'error')
                return redirect(url_for('admin_usuarios'))
            
            db.session.delete(usuario)
            db.session.commit()
            
            flash('Usuário excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir usuário do banco: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir usuário: {str(e)}', 'error')
    else:
        # Fallback para JSON
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
            # Fazer rollback explícito para evitar InFailedSqlTransaction
            try:
                db.session.rollback()
            except:
                pass
            footer_data = None
    
    # Se não encontrou no banco, retornar footer padrão (não usar JSON)
    if footer_data is None:
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
            # Fazer rollback explícito para evitar InFailedSqlTransaction
            try:
                db.session.rollback()
            except:
                pass
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

@app.context_processor
def inject_paginas_servicos():
    """Injeta páginas de serviços ativas em todos os templates para o menu"""
    paginas_servicos_menu = []
    primeira_pagina_servico = None
    
    if use_database():
        try:
            paginas_db = PaginaServico.query.filter_by(ativo=True).order_by(PaginaServico.ordem).all()
            for p in paginas_db:
                paginas_servicos_menu.append({
                    'id': p.id,
                    'slug': p.slug,
                    'titulo': p.titulo,
                    'ordem': p.ordem
                })
            
            # Pegar a primeira página para usar como fallback
            if paginas_db:
                primeira_pagina_servico = paginas_db[0].slug
        except Exception as e:
            print(f"Erro ao carregar páginas de serviços do banco em inject_paginas_servicos: {e}")
            # Fazer rollback explícito para evitar InFailedSqlTransaction
            try:
                db.session.rollback()
            except:
                pass
            paginas_servicos_menu = []
    
    return {
        'paginas_servicos_menu': paginas_servicos_menu,
        'primeira_pagina_servico_slug': primeira_pagina_servico
    }

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
        
        # Buscar número do WhatsApp do footer do banco de dados
        whatsapp_link = ''
        if use_database():
            try:
                footer_obj = Footer.query.first()
                if footer_obj:
                    whatsapp_link = footer_obj.whatsapp_float or (footer_obj.redes_sociais.get('whatsapp') if footer_obj.redes_sociais else '')
            except Exception as e:
                print(f"Erro ao buscar WhatsApp do footer: {e}")
        
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
        if use_database():
            try:
                # Converter data_agendamento para formato date
                from datetime import datetime as dt
                try:
                    data_agendamento_obj = dt.strptime(data_agendamento, '%Y-%m-%d').date()
                except:
                    data_agendamento_obj = dt.now().date()
                
                novo_agendamento = Agendamento(
                    nome=nome,
                    telefone=telefone,
                    email=email if email else None,
                    data_agendamento=data_agendamento_obj,
                    hora_agendamento=hora_agendamento,
                    tipo_servico=tipo_servico,
                    observacoes=observacoes if observacoes else None,
                    status='pendente',
                    data_criacao=datetime.now()
                )
                db.session.add(novo_agendamento)
                db.session.commit()
                
                # Para mensagem de notificação
                data_criacao_str = novo_agendamento.data_criacao.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Erro ao salvar agendamento no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash('Erro ao salvar agendamento. Tente novamente.', 'error')
                return redirect(url_for('agendamento'))
        else:
            # Fallback para JSON
            init_agendamentos_file()
            with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
                agendamentos_data = json.load(f)
            
            novo_agendamento = {
                'id': len(agendamentos_data.get('agendamentos', [])) + 1,
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
            
            if 'agendamentos' not in agendamentos_data:
                agendamentos_data['agendamentos'] = []
            agendamentos_data['agendamentos'].append(novo_agendamento)
            
            with open(AGENDAMENTOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(agendamentos_data, f, ensure_ascii=False, indent=2)
            
            data_criacao_str = novo_agendamento['data_criacao']
        
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
        mensagem += f"\n_Agendamento criado em {data_criacao_str}_"
        
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
    if use_database():
        try:
            agendamentos_db = Agendamento.query.order_by(Agendamento.data_criacao.desc()).all()
            # Converter para formato similar ao JSON para compatibilidade com template
            agendamentos = []
            for ag in agendamentos_db:
                agendamentos.append({
                    'id': ag.id,
                    'nome': ag.nome,
                    'telefone': ag.telefone,
                    'email': ag.email or '',
                    'data_agendamento': ag.data_agendamento.strftime('%Y-%m-%d') if ag.data_agendamento else '',
                    'hora_agendamento': ag.hora_agendamento or '',
                    'tipo_servico': ag.tipo_servico or '',
                    'observacoes': ag.observacoes or '',
                    'status': ag.status or 'pendente',
                    'data_criacao': ag.data_criacao.strftime('%Y-%m-%d %H:%M:%S') if ag.data_criacao else ''
                })
        except Exception as e:
            print(f"Erro ao listar agendamentos do banco: {e}")
            import traceback
            traceback.print_exc()
            agendamentos = []
    else:
        # Fallback para JSON
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
    
    if use_database():
        try:
            agendamento = Agendamento.query.get(agendamento_id)
            if agendamento:
                agendamento.status = novo_status
                db.session.commit()
                flash('Status do agendamento atualizado com sucesso!', 'success')
            else:
                flash('Agendamento não encontrado!', 'error')
        except Exception as e:
            print(f"Erro ao atualizar status do agendamento: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash('Erro ao atualizar status do agendamento.', 'error')
    else:
        # Fallback para JSON
        init_agendamentos_file()
        with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
            agendamentos_data = json.load(f)
        
        agendamento = next((a for a in agendamentos_data.get('agendamentos', []) if a.get('id') == agendamento_id), None)
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
    if use_database():
        try:
            agendamento = Agendamento.query.get(agendamento_id)
            if not agendamento:
                return jsonify({'success': False, 'error': 'Agendamento não encontrado'}), 404
            
            # Montar mensagem
            mensagem = f"🔔 *NOVO AGENDAMENTO*\n\n"
            mensagem += f"👤 *Cliente:* {agendamento.nome}\n"
            mensagem += f"📞 *Telefone:* {agendamento.telefone or ''}\n"
            if agendamento.email:
                mensagem += f"📧 *E-mail:* {agendamento.email}\n"
            mensagem += f"📅 *Data:* {agendamento.data_agendamento.strftime('%Y-%m-%d') if agendamento.data_agendamento else ''}\n"
            mensagem += f"⏰ *Hora:* {agendamento.hora_agendamento or ''}\n"
            mensagem += f"🔧 *Serviço:* {agendamento.tipo_servico or ''}\n"
            if agendamento.observacoes:
                mensagem += f"📝 *Observações:* {agendamento.observacoes}\n"
            mensagem += f"\n_Agendamento criado em {agendamento.data_criacao.strftime('%Y-%m-%d %H:%M:%S') if agendamento.data_criacao else ''}_"
        except Exception as e:
            print(f"Erro ao buscar agendamento: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': 'Erro ao buscar agendamento'}), 500
    else:
        # Fallback para JSON
        init_agendamentos_file()
        with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
            agendamentos_data = json.load(f)
        
        agendamento = next((a for a in agendamentos_data.get('agendamentos', []) if a.get('id') == agendamento_id), None)
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
    if use_database():
        try:
            agendamento = Agendamento.query.get(agendamento_id)
            if not agendamento:
                flash('Agendamento não encontrado!', 'error')
                return redirect(url_for('admin_agendamentos'))
            
            db.session.delete(agendamento)
            db.session.commit()
            
            flash('Agendamento excluído com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir agendamento do banco: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao excluir agendamento: {str(e)}', 'error')
    else:
        # Fallback para JSON
        init_agendamentos_file()
        with open(AGENDAMENTOS_FILE, 'r', encoding='utf-8') as f:
            agendamentos_data = json.load(f)
        
        agendamentos_data['agendamentos'] = [a for a in agendamentos_data.get('agendamentos', []) if a.get('id') != agendamento_id]
        
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

# ==================== PÁGINAS DE SERVIÇOS (ADMIN) ====================

@app.route('/admin/paginas-servicos')
@login_required
def admin_paginas_servicos():
    """Lista todas as páginas de serviços cadastradas"""
    # SEMPRE usar banco de dados - não há fallback para JSON
    if not use_database():
        flash('Banco de dados não configurado. Configure DATABASE_URL no Render.', 'error')
        return render_template('admin/paginas_servicos.html', paginas=[])
    
    try:
        paginas_db = PaginaServico.query.order_by(PaginaServico.ordem).all()
        paginas = []
        for p in paginas_db:
            if p.imagem_id:
                imagem_url = f'/admin/paginas-servicos/imagem/{p.imagem_id}'
            else:
                imagem_url = None
            
            paginas.append({
                'id': p.id,
                'slug': p.slug,
                'titulo': p.titulo,
                'descricao': p.descricao or '',
                'imagem': imagem_url,
                'ordem': p.ordem,
                'ativo': p.ativo
            })
    except Exception as e:
        print(f"Erro ao buscar páginas de serviços do banco: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar páginas: {str(e)}', 'error')
        paginas = []
    
    return render_template('admin/paginas_servicos.html', paginas=paginas)

@app.route('/admin/paginas-servicos/add', methods=['GET', 'POST'])
@login_required
def add_pagina_servico():
    """Adiciona uma nova página de serviço"""
    if request.method == 'POST':
        if use_database():
            try:
                slug = request.form.get('slug', '').strip().lower().replace(' ', '-')
                titulo = request.form.get('titulo', '').strip()
                descricao = request.form.get('descricao', '').strip()
                conteudo = request.form.get('conteudo', '').strip()
                imagem_path = request.form.get('imagem', '').strip()
                ordem = request.form.get('ordem', '1')
                ativo = request.form.get('ativo') == 'on'
                meta_titulo = request.form.get('meta_titulo', '').strip()
                meta_descricao = request.form.get('meta_descricao', '').strip()
                meta_keywords = request.form.get('meta_keywords', '').strip()
                
                if not slug or not titulo:
                    flash('Por favor, preencha o slug e o título.', 'error')
                    return redirect(url_for('add_pagina_servico'))
                
                # Verificar se slug já existe
                if PaginaServico.query.filter_by(slug=slug).first():
                    flash('Este slug já está em uso. Escolha outro.', 'error')
                    return redirect(url_for('add_pagina_servico'))
                
                # Extrair image_id do path se for do banco
                imagem_id = None
                if imagem_path.startswith('/admin/paginas-servicos/imagem/'):
                    try:
                        imagem_id = int(imagem_path.split('/')[-1])
                    except:
                        pass
                
                if not ordem or not ordem.isdigit():
                    ultima_pagina = PaginaServico.query.order_by(PaginaServico.ordem.desc()).first()
                    ordem = (ultima_pagina.ordem + 1) if ultima_pagina else 1
                else:
                    ordem = int(ordem)
                
                nova_pagina = PaginaServico(
                    slug=slug,
                    titulo=titulo,
                    descricao=descricao if descricao else None,
                    conteudo=conteudo if conteudo else None,
                    # imagem=imagem_path if not imagem_id else None,  # Temporariamente desabilitado até migração
                    imagem_id=imagem_id,
                    ordem=ordem,
                    ativo=ativo,
                    meta_titulo=meta_titulo if meta_titulo else None,
                    meta_descricao=meta_descricao if meta_descricao else None,
                    meta_keywords=meta_keywords if meta_keywords else None
                )
                
                db.session.add(nova_pagina)
                db.session.commit()
                
                flash('Página de serviço cadastrada com sucesso!', 'success')
                return redirect(url_for('admin_paginas_servicos'))
            except Exception as e:
                print(f"Erro ao salvar página de serviço no banco: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                flash(f'Erro ao salvar página: {str(e)}', 'error')
        else:
            flash('Banco de dados não configurado. Configure DATABASE_URL no Render. As páginas devem ser salvas no banco de dados para evitar perda de dados após hibernação.', 'error')
            return redirect(url_for('admin_paginas_servicos'))
    
    return render_template('admin/add_pagina_servico.html')

@app.route('/admin/paginas-servicos/<int:pagina_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_pagina_servico(pagina_id):
    """Edita uma página de serviço existente"""
    if use_database():
        try:
            pagina = PaginaServico.query.get(pagina_id)
            if not pagina:
                flash('Página não encontrada!', 'error')
                return redirect(url_for('admin_paginas_servicos'))
            
            if request.method == 'POST':
                slug = request.form.get('slug', '').strip().lower().replace(' ', '-')
                titulo = request.form.get('titulo', '').strip()
                descricao = request.form.get('descricao', '').strip()
                conteudo = request.form.get('conteudo', '').strip()
                imagem_path = request.form.get('imagem', '').strip()
                ordem = request.form.get('ordem', '1')
                ativo = request.form.get('ativo') == 'on'
                meta_titulo = request.form.get('meta_titulo', '').strip()
                meta_descricao = request.form.get('meta_descricao', '').strip()
                meta_keywords = request.form.get('meta_keywords', '').strip()
                
                if not slug or not titulo:
                    flash('Por favor, preencha o slug e o título.', 'error')
                    return redirect(url_for('edit_pagina_servico', pagina_id=pagina_id))
                
                # Verificar se slug já existe em outra página
                pagina_existente = PaginaServico.query.filter_by(slug=slug).first()
                if pagina_existente and pagina_existente.id != pagina_id:
                    flash('Este slug já está em uso. Escolha outro.', 'error')
                    return redirect(url_for('edit_pagina_servico', pagina_id=pagina_id))
                
                # Extrair image_id do path se for do banco
                imagem_id = None
                if imagem_path.startswith('/admin/paginas-servicos/imagem/'):
                    try:
                        imagem_id = int(imagem_path.split('/')[-1])
                    except:
                        pass
                
                pagina.slug = slug
                pagina.titulo = titulo
                pagina.descricao = descricao if descricao else None
                pagina.conteudo = conteudo if conteudo else None
                
                if imagem_id:
                    pagina.imagem_id = imagem_id
                    # pagina.imagem = None  # Temporariamente desabilitado até migração
                # else:
                #     pagina.imagem = imagem_path if imagem_path else None  # Temporariamente desabilitado até migração
                #     pagina.imagem_id = None
                
                if ordem and ordem.isdigit():
                    pagina.ordem = int(ordem)
                
                pagina.ativo = ativo
                pagina.meta_titulo = meta_titulo if meta_titulo else None
                pagina.meta_descricao = meta_descricao if meta_descricao else None
                pagina.meta_keywords = meta_keywords if meta_keywords else None
                pagina.data_atualizacao = datetime.now()
                
                db.session.commit()
                
                flash('Página atualizada com sucesso!', 'success')
                return redirect(url_for('admin_paginas_servicos'))
            
            # Preparar dados para o template
            if pagina.imagem_id:
                imagem_url = f'/admin/paginas-servicos/imagem/{pagina.imagem_id}'
            # elif hasattr(pagina, 'imagem') and pagina.imagem:  # Temporariamente desabilitado até migração
            #     imagem_url = pagina.imagem
            else:
                imagem_url = ''
            
            pagina_data = {
                'id': pagina.id,
                'slug': pagina.slug,
                'titulo': pagina.titulo,
                'descricao': pagina.descricao or '',
                'conteudo': pagina.conteudo or '',
                'imagem': imagem_url,
                'ordem': pagina.ordem,
                'ativo': pagina.ativo,
                'meta_titulo': pagina.meta_titulo or '',
                'meta_descricao': pagina.meta_descricao or '',
                'meta_keywords': pagina.meta_keywords or ''
            }
            
            return render_template('admin/edit_pagina_servico.html', pagina=pagina_data)
        except Exception as e:
            print(f"Erro ao editar página de serviço: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao editar página: {str(e)}', 'error')
            return redirect(url_for('admin_paginas_servicos'))
    else:
        flash('Banco de dados não configurado. Configure DATABASE_URL no Render. As páginas devem ser salvas no banco de dados para evitar perda de dados após hibernação.', 'error')
        return redirect(url_for('admin_paginas_servicos'))

@app.route('/admin/paginas-servicos/<int:pagina_id>/delete', methods=['POST'])
@login_required
def delete_pagina_servico(pagina_id):
    """Exclui uma página de serviço"""
    if use_database():
        try:
            pagina = PaginaServico.query.get(pagina_id)
            if not pagina:
                flash('Página não encontrada!', 'error')
                return redirect(url_for('admin_paginas_servicos'))
            
            db.session.delete(pagina)
            db.session.commit()
            
            flash('Página excluída com sucesso!', 'success')
        except Exception as e:
            print(f"Erro ao excluir página de serviço: {e}")
            db.session.rollback()
            flash(f'Erro ao excluir página: {str(e)}', 'error')
    else:
        flash('Banco de dados não configurado. Configure DATABASE_URL no Render.', 'error')
    
    return redirect(url_for('admin_paginas_servicos'))

@app.route('/admin/paginas-servicos/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_pagina_servico():
    """Upload de imagem para páginas de serviços - salva no banco de dados"""
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
    
    # SEMPRE usar banco de dados - imagens devem ser salvas no banco para evitar perda de dados
    if not use_database():
        return jsonify({'success': False, 'error': 'Banco de dados não configurado. Configure DATABASE_URL no Render. As imagens devem ser salvas no banco de dados para evitar perda de dados após hibernação.'}), 500
    
    try:
        imagem = Imagem(
            nome=secure_filename(file.filename),
            dados=file_data,
            tipo_mime=imagem_tipo,
            tamanho=file_size,
            referencia=f'pagina_servico_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )
        db.session.add(imagem)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'path': f'/admin/paginas-servicos/imagem/{imagem.id}',
            'image_id': imagem.id
        })
    except Exception as e:
        print(f"Erro ao salvar imagem de página de serviço no banco: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erro ao salvar imagem no banco de dados: {str(e)}'}), 500

@app.route('/admin/paginas-servicos/imagem/<int:image_id>')
def servir_imagem_pagina_servico(image_id):
    """Rota para servir imagens de páginas de serviços do banco de dados"""
    # SEMPRE usar banco de dados - imagens são salvas no banco
    if not use_database():
        return redirect(url_for('static', filename='img/placeholder.png'))
    
    try:
        imagem = Imagem.query.get(image_id)
        if imagem and imagem.dados:
            return Response(
                imagem.dados,
                mimetype=imagem.tipo_mime,
                headers={'Content-Disposition': f'inline; filename={imagem.nome}'}
            )
    except Exception as e:
        print(f"Erro ao buscar imagem de página de serviço: {e}")
    
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
    """Salva imagem no banco de dados e retorna objeto Imagem - SEMPRE salva no banco"""
    # Verificar se banco de dados está disponível
    if not use_database():
        print("ERRO: Banco de dados não disponível para salvar imagem")
        return None
    
    if not file or not file.filename:
        return None
    
    if not allowed_file(file.filename):
        print(f"ERRO: Tipo de arquivo não permitido: {file.filename}")
        return None
    
    # Verificar tamanho
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        print(f"ERRO: Arquivo muito grande: {file_size} bytes (máx: {MAX_FILE_SIZE})")
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
        print(f"SUCCESS: Imagem salva no banco com ID: {imagem.id}")
        return imagem
    except Exception as e:
        db.session.rollback()
        print(f"ERRO ao salvar imagem no banco: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================== ADMIN - LOJA (REMOVIDO) ====================
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

# ==================== ORÇAMENTO AR-CONDICIONADO ====================

def calcular_preco_orcamento_ar(tipo_servico, potencia_btu, tipo_acesso, material_adicional=None, valor_material_adicional=0):
    """Calcula o preço do orçamento de ar-condicionado baseado nas regras fornecidas"""
    
    # Tabela de preços base por tipo de serviço e BTU (Acesso Fácil)
    precos_base = {
        'Instalação de Ar-Condicionado Split': {
            9000: 650.00,
            12000: 700.00,
            18000: 750.00,
            24000: 800.00,
            36000: 900.00,
            48000: 1200.00,
            60000: 1800.00
        },
        'Limpeza preventiva da Evaporadora': {
            'ate_18000': 150.00,
            '24000_36000': 200.00,
            'acima_36000': 250.00
        },
        'Limpeza preventiva Evaporadora + Condensadora': {
            'ate_18000': 250.00,
            '24000_36000': 300.00,
            'acima_36000': 350.00
        },
        'Remoção de Ar-Condicionado Split': {
            'ate_18000': 250.00,
            '24000_36000': 300.00,
            'acima_36000': 400.00
        }
    }
    
    # Calcular valor base
    valor_base = 0.00
    
    if tipo_servico == 'Instalação de Ar-Condicionado Split':
        valor_base = precos_base[tipo_servico].get(potencia_btu, 0.00)
    else:
        # Para outros serviços, usar faixas de BTU
        if potencia_btu <= 18000:
            valor_base = precos_base[tipo_servico]['ate_18000']
        elif potencia_btu <= 36000:
            valor_base = precos_base[tipo_servico]['24000_36000']
        else:
            valor_base = precos_base[tipo_servico]['acima_36000']
    
    # Calcular acréscimo por tipo de acesso
    valor_acesso = 0.00
    if tipo_servico == 'Instalação de Ar-Condicionado Split':
        if tipo_acesso == 'Moderado':
            valor_acesso = valor_base * 0.10  # 10%
        elif tipo_acesso == 'Difícil':
            valor_acesso = valor_base * 0.20  # 20%
    else:
        # Para outros serviços
        if tipo_acesso == 'Moderado':
            valor_acesso = valor_base * 0.20  # 20%
        elif tipo_acesso == 'Difícil':
            valor_acesso = valor_base * 0.30  # 30%
    
    # Valor do material adicional (se houver)
    valor_material = float(valor_material_adicional) if valor_material_adicional else 0.00
    if material_adicional == 'Kit Convencional (3m de tubulação)':
        valor_material = 250.00
    
    # Calcular total
    valor_total = valor_base + valor_acesso + valor_material
    
    return {
        'valor_base': round(valor_base, 2),
        'valor_acesso': round(valor_acesso, 2),
        'valor_material': round(valor_material, 2),
        'valor_total': round(valor_total, 2)
    }

def gerar_pdf_orcamento_ar(orçamento):
    """Gera PDF do orçamento de ar-condicionado e salva no banco"""
    pdf_filename = f"orcamento_ar_{orçamento.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
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
    story.append(Paragraph("ORÇAMENTO DE AR-CONDICIONADO", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informações do Orçamento
    data_formatada = orçamento.data_criacao.strftime('%d/%m/%Y %H:%M') if orçamento.data_criacao else datetime.now().strftime('%d/%m/%Y %H:%M')
    
    info_data = [
        ['Número do Orçamento:', f"#{orçamento.id:04d}"],
        ['Data:', data_formatada],
        ['Cliente:', orçamento.cliente.nome if orçamento.cliente else 'N/A'],
        ['Técnico:', orçamento.tecnico.nome if orçamento.tecnico else 'Não atribuído'],
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
    
    # Detalhes do Serviço
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#215f97'),
        spaceAfter=8,
        spaceBefore=0,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("Detalhes do Serviço", heading_style))
    
    detalhes_data = [
        ['Tipo de Serviço:', orçamento.tipo_servico],
        ['Potência (BTU):', f"{orçamento.potencia_btu} BTU"],
        ['Tipo de Acesso:', orçamento.tipo_acesso],
        ['Marca:', orçamento.marca_aparelho or 'N/A'],
        ['Modelo:', orçamento.modelo_aparelho or 'N/A'],
    ]
    
    if orçamento.material_adicional:
        detalhes_data.append(['Material Adicional:', orçamento.material_adicional])
    
    if orçamento.prazo_estimado:
        detalhes_data.append(['Prazo Estimado:', orçamento.prazo_estimado])
    
    detalhes_table = Table(detalhes_data, colWidths=[5*cm, 12*cm])
    detalhes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(detalhes_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Valores
    story.append(Paragraph("Valores", heading_style))
    
    valores_data = [
        ['Descrição', 'Valor'],
        ['Valor Base', f"R$ {orçamento.valor_base:.2f}"],
        ['Acréscimo por Acesso', f"R$ {orçamento.valor_acesso:.2f}"],
    ]
    
    if orçamento.valor_material_adicional > 0:
        valores_data.append(['Material Adicional', f"R$ {float(orçamento.valor_material_adicional):.2f}"])
    
    valores_data.append(['TOTAL', f"R$ {orçamento.valor_total:.2f}"])
    
    valores_table = Table(valores_data, colWidths=[12*cm, 5*cm])
    valores_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#215f97')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (-1, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (-1, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (-1, -1), (-1, -1), colors.HexColor('#f0f0f0')),
    ]))
    story.append(valores_table)
    
    # Gerar PDF
    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Salvar no banco
    pdf_id = salvar_pdf_no_banco(pdf_data, pdf_filename, 'orcamento_ar', orçamento.id)
    
    return {
        'pdf_id': pdf_id,
        'pdf_filename': pdf_filename
    }

@app.route('/admin/orcamentos-ar')
@login_required
def admin_orcamentos_ar():
    """Lista todos os orçamentos de ar-condicionado"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        orcamentos_db = OrcamentoArCondicionado.query.order_by(OrcamentoArCondicionado.data_criacao.desc()).all()
        orcamentos = []
        for o in orcamentos_db:
            orcamentos.append({
                'id': o.id,
                'cliente_nome': o.cliente.nome if o.cliente else 'Cliente não encontrado',
                'tipo_servico': o.tipo_servico,
                'potencia_btu': o.potencia_btu,
                'tipo_acesso': o.tipo_acesso,
                'valor_total': float(o.valor_total) if o.valor_total else 0.00,
                'status': o.status or 'pendente',
                'data_criacao': o.data_criacao.strftime('%d/%m/%Y %H:%M') if o.data_criacao else '',
                'prazo_estimado': o.prazo_estimado or '',
                'pdf_id': o.pdf_id,
                'pdf_filename': o.pdf_filename or ''
            })
    except Exception as e:
        print(f"Erro ao listar orçamentos: {e}")
        import traceback
        traceback.print_exc()
        orcamentos = []
    
    return render_template('admin/orcamentos_ar.html', orcamentos=orcamentos)

@app.route('/admin/orcamentos-ar/add', methods=['GET', 'POST'])
@login_required
def add_orcamento_ar():
    """Adiciona um novo orçamento de ar-condicionado"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    if request.method == 'POST':
        try:
            cliente_id = int(request.form.get('cliente_id'))
            tecnico_id = request.form.get('tecnico_id')
            tipo_servico = request.form.get('tipo_servico')
            potencia_btu = int(request.form.get('potencia_btu'))
            tipo_acesso = request.form.get('tipo_acesso')
            marca_aparelho = request.form.get('marca_aparelho', '').strip()
            modelo_aparelho = request.form.get('modelo_aparelho', '').strip()
            material_adicional = request.form.get('material_adicional', '').strip() or None
            valor_material_adicional = request.form.get('valor_material_adicional', '0').strip()
            status = request.form.get('status', 'pendente')
            prazo_estimado = request.form.get('prazo_estimado', '').strip() or None
            
            # Calcular valores
            valor_material = 0.00
            if material_adicional == 'Tubulação extra acima de 3m' and valor_material_adicional:
                valor_material = float(valor_material_adicional)
            
            calculo = calcular_preco_orcamento_ar(tipo_servico, potencia_btu, tipo_acesso, material_adicional, valor_material)
            
            # Criar orçamento
            orcamento = OrcamentoArCondicionado(
                cliente_id=cliente_id,
                tecnico_id=int(tecnico_id) if tecnico_id and tecnico_id != '' else None,
                tipo_servico=tipo_servico,
                potencia_btu=potencia_btu,
                tipo_acesso=tipo_acesso,
                marca_aparelho=marca_aparelho if marca_aparelho else None,
                modelo_aparelho=modelo_aparelho if modelo_aparelho else None,
                material_adicional=material_adicional,
                valor_material_adicional=valor_material,
                valor_base=calculo['valor_base'],
                valor_acesso=calculo['valor_acesso'],
                valor_total=calculo['valor_total'],
                status=status,
                prazo_estimado=prazo_estimado
            )
            
            db.session.add(orcamento)
            db.session.commit()
            
            # Gerar PDF
            pdf_result = gerar_pdf_orcamento_ar(orcamento)
            if pdf_result and pdf_result.get('pdf_id'):
                orcamento.pdf_id = pdf_result['pdf_id']
                orcamento.pdf_filename = pdf_result['pdf_filename']
                db.session.commit()
            
            flash('Orçamento criado com sucesso!', 'success')
            return redirect(url_for('admin_orcamentos_ar'))
        except Exception as e:
            print(f"Erro ao criar orçamento: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash(f'Erro ao criar orçamento: {str(e)}', 'error')
    
    # GET - Exibir formulário
    try:
        clientes_db = Cliente.query.all()
        clientes = [{'id': c.id, 'nome': c.nome, 'email': c.email or ''} for c in clientes_db]
        
        tecnicos_db = Tecnico.query.filter_by(ativo=True).all()
        tecnicos = [{'id': t.id, 'nome': t.nome} for t in tecnicos_db]
    except Exception as e:
        print(f"Erro ao buscar clientes/técnicos: {e}")
        clientes = []
        tecnicos = []
    
    return render_template('admin/add_orcamento_ar.html', clientes=clientes, tecnicos=tecnicos)

@app.route('/admin/orcamentos-ar/<int:orcamento_id>')
@login_required
def view_orcamento_ar(orcamento_id):
    """Visualiza detalhes de um orçamento"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    try:
        orcamento = OrcamentoArCondicionado.query.get(orcamento_id)
        if not orcamento:
            flash('Orçamento não encontrado!', 'error')
            return redirect(url_for('admin_orcamentos_ar'))
        
        orcamento_dict = {
            'id': orcamento.id,
            'cliente_nome': orcamento.cliente.nome if orcamento.cliente else 'N/A',
            'cliente_email': orcamento.cliente.email if orcamento.cliente else '',
            'cliente_telefone': orcamento.cliente.telefone if orcamento.cliente else '',
            'tecnico_nome': orcamento.tecnico.nome if orcamento.tecnico else 'Não atribuído',
            'tipo_servico': orcamento.tipo_servico,
            'potencia_btu': orcamento.potencia_btu,
            'tipo_acesso': orcamento.tipo_acesso,
            'marca_aparelho': orcamento.marca_aparelho or '',
            'modelo_aparelho': orcamento.modelo_aparelho or '',
            'material_adicional': orcamento.material_adicional or '',
            'valor_material_adicional': float(orcamento.valor_material_adicional) if orcamento.valor_material_adicional else 0.00,
            'valor_base': float(orcamento.valor_base) if orcamento.valor_base else 0.00,
            'valor_acesso': float(orcamento.valor_acesso) if orcamento.valor_acesso else 0.00,
            'valor_total': float(orcamento.valor_total) if orcamento.valor_total else 0.00,
            'status': orcamento.status or 'pendente',
            'prazo_estimado': orcamento.prazo_estimado or '',
            'data_criacao': orcamento.data_criacao.strftime('%d/%m/%Y %H:%M') if orcamento.data_criacao else '',
            'pdf_id': orcamento.pdf_id,
            'pdf_filename': orcamento.pdf_filename or ''
        }
    except Exception as e:
        print(f"Erro ao buscar orçamento: {e}")
        flash('Erro ao buscar orçamento.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    return render_template('admin/view_orcamento_ar.html', orcamento=orcamento_dict)

@app.route('/admin/orcamentos-ar/<int:orcamento_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_orcamento_ar(orcamento_id):
    """Edita um orçamento existente"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    try:
        orcamento = OrcamentoArCondicionado.query.get(orcamento_id)
        if not orcamento:
            flash('Orçamento não encontrado!', 'error')
            return redirect(url_for('admin_orcamentos_ar'))
        
        if request.method == 'POST':
            orcamento.cliente_id = int(request.form.get('cliente_id'))
            tecnico_id = request.form.get('tecnico_id')
            orcamento.tecnico_id = int(tecnico_id) if tecnico_id and tecnico_id != '' else None
            orcamento.tipo_servico = request.form.get('tipo_servico')
            orcamento.potencia_btu = int(request.form.get('potencia_btu'))
            orcamento.tipo_acesso = request.form.get('tipo_acesso')
            orcamento.marca_aparelho = request.form.get('marca_aparelho', '').strip() or None
            orcamento.modelo_aparelho = request.form.get('modelo_aparelho', '').strip() or None
            material_adicional = request.form.get('material_adicional', '').strip() or None
            valor_material_adicional = request.form.get('valor_material_adicional', '0').strip()
            orcamento.status = request.form.get('status', 'pendente')
            orcamento.prazo_estimado = request.form.get('prazo_estimado', '').strip() or None
            
            # Recalcular valores
            valor_material = 0.00
            if material_adicional == 'Tubulação extra acima de 3m' and valor_material_adicional:
                valor_material = float(valor_material_adicional)
            
            calculo = calcular_preco_orcamento_ar(orcamento.tipo_servico, orcamento.potencia_btu, orcamento.tipo_acesso, material_adicional, valor_material)
            
            orcamento.material_adicional = material_adicional
            orcamento.valor_material_adicional = valor_material
            orcamento.valor_base = calculo['valor_base']
            orcamento.valor_acesso = calculo['valor_acesso']
            orcamento.valor_total = calculo['valor_total']
            orcamento.data_atualizacao = datetime.now()
            
            # Regenerar PDF
            pdf_result = gerar_pdf_orcamento_ar(orcamento)
            if pdf_result and pdf_result.get('pdf_id'):
                # Deletar PDF antigo se existir
                if orcamento.pdf_id:
                    try:
                        pdf_antigo = PDFDocument.query.get(orcamento.pdf_id)
                        if pdf_antigo:
                            db.session.delete(pdf_antigo)
                    except:
                        pass
                
                orcamento.pdf_id = pdf_result['pdf_id']
                orcamento.pdf_filename = pdf_result['pdf_filename']
            
            db.session.commit()
            
            flash('Orçamento atualizado com sucesso!', 'success')
            return redirect(url_for('admin_orcamentos_ar'))
        
        # GET - Exibir formulário
        clientes_db = Cliente.query.all()
        clientes = [{'id': c.id, 'nome': c.nome, 'email': c.email or ''} for c in clientes_db]
        
        tecnicos_db = Tecnico.query.filter_by(ativo=True).all()
        tecnicos = [{'id': t.id, 'nome': t.nome} for t in tecnicos_db]
        
        orcamento_dict = {
            'id': orcamento.id,
            'cliente_id': orcamento.cliente_id,
            'tecnico_id': orcamento.tecnico_id,
            'tipo_servico': orcamento.tipo_servico,
            'potencia_btu': orcamento.potencia_btu,
            'tipo_acesso': orcamento.tipo_acesso,
            'marca_aparelho': orcamento.marca_aparelho or '',
            'modelo_aparelho': orcamento.modelo_aparelho or '',
            'material_adicional': orcamento.material_adicional or '',
            'valor_material_adicional': float(orcamento.valor_material_adicional) if orcamento.valor_material_adicional else 0.00,
            'status': orcamento.status or 'pendente',
            'prazo_estimado': orcamento.prazo_estimado or ''
        }
        
        return render_template('admin/edit_orcamento_ar.html', orcamento=orcamento_dict, clientes=clientes, tecnicos=tecnicos)
    except Exception as e:
        print(f"Erro ao editar orçamento: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f'Erro ao editar orçamento: {str(e)}', 'error')
        return redirect(url_for('admin_orcamentos_ar'))

@app.route('/admin/orcamentos-ar/<int:orcamento_id>/delete', methods=['POST'])
@login_required
def delete_orcamento_ar(orcamento_id):
    """Deleta um orçamento"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    try:
        orcamento = OrcamentoArCondicionado.query.get(orcamento_id)
        if not orcamento:
            flash('Orçamento não encontrado!', 'error')
            return redirect(url_for('admin_orcamentos_ar'))
        
        # Deletar PDF se existir
        if orcamento.pdf_id:
            try:
                pdf_doc = PDFDocument.query.get(orcamento.pdf_id)
                if pdf_doc:
                    db.session.delete(pdf_doc)
            except Exception as e:
                print(f"Erro ao deletar PDF: {e}")
        
        db.session.delete(orcamento)
        db.session.commit()
        
        flash('Orçamento excluído com sucesso!', 'success')
    except Exception as e:
        print(f"Erro ao deletar orçamento: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f'Erro ao excluir orçamento: {str(e)}', 'error')
    
    return redirect(url_for('admin_orcamentos_ar'))

@app.route('/admin/orcamentos-ar/<int:orcamento_id>/pdf')
@login_required
def download_orcamento_ar_pdf(orcamento_id):
    """Download do PDF do orçamento"""
    if not use_database():
        flash('Banco de dados não configurado.', 'error')
        return redirect(url_for('admin_orcamentos_ar'))
    
    try:
        orcamento = OrcamentoArCondicionado.query.get(orcamento_id)
        if not orcamento or not orcamento.pdf_id:
            flash('PDF não encontrado!', 'error')
            return redirect(url_for('admin_orcamentos_ar'))
        
        pdf_doc = PDFDocument.query.get(orcamento.pdf_id)
        if pdf_doc and pdf_doc.dados:
            return Response(
                pdf_doc.dados,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'inline; filename={orcamento.pdf_filename or "orcamento.pdf"}'}
            )
        
        flash('PDF não encontrado!', 'error')
    except Exception as e:
        print(f"Erro ao buscar PDF: {e}")
        flash('Erro ao buscar PDF.', 'error')
    
    return redirect(url_for('admin_orcamentos_ar'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)

