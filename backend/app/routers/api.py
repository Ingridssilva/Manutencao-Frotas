"""API REST interna — usada pelo frontend via fetch"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, text
from datetime import date, datetime
from app import db, csrf
from app.models.usuario import (
    Alerta, Veiculo, OrdemServico, Motorista,
    CatalogoServico, CatalogoMaterial
)

bp = Blueprint('api', __name__, url_prefix='/api')
csrf.exempt(bp)  # API interna usa session/login, não tokens de formulário


# ── ALERTAS ─────────────────────────────────────────────
@bp.route('/alertas/marcar-lido/<int:id>', methods=['POST'])
@login_required
def marcar_alerta_lido(id):
    a = Alerta.query.get_or_404(id)
    a.lido    = True
    a.lido_por= current_user.id
    a.lido_em = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/alertas/marcar-todos-lidos', methods=['POST'])
@login_required
def marcar_todos_lidos():
    Alerta.query.filter_by(lido=False).update({
        'lido': True, 'lido_por': current_user.id, 'lido_em': datetime.utcnow()
    })
    db.session.commit()
    return jsonify({'ok': True})


# ── CUSTOS (dashboard chart) ─────────────────────────────
@bp.route('/custos-mes')
@login_required
def custos_mes():
    rows = db.session.execute(text("""
        SELECT DATE_TRUNC('month', data_abertura) AS mes,
               COALESCE(SUM(custo_total), 0) AS total
        FROM ordens_servico
        WHERE status = 'concluida'
          AND data_abertura >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', data_abertura)
        ORDER BY mes DESC
    """)).mappings().all()
    return jsonify([{'mes': str(r['mes']), 'total': float(r['total'])} for r in rows])


# ── BUSCA GLOBAL ─────────────────────────────────────────
@bp.route('/busca')
@login_required
def busca():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'veiculos': [], 'motoristas': [], 'os': []})

    veiculos = Veiculo.query.filter(
        db.or_(Veiculo.placa.ilike(f'%{q}%'), Veiculo.descricao.ilike(f'%{q}%'))
    ).limit(5).all()

    motoristas = Motorista.query.filter(
        db.or_(Motorista.nome.ilike(f'%{q}%'), Motorista.cpf.ilike(f'%{q}%'))
    ).limit(5).all()

    os_list = OrdemServico.query.filter(
        OrdemServico.numero.ilike(f'%{q}%')
    ).limit(5).all()

    return jsonify({
        'veiculos':   [{'id': v.id, 'placa': v.placa, 'nome': v.nome_display} for v in veiculos],
        'motoristas': [{'id': m.id, 'nome': m.nome} for m in motoristas],
        'os':         [{'id': o.id, 'numero': o.numero, 'status': o.status} for o in os_list],
    })


# ── AUTOCOMPLETE SERVIÇOS/MATERIAIS ─────────────────────
@bp.route('/servicos')
@login_required
def servicos():
    q    = request.args.get('q', '')
    svcs = CatalogoServico.query.filter(
        CatalogoServico.ativo == True,
        CatalogoServico.nome.ilike(f'%{q}%')
    ).limit(20).all()
    return jsonify([{
        'id': s.id, 'nome': s.nome,
        'valor': float(s.valor_referencia or 0),
        'tempo': float(s.tempo_estimado_h or 0),
    } for s in svcs])


@bp.route('/materiais')
@login_required
def materiais():
    q    = request.args.get('q', '')
    mats = CatalogoMaterial.query.filter(
        CatalogoMaterial.ativo == True,
        CatalogoMaterial.nome.ilike(f'%{q}%')
    ).limit(20).all()
    return jsonify([{
        'id': m.id, 'nome': m.nome,
        'valor': float(m.valor_referencia or 0),
        'unidade': m.unidade,
    } for m in mats])


# ── STATS RÁPIDAS ────────────────────────────────────────
@bp.route('/stats')
@login_required
def stats():
    from app.models.usuario import OSPagamento, Orcamento
    hoje = date.today()
    return jsonify({
        'alertas_criticos': Alerta.query.filter_by(nivel='critico', lido=False).count(),
        'os_abertas':       OrdemServico.query.filter(OrdemServico.status.in_(['aberta','em_execucao'])).count(),
        'pag_urgentes':     OSPagamento.query.filter(
                                OSPagamento.status == 'pendente',
                                OSPagamento.data_vencimento <= hoje
                            ).count(),
        'orc_pendentes':    Orcamento.query.filter_by(status='aguardando_aprovacao').count(),
    })


@bp.route('/disponibilidade-mes')
@login_required
def disponibilidade_mes():
    """Dados de disponibilidade mensal para gráficos BI."""
    rows = db.session.execute(text("""
        SELECT mes, placa, descricao, municipio_base,
               pct_disponibilidade, upe_total_perdido,
               dias_disponivel, dias_indisponivel
        FROM vw_bi_disponibilidade
        ORDER BY mes DESC
        LIMIT 300
    """)).mappings().all()
    return jsonify([{
        'mes': str(r['mes']),
        'placa': r['placa'],
        'descricao': r['descricao'],
        'municipio_base': r['municipio_base'],
        'pct_disponibilidade': float(r['pct_disponibilidade'] or 0),
        'upe_total_perdido': float(r['upe_total_perdido'] or 0),
        'dias_disponivel': int(r['dias_disponivel'] or 0),
        'dias_indisponivel': int(r['dias_indisponivel'] or 0),
    } for r in rows])


@bp.route('/bi-custos')
@login_required
def bi_custos():
    """Custo detalhado por veículo/mês para BI."""
    rows = db.session.execute(text("""
        SELECT placa, descricao, municipio_base, tipo_propriedade,
               mes, tipo_manutencao, qtd_os,
               custo_total, custo_corretiva, custo_preventiva, custo_preditiva
        FROM vw_bi_custo_veiculo
        WHERE mes IS NOT NULL
        ORDER BY mes DESC, custo_total DESC
        LIMIT 400
    """)).mappings().all()
    return jsonify([{
        'placa': r['placa'],
        'descricao': r['descricao'],
        'municipio_base': r['municipio_base'],
        'tipo_propriedade': r['tipo_propriedade'],
        'mes': str(r['mes']),
        'tipo_manutencao': r['tipo_manutencao'],
        'qtd_os': int(r['qtd_os'] or 0),
        'custo_total': float(r['custo_total'] or 0),
        'custo_corretiva': float(r['custo_corretiva'] or 0),
        'custo_preventiva': float(r['custo_preventiva'] or 0),
        'custo_preditiva': float(r['custo_preditiva'] or 0),
    } for r in rows])
