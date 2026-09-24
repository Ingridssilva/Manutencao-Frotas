"""
Geração de PDF — Ordem de Compra (para envio ao fornecedor)
Usa ReportLab (já presente nos requirements).
"""
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)

LARANJA   = colors.HexColor('#F7931E')
ESCURO    = colors.HexColor('#1C1C1E')
CINZA_BG  = colors.HexColor('#F5F5F5')
CINZA_LBL = colors.HexColor('#999999')
CINZA_BD  = colors.HexColor('#DDDDDD')
AZUL_OC   = colors.HexColor('#2980B9')
BRANCO    = colors.white


def _fmt_brl(valor) -> str:
    """Formata valor como R$ 1.234,56"""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return 'R$ 0,00'
    return 'R$ {:,.2f}'.format(v).replace(',', 'X').replace('.', ',').replace('X', '.')


def _fmt_data(dt) -> str:
    if dt is None:
        return '—'
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y')
    return str(dt)


def gerar_pdf_oc(oc) -> BytesIO:
    """
    Recebe um objeto OrdemCompra (SQLAlchemy) e retorna BytesIO com o PDF pronto.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.8 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # ── estilos personalizados ────────────────────────────────────────────────
    st_marca = ParagraphStyle('marca', parent=styles['Normal'],
                              fontSize=10, textColor=LARANJA,
                              fontName='Helvetica-Bold', spaceAfter=2)
    st_titulo = ParagraphStyle('titulo', parent=styles['Normal'],
                               fontSize=20, textColor=ESCURO,
                               fontName='Helvetica-Bold', spaceAfter=2)
    st_sub = ParagraphStyle('sub', parent=styles['Normal'],
                            fontSize=9, textColor=CINZA_LBL, spaceAfter=14)
    st_lbl = ParagraphStyle('lbl', parent=styles['Normal'],
                            fontSize=8, textColor=CINZA_LBL)
    st_val = ParagraphStyle('val', parent=styles['Normal'],
                            fontSize=10, textColor=ESCURO,
                            fontName='Helvetica-Bold')
    st_val_sm = ParagraphStyle('val_sm', parent=styles['Normal'],
                               fontSize=9, textColor=ESCURO)
    st_th = ParagraphStyle('th', parent=styles['Normal'],
                           fontSize=9, textColor=BRANCO,
                           fontName='Helvetica-Bold')
    st_td = ParagraphStyle('td', parent=styles['Normal'],
                           fontSize=9, textColor=ESCURO)
    st_td_mono = ParagraphStyle('td_mono', parent=styles['Normal'],
                                fontSize=9, textColor=ESCURO,
                                fontName='Courier')
    st_total = ParagraphStyle('total', parent=styles['Normal'],
                              fontSize=14, textColor=AZUL_OC,
                              fontName='Helvetica-Bold')
    st_rodape = ParagraphStyle('rodape', parent=styles['Normal'],
                               fontSize=8, textColor=CINZA_LBL, alignment=1)

    elementos = []

    # ── CABEÇALHO ─────────────────────────────────────────────────────────────
    elementos.append(Paragraph('EMPRESA EXEMPLO', st_marca))
    elementos.append(Paragraph(f'Ordem de Compra — {oc.numero}', st_titulo))
    elementos.append(Paragraph(
        f'Gerada em {_fmt_data(oc.gerada_em)} &nbsp;|&nbsp; '
        f'Gerada por: {oc.gerador.nome if oc.gerador else "—"}',
        st_sub,
    ))
    elementos.append(HRFlowable(width='100%', color=LARANJA, thickness=2, spaceAfter=16))

    # ── BLOCO: DADOS DA OC + FORNECEDOR ──────────────────────────────────────
    orc = oc.orcamento
    veiculo = orc.veiculo if orc else None

    dados_bloco = [
        # linha 1: OC | Orçamento de origem
        [
            Paragraph('Nº da Ordem de Compra', st_lbl),
            Paragraph('Orçamento de Origem', st_lbl),
            Paragraph('Data de Emissão', st_lbl),
            Paragraph('Prazo de Entrega', st_lbl),
        ],
        [
            Paragraph(oc.numero, ParagraphStyle('oc_num', parent=styles['Normal'],
                      fontSize=13, textColor=AZUL_OC, fontName='Helvetica-Bold')),
            Paragraph(orc.numero if orc else '—', st_val),
            Paragraph(_fmt_data(oc.gerada_em), st_val),
            Paragraph(f'{oc.prazo_dias} dias' if oc.prazo_dias else '—', st_val),
        ],
    ]
    t_dados = Table(dados_bloco, colWidths=[4.2 * cm, 4.2 * cm, 3.8 * cm, 3.8 * cm])
    t_dados.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), CINZA_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, CINZA_BD),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(t_dados)
    elementos.append(Spacer(1, 12))

    # ── FORNECEDOR ────────────────────────────────────────────────────────────
    forn = oc.fornecedor
    forn_end = forn.endereco or ''
    if forn.municipio:
        forn_end = (forn_end + ' — ' + forn.municipio).strip(' — ')
    if forn.uf:
        forn_end += f'/{forn.uf}'

    bloco_forn = [
        [Paragraph('FORNECEDOR', st_lbl), Paragraph('CNPJ', st_lbl),
         Paragraph('E-MAIL', st_lbl), Paragraph('TELEFONE', st_lbl)],
        [Paragraph(forn.razao_social, st_val),
         Paragraph(forn.cnpj or '—', st_val_sm),
         Paragraph(forn.email or '—', st_val_sm),
         Paragraph(forn.telefone or '—', st_val_sm)],
        [Paragraph('ENDEREÇO', st_lbl), Paragraph('', st_lbl),
         Paragraph('', st_lbl), Paragraph('', st_lbl)],
        [Paragraph(forn_end or '—', st_val_sm),
         Paragraph('', st_val_sm), Paragraph('', st_val_sm), Paragraph('', st_val_sm)],
    ]
    t_forn = Table(bloco_forn, colWidths=[6 * cm, 3.5 * cm, 4 * cm, 2.5 * cm])
    t_forn.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), CINZA_BG),
        ('BACKGROUND', (0, 2), (-1, 2), CINZA_BG),
        ('SPAN', (0, 3), (-1, 3)),
        ('BOX', (0, 0), (-1, -1), 0.5, CINZA_BD),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(Paragraph('Dados do Fornecedor', ParagraphStyle(
        'sec', parent=styles['Normal'], fontSize=10, textColor=ESCURO,
        fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=6,
    )))
    elementos.append(t_forn)
    elementos.append(Spacer(1, 14))

    # ── VEÍCULO / REFERÊNCIA ──────────────────────────────────────────────────
    if veiculo:
        bloco_vei = [
            [Paragraph('VEÍCULO', st_lbl), Paragraph('PLACA', st_lbl),
             Paragraph('OS VINCULADA', st_lbl), Paragraph('DESCRIÇÃO', st_lbl)],
            [Paragraph(f'{veiculo.marca or ""} {veiculo.modelo or ""}'.strip() or veiculo.descricao or '—', st_val_sm),
             Paragraph(veiculo.placa, st_val),
             Paragraph(oc.os.numero if oc.os else '—', st_val_sm),
             Paragraph(orc.descricao[:80] if orc and orc.descricao else '—', st_val_sm)],
        ]
        t_vei = Table(bloco_vei, colWidths=[4.5 * cm, 2.5 * cm, 3.5 * cm, 5.5 * cm])
        t_vei.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CINZA_BG),
            ('BOX', (0, 0), (-1, -1), 0.5, CINZA_BD),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elementos.append(Paragraph('Veículo de Referência', ParagraphStyle(
            'sec2', parent=styles['Normal'], fontSize=10, textColor=ESCURO,
            fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=6,
        )))
        elementos.append(t_vei)
        elementos.append(Spacer(1, 14))

    # ── ITENS DO ORÇAMENTO ────────────────────────────────────────────────────
    itens = orc.itens if orc else []
    elementos.append(Paragraph('Itens Solicitados', ParagraphStyle(
        'sec3', parent=styles['Normal'], fontSize=10, textColor=ESCURO,
        fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=6,
    )))

    cab_itens = [
        Paragraph('#', st_th),
        Paragraph('Tipo', st_th),
        Paragraph('Descrição', st_th),
        Paragraph('Qtd', st_th),
        Paragraph('Valor Unit.', st_th),
        Paragraph('Total', st_th),
    ]
    linhas_itens = [cab_itens]

    for idx, item in enumerate(itens, 1):
        tipo_map = {'servico': 'Serviço', 'material': 'Material', 'implemento': 'Implemento'}
        tipo_txt = tipo_map.get(item.tipo_item, item.tipo_item.capitalize())

        if item.tipo_item == 'servico' and item.servico:
            desc = item.servico.nome
        elif item.tipo_item in ('material', 'implemento') and item.material:
            desc = item.material.nome
        else:
            desc = item.descricao_livre or '—'

        qtd = float(item.quantidade or 1)
        val_unit = float(item.valor_unitario or 0)
        val_tot = qtd * val_unit

        linhas_itens.append([
            Paragraph(str(idx), st_td),
            Paragraph(tipo_txt, st_td),
            Paragraph(desc[:60], st_td),
            Paragraph(f'{qtd:g}', st_td_mono),
            Paragraph(_fmt_brl(val_unit), st_td_mono),
            Paragraph(_fmt_brl(val_tot), st_td_mono),
        ])

    if not itens:
        linhas_itens.append([
            Paragraph('', st_td),
            Paragraph('', st_td),
            Paragraph('(Sem itens detalhados — ver descrição do orçamento)', st_td),
            Paragraph('', st_td), Paragraph('', st_td), Paragraph('', st_td),
        ])

    col_w_itens = [0.8 * cm, 2.2 * cm, 7.5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm]
    t_itens = Table(linhas_itens, colWidths=col_w_itens, repeatRows=1)
    row_bg = [BRANCO, CINZA_BG] * (len(linhas_itens) + 1)
    t_itens.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LARANJA),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BRANCO, CINZA_BG]),
        ('BOX', (0, 0), (-1, -1), 0.5, CINZA_BD),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
    ]))
    elementos.append(t_itens)
    elementos.append(Spacer(1, 10))

    # ── VALOR TOTAL ───────────────────────────────────────────────────────────
    val_total_txt = _fmt_brl(oc.valor_total)
    t_total = Table(
        [[Paragraph('VALOR TOTAL DA ORDEM DE COMPRA', st_lbl),
          Paragraph(val_total_txt, st_total)]],
        colWidths=[12 * cm, 4 * cm],
    )
    t_total.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EBF5FB')),
        ('BOX', (0, 0), (-1, -1), 1, AZUL_OC),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('RIGHTPADDING', (1, 0), (1, 0), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(KeepTogether(t_total))
    elementos.append(Spacer(1, 14))

    # ── CONDIÇÕES E OBSERVAÇÕES ───────────────────────────────────────────────
    cond_obs = []
    if oc.condicoes:
        cond_obs.append(('Condições de Pagamento', oc.condicoes))
    if oc.observacoes:
        cond_obs.append(('Observações', oc.observacoes))

    if cond_obs:
        for titulo_co, texto_co in cond_obs:
            elementos.append(Paragraph(titulo_co, ParagraphStyle(
                'co_tit', parent=styles['Normal'], fontSize=9, textColor=ESCURO,
                fontName='Helvetica-Bold', spaceAfter=3,
            )))
            elementos.append(Paragraph(texto_co, ParagraphStyle(
                'co_txt', parent=styles['Normal'], fontSize=9, textColor=ESCURO,
                spaceAfter=8, leftIndent=8,
            )))

    # ── ASSINATURAS ───────────────────────────────────────────────────────────
    elementos.append(Spacer(1, 30))
    t_assin = Table(
        [[
            Paragraph('_' * 35, ParagraphStyle('assin', parent=styles['Normal'],
                       fontSize=9, textColor=CINZA_LBL, alignment=1)),
            Paragraph('_' * 35, ParagraphStyle('assin', parent=styles['Normal'],
                       fontSize=9, textColor=CINZA_LBL, alignment=1)),
        ],
        [
            Paragraph('Autorizado por — Empresa Exemplo', ParagraphStyle(
                'assin_lbl', parent=styles['Normal'], fontSize=8,
                textColor=CINZA_LBL, alignment=1)),
            Paragraph('Ciente — Fornecedor / Representante', ParagraphStyle(
                'assin_lbl', parent=styles['Normal'], fontSize=8,
                textColor=CINZA_LBL, alignment=1)),
        ]],
        colWidths=[8 * cm, 8 * cm],
    )
    t_assin.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elementos.append(t_assin)

    # ── RODAPÉ ────────────────────────────────────────────────────────────────
    elementos.append(Spacer(1, 16))
    elementos.append(HRFlowable(width='100%', color=colors.HexColor('#EEEEEE'), thickness=1))
    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph(
        f'Empresa Exemplo · Ordem de Compra {oc.numero} · '
        f'Emitida em {_fmt_data(oc.gerada_em)} · '
        f'Este documento é válido apenas com assinatura autorizada.',
        st_rodape,
    ))

    doc.build(elementos)
    buf.seek(0)
    return buf
