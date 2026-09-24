"""Rotas — Reserva de Veículo (pública + gestão interna)"""
import logging
from datetime import date, datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models.usuario import ReservaVeiculo, Veiculo, DisponibilidadeDiaria

logger = logging.getLogger(__name__)

bp = Blueprint('reservas', __name__)


# ── PÁGINA PÚBLICA: formulário de reserva ───────────────────────────────────
@bp.route('/reservar', methods=['GET', 'POST'])
def nova_reserva():
    """Qualquer pessoa pode solicitar reserva sem login."""
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    sucesso = False
    erro = None

    if request.method == 'POST':
        nome      = request.form.get('nome_solicitante', '').strip()
        setor     = request.form.get('setor_solicitante', '').strip()
        contato   = request.form.get('contato', '').strip()
        destino   = request.form.get('destino', '').strip()
        finalidade= request.form.get('finalidade', '').strip()
        passag    = request.form.get('n_passageiros', '1')
        tipo_pref = request.form.get('tipo_veiculo_pref', '').strip()
        veiculo_id= request.form.get('veiculo_id') or None
        data_ini  = request.form.get('data_inicio', '').strip()
        data_fim  = request.form.get('data_fim', '').strip()

        if not nome or not destino or not data_ini or not data_fim:
            erro = 'Preencha os campos obrigatórios: nome, destino e datas.'
        else:
            try:
                d_ini = date.fromisoformat(data_ini)
                d_fim = date.fromisoformat(data_fim)
                if d_fim < d_ini:
                    erro = 'A data de retorno não pode ser anterior à data de saída.'
                elif d_ini < date.today():
                    erro = 'A data de saída não pode ser no passado.'
                else:
                    r = ReservaVeiculo(
                        veiculo_id       = int(veiculo_id) if veiculo_id else None,
                        nome_solicitante = nome,
                        setor_solicitante= setor or None,
                        contato          = contato or None,
                        destino          = destino,
                        finalidade       = finalidade or None,
                        n_passageiros    = max(1, int(passag or 1)),
                        tipo_veiculo_pref= tipo_pref or None,
                        data_inicio      = d_ini,
                        data_fim         = d_fim,
                        status           = 'pendente',
                    )
                    db.session.add(r)
                    db.session.commit()
                    sucesso = True

                    # Notifica gestores internos sobre nova reserva
                    try:
                        from app.services.notificacoes import notificar_nova_reserva
                        notificar_nova_reserva(r)
                    except Exception as e:
                        logger.error(f'notificar_nova_reserva falhou: {e}', exc_info=True)

            except Exception as e:
                db.session.rollback()
                erro = f'Erro ao registrar: {e}'

    return render_template('public/reservar.html',
                           veiculos=veiculos,
                           sucesso=sucesso,
                           erro=erro,
                           hoje=date.today().isoformat())


# ── GESTÃO INTERNA: lista de reservas ───────────────────────────────────────
@bp.route('/disponibilidade/reservas')
@login_required
def lista_reservas():
    status_f = request.args.get('status', 'pendente')
    q = ReservaVeiculo.query
    if status_f and status_f != 'todos':
        q = q.filter(ReservaVeiculo.status == status_f)
    reservas = q.order_by(ReservaVeiculo.data_inicio.asc()).all()
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    return render_template('disponibilidade/reservas.html',
                           reservas=reservas,
                           veiculos=veiculos,
                           status_f=status_f)


