"""Entrypoint — Sistema de Frota Empresa Exemplo"""
import os
from app import create_app, db
from flask import jsonify

app = create_app(os.environ.get('FLASK_ENV', 'development'))


# ── Health check — mantém o Render acordado via UptimeRobot ──
@app.route('/ping')
def ping():
    return 'ok', 200


# ── CLI: inicializar banco ────────────────────────────────────
@app.cli.command('init-db')
def init_db():
    """Cria tabelas e insere dados iniciais."""
    from werkzeug.security import generate_password_hash
    db.create_all()

    from app.models.usuario import PerfilAcesso, Usuario

    # Perfis
    perfis = [
        ('admin',        'Administrador do sistema', True),
        ('gestor',       'Gestor de frota',           True),
        ('operador',     'Operador / técnico',         False),
        ('visualizador', 'Somente leitura',            False),
    ]
    for nome, desc, pode_aprovar in perfis:
        if not PerfilAcesso.query.filter_by(nome=nome).first():
            db.session.add(PerfilAcesso(
                nome=nome, descricao=desc, pode_aprovar=pode_aprovar))
    db.session.commit()
    print('Perfis criados.')

    # Usuário admin
    if not Usuario.query.filter_by(email='admin@empresaexemplo.com.br').first():
        import secrets
        perfil_admin = PerfilAcesso.query.filter_by(nome='admin').first()
        # Senha fixa hardcoded no código-fonte é um risco de segurança (fica visível
        # no histórico do Git). Prioriza ADMIN_SENHA_INICIAL do ambiente; se ausente,
        # gera uma senha aleatória forte e a exibe só nesta execução do comando.
        senha_inicial = os.environ.get('ADMIN_SENHA_INICIAL') or secrets.token_urlsafe(12)
        db.session.add(Usuario(
            nome       = 'Administrador',
            email      = 'admin@empresaexemplo.com.br',
            senha_hash = generate_password_hash(senha_inicial),
            perfil_id  = perfil_admin.id,
            ativo      = True,
        ))
        db.session.commit()
        print(f'Usuário admin criado. Email: admin@empresaexemplo.com.br  Senha: {senha_inicial}')
        if not os.environ.get('ADMIN_SENHA_INICIAL'):
            print('⚠️  Senha gerada automaticamente — anote agora e troque no primeiro login. '
                  'Não fica salva em nenhum arquivo.')

    # Catálogos padrão
    from app.models.usuario import (
        CatalogoServico, CatalogoMaterial,
        CategoriaServico, CategoriaMaterial,
    )

    def _get_or_create_cat_servico(nome):
        c = CategoriaServico.query.filter_by(nome=nome).first()
        if not c:
            c = CategoriaServico(nome=nome, ativo=True)
            db.session.add(c)
            db.session.flush()
        return c.id

    def _get_or_create_cat_material(nome):
        c = CategoriaMaterial.query.filter_by(nome=nome).first()
        if not c:
            c = CategoriaMaterial(nome=nome, ativo=True)
            db.session.add(c)
            db.session.flush()
        return c.id

    servicos_padrao = [
        ('Troca de óleo e filtro',         'Preventiva',   250.00, 1.0),
        ('Troca de filtro de ar',           'Preventiva',    80.00, 0.5),
        ('Troca de filtro de combustível',  'Preventiva',   120.00, 0.5),
        ('Revisão de freios',               'Preventiva',   400.00, 2.0),
        ('Alinhamento e balanceamento',     'Preventiva',   180.00, 1.5),
        ('Troca de correia dentada',        'Preventiva',   600.00, 3.0),
        ('Diagnóstico eletrônico',          'Diagnóstico',  150.00, 1.0),
        ('Reparo elétrico geral',           'Corretiva',    350.00, 3.0),
        ('Troca de bateria',                'Corretiva',    450.00, 0.5),
        ('Calibração de tacógrafo',         'Legal',        300.00, 2.0),
        ('Vistoria geral',                  'Preventiva',   200.00, 2.0),
    ]
    for nome, cat_nome, val, tempo in servicos_padrao:
        if not CatalogoServico.query.filter_by(nome=nome).first():
            db.session.add(CatalogoServico(
                nome=nome,
                categoria_id=_get_or_create_cat_servico(cat_nome),
                valor_referencia=val,
                tempo_estimado_h=tempo,
                ativo=True,
            ))

    materiais_padrao = [
        ('Óleo motor 15W40',        'L',    'Lubrificantes', 25.00),
        ('Óleo motor 5W30',         'L',    'Lubrificantes', 30.00),
        ('Filtro de óleo',          'un',   'Filtros',       35.00),
        ('Filtro de ar',            'un',   'Filtros',       45.00),
        ('Filtro de combustível',   'un',   'Filtros',       40.00),
        ('Pastilha de freio diant.','jogo', 'Freios',       180.00),
        ('Pastilha de freio tras.', 'jogo', 'Freios',       150.00),
        ('Bateria 60Ah',            'un',   'Elétrica',     450.00),
        ('Bateria 100Ah',           'un',   'Elétrica',     650.00),
        ('Fluido de freio DOT4',    'L',    'Fluidos',       25.00),
    ]
    for nome, unid, cat_nome, val in materiais_padrao:
        if not CatalogoMaterial.query.filter_by(nome=nome).first():
            db.session.add(CatalogoMaterial(
                nome=nome,
                unidade=unid,
                categoria_id=_get_or_create_cat_material(cat_nome),
                valor_referencia=val,
                ativo=True,
            ))

    db.session.commit()
    print('Banco inicializado com dados padrão.')


# ── CLI: varrer alertas ───────────────────────────────────────
@app.cli.command('varrer-alertas')
def varrer_alertas():
    """Varre vencimentos e gera alertas no banco."""
    from app.services.negocio import varrer_vencimentos
    varrer_vencimentos()
    print('Alertas varridos.')


# ── CLI: disparar notificações por e-mail ────────────────────
@app.cli.command('enviar-notificacoes')
def enviar_notificacoes():
    """Envia e-mails de alerta para gestores."""
    from app.services.notificacoes import executar_todas_notificacoes
    resultado = executar_todas_notificacoes()
    print(f'Notificações enviadas: {resultado}')


if __name__ == '__main__':
    app.run(debug=True)
