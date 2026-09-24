"""Rotas — Relatórios e BI"""
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import text
from datetime import date
from io import BytesIO
from app import db
from sqlalchemy import extract as db_extract
from app.models.usuario import OrdemServico, Veiculo, DisponibilidadeDiaria, Multa

bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')


@bp.route('/bi')
@login_required
def bi():
    """Dashboard BI — disponibilidade e custo por município."""
    rows = db.session.execute(text("""
        SELECT mes, placa, descricao, municipio_base,
               dias_no_mes, dias_disponivel, dias_indisponivel,
               pct_disponibilidade, upe_total_perdido
        FROM vw_bi_disponibilidade
        ORDER BY mes DESC, placa
        LIMIT 200
    """)).mappings().all()
    return render_template('relatorios/bi.html', rows=rows, hoje=date.today())


@bp.route('/vencimentos')
@login_required
def vencimentos():
    """Documentos vencendo nos próximos N dias."""
    dias = request.args.get('dias', 90, type=int)
    # Parâmetro nomeado — sem interpolação de string no SQL
    rows = db.session.execute(text("""
        SELECT veiculo_id, placa, descricao, tipo_doc, data_vencimento, status
        FROM vw_vencimentos_proximos
        WHERE data_vencimento <= CURRENT_DATE + (:dias * INTERVAL '1 day')
        ORDER BY data_vencimento
    """), {'dias': dias}).mappings().all()
    return render_template('relatorios/vencimentos.html', rows=rows, dias=dias, hoje=date.today())


@bp.route('/custos')
@login_required
def custos():
    """Custo por veículo e período."""
    ano  = request.args.get('ano',  date.today().year,  type=int)
    mes  = request.args.get('mes',  0, type=int)  # 0 = todos os meses
    tipo = request.args.get('tipo', '').strip()

    # Todos os filtros opcionais via parâmetros nomeados — sem f-string no SQL
    filtro_mes  = "AND EXTRACT(MONTH FROM os.data_abertura) = :mes"  if mes  else ""
    filtro_tipo = "AND os.tipo_manutencao = :tipo"                   if tipo else ""

    params: dict = {'ano': ano}
    if mes:
        params['mes'] = mes
    if tipo:
        params['tipo'] = tipo

    rows = db.session.execute(text(f"""
        SELECT v.id AS veiculo_id, v.placa, v.descricao, v.municipio_base, v.tipo_propriedade,
               os.tipo_manutencao,
               COUNT(os.id) AS qtd_os,
               COALESCE(SUM(os.custo_total), 0) AS custo_total
        FROM veiculos v
        LEFT JOIN ordens_servico os ON os.veiculo_id = v.id
            AND os.status = 'concluida'
            AND EXTRACT(YEAR FROM os.data_abertura) = :ano
            {filtro_mes}
            {filtro_tipo}
        GROUP BY v.id, v.placa, v.descricao, v.municipio_base, v.tipo_propriedade,
                 os.tipo_manutencao
        ORDER BY custo_total DESC
    """), params).mappings().all()

    total_geral = sum(float(r['custo_total'] or 0) for r in rows)
    anos_disp   = db.session.execute(text("""
        SELECT DISTINCT EXTRACT(YEAR FROM data_abertura)::int AS ano
        FROM ordens_servico ORDER BY ano DESC
    """)).scalars().all()

    return render_template('relatorios/custos.html', rows=rows, total=total_geral,
                           ano=ano, mes=mes, tipo=tipo, anos=anos_disp, hoje=date.today())


