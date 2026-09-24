"""Rotas públicas — Kanban visível sem login + aprovação via token de e-mail"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from app import db
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify
from app.models.usuario import OrdemServico, Orcamento

bp = Blueprint('public', __name__)


# ── KANBAN PÚBLICO ──────────────────────────────────────────────────────────

@bp.route('/')
def kanban():
    """
    Página inicial pública — Kanban das OS.
    Qualquer pessoa com o link vê. Não precisa de login.
    """
    colunas = {
        'aberta':          'Aberta',
        'em_execucao':     'Em Manutenção',
        'aguardando_peca': 'Aguardando Peça',
        'concluida':       'Concluída',
    }
    os_por_status = {}
    for status in colunas:
        q = (
            OrdemServico.query
            .filter_by(status=status)
            .order_by(OrdemServico.data_abertura.desc())
        )
        # Concluídas: mostra apenas as 20 mais recentes para não sobrecarregar
        if status == 'concluida':
            q = q.limit(20)
        os_por_status[status] = q.all()
    from datetime import date as _date
    return render_template('public/kanban.html',
                           colunas=colunas,
                           os_por_status=os_por_status,
                           hoje=_date.today())


# ── APROVAÇÃO VIA TOKEN (sem login) ─────────────────────────────────────────

@bp.route('/aprovar/<token>', methods=['GET', 'POST'])
def aprovar_token(token):
    """
    Aprovação da OS via link do e-mail — sem necessidade de login.
    O token é gerado ao criar a OS e expira em 7 dias.
    """
    if not token or len(token) < 32:
        abort(404)

    o = OrdemServico.query.filter_by(aprovacao_token=token).first_or_404()

    # Verifica expiração
    if o.aprovacao_token_exp and datetime.now(timezone.utc) > o.aprovacao_token_exp:
        return render_template('public/token_expirado.html', o=o)

    if o.aprovacao_status != 'pendente':
        return render_template('public/ja_processado.html', o=o)

    custo = float(o.custo_total or 0)

    if request.method == 'POST':
        acao   = request.form.get('acao')
        obs    = request.form.get('obs', '').strip()
        nome_ap= request.form.get('nome_aprovador', '').strip()

        if acao == 'aprovar':
            o.aprovacao_status = 'aprovada'
            o.aprovado_em      = datetime.now(timezone.utc)
            o.aprovacao_obs    = obs or 'Aprovado via e-mail'
            # Guarda nome do aprovador no obs se não tiver usuário
            if nome_ap:
                o.aprovacao_obs = f'[{nome_ap}] {o.aprovacao_obs}'
            # Invalida token após uso
            o.aprovacao_token     = None
            o.aprovacao_token_exp = None
            db.session.commit()

            # Gera e envia PDF
            try:
                from app.services.aprovacao_os import gerar_pdf_de_acordo, _enviar_pdf_sem_usuario
                pdf_bytes = gerar_pdf_de_acordo(o, None, nome_aprovador=nome_ap)
                _enviar_pdf_sem_usuario(o, nome_ap, pdf_bytes)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f'PDF aprovação token: {e}', exc_info=True)

            return render_template('public/aprovado.html', o=o, custo=custo)

        elif acao == 'rejeitar':
            if not obs:
                return render_template('public/aprovar_token.html',
                                       o=o, custo=custo,
                                       erro='Informe o motivo da rejeição.')
            o.aprovacao_status    = 'rejeitada'
            o.aprovado_em         = datetime.now(timezone.utc)
            o.aprovacao_obs       = f'[{nome_ap}] {obs}' if nome_ap else obs
            o.status              = 'aberta'
            o.data_conclusao      = datetime.now(timezone.utc).date()
            o.aprovacao_token     = None
            o.aprovacao_token_exp = None
            db.session.commit()

            # Restaura disponibilidade do veículo — rejeição cancela o bloqueio
            try:
                from app.routes.os import _restaurar_disponivel
                _restaurar_disponivel(o)
                db.session.commit()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f'Restaurar disponível (rejeição token): {e}', exc_info=True)

            try:
                from app.services.aprovacao_os import _notificar_rejeicao_email
                _notificar_rejeicao_email(o, nome_ap, obs)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f'Notif rejeição: {e}', exc_info=True)

            return render_template('public/rejeitado.html', o=o)

    return render_template('public/aprovar_token.html', o=o, custo=custo)


# ── APROVAÇÃO DE ORÇAMENTO VIA TOKEN (sem login) ────────────────────────────

@bp.route('/orcamentos/aprovar/<token>', methods=['GET', 'POST'])
def aprovar_orc_token(token):
    """Aprovação de orçamento via link do e-mail — sem login necessário."""
    if not token or len(token) < 32:
        abort(404)

    from app.services import aprovacao_orcamento as svc_orc
    from app.services.aprovacao_orcamento import registrar_aprovacao_token, registrar_rejeicao_token

    orc = Orcamento.query.filter_by(aprovacao_token=token).first_or_404()

    if orc.aprovacao_token_exp and datetime.now(timezone.utc) > orc.aprovacao_token_exp.replace(tzinfo=timezone.utc):
        return render_template('public/token_expirado.html', o=orc)

    if orc.status not in ('em_aprovacao', 'aguardando_aprovacao'):
        return render_template('public/ja_processado.html', o=orc)

    custo = float(orc.valor_total_estimado or 0)
    acao  = request.args.get('acao') or request.form.get('acao')

    if request.method == 'POST' or acao in ('aprovar', 'rejeitar'):
        obs      = request.form.get('obs', '').strip() or request.args.get('obs', '').strip()
        nome_ap  = request.form.get('nome_aprovador', '').strip() or 'Aprovador (e-mail)'

        if acao == 'aprovar':
            registrar_aprovacao_token(orc, nome_ap)
            return render_template('public/aprovado.html', o=orc, custo=custo)

        elif acao == 'rejeitar':
            if not obs and request.method == 'POST':
                return render_template('public/aprovar_orc_token.html',
                                       o=orc, custo=custo,
                                       erro='Informe o motivo da rejeição.')
            registrar_rejeicao_token(orc, nome_ap, obs or '—')
            return render_template('public/rejeitado.html', o=orc)

    return render_template('public/aprovar_orc_token.html', o=orc, custo=custo)


@bp.route('/orcamentos/rejeitar/<token>', methods=['GET', 'POST'])
def rejeitar_orc_token(token):
    """Redireciona para a tela de rejeição do orçamento."""
    return redirect(url_for('public.aprovar_orc_token', token=token, acao='rejeitar'))


# ── API: INDICADORES PÚBLICOS ─────────────────────────────────────────────────
@bp.route('/api/indicadores')
def api_indicadores():
    """Retorna KPIs consolidados para a tela de indicadores pública."""
    import traceback, logging
    log = logging.getLogger(__name__)
    try:
        from datetime import date, timedelta
        from app.models.usuario import (
            OrdemServico, Veiculo, Motorista, CRLV, Multa,
            DisponibilidadeDiaria, ReservaVeiculo
        )
        from sqlalchemy import func

        hoje       = date.today()
        inicio_mes = hoje.replace(day=1)
        inicio_ano = hoje.replace(month=1, day=1)

        # Garante que o snapshot de disponibilidade de HOJE existe para todos os
        # veículos ativos. Antes isso só era criado quando alguém abria a tela
        # interna "/disponibilidade", então em dias sem essa visita o snapshot
        # do dia ficava incompleto (só os veículos com OS aberta eram gravados)
        # e o gauge "Disponibilidade do mês" caía para perto de 0%.
        try:
            from app.services.negocio import popular_disponibilidade_hoje
            popular_disponibilidade_hoje()
        except Exception as e:
            log.warning(f'popular_disponibilidade_hoje (api_indicadores) falhou: {e}')

        # ── Frota ──
        total_veiculos    = Veiculo.query.filter_by(status='ativo').count()
        veiculos_inativos = Veiculo.query.filter_by(status='inativo').count()
        veic_em_manut = (
            db.session.query(func.count(func.distinct(OrdemServico.veiculo_id)))
            .filter(OrdemServico.status.in_(['aberta','em_execucao','aguardando_peca']))
            .scalar() or 0
        )
        veic_disponiveis = max(0, total_veiculos - veic_em_manut)

        # Disponibilidade média do mês
        try:
            regs_mes = DisponibilidadeDiaria.query.filter(
                DisponibilidadeDiaria.data >= inicio_mes,
                DisponibilidadeDiaria.data <= hoje
            ).all()
            pct_disp = round(sum(1 for r in regs_mes if r.disponivel) / len(regs_mes) * 100, 1) if regs_mes else 100.0
        except Exception:
            pct_disp = 100.0

        # ── OS ──
        os_abertas        = OrdemServico.query.filter_by(status='aberta').count()
        os_execucao       = OrdemServico.query.filter_by(status='em_execucao').count()
        os_ag_peca        = OrdemServico.query.filter_by(status='aguardando_peca').count()
        os_mes            = OrdemServico.query.filter(OrdemServico.data_abertura >= inicio_mes).count()
        os_concluidas_mes = OrdemServico.query.filter(
            OrdemServico.status == 'concluida',
            OrdemServico.data_conclusao >= inicio_mes
        ).count()

        # Tempo médio de conclusão (MTTR) — dias entre abertura e conclusão
        try:
            os_conc = OrdemServico.query.filter(
                OrdemServico.status == 'concluida',
                OrdemServico.data_conclusao >= inicio_mes,
                OrdemServico.data_abertura.isnot(None),
                OrdemServico.data_conclusao.isnot(None),
            ).all()
            if os_conc:
                total_dias  = sum((o.data_conclusao - o.data_abertura).days for o in os_conc)
                mttr_dias   = round(total_dias / len(os_conc), 1)
                tempo_medio = mttr_dias
            else:
                mttr_dias   = 0
                tempo_medio = 0
        except Exception:
            mttr_dias   = 0
            tempo_medio = 0

        # MTBF — tempo médio entre falhas (dias entre conclusão de uma OS e abertura da próxima, por veículo)
        # Aproximação: (dias no mês - total dias em manutenção) / nº de falhas corretivas
        # Usa data_conclusao (não data_abertura) para bater com os demais indicadores "do mês"
        # (MTTR, custo do mês, OS concluídas) — uma OS aberta em maio e concluída em julho
        # deve contar como falha corretiva "deste mês", já que foi isso que impactou o mês.
        try:
            os_corretivas = OrdemServico.query.filter(
                OrdemServico.tipo_manutencao == 'corretiva',
                OrdemServico.data_conclusao >= inicio_mes,
                OrdemServico.status == 'concluida',
                OrdemServico.data_abertura.isnot(None),
                OrdemServico.data_conclusao.isnot(None),
            ).all()
            n_corretivas = len(os_corretivas)
            dias_no_mes  = (hoje - inicio_mes).days + 1
            dias_em_manut_corr = sum(
                (min(o.data_conclusao, hoje) - max(o.data_abertura, inicio_mes)).days
                for o in os_corretivas
            )
            dias_operacao = max(1, dias_no_mes * max(1, total_veiculos) - dias_em_manut_corr)
            mtbf_dias = round(dias_operacao / n_corretivas, 1) if n_corretivas > 0 else None
        except Exception:
            mtbf_dias = None

        # OS críticas
        limite_critico = hoje - timedelta(days=7)
        os_criticas = OrdemServico.query.filter(
            OrdemServico.status.in_(['aberta','em_execucao','aguardando_peca']),
            OrdemServico.data_abertura <= limite_critico
        ).count()

        # ── Custos ──
        custo_mes = float(db.session.query(func.sum(OrdemServico.custo_total)).filter(
            OrdemServico.status == 'concluida',
            OrdemServico.data_conclusao >= inicio_mes
        ).scalar() or 0)
        custo_ano = float(db.session.query(func.sum(OrdemServico.custo_total)).filter(
            OrdemServico.status == 'concluida',
            OrdemServico.data_conclusao >= inicio_ano
        ).scalar() or 0)

        # ── Multas ──
        try:
            multas_abertas = Multa.query.filter(Multa.status.in_(['pendente','aberta'])).count()
            multas_mes     = Multa.query.filter(Multa.data_infracao >= inicio_mes).count()
        except Exception:
            multas_abertas = 0; multas_mes = 0

        # ── CRLV ──
        try:
            vencendo_30 = CRLV.query.filter(
                CRLV.data_vencimento >= hoje,
                CRLV.data_vencimento <= hoje + timedelta(days=30)
            ).count()
            vencidos = CRLV.query.filter(CRLV.data_vencimento < hoje).count()
        except Exception:
            vencendo_30 = 0; vencidos = 0

        # ── Motoristas (usa campo ativo, não status) ──
        total_motoristas = Motorista.query.filter_by(ativo=True).count()

        # ── Reservas ──
        try:
            reservas_pend = ReservaVeiculo.query.filter_by(status='pendente').count()
        except Exception:
            reservas_pend = 0

        # ── OS por tipo ──
        try:
            tipos = db.session.query(
                OrdemServico.tipo_manutencao,
                func.count(OrdemServico.id)
            ).filter(OrdemServico.data_abertura >= inicio_mes).group_by(OrdemServico.tipo_manutencao).all()
            os_por_tipo = {t: c for t, c in tipos if t}
        except Exception:
            os_por_tipo = {}

        # ── Top veículos por custo acumulado no mês (não por quantidade de OS —
        # um veículo com 1 OS cara pesa mais no orçamento que vários com OS baratas) ──
        try:
            top_veic = db.session.query(
                Veiculo.placa,
                func.count(OrdemServico.id).label('qtd'),
                func.coalesce(func.sum(OrdemServico.custo_total), 0).label('custo')
            ).join(OrdemServico, OrdemServico.veiculo_id == Veiculo.id)             .filter(OrdemServico.data_abertura >= inicio_mes)             .group_by(Veiculo.placa)             .order_by(func.coalesce(func.sum(OrdemServico.custo_total), 0).desc())             .limit(5).all()
            top_veiculos = [{'placa': p, 'qtd': q, 'custo': float(c)} for p, q, c in top_veic]
        except Exception:
            top_veiculos = []

        # ── Ordens de compra em aberto (não finalizadas nem canceladas) ──
        try:
            from app.models.usuario import OrdemCompra
            oc_abertas = OrdemCompra.query.filter(
                OrdemCompra.status.notin_(['finalizada', 'cancelada'])
            ).count()
            oc_valor_aberto = float(db.session.query(func.sum(OrdemCompra.valor_total)).filter(
                OrdemCompra.status.notin_(['finalizada', 'cancelada'])
            ).scalar() or 0)
        except Exception:
            oc_abertas = 0
            oc_valor_aberto = 0.0

        return jsonify({
            'timestamp': hoje.isoformat(),
            'frota': {
                'total':               total_veiculos,
                'disponiveis':         veic_disponiveis,
                'em_manutencao':       veic_em_manut,
                'inativos':            veiculos_inativos,
                'pct_disponibilidade': pct_disp,
            },
            'os': {
                'abertas':          os_abertas,
                'em_execucao':      os_execucao,
                'aguardando_peca':  os_ag_peca,
                'criticas':         os_criticas,
                'abertas_mes':      os_mes,
                'concluidas_mes':   os_concluidas_mes,
                'tempo_medio_dias': tempo_medio,
                'mttr_dias':        mttr_dias,
                'mtbf_dias':        mtbf_dias,
            },
            'custos': {'mes': custo_mes, 'ano': custo_ano},
            'documentos': {'crlv_vencendo_30d': vencendo_30, 'crlv_vencidos': vencidos},
            'multas': {'abertas': multas_abertas, 'mes': multas_mes},
            'motoristas':         total_motoristas,
            'reservas_pendentes': reservas_pend,
            'os_por_tipo':        os_por_tipo,
            'top_veiculos':       top_veiculos,
            'ordens_compra':      {'abertas': oc_abertas, 'valor_aberto': oc_valor_aberto},
        })

    except Exception as e:
        # Loga o traceback completo apenas no servidor — nunca no corpo da resposta,
        # já que esta é uma rota pública e não-autenticada.
        log.error(f'api_indicadores erro: {e}\n{traceback.format_exc()}')
        return jsonify({'erro': 'Erro ao carregar indicadores. Tente novamente em instantes.'}), 500
