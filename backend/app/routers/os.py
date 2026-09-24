"""Rotas — Ordens de Serviço (com aprovação, baixa e disponibilidade automática)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from datetime import date
import datetime as _dt

def _parse_date(val):
    """Converte string de data do formulário para objeto date com segurança."""
    if not val or not str(val).strip():
        return None
    s = str(val).strip()
    # Aceita apenas formato YYYY-MM-DD e valida o ano
    if len(s) != 10 or s[4] != '-':
        return None
    try:
        d = _dt.date.fromisoformat(s)
        # Rejeita anos fora do intervalo razoável
        if d.year < 2000 or d.year > 2100:
            return None
        return d
    except (ValueError, OverflowError):
        return None

from app import db
from app.models.usuario import (
    OSStatusLog, OrdemServico, OSItemServico, OSItemMaterial, OSItemImplemento, OSPagamento,
    Veiculo, Fornecedor, Motorista, PlanoManutencao,
    CatalogoServico, CatalogoMaterial, CatalogoImplemento, Orcamento, DisponibilidadeDiaria
)
from app.services.negocio import gerar_numero_os, registrar_km
import logging

logger = logging.getLogger(__name__)
bp     = Blueprint('os', __name__, url_prefix='/os')


def _filtrar_aprovacao(query, aprovacao):
    """
    Filtra OS por aprovacao_status.
    Quando o filtro é 'pendente', inclui também registros com NULL
    (OS criadas antes da coluna existir ou quando o e-mail de aprovação falhou).
    """
    if not aprovacao:
        return query
    if aprovacao == 'pendente':
        return query.filter(
            db.or_(
                OrdemServico.aprovacao_status == 'pendente',
                OrdemServico.aprovacao_status == None  # noqa: E711
            )
        )
    return query.filter(OrdemServico.aprovacao_status == aprovacao)


@bp.route('/exportar-excel')
@login_required
def exportar_excel():
    """Exporta OS filtradas para Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        from flask import abort
        abort(400, 'openpyxl não instalado')

    status   = request.args.get('status', '')
    tipo_man = request.args.get('tipo_manutencao', '')
    veiculo  = request.args.get('veiculo_id', '')
    baixada  = request.args.get('baixada', '')
    data_de  = request.args.get('data_de', '')
    data_ate = request.args.get('data_ate', '')
    val_min  = request.args.get('val_min', type=float)
    val_max  = request.args.get('val_max', type=float)
    aprovacao= request.args.get('aprovacao', '')
    q        = request.args.get('q', '').strip()

    query = OrdemServico.query.order_by(OrdemServico.data_abertura.desc())
    if status:   query = query.filter_by(status=status)
    if tipo_man: query = query.filter_by(tipo_manutencao=tipo_man)
    if veiculo:  query = query.filter_by(veiculo_id=int(veiculo))
    query = _filtrar_aprovacao(query, aprovacao)
    if data_de:  query = query.filter(OrdemServico.data_abertura >= data_de)
    if data_ate: query = query.filter(OrdemServico.data_abertura <= data_ate)
    if val_min is not None: query = query.filter(OrdemServico.custo_total >= val_min)
    if val_max is not None: query = query.filter(OrdemServico.custo_total <= val_max)
    if q:
        query = query.join(Veiculo, OrdemServico.veiculo_id == Veiculo.id).filter(
            db.or_(OrdemServico.numero.ilike(f'%{q}%'), Veiculo.placa.ilike(f'%{q}%'),
                   OrdemServico.descricao_problema.ilike(f'%{q}%'))
        )
    if baixada == '1': query = query.filter_by(baixada=True)
    elif baixada == '0': query = query.filter_by(baixada=False)
    os_list = query.limit(2000).all()

    from io import BytesIO
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Ordens de Serviço'
    laranja = 'F7931E'
    hf = PatternFill('solid', fgColor=laranja)
    hfont = Font(bold=True, color='FFFFFF')
    headers = ['Número','Veículo','Descrição','Tipo OS','Manutenção','Abertura','Previsão','Conclusão','Status','Aprovação','Custo (R$)','Baixada']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.fill = hf; c.font = hfont; c.alignment = Alignment(horizontal='center')
    for ri, o in enumerate(os_list, 2):
        ws.cell(ri,1,o.numero)
        ws.cell(ri,2,o.veiculo.placa if o.veiculo else '')
        ws.cell(ri,3,o.veiculo.descricao if o.veiculo else '')
        ws.cell(ri,4,o.tipo_os)
        ws.cell(ri,5,o.tipo_manutencao)
        ws.cell(ri,6,str(o.data_abertura) if o.data_abertura else '')
        ws.cell(ri,7,str(o.data_prevista) if o.data_prevista else '')
        ws.cell(ri,8,str(o.data_conclusao) if o.data_conclusao else '')
        ws.cell(ri,9,o.status)
        ws.cell(ri,10,o.aprovacao_status or '')
        c = ws.cell(ri,11,float(o.custo_total or 0)); c.number_format='#,##0.00'
        ws.cell(ri,12,'Sim' if o.baixada else 'Não')
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    from flask import Response
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=ordens_servico.xlsx'})