@bp.route('/custos/excel')
@login_required
def custos_excel():
    """Exporta relatório de custos para Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        from flask import flash
        flash('openpyxl não instalado. Execute: pip install openpyxl', 'danger')
        return '', 400

    ano = request.args.get('ano', date.today().year, type=int)
    rows = db.session.execute(text("""
        SELECT v.placa, v.descricao, v.municipio_base,
               os.tipo_manutencao,
               COUNT(os.id) AS qtd_os,
               COALESCE(SUM(os.custo_total), 0) AS custo_total
        FROM veiculos v
        LEFT JOIN ordens_servico os ON os.veiculo_id = v.id
            AND os.status = 'concluida'
            AND EXTRACT(YEAR FROM os.data_abertura) = :ano
        GROUP BY v.placa, v.descricao, v.municipio_base, os.tipo_manutencao
        ORDER BY custo_total DESC
    """), {'ano': ano}).mappings().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Custos {ano}'
    laranja = 'F7931E'
    header_fill = PatternFill('solid', fgColor=laranja)
    header_font = Font(bold=True, color='FFFFFF')

    headers = ['Placa', 'Descrição', 'Município', 'Tipo manutenção', 'Qtd OS', 'Custo Total (R$)']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for row_i, r in enumerate(rows, 2):
        ws.cell(row=row_i, column=1, value=r['placa'])
        ws.cell(row=row_i, column=2, value=r['descricao'])
        ws.cell(row=row_i, column=3, value=r['municipio_base'])
        ws.cell(row=row_i, column=4, value=r['tipo_manutencao'] or '—')
        ws.cell(row=row_i, column=5, value=int(r['qtd_os'] or 0))
        c = ws.cell(row=row_i, column=6, value=float(r['custo_total'] or 0))
        c.number_format = '#,##0.00'

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename=custos_{ano}.xlsx'}
    )


@bp.route('/custos/veiculo')
@login_required
def custos_veiculo():
    """Relatório detalhado de custo por veículo."""
    from app.models.usuario import OrdemServico, Veiculo
    veiculo_id = request.args.get('veiculo_id', type=int)
    ano        = request.args.get('ano', date.today().year, type=int)

    if not veiculo_id:
        # Redireciona para custos gerais se não tem veículo
        from flask import redirect, url_for
        return redirect(url_for('relatorios.custos'))

    veiculo = Veiculo.query.get_or_404(veiculo_id)

    anos_disp = db.session.execute(text("""
        SELECT DISTINCT EXTRACT(YEAR FROM data_abertura)::int AS ano
        FROM ordens_servico WHERE veiculo_id = :vid ORDER BY ano DESC
    """), {'vid': veiculo_id}).scalars().all() or [date.today().year]

    os_list = OrdemServico.query.filter_by(veiculo_id=veiculo_id).filter(
        db.extract('year', OrdemServico.data_abertura) == ano
    ).order_by(OrdemServico.data_abertura.desc()).all()

    # Métricas
    custo_ano  = sum(float(o.custo_total or 0) for o in os_list)
    total_os   = len(os_list)
    qtd_prev   = sum(1 for o in os_list if o.tipo_manutencao == 'preventiva')
    qtd_corr   = sum(1 for o in os_list if o.tipo_manutencao == 'corretiva')
    qtd_pred   = sum(1 for o in os_list if o.tipo_manutencao == 'preditiva')
    custo_prev = sum(float(o.custo_total or 0) for o in os_list if o.tipo_manutencao == 'preventiva')
    custo_corr = sum(float(o.custo_total or 0) for o in os_list if o.tipo_manutencao == 'corretiva')
    custo_pred = sum(float(o.custo_total or 0) for o in os_list if o.tipo_manutencao == 'preditiva')

    # Dados mensais para gráfico
    from calendar import month_abbr
    meses_labels = [month_abbr[m] for m in range(1, 13)]
    meses_custos = [0.0] * 12
    meses_qtds   = [0] * 12
    for o in os_list:
        m = o.data_abertura.month - 1
        meses_custos[m] += float(o.custo_total or 0)
        meses_qtds[m]   += 1

    return render_template('relatorios/custos_veiculo.html',
        veiculo     = veiculo,
        ano         = ano,
        anos        = anos_disp,
        os_list     = os_list,
        custo_ano   = custo_ano,
        total_os    = total_os,
        qtd_prev    = qtd_prev,
        qtd_corr    = qtd_corr,
        qtd_pred    = qtd_pred,
        custo_prev  = custo_prev,
        custo_corr  = custo_corr,
        custo_pred  = custo_pred,
        meses_labels= meses_labels,
        meses_custos= meses_custos,
        meses_qtds  = meses_qtds,
        hoje        = date.today(),
    )


@bp.route('/custos/veiculo/excel')
@login_required
def custos_veiculo_excel():
    """Exporta relatório de custo do veículo para Excel."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        from flask import abort; abort(400)

    from app.models.usuario import OrdemServico, Veiculo
    veiculo_id = request.args.get('veiculo_id', type=int)
    ano        = request.args.get('ano', date.today().year, type=int)
    veiculo    = Veiculo.query.get_or_404(veiculo_id)

    os_list = OrdemServico.query.filter_by(veiculo_id=veiculo_id).filter(
        db.extract('year', OrdemServico.data_abertura) == ano
    ).order_by(OrdemServico.data_abertura).all()

    from io import BytesIO
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{veiculo.placa} {ano}'
    hf = PatternFill('solid', fgColor='F7931E')
    hfont = Font(bold=True, color='FFFFFF')
    headers = ['Número','Tipo OS','Manutenção','Abertura','Conclusão','Status','Aprovação','Custo (R$)']
    for col, h in enumerate(headers, 1):
        c = ws.cell(1, col, h); c.fill = hf; c.font = hfont; c.alignment = Alignment(horizontal='center')
    for ri, o in enumerate(os_list, 2):
        ws.cell(ri,1,o.numero); ws.cell(ri,2,o.tipo_os); ws.cell(ri,3,o.tipo_manutencao)
        ws.cell(ri,4,str(o.data_abertura)); ws.cell(ri,5,str(o.data_conclusao or ''))
        ws.cell(ri,6,o.status); ws.cell(ri,7,o.aprovacao_status or '')
        c = ws.cell(ri,8,float(o.custo_total or 0)); c.number_format='#,##0.00'
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={veiculo.placa}_{ano}.xlsx'})
