#!/usr/bin/env python3
"""
Script de migração de dados JSON para PostgreSQL
Migra todos os dados dos arquivos JSON para o banco de dados PostgreSQL
"""

import os
import json
from datetime import datetime
from app import app, db
from models import (
    Cliente, Servico, Tecnico, OrdemServico, Comprovante, Cupom,
    Slide, Footer, Marca, Milestone, AdminUser, Agendamento, Artigo, Contato
)

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

def migrate_clients():
    """Migra clientes e suas ordens de serviço"""
    if not os.path.exists('data/clients.json'):
        print("Arquivo clients.json não encontrado")
        return
    
    with open('data/clients.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for client_data in data.get('clients', []):
        # Verificar se já existe
        cliente = Cliente.query.get(client_data.get('id'))
        if not cliente:
            cliente = Cliente(
                id=client_data.get('id'),
                nome=client_data.get('nome'),
                email=client_data.get('email'),
                telefone=client_data.get('telefone'),
                cpf=client_data.get('cpf'),
                endereco=client_data.get('endereco'),
                username=client_data.get('username'),
                password=client_data.get('password'),
                data_cadastro=parse_datetime(client_data.get('data_cadastro'))
            )
            db.session.add(cliente)
            count += 1
        
        # Migrar ordens de serviço do cliente
        for ordem_data in client_data.get('ordens', []):
            ordem = OrdemServico.query.filter_by(numero_ordem=str(ordem_data.get('numero_ordem'))).first()
            if not ordem:
                ordem = OrdemServico(
                    id=ordem_data.get('id'),
                    numero_ordem=str(ordem_data.get('numero_ordem')),
                    cliente_id=client_data.get('id'),
                    tecnico_id=ordem_data.get('tecnico_id'),
                    servico=ordem_data.get('servico'),
                    tipo_aparelho=ordem_data.get('tipo_aparelho'),
                    marca=ordem_data.get('marca'),
                    modelo=ordem_data.get('modelo'),
                    numero_serie=ordem_data.get('numero_serie'),
                    defeitos_cliente=ordem_data.get('defeitos_cliente'),
                    diagnostico_tecnico=ordem_data.get('diagnostico_tecnico'),
                    pecas=ordem_data.get('pecas', []),
                    custo_pecas=float(ordem_data.get('custo_pecas', 0)) or 0,
                    custo_mao_obra=float(ordem_data.get('custo_mao_obra', 0)) or 0,
                    subtotal=float(ordem_data.get('subtotal', 0)) or 0,
                    desconto_percentual=float(ordem_data.get('desconto_percentual', 0)) or 0,
                    valor_desconto=float(ordem_data.get('valor_desconto', 0)) or 0,
                    cupom_id=ordem_data.get('cupom_id'),
                    total=float(ordem_data.get('total', 0)) or 0,
                    status=ordem_data.get('status', 'pendente'),
                    prazo_estimado=ordem_data.get('prazo_estimado'),
                    pdf_filename=ordem_data.get('pdf_filename'),
                    data=parse_datetime(ordem_data.get('data'))
                )
                db.session.add(ordem)
    
    db.session.commit()
    print(f"✅ Migrados {count} clientes e suas ordens de serviço")

def migrate_services():
    """Migra serviços"""
    if not os.path.exists('data/services.json'):
        print("Arquivo services.json não encontrado")
        return
    
    with open('data/services.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for service_data in data.get('services', []):
        servico = Servico.query.get(service_data.get('id'))
        if not servico:
            servico = Servico(
                id=service_data.get('id'),
                nome=service_data.get('nome'),
                descricao=service_data.get('descricao'),
                imagem=service_data.get('imagem', ''),
                ordem=service_data.get('ordem', 999),
                ativo=service_data.get('ativo', True),
                data=parse_datetime(service_data.get('data'))
            )
            db.session.add(servico)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} serviços")

def migrate_tecnicos():
    """Migra técnicos"""
    if not os.path.exists('data/tecnicos.json'):
        print("Arquivo tecnicos.json não encontrado")
        return
    
    with open('data/tecnicos.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for tecnico_data in data.get('tecnicos', []):
        tecnico = Tecnico.query.get(tecnico_data.get('id'))
        if not tecnico:
            tecnico = Tecnico(
                id=tecnico_data.get('id'),
                nome=tecnico_data.get('nome'),
                telefone=tecnico_data.get('telefone'),
                email=tecnico_data.get('email'),
                especialidade=tecnico_data.get('especialidade'),
                ativo=tecnico_data.get('ativo', True),
                data_criacao=parse_datetime(tecnico_data.get('data_criacao'))
            )
            db.session.add(tecnico)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} técnicos")

def migrate_slides():
    """Migra slides"""
    if not os.path.exists('data/slides.json'):
        print("Arquivo slides.json não encontrado")
        return
    
    with open('data/slides.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for slide_data in data.get('slides', []):
        slide = Slide.query.get(slide_data.get('id'))
        if not slide:
            slide = Slide(
                id=slide_data.get('id'),
                imagem=slide_data.get('imagem'),
                link=slide_data.get('link'),
                link_target=slide_data.get('link_target', '_self'),
                ordem=slide_data.get('ordem', 1),
                ativo=slide_data.get('ativo', True)
            )
            db.session.add(slide)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} slides")

def migrate_footer():
    """Migra configurações do footer"""
    if not os.path.exists('data/footer.json'):
        print("Arquivo footer.json não encontrado")
        return
    
    with open('data/footer.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    footer = Footer.query.first()
    if not footer:
        footer = Footer(
            id=1,
            descricao=data.get('descricao'),
            redes_sociais=data.get('redes_sociais', {}),
            contato=data.get('contato', {}),
            copyright=data.get('copyright'),
            whatsapp_float=data.get('whatsapp_float')
        )
        db.session.add(footer)
        db.session.commit()
        print("✅ Migrado footer")

def migrate_marcas():
    """Migra marcas"""
    if not os.path.exists('data/marcas.json'):
        print("Arquivo marcas.json não encontrado")
        return
    
    with open('data/marcas.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for marca_data in data.get('marcas', []):
        marca = Marca.query.get(marca_data.get('id'))
        if not marca:
            marca = Marca(
                id=marca_data.get('id'),
                nome=marca_data.get('nome'),
                imagem=marca_data.get('imagem'),
                ordem=marca_data.get('ordem', 1),
                ativo=marca_data.get('ativo', True)
            )
            db.session.add(marca)
            count += 1
    
    db.session.commit()
    print(f"✅ Migradas {count} marcas")

def migrate_milestones():
    """Migra milestones"""
    if not os.path.exists('data/milestones.json'):
        print("Arquivo milestones.json não encontrado")
        return
    
    with open('data/milestones.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for milestone_data in data.get('milestones', []):
        milestone = Milestone.query.get(milestone_data.get('id'))
        if not milestone:
            milestone = Milestone(
                id=milestone_data.get('id'),
                titulo=milestone_data.get('titulo'),
                imagem=milestone_data.get('imagem'),
                ordem=milestone_data.get('ordem', 1),
                ativo=milestone_data.get('ativo', True)
            )
            db.session.add(milestone)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} milestones")

def migrate_admin_users():
    """Migra usuários admin"""
    if not os.path.exists('data/admin_users.json'):
        print("Arquivo admin_users.json não encontrado")
        return
    
    with open('data/admin_users.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for user_data in data.get('users', []):
        user = AdminUser.query.get(user_data.get('id'))
        if not user:
            user = AdminUser(
                id=user_data.get('id'),
                username=user_data.get('username'),
                password=user_data.get('password'),
                nome=user_data.get('nome'),
                email=user_data.get('email'),
                ativo=user_data.get('ativo', True),
                data_criacao=parse_datetime(user_data.get('data_criacao'))
            )
            db.session.add(user)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} usuários admin")

def migrate_agendamentos():
    """Migra agendamentos"""
    if not os.path.exists('data/agendamentos.json'):
        print("Arquivo agendamentos.json não encontrado")
        return
    
    with open('data/agendamentos.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for agendamento_data in data.get('agendamentos', []):
        agendamento = Agendamento.query.get(agendamento_data.get('id'))
        if not agendamento:
            data_agendamento = agendamento_data.get('data_agendamento')
            if isinstance(data_agendamento, str):
                try:
                    data_agendamento = datetime.strptime(data_agendamento, '%Y-%m-%d').date()
                except:
                    data_agendamento = datetime.now().date()
            
            agendamento = Agendamento(
                id=agendamento_data.get('id'),
                nome=agendamento_data.get('nome'),
                email=agendamento_data.get('email'),
                telefone=agendamento_data.get('telefone'),
                data_agendamento=data_agendamento,
                hora_agendamento=agendamento_data.get('hora_agendamento', ''),
                tipo_servico=agendamento_data.get('tipo_servico'),
                observacoes=agendamento_data.get('observacoes'),
                status=agendamento_data.get('status', 'pendente'),
                data_criacao=parse_datetime(agendamento_data.get('data_criacao'))
            )
            db.session.add(agendamento)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} agendamentos")

def migrate_blog():
    """Migra artigos do blog"""
    if not os.path.exists('data/blog.json'):
        print("Arquivo blog.json não encontrado")
        return
    
    with open('data/blog.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for artigo_data in data.get('artigos', []):
        artigo = Artigo.query.get(artigo_data.get('id'))
        if not artigo:
            data_pub = artigo_data.get('data_publicacao')
            if isinstance(data_pub, str):
                try:
                    data_pub = datetime.strptime(data_pub, '%Y-%m-%d %H:%M:%S')
                except:
                    try:
                        data_pub = datetime.strptime(data_pub, '%Y-%m-%d')
                    except:
                        data_pub = datetime.now()
            
            artigo = Artigo(
                id=artigo_data.get('id'),
                titulo=artigo_data.get('titulo'),
                subtitulo=artigo_data.get('subtitulo'),
                slug=artigo_data.get('slug'),
                categoria=artigo_data.get('categoria'),
                autor=artigo_data.get('autor'),
                resumo=artigo_data.get('resumo'),
                conteudo=artigo_data.get('conteudo'),
                imagem_destaque=artigo_data.get('imagem_destaque'),
                data_publicacao=data_pub,
                ativo=artigo_data.get('ativo', True),
                data_criacao=parse_datetime(artigo_data.get('data_criacao'))
            )
            db.session.add(artigo)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} artigos do blog")

def migrate_comprovantes():
    """Migra comprovantes"""
    if not os.path.exists('data/comprovantes.json'):
        print("Arquivo comprovantes.json não encontrado")
        return
    
    with open('data/comprovantes.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for comprovante_data in data.get('comprovantes', []):
        comprovante = Comprovante.query.get(comprovante_data.get('id'))
        if not comprovante:
            comprovante = Comprovante(
                id=comprovante_data.get('id'),
                cliente_id=comprovante_data.get('cliente_id'),
                cliente_nome=comprovante_data.get('cliente_nome'),
                ordem_id=comprovante_data.get('ordem_id'),
                numero_ordem=comprovante_data.get('numero_ordem'),
                valor_total=float(comprovante_data.get('valor_total', 0)) or 0,
                valor_pago=float(comprovante_data.get('valor_pago', 0)) or 0,
                forma_pagamento=comprovante_data.get('forma_pagamento'),
                parcelas=comprovante_data.get('parcelas', 1),
                pdf_filename=comprovante_data.get('pdf_filename'),
                data=parse_datetime(comprovante_data.get('data'))
            )
            db.session.add(comprovante)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} comprovantes")

def migrate_cupons():
    """Migra cupons de fidelidade"""
    if not os.path.exists('data/fidelidade.json'):
        print("Arquivo fidelidade.json não encontrado")
        return
    
    with open('data/fidelidade.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for cupom_data in data.get('cupons', []):
        cupom = Cupom.query.get(cupom_data.get('id'))
        if not cupom:
            cupom = Cupom(
                id=cupom_data.get('id'),
                cliente_id=cupom_data.get('cliente_id'),
                cliente_nome=cupom_data.get('cliente_nome'),
                desconto_percentual=float(cupom_data.get('desconto_percentual', 0)) or 0,
                usado=cupom_data.get('usado', False),
                ordem_id=cupom_data.get('ordem_id'),
                data_emissao=parse_datetime(cupom_data.get('data_emissao')),
                data_uso=parse_datetime(cupom_data.get('data_uso')) if cupom_data.get('data_uso') else None
            )
            db.session.add(cupom)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} cupons")

def migrate_contatos():
    """Migra contatos do formulário"""
    if not os.path.exists('data/services.json'):
        return
    
    with open('data/services.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for contato_data in data.get('contacts', []):
        contato = Contato.query.get(contato_data.get('id'))
        if not contato:
            contato = Contato(
                id=contato_data.get('id'),
                nome=contato_data.get('nome'),
                email=contato_data.get('email'),
                telefone=contato_data.get('telefone'),
                servico=contato_data.get('servico'),
                mensagem=contato_data.get('mensagem'),
                data=parse_datetime(contato_data.get('data'))
            )
            db.session.add(contato)
            count += 1
    
    db.session.commit()
    print(f"✅ Migrados {count} contatos")

def main():
    """Executa todas as migrações"""
    print("=" * 60)
    print("MIGRAÇÃO DE DADOS JSON PARA POSTGRESQL")
    print("=" * 60)
    print()
    
    with app.app_context():
        # Criar todas as tabelas
        db.create_all()
        print("✅ Tabelas criadas/verificadas\n")
        
        # Executar migrações
        migrate_clients()
        migrate_services()
        migrate_tecnicos()
        migrate_slides()
        migrate_footer()
        migrate_marcas()
        migrate_milestones()
        migrate_admin_users()
        migrate_agendamentos()
        migrate_blog()
        migrate_comprovantes()
        migrate_cupons()
        migrate_contatos()
        
        print()
        print("=" * 60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print()
        print("Todos os dados foram migrados para o banco de dados PostgreSQL.")
        print("Os arquivos JSON originais foram preservados como backup.")

if __name__ == '__main__':
    main()

