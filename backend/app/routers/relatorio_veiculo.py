"""Relatório de custo por veículo em PDF — Frota Empresa Exemplo"""
from flask import Blueprint, Response, request, abort
from flask_login import login_required
from datetime import date, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from app.models.usuario import (
    Veiculo, OrdemServico, TrocaFluido, Pneu, PneuVeiculo
)

bp = Blueprint('relatorio_veiculo', __name__, url_prefix='/relatorios')

# Cores da marca
LARANJA  = colors.HexColor('#F7931E')
PRETO    = colors.HexColor('#1C1C1E')
CINZA_50 = colors.HexColor('#F2F2F7')
CINZA_200= colors.HexColor('#C7C7CC')
CINZA_600= colors.HexColor('#636366')
BRANCO   = colors.white
VERDE    = colors.HexColor('#30D158')
VERMELHO = colors.HexColor('#FF453A')


def _brl(valor):
    """Formata valor em Real."""
    try:
        return f'R$ {float(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return 'R$ 0,00'


def _km(valor):
    try:
        return f'{int(valor):,}'.replace(',', '.') + ' km'
    except Exception:
        return '—'


@bp.route('/veiculo/<int:veiculo_id>/pdf')
@login_required
def veiculo_pdf(veiculo_id):
    """Gera PDF de custo completo do veículo."""
    v = Veiculo.query.get_or_404(veiculo_id)

    # Período do relatório
    meses = request.args.get('meses', 12, type=int)
    ate   = date.today()
    de    = ate - timedelta(days=meses * 30)

    # ── Dados ────────────────────────────────────────────
    os_list = (OrdemServico.query
               .filter_by(veiculo_id=veiculo_id)
               .filter(OrdemServico.data_abertura >= de)
               .order_by(OrdemServico.data_abertura.desc()).all())

    fluidos = (TrocaFluido.query
               .filter_by(veiculo_id=veiculo_id)
               .filter(TrocaFluido.data_troca >= de)
               .order_by(TrocaFluido.data_troca.desc()).all())

    pneus_montados = (PneuVeiculo.query
                      .filter_by(veiculo_id=veiculo_id)
                      .order_by(PneuVeiculo.data_inicio.desc()).all())

    custo_os      = sum(float(o.custo_total or 0) for o in os_list if o.status == 'concluida')
    custo_fluidos = sum(float(f.custo or 0) for f in fluidos)
    custo_total   = custo_os + custo_fluidos

    os_corretivas  = [o for o in os_list if o.tipo_manutencao == 'corretiva']
    os_preventivas = [o for o in os_list if o.tipo_manutencao == 'preventiva']

    # ── PDF ─────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    story  = []

    # Estilos customizados
    h1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=18,
                         textColor=PRETO, spaceAfter=4, leading=22)
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=13,
                         textColor=PRETO, spaceAfter=6, spaceBefore=16, leading=16)
    h3 = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=11,
                         textColor=CINZA_600, spaceAfter=4, spaceBefore=8, leading=13)
    normal = ParagraphStyle('normal', fontName='Helvetica', fontSize=9,
                             textColor=PRETO, leading=13)
    small  = ParagraphStyle('small', fontName='Helvetica', fontSize=8,
                             textColor=CINZA_600, leading=11)
    right  = ParagraphStyle('right', fontName='Helvetica', fontSize=9,
                             textColor=PRETO, alignment=TA_RIGHT, leading=13)

    def section_title(texto):
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=CINZA_200))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(texto, h2))

    # ── CABEÇALHO ─────────────────────────────────────
    header_data = [[
        Paragraph('<b><font color="#F7931E">Empresa</font> Exemplo</b>', ParagraphStyle('logo', fontName='Helvetica-Bold', fontSize=20, textColor=PRETO, leading=24)),
        Paragraph(f'<b>Relatório de Custos</b><br/><font color="#636366" size="9">Gerado em {date.today().strftime("%d/%m/%Y")}</font>', ParagraphStyle('data', fontName='Helvetica-Bold', fontSize=13, textColor=PRETO, alignment=TA_RIGHT, leading=18)),
    ]]
    header_table = Table(header_data, colWidths=['60%', '40%'])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.5*cm))

    # ── IDENTIFICAÇÃO DO VEÍCULO ──────────────────────
    story.append(Paragraph(f'{v.placa} — {v.descricao or v.modelo or ""}', h1))
    story.append(Paragraph(f'{v.marca or ""} {v.modelo or ""} · {v.ano_fabricacao or "—"} · {v.cor or "—"} · {v.tipo_propriedade.upper()}', small))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f'Período: {de.strftime("%d/%m/%Y")} a {ate.strftime("%d/%m/%Y")} ({meses} meses)', small))

    # ── RESUMO EXECUTIVO ──────────────────────────────
    section_title('Resumo Executivo')

    resumo_data = [
        ['Indicador', 'Valor'],
        ['Custo total no período', _brl(custo_total)],
        ['Custo em OS (manutenção)', _brl(custo_os)],
        ['Custo em fluidos', _brl(custo_fluidos)],
        ['Total de OS abertas', str(len(os_list))],
        ['OS corretivas', str(len(os_corretivas))],
        ['OS preventivas', str(len(os_preventivas))],
        ['KM atual', _km(v.km_atual)],
    ]

    resumo_table = Table(resumo_data, colWidths=['65%', '35%'])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRETO),
        ('TEXTCOLOR', (0,0), (-1,0), BRANCO),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [BRANCO, CINZA_50]),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, CINZA_200),
        ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1,1), (1,1), LARANJA),
    ]))
    story.append(resumo_table)

    # ── ORDENS DE SERVIÇO ─────────────────────────────
    if os_list:
        section_title(f'Ordens de Serviço ({len(os_list)})')

        os_data = [['Número', 'Data', 'Tipo', 'Status', 'Custo']]
        for o in os_list:
            status_label = {
                'concluida': 'Concluída', 'aberta': 'Aberta',
                'em_execucao': 'Em execução', 'cancelada': 'Cancelada',
                'aguardando_peca': 'Aguard. peça'
            }.get(o.status, o.status)
            os_data.append([
                o.numero or '—',
                o.data_abertura.strftime('%d/%m/%Y') if o.data_abertura else '—',
                (o.tipo_manutencao or '—').capitalize(),
                status_label,
                _brl(o.custo_total) if o.custo_total else '—',
            ])

        os_table = Table(os_data, colWidths=['18%', '15%', '17%', '20%', '30%'])
        os_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRETO),
            ('TEXTCOLOR', (0,0), (-1,0), BRANCO),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [BRANCO, CINZA_50]),
            ('ALIGN', (4,0), (4,-1), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.3, CINZA_200),
        ]))
        story.append(os_table)

        # Total OS
        total_os_data = [['', '', '', 'Total OS concluídas:', _brl(custo_os)]]
        total_os_table = Table(total_os_data, colWidths=['18%', '15%', '17%', '20%', '30%'])
        total_os_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (3,0), (4,0), 'RIGHT'),
            ('TEXTCOLOR', (4,0), (4,0), LARANJA),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('LINEABOVE', (0,0), (-1,0), 1, PRETO),
        ]))
        story.append(total_os_table)

    # ── FLUIDOS ───────────────────────────────────────
    if fluidos:
        section_title(f'Troca de Fluidos ({len(fluidos)})')

        flu_data = [['Data', 'Fluido', 'Produto', 'KM', 'Custo']]
        for f in fluidos:
            flu_data.append([
                f.data_troca.strftime('%d/%m/%Y'),
                f.tipo_display,
                f'{f.marca_produto or ""} {f.viscosidade or ""}'.strip() or '—',
                _km(f.km_troca) if f.km_troca else '—',
                _brl(f.custo) if f.custo else '—',
            ])

        flu_table = Table(flu_data, colWidths=['15%', '22%', '28%', '15%', '20%'])
        flu_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRETO),
            ('TEXTCOLOR', (0,0), (-1,0), BRANCO),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [BRANCO, CINZA_50]),
            ('ALIGN', (4,0), (4,-1), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.3, CINZA_200),
        ]))
        story.append(flu_table)

    # ── PNEUS ─────────────────────────────────────────
    if pneus_montados:
        section_title('Histórico de Pneus')

        pneu_data = [['Pneu', 'Posição', 'Tipo', 'Montagem', 'Desmontagem', 'KM rodado']]
        for pv in pneus_montados:
            p = pv.pneu
            km_rod = ''
            if pv.km_inicio and pv.km_fim:
                km_rod = _km(pv.km_fim - pv.km_inicio)
            elif pv.km_inicio and pv.ativo and p.km_rodado:
                km_rod = _km(p.km_rodado) + ' *'

            pneu_data.append([
                p.nome_display[:25],
                pv.posicao_display,
                p.tipo.capitalize(),
                pv.data_inicio.strftime('%d/%m/%Y') if pv.data_inicio else '—',
                pv.data_fim.strftime('%d/%m/%Y') if pv.data_fim else 'Atual',
                km_rod or '—',
            ])

        pneu_table = Table(pneu_data, colWidths=['28%', '18%', '10%', '14%', '14%', '16%'])
        pneu_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRETO),
            ('TEXTCOLOR', (0,0), (-1,0), BRANCO),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [BRANCO, CINZA_50]),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.3, CINZA_200),
        ]))
        story.append(pneu_table)
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph('* KM calculado até o odômetro atual', small))

    # ── TOTAL GERAL ────────────────────────────────────
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.3*cm))

    total_data = [['CUSTO TOTAL DO PERÍODO', _brl(custo_total)]]
    total_table = Table(total_data, colWidths=['70%', '30%'])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), PRETO),
        ('TEXTCOLOR', (0,0), (0,-1), BRANCO),
        ('TEXTCOLOR', (1,0), (1,-1), LARANJA),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 13),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
        ('ROUNDEDCORNERS', [8]),
    ]))
    story.append(total_table)

    # ── Gera PDF ─────────────────────────────────────
    doc.build(story)
    buf.seek(0)

    filename = f'custo_{v.placa}_{date.today().strftime("%Y%m%d")}.pdf'
    return Response(
        buf.read(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{filename}"'}
    )