@bp.route('/')
@login_required
def lista():
    status   = request.args.get('status', '')
    tipo_man = request.args.get('tipo_manutencao', '')
    veiculo  = request.args.get('veiculo_id', '')
    baixada  = request.args.get('baixada', '')
    data_de  = request.args.get('data_de', '')
    data_ate = request.args.get('data_ate', '')
    val_min  = request.args.get('val_min', type=float)
    val_max  = request.args.get('val_max', type=float)
    aprovacao= request.args.get('aprovacao', '')
    q        = request.args.get('q', '').strip()
    page     = request.args.get('page', 1, type=int)

    query = OrdemServico.query
    if status:   query = query.filter_by(status=status)
    if tipo_man: query = query.filter_by(tipo_manutencao=tipo_man)
    if veiculo:  query = query.filter_by(veiculo_id=int(veiculo))
    query = _filtrar_aprovacao(query, aprovacao)
    if data_de:  query = query.filter(OrdemServico.data_abertura >= data_de)
    if data_ate: query = query.filter(OrdemServico.data_abertura <= data_ate)
    if val_min is not None: query = query.filter(OrdemServico.custo_total >= val_min)
    if val_max is not None: query = query.filter(OrdemServico.custo_total <= val_max)
    if q:
        query = query.join(Veiculo, OrdemServico.veiculo_id == Veiculo.id).filter(
            db.or_(OrdemServico.numero.ilike(f'%{q}%'), Veiculo.placa.ilike(f'%{q}%'),
                   OrdemServico.descricao_problema.ilike(f'%{q}%'))
        )
    if baixada == '1':
        query = query.filter_by(baixada=True)
    elif baixada == '0':
        query = query.filter(
            (OrdemServico.baixada == False) | (OrdemServico.baixada == None)
        )

    os_list  = query.options(
                   joinedload(OrdemServico.veiculo),
                   joinedload(OrdemServico.fornecedor),
               ).order_by(OrdemServico.data_abertura.desc()).paginate(
                   page=page, per_page=25, error_out=False)
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    try:
        custo_total_filtrado = sum(float(o.custo_total or 0) for o in os_list.items)
    except Exception:
        custo_total_filtrado = 0
    return render_template('os/lista.html', os_list=os_list, veiculos=veiculos,
                           status=status, tipo_man=tipo_man, veiculo=veiculo,
                           baixada=baixada, aprovacao=aprovacao,
                           custo_total_filtrado=custo_total_filtrado)


@bp.route('/<int:id>')
@login_required
def detalhe(id):
    o = (OrdemServico.query
         .options(
             joinedload(OrdemServico.veiculo),
             joinedload(OrdemServico.fornecedor),
             joinedload(OrdemServico.responsavel),
             joinedload(OrdemServico.motorista),
             joinedload(OrdemServico.itens_servico),
             joinedload(OrdemServico.itens_material),
             joinedload(OrdemServico.itens_implemento),
         )
         .get_or_404(id))
    status_log_ordenado = (
        OSStatusLog.query
        .filter_by(os_id=id)
        .order_by(OSStatusLog.created_at)
        .all()
    )
    from app.models.usuario import Orcamento
    orcamentos_da_os = Orcamento.query.filter_by(os_vinculada_id=id).order_by(Orcamento.created_at.desc()).all()
    # Catálogos para os modais de adição de itens
    catalogo_servicos    = _get_ativos(CatalogoServico)
    catalogo_materiais   = _get_ativos(CatalogoMaterial)
    catalogo_implementos = _get_ativos(CatalogoImplemento)
    catalogo_servicos_json = [{'id': s.id, 'nome': s.nome} for s in catalogo_servicos]
    return render_template('os/detalhe.html', o=o, hoje=date.today(),
                           status_log_ordenado=status_log_ordenado,
                           orcamentos_da_os=orcamentos_da_os,
                           catalogo_servicos=catalogo_servicos,
                           catalogo_servicos_json=catalogo_servicos_json,
                           catalogo_materiais=catalogo_materiais,
                           catalogo_implementos=catalogo_implementos)