# ── API: aprovar / rejeitar / concluir / cancelar ────────────────────────────
@bp.route('/disponibilidade/reservas/<int:rid>/acao', methods=['POST'])
@login_required
def acao_reserva(rid):
    r = ReservaVeiculo.query.get_or_404(rid)
    acao      = request.form.get('acao')
    obs       = request.form.get('obs_admin', '').strip() or None
    veiculo_id= request.form.get('veiculo_id') or None

    if acao == 'aprovar':
        r.status      = 'aprovada'
        r.obs_admin   = obs
        r.aprovado_por= current_user.id
        r.aprovado_em = datetime.now(timezone.utc)
        if veiculo_id:
            r.veiculo_id = int(veiculo_id)
        db.session.commit()
        flash('Reserva aprovada com sucesso.', 'success')

        # Notifica solicitante (só se contato for e-mail)
        try:
            from app.services.notificacoes import notificar_reserva_aprovada
            notificar_reserva_aprovada(r)
        except Exception as e:
            logger.error(f'notificar_reserva_aprovada falhou: {e}', exc_info=True)

    elif acao == 'rejeitar':
        r.status      = 'rejeitada'
        r.obs_admin   = obs
        r.aprovado_por= current_user.id
        r.aprovado_em = datetime.now(timezone.utc)
        db.session.commit()
        flash('Reserva rejeitada.', 'warning')

        # Notifica solicitante (só se contato for e-mail)
        try:
            from app.services.notificacoes import notificar_reserva_rejeitada
            notificar_reserva_rejeitada(r)
        except Exception as e:
            logger.error(f'notificar_reserva_rejeitada falhou: {e}', exc_info=True)

    elif acao == 'concluir':
        r.status = 'concluida'
        db.session.commit()
        flash('Reserva marcada como concluída.', 'success')

    elif acao == 'cancelar':
        r.status = 'cancelada'
        db.session.commit()
        flash('Reserva cancelada.', 'info')

    else:
        flash('Ação inválida.', 'danger')

    return redirect(url_for('reservas.lista_reservas'))


# ── API JSON: disponibilidade pública (para o toggle do kanban) ──────────────
@bp.route('/api/disponibilidade-publica')
def api_disponibilidade_publica():
    """Retorna disponibilidade atual apenas de veículos terrestres ativos (sem login).
    Excluídos: embarcações, geradores e equipamentos náuticos/estacionários.
    """
    from app.models.usuario import OrdemServico

    # Tipos que NÃO devem aparecer no painel de frota terrestre
    TIPOS_EXCLUIDOS = {
        'Embarcação', 'Embarcacao',
        'Barco', 'Balsa', 'Lancha', 'Ferry', 'Ferry Boat',
        'Rabeta', 'Gerador',
    }

    hoje = date.today()

    veiculos = (
        Veiculo.query
        .filter(Veiculo.status != 'inativo')
        .order_by(Veiculo.placa)
        .all()
    )

    # Registros de disponibilidade lançados hoje
    registros = {
        r.veiculo_id: r
        for r in DisponibilidadeDiaria.query.filter_by(data=hoje).all()
    }

    # Reservas aprovadas que cobrem hoje
    reservas_hoje = {
        r.veiculo_id
        for r in ReservaVeiculo.query.filter(
            ReservaVeiculo.status == 'aprovada',
            ReservaVeiculo.data_inicio <= hoje,
            ReservaVeiculo.data_fim   >= hoje,
        ).all()
        if r.veiculo_id
    }

    # Veículos com OS aberta/em execução/aguardando peça HOJE
    os_abertas_ids = {
        row.veiculo_id
        for row in OrdemServico.query
        .filter(
            OrdemServico.status.in_(['aberta', 'em_execucao', 'aguardando_peca']),
            OrdemServico.veiculo_id.isnot(None),
        )
        .with_entities(OrdemServico.veiculo_id)
        .all()
    }

    resultado = []
    for v in veiculos:
        # Excluir tipos não-terrestres (comparação case-insensitive)
        tipo_lower = (v.tipo_veiculo or '').strip().lower()
        excluidos_lower = {t.lower() for t in TIPOS_EXCLUIDOS}
        if tipo_lower in excluidos_lower:
            continue

        # Determinar disponibilidade
        reg = registros.get(v.id)
        if reg:
            disp   = reg.disponivel
            motivo = reg.motivo_indisponibilidade or ''
        else:
            disp   = True
            motivo = ''

        # OS aberta em qualquer data = indisponível agora
        if v.id in os_abertas_ids:
            disp   = False
            motivo = motivo or 'manutencao'

        # Reserva aprovada cobrindo hoje = indisponível
        if v.id in reservas_hoje:
            disp   = False
            motivo = 'reservado'

        resultado.append({
            'id':        v.id,
            'placa':     v.placa,
            'modelo':    v.modelo or v.descricao or '',
            'tipo':      v.tipo_veiculo or '',
            'municipio': v.municipio_base or '',
            'disponivel': disp,
            'motivo':    motivo,
        })

    return jsonify(resultado)
