"""
Geração de PDF — Plano de Manutenção
Usa ReportLab (já disponível nos outros sistemas do portfólio)
"""
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

LARANJA  = colors.HexColor('#F7931E')
ESCURO   = colors.HexColor('#1C1C1E')
CINZA_BG = colors.HexColor('#F5F5F5')
BRANCO   = colors.white

def gerar_pdf_plano(veiculo, planos, usuario_nome=''):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'titulo', parent=styles['Heading1'],
        fontSize=18, textColor=ESCURO, spaceAfter=4,
        fontName='Helvetica-Bold',
    )
    sub_style = ParagraphStyle(
        'sub', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#666666'), spaceAfter=12,
    )
    label_style = ParagraphStyle(
        'label', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#999999'),
    )
    valor_style = ParagraphStyle(
        'valor', parent=styles['Normal'],
        fontSize=11, textColor=ESCURO, fontName='Helvetica-Bold',
    )

    elementos = []

    # Cabeçalho
    elementos.append(Paragraph('EMPRESA EXEMPLO', ParagraphStyle(
        'marca', parent=styles['Normal'],
        fontSize=10, textColor=LARANJA, fontName='Helvetica-Bold', spaceAfter=4,
    )))
    elementos.append(Paragraph('Plano de Manutenção de Frota', titulo_style))
    elementos.append(Paragraph(
        f'Gerado em {date.today().strftime("%d/%m/%Y")} por {usuario_nome}', sub_style
    ))
    elementos.append(HRFlowable(width='100%', color=LARANJA, thickness=2, spaceAfter=16))

    # Informações do veículo
    info_data = [
        [Paragraph('Veículo', label_style), Paragraph('Placa', label_style),
         Paragraph('KM Atual', label_style), Paragraph('Município', label_style)],
        [Paragraph(veiculo.descricao or '—', valor_style),
         Paragraph(veiculo.placa, valor_style),
         Paragraph(f'{veiculo.km_atual:,} km'.replace(',', '.'), valor_style),
         Paragraph(veiculo.municipio_base or '—', valor_style)],
    ]
    t_info = Table(info_data, colWidths=[6*cm, 3*cm, 3*cm, 4.8*cm])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), CINZA_BG),
        ('ROWBACKGROUNDS', (0, 1), (-1, 1), [BRANCO]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(t_info)
    elementos.append(Spacer(1, 20))

    if not planos:
        elementos.append(Paragraph('Nenhum plano de manutenção cadastrado para este veículo.', styles['Normal']))
    else:
        # Tabela de planos
        cabecalho = [
            Paragraph('Serviço', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
            Paragraph('Tipo', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
            Paragraph('Gatilho', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
            Paragraph('Próximo KM', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
            Paragraph('Próxima Data', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
            Paragraph('Status', ParagraphStyle('ch', parent=styles['Normal'],
                       fontSize=9, textColor=BRANCO, fontName='Helvetica-Bold')),
        ]
        dados = [cabecalho]

        for p in planos:
            km_str   = f'{p.proximo_km:,}'.replace(',', '.') if p.proximo_km else '—'
            data_str = p.proxima_data.strftime('%d/%m/%Y') if p.proxima_data else '—'

            # Status do plano
            status = 'Ok'
            cor_status = colors.HexColor('#27AE60')
            hoje = date.today()
            if p.proximo_km and veiculo.km_atual >= p.proximo_km:
                status = 'Vencido (km)'
                cor_status = colors.HexColor('#E74C3C')
            elif p.proxima_data and p.proxima_data < hoje:
                status = 'Vencido (data)'
                cor_status = colors.HexColor('#E74C3C')
            elif (p.proximo_km and veiculo.km_atual >= p.proximo_km - p.alerta_km_antes):
                status = 'Próximo'
                cor_status = LARANJA
            elif (p.proxima_data and (p.proxima_data - hoje).days <= p.alerta_dias_antes):
                status = 'Próximo'
                cor_status = LARANJA

            linha = [
                Paragraph(p.servico.nome, styles['Normal']),
                Paragraph(p.tipo.capitalize(), styles['Normal']),
                Paragraph(p.gatilho_tipo.upper(), styles['Normal']),
                Paragraph(km_str, styles['Normal']),
                Paragraph(data_str, styles['Normal']),
                Paragraph(status, ParagraphStyle('st', parent=styles['Normal'],
                           fontSize=9, textColor=cor_status, fontName='Helvetica-Bold')),
            ]
            dados.append(linha)

        t = Table(dados, colWidths=[5.5*cm, 2.5*cm, 2.3*cm, 2.5*cm, 2.8*cm, 2.2*cm])
        row_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), LARANJA),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BRANCO, CINZA_BG]),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#EEEEEE')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]
        t.setStyle(TableStyle(row_styles))
        elementos.append(t)

    elementos.append(Spacer(1, 24))
    elementos.append(HRFlowable(width='100%', color=colors.HexColor('#EEEEEE'), thickness=1))
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph(
        f'Empresa Exemplo · Sistema de Frota · {date.today().strftime("%d/%m/%Y")}',
        ParagraphStyle('rodape', parent=styles['Normal'],
                       fontSize=8, textColor=colors.HexColor('#AAAAAA'), alignment=1),
    ))

    doc.build(elementos)
    buf.seek(0)
    return buf