@bp.route('/<int:id>/pagamento/<int:pag_id>/marcar_pago', methods=['POST'])
@login_required
def marcar_pago(id, pag_id):
    """Marca uma parcela de pagamento como paga."""
    from app.models.usuario import OSPagamento
    o = OrdemServico.query.get_or_404(id)
    p = OSPagamento.query.filter_by(id=pag_id, os_id=id).first_or_404()
    p.status         = 'pago'
    p.data_pagamento = date.today()
    db.session.commit()
    flash('Parcela quitada com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


def _get_ativos(model):
    try:
        return model.query.filter_by(ativo=True).all()
    except Exception as e:
        logger.warning(f"Coluna 'ativo' não encontrada em {model.__tablename__}: {e}")
        return model.query.all()


@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    try:
        veiculos     = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
        fornecedores = _get_ativos(Fornecedor)
        motoristas   = _get_ativos(Motorista)
        servicos     = _get_ativos(CatalogoServico)
        materiais    = _get_ativos(CatalogoMaterial)
        implementos  = _get_ativos(CatalogoImplemento)
        planos       = PlanoManutencao.query.filter_by(ativo=True).order_by(PlanoManutencao.veiculo_id).all()
    except Exception as e:
        logger.error(f"Erro ao carregar dados da OS: {e}", exc_info=True)
        return render_template('os/form.html',
            veiculos=[], fornecedores=[], motoristas=[],
            servicos=[], materiais=[], implementos=[], planos=[], erro=str(e))

    if request.method == 'POST':
        try:
            f  = request.form
            km = int(f.get('km_abertura') or 0)
            o  = OrdemServico(
                numero=gerar_numero_os(),
                veiculo_id=int(f['veiculo_id']),
                tipo_os=f['tipo_os'],
                tipo_manutencao=f['tipo_manutencao'],
                plano_id=int(f['plano_id']) if f.get('plano_id') else None,
                fornecedor_id=f.get('fornecedor_id') or None,
                responsavel_id=current_user.id if f['tipo_os'] == 'interna' else None,
                motorista_id=f.get('motorista_id') or None,
                km_abertura=km or None,
                descricao_problema=f.get('descricao_problema'),
                data_abertura=_parse_date(f.get('data_abertura')) or date.today(),
                data_prevista=_parse_date(f.get('data_prevista')),
                status='aberta',
                observacoes=f.get('observacoes'),
                created_by=current_user.id,
                data_entrada=_dt.datetime.now(),
            )
            db.session.add(o)
            db.session.flush()

            for i, sid in enumerate(request.form.getlist('servico_id[]')):
                qty = float(request.form.getlist('svc_qty[]')[i] or 1)
                val = float(request.form.getlist('svc_val[]')[i] or 0)
                db.session.add(OSItemServico(
                    os_id=o.id,
                    servico_id=int(sid) if sid else None,
                    descricao_livre=request.form.getlist('svc_desc[]')[i] or None,
                    quantidade=qty, valor_unitario=val,
                    executado_por=request.form.getlist('svc_exec[]')[i] or None,
                ))

            for i, mid in enumerate(request.form.getlist('material_id[]')):
                qty = float(request.form.getlist('mat_qty[]')[i] or 1)
                val = float(request.form.getlist('mat_val[]')[i] or 0)
                db.session.add(OSItemMaterial(
                    os_id=o.id,
                    material_id=int(mid) if mid else None,
                    descricao_livre=request.form.getlist('mat_desc[]')[i] or None,
                    quantidade=qty, valor_unitario=val,
                ))

            for i, iid in enumerate(request.form.getlist('imp_id[]')):
                qty = float(request.form.getlist('imp_qty[]')[i] or 1)
                val = float(request.form.getlist('imp_val[]')[i] or 0)
                db.session.add(OSItemImplemento(
                    os_id=o.id,
                    implemento_id=int(iid) if iid else None,
                    descricao_livre=request.form.getlist('imp_desc[]')[i] or None,
                    numero_serie=request.form.getlist('imp_serie[]')[i] or None,
                    quantidade=qty, valor_unitario=val,
                ))

            for i, venc in enumerate(request.form.getlist('pag_venc[]')):
                if not venc: continue
                val_p = float(request.form.getlist('pag_val[]')[i] or 0)
                db.session.add(OSPagamento(
                    os_id=o.id,
                    numero_nf=request.form.getlist('pag_nf[]')[i] or None,
                    valor=val_p,
                    data_vencimento=_parse_date(venc),
                    forma_pagamento=request.form.getlist('pag_forma[]')[i] or None,
                ))

            if km:
                registrar_km(o.veiculo_id, km, origem='os',
                             referencia_id=o.id, user_id=current_user.id)

            # Calcula custo estimado já na criação para rotear aprovação corretamente
            total_svc = sum(i.valor_total for i in o.itens_servico)
            total_mat = sum(i.valor_total for i in o.itens_material)
            total_imp = sum(i.valor_total for i in o.itens_implemento)
            o.custo_total = total_svc + total_mat + total_imp
            db.session.commit()

            # Marca veículo como indisponível enquanto OS está aberta
            _marcar_indisponivel(o)

            # Envia e-mail de solicitação de aprovação ao criar a OS
            # Regra: custo >= R$1.000 → Rafael | custo < R$1.000 → Pedro
            try:
                from app.services.aprovacao_os import solicitar_aprovacao
                solicitar_aprovacao(o)
                flash(f'OS {o.numero} criada. E-mail de aprovação enviado aos responsáveis.', 'success')
            except Exception as e:
                logger.error(f'Erro ao enviar aprovação OS {o.numero}: {e}', exc_info=True)
                flash(f'OS {o.numero} criada, mas falha ao enviar e-mail de aprovação.', 'warning')

            return redirect(url_for('os.detalhe', id=o.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar OS: {e}", exc_info=True)
            flash(f'Erro ao criar OS: {e}', 'danger')

    return render_template('os/form.html',
        veiculos=veiculos, fornecedores=fornecedores,
        motoristas=motoristas, servicos=servicos, materiais=materiais,
        implementos=implementos, planos=planos)


@bp.route('/<int:id>/concluir', methods=['POST'])
@login_required
def concluir(id):
    o = OrdemServico.query.get_or_404(id)

    # Idempotência: evita reenvio de e-mails/PDF e duplicidade de KM em duplo-clique/duplo-submit.
    if o.status == 'concluida':
        flash('Esta OS já está concluída.', 'info')
        return redirect(url_for('os.detalhe', id=id))

    f = request.form
    status_anterior = o.status

    o.status         = 'concluida'
    o.data_conclusao = _parse_date(f.get('data_conclusao')) or date.today()
    km_fin = int(f.get('km_conclusao') or 0)
    if km_fin:
        o.km_conclusao = km_fin
        registrar_km(o.veiculo_id, km_fin, 'os', o.id, current_user.id)

    total_svc   = sum(i.valor_total for i in o.itens_servico)
    total_mat   = sum(i.valor_total for i in o.itens_material)
    total_imp   = sum(i.valor_total for i in o.itens_implemento)
    o.custo_total = total_svc + total_mat + total_imp

    if o.plano_id:
        from datetime import timedelta
        pl = PlanoManutencao.query.get(o.plano_id)
        if pl:
            pl.km_referencia = km_fin or o.km_abertura
            if pl.intervalo_km and pl.km_referencia:
                pl.proximo_km = pl.km_referencia + pl.intervalo_km
            if pl.intervalo_dias:
                pl.proxima_data = date.today() + timedelta(days=pl.intervalo_dias)

    # Restaura disponibilidade ao concluir
    _restaurar_disponivel(o)

    # Registra no histórico de status — antes só acontecia via mover_status() (kanban),
    # deixando o histórico incompleto quando a conclusão vinha deste formulário.
    _log_status(o, status_anterior, 'concluida')

    db.session.commit()

    # Envia e-mail de conclusão para quem aprovou a OS
    try:
        from app.services.aprovacao_os import notificar_conclusao
        notificar_conclusao(o)
    except Exception as e:
        logger.error(f'Erro ao enviar e-mail de conclusão OS {o.numero}: {e}', exc_info=True)

    # Gera PDF De Acordo e envia ao Financeiro com NFs
    try:
        from app.services.aprovacao_os import gerar_pdf_de_acordo
        from app.services.financeiro import notificar_financeiro_os_concluida
        # Tenta com aprovador; se não houver (aprovado via token), gera sem usuário
        try:
            pdf_bytes = gerar_pdf_de_acordo(o, o.aprovador)
        except Exception:
            pdf_bytes = gerar_pdf_de_acordo(o, None)
        notificar_financeiro_os_concluida(o, pdf_bytes)
    except Exception as e_fin:
        logger.error(f'Notif. financeiro OS {o.numero} falhou: {e_fin}', exc_info=True)

    flash('OS concluída com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


# ── APROVAÇÃO ──────────────────────────────────────────────────────────────

@bp.route('/<int:id>/aprovar', methods=['GET', 'POST'])
@login_required
def aprovar_form(id):
    """Página de aprovação — aprovador vê OS e aprova ou rejeita."""
    o = OrdemServico.query.get_or_404(id)

    from app.services.aprovacao_os import aprovadores_para_os, LIMITE_APROVACAO
    custo = float(o.custo_total or 0)
    emails_validos = aprovadores_para_os(custo)

    # Permite admin ou aprovadores válidos
    from app.models.usuario import PerfilAcesso
    perfil_nome = current_user.perfil.nome if current_user.perfil else ''
    eh_admin = perfil_nome in ('admin', 'gestor')

    if not eh_admin and current_user.email.lower() not in [e.lower() for e in emails_validos]:
        flash('Você não tem permissão para aprovar esta OS.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    if request.method == 'POST':
        acao = request.form.get('acao')
        obs  = request.form.get('obs', '')

        if acao == 'aprovar':
            try:
                from sqlalchemy import text
                logger.warning(f'[APROVAR] Iniciando aprovação OS id={o.id} numero={o.numero} user={current_user.id}')
                result = db.session.execute(text("""
                    UPDATE ordens_servico
                    SET aprovacao_status    = 'aprovada',
                        aprovado_por        = :uid,
                        aprovado_em         = NOW(),
                        aprovacao_obs       = :obs,
                        aprovacao_token     = NULL,
                        aprovacao_token_exp = NULL
                    WHERE id = :oid
                """), {'uid': str(current_user.id), 'obs': obs or '', 'oid': int(o.id)})
                logger.warning(f'[APROVAR] UPDATE rowcount={result.rowcount}')
                db.session.commit()
                logger.warning(f'[APROVAR] COMMIT OK para OS {o.numero}')
                flash('OS aprovada com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f'[APROVAR] ERRO ao salvar OS {o.numero}: {e}', exc_info=True)
                flash(f'Erro ao aprovar: {e}', 'danger')

            # Gera PDF e envia e-mail — falha aqui não desfaz a aprovação
            try:
                from app.services.aprovacao_os import gerar_pdf_de_acordo, _enviar_pdf_aprovacao
                o_fresh = OrdemServico.query.get(o.id)
                pdf_bytes = gerar_pdf_de_acordo(o_fresh, current_user)
                _enviar_pdf_aprovacao(o_fresh, current_user.nome, current_user.email, pdf_bytes)
            except Exception as e:
                logger.error(f'PDF/e-mail aprovação OS {o.numero}: {e}', exc_info=True)

        elif acao == 'rejeitar':
            if not obs:
                flash('Informe o motivo da rejeição.', 'danger')
                return render_template('os/aprovar.html', o=o, custo=custo,
                                       limite=LIMITE_APROVACAO)
            from app.services.aprovacao_os import registrar_rejeicao
            registrar_rejeicao(o, current_user, obs)
            flash('OS rejeitada. O criador foi notificado.', 'warning')

        return redirect(url_for('os.detalhe', id=id))

    from app.services.aprovacao_os import LIMITE_APROVACAO
    return render_template('os/aprovar.html', o=o, custo=custo,
                           limite=LIMITE_APROVACAO)



@bp.route('/<int:id>/imprimir')
@login_required
def imprimir(id):
    """Página de impressão limpa da OS — abre em nova aba."""
    import datetime as _datetime
    o = OrdemServico.query.get_or_404(id)
    agora = _datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')
    return render_template('os/imprimir.html', o=o, hoje=date.today(), agora=agora)


@bp.route('/<int:id>/pdf-de-acordo')
@login_required
def pdf_de_acordo(id):
    """Download do PDF De Acordo da OS."""
    o = OrdemServico.query.get_or_404(id)
    from app.services.aprovacao_os import gerar_pdf_de_acordo

    # Busca aprovador
    aprovador = None
    if o.aprovado_por:
        from app.models.usuario import Usuario
        aprovador = Usuario.query.get(o.aprovado_por)

    try:
        pdf_bytes = gerar_pdf_de_acordo(o, aprovador)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'inline; filename="DeAcordo_{o.numero}.pdf"'}
        )
    except Exception as e:
        logger.error(f'Erro ao gerar PDF De Acordo OS {o.numero}: {e}', exc_info=True)
        flash(f'Erro ao gerar PDF: {e}', 'danger')
        return redirect(url_for('os.detalhe', id=id))


# ── BAIXA ──────────────────────────────────────────────────────────────────

@bp.route('/<int:id>/baixar', methods=['POST'])
@login_required
def baixar(id):
    """Marca a OS como baixada (encerrada/quitada)."""
    o = OrdemServico.query.get_or_404(id)
    from datetime import datetime
    o.baixada    = True
    o.baixada_em = datetime.utcnow()
    o.baixada_por= current_user.id
    db.session.commit()
    flash('OS baixada com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/desbaixar', methods=['POST'])
@login_required
def desbaixar(id):
    """Desfaz a baixa da OS."""
    o = OrdemServico.query.get_or_404(id)
    o.baixada     = False
    o.baixada_em  = None
    o.baixada_por = None
    db.session.commit()
    flash('Baixa desfeita.', 'info')
    return redirect(url_for('os.detalhe', id=id))


# ── STATUS (kanban) ─────────────────────────────────────────────────────────

def _log_status(os_obj, status_de, status_para, obs=''):
    """Registra mudança de status no histórico."""
    from flask_login import current_user as cu
    log = OSStatusLog(
        os_id      = os_obj.id,
        status_de  = status_de,
        status_para= status_para,
        usuario_id = cu.id if cu and cu.is_authenticated else None,
        obs        = obs,
    )
    db.session.add(log)


@bp.route('/<int:id>/mover_status', methods=['POST'])
@login_required
def mover_status(id):
    o = OrdemServico.query.get_or_404(id)
    novo = request.form.get('status') or (request.json or {}).get('status')
    validos = ['aberta', 'em_execucao', 'aguardando_peca', 'concluida', 'cancelada']
    if novo not in validos:
        if request.is_json:
            return jsonify({'ok': False, 'erro': 'Status inválido'}), 400
        flash('Status inválido.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    agora = _dt.datetime.now()

    if novo == 'concluida' and o.status != 'concluida':
        o.data_conclusao = date.today()
        o.custo_total = (
            sum(i.valor_total for i in o.itens_servico) +
            sum(i.valor_total for i in o.itens_material) +
            sum(i.valor_total for i in o.itens_implemento)
        )
        _restaurar_disponivel(o)
        _log_status(o, o.status, novo)
        o.status = novo
        db.session.commit()
        # Dispara e-mails igual à rota /concluir
        try:
            from app.services.aprovacao_os import notificar_conclusao
            notificar_conclusao(o)
        except Exception as e:
            logger.error(f'mover_status conclusao notif: {e}', exc_info=True)
        try:
            from app.services.aprovacao_os import gerar_pdf_de_acordo
            from app.services.financeiro import notificar_financeiro_os_concluida
            try:
                pdf_bytes = gerar_pdf_de_acordo(o, o.aprovador)
            except Exception:
                pdf_bytes = gerar_pdf_de_acordo(o, None)
            notificar_financeiro_os_concluida(o, pdf_bytes)
        except Exception as e:
            logger.error(f'mover_status financeiro notif: {e}', exc_info=True)
        if request.is_json:
            return jsonify({'ok': True, 'status': novo})
        flash('Status atualizado.', 'success')
        return redirect(url_for('os.detalhe', id=id))
    elif novo == 'em_execucao' and o.status != 'em_execucao':
        o.data_em_execucao = agora
        _marcar_indisponivel(o)
    elif novo == 'aguardando_peca' and o.status != 'aguardando_peca':
        o.data_aguardando_peca = agora
        _marcar_indisponivel(o)
    elif novo == 'aberta':
        _marcar_indisponivel(o)

    _log_status(o, o.status, novo)
    o.status = novo
    db.session.commit()

    if request.is_json:
        return jsonify({'ok': True, 'status': novo})
    flash('Status atualizado.', 'success')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/painel')
@login_required
def painel():
    colunas = {
        'aberta':          'Recepção / Aberta',
        'em_execucao':     'Em Manutenção',
        'aguardando_peca': 'Aguardando Peça',
        'concluida':       'Concluída',
        'cancelada':       'Cancelada',
    }
    os_por_status = {}
    for status in colunas:
        os_por_status[status] = (
            OrdemServico.query.filter_by(status=status)
            .order_by(OrdemServico.data_abertura.desc())
            .limit(50).all()
        )
    return render_template('os/painel.html', colunas=colunas,
                           os_por_status=os_por_status, hoje=date.today())


# ── DISPONIBILIDADE AUTOMÁTICA ──────────────────────────────────────────────

def _marcar_indisponivel(o: OrdemServico):
    """
    Marca o veículo como indisponível no dia de abertura da OS.
    Cria ou atualiza o registro de DisponibilidadeDiaria.
    """
    if not o.veiculo_id:
        return
    try:
        dia = o.data_abertura or date.today()
        reg = DisponibilidadeDiaria.query.filter_by(
            veiculo_id=o.veiculo_id, data=dia).first()
        if not reg:
            reg = DisponibilidadeDiaria(
                veiculo_id=o.veiculo_id,
                data=dia,
            )
            db.session.add(reg)
        reg.disponivel               = False
        reg.motivo_indisponibilidade = f'OS {o.numero} — {(o.tipo_manutencao or "").capitalize()}'
        reg.os_id                    = o.id
        db.session.flush()
    except Exception as e:
        logger.warning(f'Erro ao marcar indisponível: {e}')


def _restaurar_disponivel(o: OrdemServico):
    """
    Restaura disponibilidade do veículo no dia de conclusão/cancelamento.
    Só restaura se não houver outra OS aberta para o mesmo veículo no dia.
    """
    if not o.veiculo_id:
        return
    try:
        dia = o.data_conclusao or date.today()
        # Verifica se há outra OS aberta para este veículo hoje
        outra = (OrdemServico.query
                 .filter(OrdemServico.veiculo_id == o.veiculo_id)
                 .filter(OrdemServico.id != o.id)
                 .filter(OrdemServico.status.in_(['aberta','em_execucao','aguardando_peca']))
                 .first())
        if outra:
            return  # Ainda tem outra OS aberta — mantém indisponível

        reg = DisponibilidadeDiaria.query.filter_by(
            veiculo_id=o.veiculo_id, data=dia).first()
        if reg:
            reg.disponivel               = True
            reg.motivo_indisponibilidade = None
            reg.os_id                    = None
            db.session.flush()
    except Exception as e:
        logger.warning(f'Erro ao restaurar disponível: {e}')


# ── ADIÇÃO DE ITENS PÓS-CRIAÇÃO ────────────────────────────────────────────

def _recalcular_custo(o: OrdemServico):
    """Recalcula e salva o custo_total da OS."""
    o.custo_total = (
        sum(i.valor_total for i in o.itens_servico) +
        sum(i.valor_total for i in o.itens_material) +
        sum(i.valor_total for i in o.itens_implemento)
    )


@bp.route('/<int:id>/add_servico', methods=['POST'])
@login_required
def add_servico(id):
    """Adiciona um item de serviço a uma OS já existente (mesmo após aprovação)."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível adicionar itens a uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    f = request.form
    sid  = f.get('servico_id') or None
    desc = f.get('svc_desc') or None
    try:
        qty = float(f.get('svc_qty') or 1)
        val = float(f.get('svc_val') or 0)
    except (ValueError, TypeError):
        flash('Quantidade ou valor inválido.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    if not sid and not desc:
        flash('Informe o serviço ou uma descrição livre.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    item = OSItemServico(
        os_id=o.id,
        servico_id=int(sid) if sid else None,
        descricao_livre=desc,
        quantidade=qty,
        valor_unitario=val,
        executado_por=f.get('svc_exec') or None,
    )
    db.session.add(item)
    _recalcular_custo(o)

    # Reenvia e-mail de aprovação se o custo mudou de faixa
    try:
        _reenviar_aprovacao_se_necessario(o)
    except Exception as e:
        logger.warning(f'Reenvio aprovação OS {o.numero}: {e}')

    db.session.commit()
    flash('Serviço adicionado com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/add_material', methods=['POST'])
@login_required
def add_material(id):
    """Adiciona uma peça/material a uma OS já existente (mesmo após aprovação)."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível adicionar itens a uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    f = request.form
    mid  = f.get('material_id') or None
    desc = f.get('mat_desc') or None
    try:
        qty = float(f.get('mat_qty') or 1)
        val = float(f.get('mat_val') or 0)
    except (ValueError, TypeError):
        flash('Quantidade ou valor inválido.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    if not mid and not desc:
        flash('Informe a peça ou uma descrição livre.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    item = OSItemMaterial(
        os_id=o.id,
        material_id=int(mid) if mid else None,
        descricao_livre=desc,
        quantidade=qty,
        valor_unitario=val,
    )
    db.session.add(item)
    _recalcular_custo(o)

    try:
        _reenviar_aprovacao_se_necessario(o)
    except Exception as e:
        logger.warning(f'Reenvio aprovação OS {o.numero}: {e}')

    db.session.commit()
    flash('Peça adicionada com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/add_implemento', methods=['POST'])
@login_required
def add_implemento(id):
    """Adiciona um implemento a uma OS já existente (mesmo após aprovação)."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível adicionar itens a uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    f = request.form
    iid  = f.get('imp_id') or None
    desc = f.get('imp_desc') or None
    try:
        qty = float(f.get('imp_qty') or 1)
        val = float(f.get('imp_val') or 0)
    except (ValueError, TypeError):
        flash('Quantidade ou valor inválido.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    if not iid and not desc:
        flash('Informe o implemento ou uma descrição livre.', 'danger')
        return redirect(url_for('os.detalhe', id=id))

    item = OSItemImplemento(
        os_id=o.id,
        implemento_id=int(iid) if iid else None,
        descricao_livre=desc,
        numero_serie=f.get('imp_serie') or None,
        quantidade=qty,
        valor_unitario=val,
    )
    db.session.add(item)
    _recalcular_custo(o)

    try:
        _reenviar_aprovacao_se_necessario(o)
    except Exception as e:
        logger.warning(f'Reenvio aprovação OS {o.numero}: {e}')

    db.session.commit()
    flash('Implemento adicionado com sucesso.', 'success')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/remover_servico/<int:item_id>', methods=['POST'])
@login_required
def remover_servico(id, item_id):
    """Remove um item de serviço da OS."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível remover itens de uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))
    item = OSItemServico.query.filter_by(id=item_id, os_id=id).first_or_404()
    db.session.delete(item)
    _recalcular_custo(o)
    db.session.commit()
    flash('Serviço removido.', 'info')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/remover_material/<int:item_id>', methods=['POST'])
@login_required
def remover_material(id, item_id):
    """Remove uma peça da OS."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível remover itens de uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))
    item = OSItemMaterial.query.filter_by(id=item_id, os_id=id).first_or_404()
    db.session.delete(item)
    _recalcular_custo(o)
    db.session.commit()
    flash('Peça removida.', 'info')
    return redirect(url_for('os.detalhe', id=id))


@bp.route('/<int:id>/remover_implemento/<int:item_id>', methods=['POST'])
@login_required
def remover_implemento(id, item_id):
    """Remove um implemento da OS."""
    o = OrdemServico.query.get_or_404(id)
    if o.status in ('concluida', 'cancelada'):
        flash('Não é possível remover itens de uma OS concluída ou cancelada.', 'danger')
        return redirect(url_for('os.detalhe', id=id))
    item = OSItemImplemento.query.filter_by(id=item_id, os_id=id).first_or_404()
    db.session.delete(item)
    _recalcular_custo(o)
    db.session.commit()
    flash('Implemento removido.', 'info')
    return redirect(url_for('os.detalhe', id=id))


def _reenviar_aprovacao_se_necessario(o: OrdemServico):
    """
    Se a OS ainda está pendente de aprovação, reenvia o e-mail com o novo custo.
    Isso garante que o aprovador veja o valor atualizado após adição de itens.
    """
    if o.aprovacao_status in ('pendente', None):
        from app.services.aprovacao_os import solicitar_aprovacao
        solicitar_aprovacao(o)
