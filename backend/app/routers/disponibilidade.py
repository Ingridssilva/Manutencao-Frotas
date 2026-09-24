"""Rotas — Disponibilidade Diária"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta
from calendar import monthrange
from app import db
from app.models.usuario import DisponibilidadeDiaria, Veiculo, OrdemServico, ReservaVeiculo
from app.services.negocio import popular_disponibilidade_hoje

bp = Blueprint('disponibilidade', __name__, url_prefix='/disponibilidade')


@bp.route('/')
@login_required
def index():
    hoje  = date.today()
    ano   = request.args.get('ano',  hoje.year,  type=int)
    mes   = request.args.get('mes',  hoje.month, type=int)

    primeiro_dia = date(ano, mes, 1)
    _, dias_mes  = monthrange(ano, mes)
    ultimo_dia   = date(ano, mes, dias_mes)

    popular_disponibilidade_hoje()

    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()

    registros = DisponibilidadeDiaria.query.filter(
        DisponibilidadeDiaria.data.between(primeiro_dia, ultimo_dia)
    ).all()

    idx = {}
    for r in registros:
        idx.setdefault(r.veiculo_id, {})[r.data] = r

    datas = [date(ano, mes, d) for d in range(1, dias_mes + 1)]

    # Índice de reservas aprovadas: {veiculo_id: {data: nome_solicitante}}
    reservas_aprovadas = ReservaVeiculo.query.filter(
        ReservaVeiculo.status == 'aprovada',
        ReservaVeiculo.data_inicio <= ultimo_dia,
        ReservaVeiculo.data_fim >= primeiro_dia,
    ).all()

    reservas_idx = {}
    for res in reservas_aprovadas:
        if res.veiculo_id:
            for d in datas:
                if res.data_inicio <= d <= res.data_fim:
                    reservas_idx.setdefault(res.veiculo_id, {})[d] = res.nome_solicitante

    # Reservas pendentes para alert
    reservas_pendentes_list = (
        ReservaVeiculo.query
        .filter_by(status='pendente')
        .order_by(ReservaVeiculo.data_inicio.asc())
        .limit(5).all()
    )
    reservas_pendentes = ReservaVeiculo.query.filter_by(status='pendente').count()

    # Stats por veículo
    stats = {}
    for v in veiculos:
        disp = sum(
            1 for d in datas
            if idx.get(v.id, {}).get(d) is None
            or idx[v.id][d].disponivel
        )
        upe = sum(
            float(idx[v.id][d].upe_impacto or 0)
            for d in datas if idx.get(v.id, {}).get(d)
        )
        stats[v.id] = {'disponivel': disp, 'total': dias_mes, 'pct': round(disp / dias_mes * 100), 'upe': upe}

    mes_ant  = (primeiro_dia - timedelta(days=1))
    mes_prox = (ultimo_dia + timedelta(days=1))

    return render_template('disponibilidade/index.html',
        veiculos=veiculos, datas=datas, idx=idx, stats=stats, hoje=hoje,
        ano=ano, mes=mes, primeiro_dia=primeiro_dia,
        mes_ant_ano=mes_ant.year, mes_ant_mes=mes_ant.month,
        mes_prox_ano=mes_prox.year, mes_prox_mes=mes_prox.month,
        reservas_idx=reservas_idx,
        reservas_pendentes=reservas_pendentes,
        reservas_pendentes_list=reservas_pendentes_list,
        MESES=['', 'Janeiro','Fevereiro','Março','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'],
    )


@bp.route('/lancar', methods=['POST'])
@login_required
def lancar():
    """Lança ou atualiza disponibilidade de um veículo em uma data."""
    data       = request.form.get('data')
    veiculo_id = int(request.form.get('veiculo_id'))
    disponivel = request.form.get('disponivel') == '1'
    motivo     = request.form.get('motivo') or None
    upe        = request.form.get('upe_impacto') or None
    obs        = request.form.get('observacoes') or None

    try:
        d = date.fromisoformat(data)
        reg = DisponibilidadeDiaria.query.filter_by(veiculo_id=veiculo_id, data=d).first()
        if reg:
            reg.disponivel               = disponivel
            reg.motivo_indisponibilidade = motivo if not disponivel else None
            reg.upe_impacto              = float(upe) if upe else None
            reg.observacoes              = obs
            reg.lancado_por              = current_user.id
        else:
            reg = DisponibilidadeDiaria(
                veiculo_id=veiculo_id, data=d,
                disponivel=disponivel,
                motivo_indisponibilidade=motivo if not disponivel else None,
                upe_impacto=float(upe) if upe else None,
                observacoes=obs,
                lancado_por=current_user.id,
            )
            db.session.add(reg)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'erro': str(e)}), 400
