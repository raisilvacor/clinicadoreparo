from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_file
from datetime import datetime
import json
import os
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui_altere_em_producao'

# Credenciais de admin (em produção, use hash e variáveis de ambiente)
ADMIN_USERNAME = 'raisilva'
ADMIN_PASSWORD = 'Rs2025'  # Altere em produção!

# Caminhos para os arquivos de dados
DATA_FILE = 'data/services.json'
CLIENTS_FILE = 'data/clients.json'
COMPROVANTES_FILE = 'data/comprovantes.json'
FIDELIDADE_FILE = 'data/fidelidade.json'
WHATSAPP_BOT_FILE = 'data/whatsapp_bot.json'
PDFS_DIR = 'static/pdfs'

# Criar diretório de PDFs se não existir
if not os.path.exists(PDFS_DIR):
    os.makedirs(PDFS_DIR)

# ==================== FUNÇÕES AUXILIARES ====================

def get_proximo_numero_ordem():
    """Retorna o próximo número sequencial de ordem"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Coletar todos os números de ordem existentes
    numeros_existentes = []
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            if ordem.get('numero_ordem'):
                try:
                    numeros_existentes.append(int(ordem['numero_ordem']))
                except:
                    pass
    
    # Retornar o próximo número
    if numeros_existentes:
        return max(numeros_existentes) + 1
    else:
        return 1

def atualizar_numeros_ordens():
    """Atualiza ordens existentes que não têm número de ordem"""
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    atualizado = False
    
    # Coletar todos os números existentes
    numeros_existentes = []
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            if ordem.get('numero_ordem'):
                try:
                    numeros_existentes.append(int(ordem['numero_ordem']))
                except:
                    pass
    
    # Determinar próximo número
    if numeros_existentes:
        numero_atual = max(numeros_existentes) + 1
    else:
        numero_atual = 1
    
    # Atribuir números para ordens sem número
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            if not ordem.get('numero_ordem'):
                ordem['numero_ordem'] = numero_atual
                numero_atual += 1
                atualizado = True
    
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
                    'preco': None,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 2,
                    'nome': 'Eletrodomésticos',
                    'descricao': 'Geladeiras, máquinas de lavar, micro-ondas e todos os eletrodomésticos.',
                    'preco': None,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 3,
                    'nome': 'Computadores e Notebook',
                    'descricao': 'Reparo e manutenção de computadores, notebooks e componentes.',
                    'preco': None,
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
                    'preco': None,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 2,
                    'nome': 'Eletrodomésticos',
                    'descricao': 'Geladeiras, máquinas de lavar, micro-ondas e todos os eletrodomésticos.',
                    'preco': None,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'id': 3,
                    'nome': 'Computadores e Notebook',
                    'descricao': 'Reparo e manutenção de computadores, notebooks e componentes.',
                    'preco': None,
                    'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            ]
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

init_data_file()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sobre')
def sobre():
    return render_template('sobre.html')

@app.route('/servicos')
def servicos():
    return render_template('servicos.html')

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
    
    return render_template('contato.html')

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
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('admin_login'))

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
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return render_template('admin/servicos.html', servicos=data['services'])

@app.route('/admin/servicos/add', methods=['GET', 'POST'])
@login_required
def add_servico_admin():
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        preco = request.form.get('preco')
        
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        novo_servico = {
            'id': len(data['services']) + 1,
            'nome': nome,
            'descricao': descricao,
            'preco': preco,
            'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        data['services'].append(novo_servico)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        flash('Serviço adicionado com sucesso!', 'success')
        return redirect(url_for('admin_servicos'))
    
    return render_template('admin/add_servico.html')

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
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Coletar todas as ordens de todos os clientes
    todas_ordens = []
    for cliente in data['clients']:
        for ordem in cliente.get('ordens', []):
            ordem_completa = ordem.copy()
            ordem_completa['cliente_nome'] = cliente['nome']
            ordem_completa['cliente_id'] = cliente['id']
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
            'total': total,
            'status': status,
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
        pdf_filename = gerar_pdf_ordem(cliente, nova_ordem)
        nova_ordem['pdf_filename'] = pdf_filename
        
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
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        services_data = json.load(f)
    
    with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
        clients_data = json.load(f)
    
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
        
        # Atualizar ordem (manter número da ordem original)
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
            'total': total,
            'status': status,
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
        if ordem.get('pdf_filename'):
            # Deletar PDF antigo se existir
            old_pdf = os.path.join(PDFS_DIR, ordem['pdf_filename'])
            if os.path.exists(old_pdf):
                os.remove(old_pdf)
        
        pdf_filename = gerar_pdf_ordem(cliente, ordem_atualizada)
        ordem_atualizada['pdf_filename'] = pdf_filename
        
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
    
    return render_template('admin/edit_ordem.html', cliente=cliente, ordem=ordem, servicos=services_data['services'])

@app.route('/admin/clientes/<int:cliente_id>/ordens/<int:ordem_id>/delete', methods=['POST'])
@login_required
def delete_ordem_servico(cliente_id, ordem_id):
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
    
    # Deletar PDF se existir
    if ordem and ordem.get('pdf_filename'):
        pdf_path = os.path.join(PDFS_DIR, ordem['pdf_filename'])
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
    
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

# ==================== PDF GENERATION ====================

def gerar_pdf_ordem(cliente, ordem):
    """Gera PDF da ordem de serviço"""
    # Nome do arquivo PDF
    pdf_filename = f"ordem_{cliente['id']}_{ordem['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(PDFS_DIR, pdf_filename)
    
    # Criar documento PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
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
    numero_ordem = ordem.get('numero_ordem', ordem.get('id', 1))
    try:
        numero_formatado = f"#{int(numero_ordem)}"
    except:
        numero_formatado = f"#{numero_ordem}"
    
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
    
    return pdf_filename

@app.route('/admin/download-pdf/<path:filename>')
@login_required
def download_pdf(filename):
    """Download do PDF da ordem (admin)"""
    pdf_path = os.path.join(PDFS_DIR, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    else:
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
    
    pdf_path = os.path.join(PDFS_DIR, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    else:
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
    
    comprovante = next((c for c in comprovantes_data['comprovantes'] if c.get('pdf_filename') == filename and c.get('cliente_id') == cliente_id), None)
    
    if not comprovante:
        flash('Você não tem permissão para baixar este arquivo!', 'error')
        return redirect(url_for('client_dashboard'))
    
    pdf_path = os.path.join(PDFS_DIR, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    else:
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
        pdf_filename = gerar_pdf_comprovante(cliente, ordem, novo_comprovante)
        novo_comprovante['pdf_filename'] = pdf_filename
        
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
    """Gera PDF do comprovante de pagamento"""
    pdf_filename = f"comprovante_{comprovante['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(PDFS_DIR, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
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
        ['Número da Ordem:', f"#{comprovante['numero_ordem']:04d}"],
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
    return pdf_filename

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
            old_pdf = os.path.join(PDFS_DIR, comprovante['pdf_filename'])
            if os.path.exists(old_pdf):
                os.remove(old_pdf)
        
        # Regenerar PDF
        pdf_filename = gerar_pdf_comprovante(cliente, ordem, comprovante)
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
    pdf_path = os.path.join(PDFS_DIR, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    else:
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

# ==================== WHATSAPP BOT ====================

def init_whatsapp_bot_file():
    """Inicializa arquivo do robô WhatsApp se não existir"""
    if not os.path.exists(WHATSAPP_BOT_FILE):
        data_dir = os.path.dirname(WHATSAPP_BOT_FILE)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        default_config = {
            'ativo': False,
            'tipo_integracao': 'evolution',
            'numero_whatsapp': '',
            'evolution_api_url': '',
            'evolution_api_key': '',
            'evolution_instance_name': 'default',
            'twilio_account_sid': '',
            'twilio_auth_token': '',
            'twilio_from_number': '',
            'business_access_token': '',
            'business_phone_number_id': '',
            'mensagem_inicial': 'Olá! sou o VirTEc, seu técnico virtual.',
            'pergunta': 'Qual serviço está buscando?',
            'opcoes': [
                {'numero': '1', 'texto': 'Reparação de celulares'},
                {'numero': '2', 'texto': 'Reparação de Eletrodomésticos'},
                {'numero': '3', 'texto': 'Reparação de Notebooks e Computadores'},
                {'numero': '4', 'texto': 'Outro tipo de serviço'},
                {'numero': '5', 'texto': 'Falar com Técnico especialista'}
            ],
            'respostas': {
                '1': 'Entendido! Você está interessado em Reparação de celulares. Em breve um técnico entrará em contato.',
                '2': 'Entendido! Você está interessado em Reparação de Eletrodomésticos. Em breve um técnico entrará em contato.',
                '3': 'Entendido! Você está interessado em Reparação de Notebooks e Computadores. Em breve um técnico entrará em contato.',
                '4': 'Entendido! Você está interessado em outro tipo de serviço. Em breve um técnico entrará em contato.',
                '5': 'Entendido! Você deseja falar com um técnico especialista. Em breve um técnico entrará em contato.'
            }
        }
        with open(WHATSAPP_BOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

@app.route('/admin/whatsapp-bot', methods=['GET', 'POST'])
@login_required
def admin_whatsapp_bot():
    """Página de configuração do robô WhatsApp"""
    init_whatsapp_bot_file()
    
    if request.method == 'POST':
        with open(WHATSAPP_BOT_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Atualizar configurações
        config['ativo'] = request.form.get('ativo') == 'on'
        config['tipo_integracao'] = request.form.get('tipo_integracao', 'evolution')
        config['numero_whatsapp'] = request.form.get('numero_whatsapp', '')
        config['evolution_api_url'] = request.form.get('evolution_api_url', '')
        config['evolution_api_key'] = request.form.get('evolution_api_key', '')
        config['evolution_instance_name'] = request.form.get('evolution_instance_name', 'default')
        config['twilio_account_sid'] = request.form.get('twilio_account_sid', '')
        config['twilio_auth_token'] = request.form.get('twilio_auth_token', '')
        config['twilio_from_number'] = request.form.get('twilio_from_number', '')
        config['business_access_token'] = request.form.get('business_access_token', '')
        config['business_phone_number_id'] = request.form.get('business_phone_number_id', '')
        config['mensagem_inicial'] = request.form.get('mensagem_inicial', '')
        config['pergunta'] = request.form.get('pergunta', '')
        
        # Atualizar opções
        config['opcoes'] = []
        for i in range(1, 6):
            numero = request.form.get(f'opcao_numero_{i}', '')
            texto = request.form.get(f'opcao_texto_{i}', '')
            if numero and texto:
                config['opcoes'].append({'numero': numero, 'texto': texto})
        
        # Atualizar respostas
        for i in range(1, 6):
            numero = request.form.get(f'opcao_numero_{i}', '')
            resposta = request.form.get(f'resposta_{i}', '')
            if numero and resposta:
                config['respostas'][numero] = resposta
        
        # Salvar configurações
        with open(WHATSAPP_BOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # Configurar webhook automaticamente na Evolution API se for esse tipo
        if config.get('tipo_integracao') == 'evolution' and config.get('evolution_api_url'):
            try:
                webhook_url = request.host_url.rstrip('/') + '/api/whatsapp/webhook'
                configurar_webhook_evolution(config, webhook_url)
            except Exception as e:
                print(f"Erro ao configurar webhook: {str(e)}")
        
        flash('Configurações do robô WhatsApp salvas com sucesso!', 'success')
        return redirect(url_for('admin_whatsapp_bot'))
    
    # GET - Exibir configurações
    with open(WHATSAPP_BOT_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return render_template('admin/whatsapp_bot.html', config=config)

def configurar_webhook_evolution(config, webhook_url):
    """Configura webhook automaticamente na Evolution API"""
    try:
        import requests
        api_url = config.get('evolution_api_url', '')
        instance_name = config.get('evolution_instance_name', 'default')
        api_key = config.get('evolution_api_key', '')
        
        if not api_url:
            return
        
        url = f"{api_url}/webhook/set/{instance_name}"
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['apikey'] = api_key
        
        payload = {
            'url': webhook_url,
            'events': ['messages.upsert', 'messages.update']
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"Webhook configurado com sucesso: {webhook_url}")
        else:
            print(f"Erro ao configurar webhook: {response.status_code}")
    except ImportError:
        print("Biblioteca 'requests' não instalada. Instale com: pip install requests")
    except Exception as e:
        print(f"Erro ao configurar webhook Evolution API: {str(e)}")

@app.route('/api/whatsapp/setup-evolution', methods=['POST'])
@login_required
def setup_evolution_api():
    """Configura automaticamente a Evolution API e retorna QR Code"""
    try:
        import requests
        import base64
        
        data = request.get_json()
        api_url = data.get('api_url', '').rstrip('/')
        api_key = data.get('api_key', '')
        
        if not api_url:
            return jsonify({'success': False, 'message': 'URL da API não fornecida'}), 400
        
        # Gerar nome único para a instância
        instance_name = f"clinica-reparo-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['apikey'] = api_key
        
        # Preparar URL do webhook
        webhook_url = request.host_url.rstrip('/') + '/api/whatsapp/webhook'
        
        # Criar instância com webhook configurado
        create_url = f"{api_url}/instance/create"
        create_payload = {
            'instanceName': instance_name,
            'token': instance_name,
            'qrcode': True,
            'integration': 'WHATSAPP-BAILEYS',
            'webhook': {
                'url': webhook_url,
                'events': ['messages.upsert', 'messages.update'],
                'webhook_by_events': True,
                'webhook_base64': False
            }
        }
        
        response = requests.post(create_url, json=create_payload, headers=headers, timeout=10)
        
        # Se falhar com webhook, tentar criar sem webhook primeiro
        if response.status_code not in [200, 201]:
            create_payload_simple = {
                'instanceName': instance_name,
                'token': instance_name,
                'qrcode': True,
                'integration': 'WHATSAPP-BAILEYS'
            }
            response = requests.post(create_url, json=create_payload_simple, headers=headers, timeout=10)
            
            if response.status_code not in [200, 201]:
                return jsonify({
                    'success': False, 
                    'message': f'Erro ao criar instância: {response.status_code} - {response.text[:200]}'
                }), 400
        
        # Aguardar um pouco para a instância ser criada
        import time
        time.sleep(2)
        
        # Obter QR Code
        qr_url = f"{api_url}/instance/connect/{instance_name}"
        qr_response = requests.get(qr_url, headers=headers, timeout=10)
        
        if qr_response.status_code == 200:
            qr_data = qr_response.json()
            qr_code_base64 = qr_data.get('base64', '') or qr_data.get('qrcode', {}).get('base64', '')
            
            if qr_code_base64:
                # Atualizar configuração com o nome da instância
                with open(WHATSAPP_BOT_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                config['evolution_api_url'] = api_url
                config['evolution_api_key'] = api_key
                config['evolution_instance_name'] = instance_name
                config['tipo_integracao'] = 'evolution'
                
                with open(WHATSAPP_BOT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                # Configurar webhook automaticamente (se não foi configurado na criação)
                try:
                    configurar_webhook_evolution(config, webhook_url)
                except:
                    pass
                
                return jsonify({
                    'success': True,
                    'qr_code': f"data:image/png;base64,{qr_code_base64}",
                    'instance_name': instance_name
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'QR Code não gerado. Verifique se a Evolution API está rodando.'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': f'Erro ao obter QR Code: {qr_response.status_code} - {qr_response.text[:200]}'
            }), 400
            
    except ImportError:
        return jsonify({
            'success': False,
            'message': 'Biblioteca requests não instalada. Execute: pip install requests'
        }), 500
    except requests.exceptions.ConnectionError as e:
        return jsonify({
            'success': False,
            'message': 'Não foi possível conectar à Evolution API. Verifique se ela está rodando. Execute: docker run -p 8080:8080 atendai/evolution-api'
        }), 400
    except Exception as e:
        error_msg = str(e)
        if 'Connection refused' in error_msg or '10061' in error_msg or 'Failed to establish' in error_msg:
            return jsonify({
                'success': False,
                'message': 'Não foi possível conectar à Evolution API em ' + api_url + '. Verifique se a Evolution API está rodando. Execute: docker run -p 8080:8080 atendai/evolution-api'
            }), 400
        return jsonify({
            'success': False,
            'message': f'Erro: {error_msg}'
        }), 500

@app.route('/api/whatsapp/test-connection', methods=['POST'])
@login_required
def test_evolution_connection():
    """Testa conexão com a Evolution API"""
    try:
        import requests
        
        data = request.get_json()
        api_url = data.get('api_url', '').rstrip('/')
        api_key = data.get('api_key', '')
        
        if not api_url:
            return jsonify({'connected': False, 'message': 'URL não fornecida'}), 400
        
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['apikey'] = api_key
        
        # Testar conexão básica com a API
        test_url = f"{api_url}/health"
        try:
            response = requests.get(test_url, headers=headers, timeout=5)
            if response.status_code == 200:
                return jsonify({
                    'connected': True,
                    'message': 'Evolution API está funcionando!'
                })
        except:
            pass
        
        # Tentar endpoint alternativo
        test_url = f"{api_url}/"
        try:
            response = requests.get(test_url, headers=headers, timeout=5)
            if response.status_code in [200, 404, 401]:  # 404 ou 401 também indica que a API está respondendo
                return jsonify({
                    'connected': True,
                    'message': 'Evolution API está respondendo!'
                })
        except:
            pass
        
        # Se chegou aqui, não conseguiu conectar
        return jsonify({
            'connected': False,
            'message': 'Não foi possível conectar à Evolution API. Verifique se ela está rodando e se a URL está correta.'
        }), 400
            
    except ImportError:
        return jsonify({
            'connected': False,
            'message': 'Biblioteca requests não instalada. Execute: pip install requests'
        }), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'connected': False,
            'message': 'Erro de conexão. Verifique se a Evolution API está rodando. Execute: docker run -p 8080:8080 atendai/evolution-api'
        }), 400
    except Exception as e:
        error_msg = str(e)
        if 'Connection refused' in error_msg or '10061' in error_msg:
            return jsonify({
                'connected': False,
                'message': 'Não foi possível conectar. Verifique se a Evolution API está rodando em ' + api_url
            }), 400
        return jsonify({
            'connected': False,
            'message': f'Erro: {error_msg}'
        }), 500

@app.route('/api/whatsapp/check-connection', methods=['POST'])
@login_required
def check_whatsapp_connection():
    """Verifica se o WhatsApp está conectado"""
    try:
        import requests
        
        data = request.get_json()
        api_url = data.get('api_url', '').rstrip('/')
        api_key = data.get('api_key', '')
        instance_name = data.get('instance_name', 'default')
        
        if not api_url:
            return jsonify({'connected': False, 'message': 'URL não fornecida'}), 400
        
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['apikey'] = api_key
        
        # Verificar status da instância
        status_url = f"{api_url}/instance/connectionState/{instance_name}"
        response = requests.get(status_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            status_data = response.json()
            state = status_data.get('state', '').lower()
            
            connected = state in ['open', 'connected']
            
            return jsonify({
                'connected': connected,
                'state': state,
                'message': 'Conectado' if connected else 'Aguardando conexão'
            })
        else:
            return jsonify({
                'connected': False,
                'message': f'Erro ao verificar status: {response.status_code}'
            }), 400
            
    except ImportError:
        return jsonify({
            'connected': False,
            'message': 'Biblioteca requests não instalada'
        }), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'connected': False,
            'message': 'Erro de conexão com a Evolution API'
        }), 400
    except Exception as e:
        return jsonify({
            'connected': False,
            'message': f'Erro: {str(e)}'
        }), 500

@app.route('/api/whatsapp/webhook', methods=['POST', 'GET'])
def whatsapp_webhook():
    """Webhook para receber mensagens do WhatsApp"""
    init_whatsapp_bot_file()
    
    if request.method == 'GET':
        # Verificação do webhook (para APIs como Twilio)
        return jsonify({'status': 'ok'}), 200
    
    # POST - Receber mensagem
    try:
        with open(WHATSAPP_BOT_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if not config.get('ativo', False):
            return jsonify({'status': 'bot_inactive'}), 200
        
        # Extrair dados da mensagem (formato pode variar conforme a API)
        # Twilio pode enviar como form-data ou JSON
        data = request.get_json() or request.form.to_dict() or {}
        
        # Tentar diferentes formatos de API
        from_number = None
        message_body = None
        
        # Formato Twilio (form-data ou JSON)
        if 'From' in data and 'Body' in data:
            from_number = data['From'].replace('whatsapp:', '').replace('+', '')
            message_body = data['Body'].strip()
        
        # Formato WhatsApp Business API
        elif 'entry' in data and len(data.get('entry', [])) > 0:
            entry = data['entry'][0]
            if 'changes' in entry and len(entry['changes']) > 0:
                change = entry['changes'][0]
                if 'value' in change and 'messages' in change['value']:
                    messages = change['value']['messages']
                    if len(messages) > 0:
                        message = messages[0]
                        from_number = message.get('from', '').replace('+', '')
                        message_body = message.get('text', {}).get('body', '').strip()
        
        # Formato genérico
        elif 'from' in data and 'message' in data:
            from_number = str(data['from']).replace('+', '')
            message_body = str(data['message']).strip()
        
        if not from_number or not message_body:
            return jsonify({'status': 'invalid_data'}), 400
        
        # Processar mensagem
        resposta = processar_mensagem_whatsapp(from_number, message_body, config)
        
        if resposta:
            # Enviar resposta automaticamente
            enviar_resposta_whatsapp(from_number, resposta, config)
            
            return jsonify({
                'status': 'success',
                'to': from_number,
                'message': resposta
            }), 200
        
        return jsonify({'status': 'no_response'}), 200
        
    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def processar_mensagem_whatsapp(from_number, message_body, config):
    """Processa mensagem recebida e retorna resposta"""
    # Normalizar mensagem
    message_lower = message_body.lower().strip()
    
    # Verificar se é primeira mensagem ou resposta a opção
    # Aqui você pode usar um sistema de sessão/conversação
    
    # Se a mensagem contém apenas números (1-5), é uma resposta às opções
    if message_lower in ['1', '2', '3', '4', '5']:
        if message_lower in config.get('respostas', {}):
            return config['respostas'][message_lower]
        else:
            return "Opção inválida. Por favor, escolha uma opção de 1 a 5."
    
    # Se é qualquer outra mensagem (oi, ola, etc), enviar mensagem inicial
    mensagem_completa = f"{config.get('mensagem_inicial', '')}\n\n{config.get('pergunta', '')}\n\n"
    
    # Adicionar opções
    for opcao in config.get('opcoes', []):
        mensagem_completa += f"{opcao['numero']}. {opcao['texto']}\n"
    
    return mensagem_completa.strip()

def enviar_resposta_whatsapp(to_number, message, config):
    """Envia resposta via API do WhatsApp"""
    try:
        tipo_integracao = config.get('tipo_integracao', 'evolution')
        
        # Evolution API
        if tipo_integracao == 'evolution':
            try:
                import requests
                api_url = config.get('evolution_api_url', '')
                instance_name = config.get('evolution_instance_name', 'default')
                api_key = config.get('evolution_api_key', '')
                
                if api_url:
                    url = f"{api_url}/message/sendText/{instance_name}"
                    headers = {'Content-Type': 'application/json'}
                    if api_key:
                        headers['apikey'] = api_key
                    
                    payload = {
                        'number': to_number,
                        'text': message
                    }
                    
                    requests.post(url, json=payload, headers=headers, timeout=5)
            except ImportError:
                print("Biblioteca 'requests' não instalada. Instale com: pip install requests")
            except Exception as e:
                print(f"Erro ao enviar via Evolution API: {str(e)}")
        
        # Twilio
        elif tipo_integracao == 'twilio':
            try:
                from twilio.rest import Client
                account_sid = config.get('twilio_account_sid', '')
                auth_token = config.get('twilio_auth_token', '')
                from_number = config.get('twilio_from_number', '')
                
                if account_sid and auth_token and from_number:
                    client = Client(account_sid, auth_token)
                    client.messages.create(
                        body=message,
                        from_=from_number,
                        to=f'whatsapp:+{to_number}'
                    )
            except ImportError:
                print("Biblioteca 'twilio' não instalada. Instale com: pip install twilio")
            except Exception as e:
                print(f"Erro ao enviar via Twilio: {str(e)}")
        
        # WhatsApp Business API
        elif tipo_integracao == 'whatsapp_business':
            try:
                import requests
                access_token = config.get('business_access_token', '')
                phone_number_id = config.get('business_phone_number_id', '')
                
                if access_token and phone_number_id:
                    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json'
                    }
                    payload = {
                        'messaging_product': 'whatsapp',
                        'to': to_number,
                        'type': 'text',
                        'text': {'body': message}
                    }
                    requests.post(url, json=payload, headers=headers, timeout=5)
            except ImportError:
                print("Biblioteca 'requests' não instalada. Instale com: pip install requests")
            except Exception as e:
                print(f"Erro ao enviar via WhatsApp Business API: {str(e)}")
                
    except Exception as e:
        print(f"Erro ao enviar mensagem: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

