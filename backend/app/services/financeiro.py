"""
Serviço de notificações ao Financeiro — Frota Empresa Exemplo

Dois gatilhos:
  1. Aprovação de Cotação (OC gerada) → e-mail ao Financeiro para solicitar pagamento
     Anexo: PDF de Ordem de Compra com todos os dados da cotação aprovada

  2. Conclusão de OS → e-mail ao Financeiro com PDF De Acordo + todas as NFs/comprovantes
     Anexos: PDF De Acordo (gerado automaticamente) + cada arquivo da OS do tipo 'nf' ou 'comprovante'

Remetente: TI@empresaexemplo.com.br  (via Microsoft Graph)
Destinatário: financeiro@empresaexemplo.com.br
"""
import os
import base64
import logging
import requests
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from app.services.msal_client import get_graph_token

logger = logging.getLogger(__name__)

EMAIL_FINANCEIRO = os.environ.get('EMAIL_FINANCEIRO', 'financeiro@empresaexemplo.com.br')
EMAIL_REMETENTE  = os.environ.get('EMAIL_REMETENTE',  'TI@empresaexemplo.com.br')
EMAIL_CC_TI      = os.environ.get('EMAIL_CC_TI',      'TI@empresaexemplo.com.br')
BASE_URL         = os.environ.get('BASE_URL', 'https://seu-app.onrender.com')

# cores PDF
LARANJA   = colors.HexColor('#F7931E')
PRETO     = colors.HexColor('#1C1C1E')
BRANCO    = colors.white
CINZA_50  = colors.HexColor('#F9F9F9')
CINZA_200 = colors.HexColor('#E5E5EA')
VERDE     = colors.HexColor('#34C759')


def _brl(v) -> str:
    try:
        return f'R$ {float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return 'R$ 0,00'


def _fmt_date(d) -> str:
    if not d:
        return '—'
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


# ─────────────────────────────────────────────────────────
#  ENVIO DE E-MAIL COM ANEXOS (Microsoft Graph)
# ─────────────────────────────────────────────────────────

def _enviar_email_financeiro(assunto: str, corpo_html: str,
                              anexos: list[dict]) -> bool:
    """
    Envia e-mail ao Financeiro via Microsoft Graph.
    anexos: lista de {'name': str, 'content_type': str, 'bytes': bytes}
    """
    token = get_graph_token()
    if not token:
        logger.error('[Financeiro] Token Graph não obtido — e-mail cancelado.')
        return False

    attachments = []
    for a in anexos:
        try:
            attachments.append({
                '@odata.type':  '#microsoft.graph.fileAttachment',
                'name':         a['name'],
                'contentType':  a.get('content_type', 'application/pdf'),
                'contentBytes': base64.b64encode(a['bytes']).decode(),
            })
        except Exception as e:
            logger.warning(f'[Financeiro] Erro ao codificar anexo {a.get("name")}: {e}')

    # CC obrigatório para TI (exceto se TI for o próprio remetente)
    cc_list = []
    if EMAIL_CC_TI and EMAIL_CC_TI.lower() != EMAIL_REMETENTE.lower():
        cc_list.append({'emailAddress': {'address': EMAIL_CC_TI}})

    payload = {
        'message': {
            'subject': assunto,
            'body': {'contentType': 'HTML', 'content': corpo_html},
            'toRecipients': [{'emailAddress': {'address': EMAIL_FINANCEIRO}}],
            'ccRecipients': cc_list,
            'attachments': attachments,
        },
        'saveToSentItems': 'true',
    }

    resp = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{EMAIL_REMETENTE}/sendMail',
        json=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=30,
    )
    if resp.status_code == 202:
        logger.info(f'[Financeiro] E-mail enviado: {assunto}')
        return True
    logger.error(f'[Financeiro] Graph sendMail {resp.status_code}: {resp.text[:300]}')
    return False


# ─────────────────────────────────────────────────────────
#  PDF — ORDEM DE COMPRA (para solicitar pagamento)
# ─────────────────────────────────────────────────────────

def gerar_pdf_ordem_compra(oc) -> bytes:
    """Gera PDF da Ordem de Compra com todos os dados relevantes para pagamento."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = []

    h2   = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11,
                           textColor=PRETO, spaceAfter=4, spaceBefore=12)
    small= ParagraphStyle('sm', fontName='Helvetica', fontSize=9,
                           textColor=colors.HexColor('#636366'), leading=13)
    body = ParagraphStyle('bd', fontName='Helvetica', fontSize=10,
                           textColor=PRETO, leading=14)
    ctr  = ParagraphStyle('ct', fontName='Helvetica-Bold', fontSize=13,
                           alignment=TA_CENTER, textColor=PRETO)

    def _tbl(data, widths):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',  (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE',  (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [BRANCO, CINZA_50]),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.3, CINZA_200),
        ]))
        return t

    # Cabeçalho
    hdr = [[
        Paragraph('<b><font color="#F7931E">Empresa</font> Exemplo</b>',
                  ParagraphStyle('lg', fontName='Helvetica-Bold', fontSize=20, textColor=PRETO)),
        Paragraph(f'<b>ORDEM DE COMPRA</b><br/>'
                  f'<font color="#636366" size="9">{oc.numero}</font>',
                  ParagraphStyle('rt', fontName='Helvetica-Bold', fontSize=13,
                                 textColor=PRETO, alignment=TA_RIGHT, leading=18)),
    ]]
    ht = Table(hdr, colWidths=['60%', '40%'])
    ht.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(ht)
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph('SOLICITAÇÃO DE PAGAMENTO — ORDEM DE COMPRA APROVADA', ctr))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=CINZA_200))

    # Dados da OC
    orc = oc.orcamento
    story.append(Paragraph('Dados da Ordem de Compra', h2))
    story.append(_tbl([
        ['Número OC',     oc.numero],
        ['Orçamento ref.',orc.numero if orc else '—'],
        ['Tipo',          'Aquisição de Serviço' if (orc and orc.tipo_solicitacao == 'aquisicao_servico') else 'Compra de Peça para OS'],
        ['Data emissão',  _fmt_date(oc.gerada_em)],
        ['Veículo',       f'{orc.veiculo.placa} — {orc.veiculo.descricao or orc.veiculo.modelo or ""}' if (orc and orc.veiculo) else '—'],
    ] + ([['OS Vinculada', oc.os.numero]] if oc.os else []),
    ['38%', '62%']))

    # Dados do fornecedor
    story.append(Paragraph('Fornecedor', h2))
    forn = oc.fornecedor
    forn_dados = [['Razão Social', forn.razao_social]]
    if getattr(forn, 'cnpj', None):       forn_dados.append(['CNPJ', forn.cnpj])
    if getattr(forn, 'telefone', None):   forn_dados.append(['Telefone', forn.telefone])
    if getattr(forn, 'email', None):      forn_dados.append(['E-mail', forn.email])
    story.append(_tbl(forn_dados, ['38%', '62%']))

    # Dados da cotação aprovada
    cot = oc.cotacao
    if cot:
        story.append(Paragraph('Proposta Aprovada', h2))
        story.append(_tbl([
            ['Fornecedor',  cot.fornecedor.razao_social if cot.fornecedor else '—'],
            ['Prazo',       f'{cot.prazo_dias} dias' if cot.prazo_dias else '—'],
            ['Condições',   cot.condicoes or '—'],
            ['Aprovado por',cot.aprovador.nome if cot.aprovador else '—'],
            ['Data aprova.',_fmt_date(cot.aprovada_em)],
        ] + ([['Justificativa', cot.justificativa]] if cot.justificativa else []),
        ['38%', '62%']))

    if cot and cot.observacoes:
        story.append(Paragraph('Observações da Proposta', h2))
        story.append(Paragraph(cot.observacoes, body))

    # Descrição do orçamento
    if orc and orc.descricao:
        story.append(Paragraph('Descrição do Serviço / Peça', h2))
        story.append(Paragraph(orc.descricao, body))

    # Itens do orçamento
    if orc and orc.itens:
        story.append(Paragraph('Itens', h2))
        rows = [['Descrição', 'Qtd', 'Valor Unit.', 'Total']]
        for i in orc.itens:
            nome = ''
            if i.tipo_item == 'servico':
                nome = i.servico.nome if i.servico else (i.descricao_livre or '—')
            else:
                nome = i.material.nome if i.material else (i.descricao_livre or '—')
            rows.append([nome,
                         f'{float(i.quantidade):.0f}x',
                         _brl(i.valor_unitario),
                         _brl(i.valor_total)])
        it = Table(rows, colWidths=['50%', '12%', '19%', '19%'])
        it.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), PRETO),
            ('TEXTCOLOR',    (0, 0), (-1, 0), BRANCO),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_50]),
            ('ALIGN',        (1, 0), (3, -1), 'RIGHT'),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID',         (0, 0), (-1, -1), 0.3, CINZA_200),
        ]))
        story.append(it)

    # Total em destaque
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.2*cm))
    tot = Table([['VALOR TOTAL A PAGAR', _brl(oc.valor_total)]],
                colWidths=['65%', '35%'])
    tot.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRETO),
        ('TEXTCOLOR',  (0, 0), (0,  0),  BRANCO),
        ('TEXTCOLOR',  (1, 0), (1,  0),  LARANJA),
        ('FONTNAME',   (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 13),
        ('ALIGN',      (1, 0), (1,  -1), 'RIGHT'),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
    ]))
    story.append(tot)

    # Condições de pagamento em destaque
    if oc.condicoes:
        story.append(Spacer(1, 0.3*cm))
        cond_box = Table([[f'Condições: {oc.condicoes}']], colWidths=['100%'])
        cond_box.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#FFF4E6')),
            ('TEXTCOLOR',     (0, 0), (-1, -1), colors.HexColor('#92570A')),
            ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 10),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING',   (0, 0), (-1, -1), 12),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
            ('BOX',           (0, 0), (-1, -1), 0.5, LARANJA),
        ]))
        story.append(cond_box)

    # Rodapé
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=CINZA_200))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f'Gerado em {datetime.utcnow().strftime("%d/%m/%Y %H:%M")} UTC · '
        f'Empresa Exemplo · CNPJ 00.000.000/0001-00 · seu-app.onrender.com',
        small))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────
#  NOTIFICAÇÃO 1: OC APROVADA → FINANCEIRO SOLICITAR PAGAMENTO
# ─────────────────────────────────────────────────────────

def notificar_financeiro_oc_aprovada(oc) -> bool:
    """
    Chamado quando uma cotação é aprovada e a OC é gerada.
    Envia e-mail ao Financeiro com PDF da OC solicitando pagamento.
    """
    orc  = oc.orcamento
    cot  = oc.cotacao
    forn = oc.fornecedor

    tipo_txt = ('Aquisição de Serviço'
                if (orc and orc.tipo_solicitacao == 'aquisicao_servico')
                else 'Compra de Peça para OS')
    veiculo_txt = ''
    if orc and orc.veiculo:
        veiculo_txt = f'{orc.veiculo.placa} — {orc.veiculo.descricao or orc.veiculo.modelo or ""}'

    aprovador_nome = cot.aprovador.nome if (cot and cot.aprovador) else 'Sistema'
    link_oc = f'{BASE_URL}/orcamentos/ordens-compra/{oc.id}'

    corpo = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;background:#F2F2F7;margin:0;padding:32px 16px;">
<table width="600" align="center" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
<tr><td style="background:#34C759;padding:24px 32px;">
  <div style="font-size:22px;font-weight:700;color:#fff;">💰 Solicitação de Pagamento</div>
  <div style="font-size:13px;color:rgba(255,255,255,.9);margin-top:4px;">
    Ordem de Compra <strong>{oc.numero}</strong> aprovada — aguarda pagamento
  </div>
</td></tr>
<tr><td style="padding:24px 32px;">

  <table width="100%" cellpadding="0" cellspacing="8" style="font-size:13px;margin-bottom:20px;">
    <tr>
      <td style="color:#636366;font-weight:600;width:38%;">Número OC</td>
      <td style="font-weight:700;font-family:monospace;font-size:15px;">{oc.numero}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Orçamento ref.</td>
      <td>{orc.numero if orc else '—'}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Tipo</td>
      <td>{tipo_txt}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Veículo</td>
      <td style="font-weight:600;color:#F7931E;">{veiculo_txt or '—'}</td>
    </tr>
    {"<tr><td style='color:#636366;font-weight:600;'>OS Vinculada</td><td>" + oc.os.numero + "</td></tr>" if oc.os else ""}
    <tr>
      <td style="color:#636366;font-weight:600;">Fornecedor</td>
      <td style="font-weight:600;">{forn.razao_social if forn else '—'}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Prazo entrega</td>
      <td>{f"{cot.prazo_dias} dias" if (cot and cot.prazo_dias) else "—"}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Condições pagto.</td>
      <td style="font-weight:600;color:#92570A;">{oc.condicoes or "—"}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Aprovado por</td>
      <td>{aprovador_nome}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Data aprovação</td>
      <td>{_fmt_date(cot.aprovada_em) if cot else '—'}</td>
    </tr>
  </table>

  <!-- VALOR DESTAQUE -->
  <div style="background:#1C1C1E;border-radius:12px;padding:18px 24px;
              display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
    <span style="color:#fff;font-size:14px;font-weight:600;">VALOR TOTAL A PAGAR</span>
    <span style="color:#F7931E;font-size:26px;font-weight:700;font-family:monospace;">
      {_brl(oc.valor_total)}
    </span>
  </div>

  {"<div style='background:#FFF4E6;border:1px solid #F7931E;border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:13px;color:#92570A;'><strong>Condições:</strong> " + oc.condicoes + "</div>" if oc.condicoes else ""}

  <p style="font-size:13px;color:#636366;">
    O PDF da Ordem de Compra está anexo a este e-mail com todos os detalhes para processamento do pagamento.
  </p>

  <div style="text-align:center;margin:24px 0;">
    <a href="{link_oc}"
       style="display:inline-block;background:#F7931E;color:#fff;font-size:14px;font-weight:700;
              padding:14px 28px;border-radius:10px;text-decoration:none;">
      Ver Ordem de Compra no sistema →
    </a>
  </div>

</td></tr>
<tr><td style="background:#F2F2F7;padding:14px 32px;text-align:center;font-size:11px;color:#8E8E93;">
  Empresa Exemplo · Sistema de Frotas · Enviado por TI@empresaexemplo.com.br
</td></tr>
</table>
</body></html>"""

    try:
        pdf_bytes = gerar_pdf_ordem_compra(oc)
    except Exception as e:
        logger.error(f'[Financeiro] Erro ao gerar PDF OC {oc.numero}: {e}', exc_info=True)
        pdf_bytes = None

    anexos = []
    if pdf_bytes:
        anexos.append({
            'name': f'OrdemCompra_{oc.numero}.pdf',
            'content_type': 'application/pdf',
            'bytes': pdf_bytes,
        })

    # Anexa o PDF/arquivo da cotação aprovada (proposta do fornecedor)
    cot = oc.cotacao
    if cot and cot.anexo_url:
        try:
            resp_cot = requests.get(cot.anexo_url, timeout=20)
            if resp_cot.status_code == 200:
                ext = cot.anexo_url.rsplit('.', 1)[-1].lower().split('?')[0]
                ct  = 'application/pdf' if ext == 'pdf' else f'image/{ext}' if ext in ('jpg','jpeg','png') else 'application/octet-stream'
                nome_cot = f'Cotacao_aprovada_{oc.numero}.{ext}'
                anexos.append({'name': nome_cot, 'content_type': ct, 'bytes': resp_cot.content})
                logger.info(f'[Financeiro] Cotação aprovada anexada: {nome_cot}')
            else:
                logger.warning(f'[Financeiro] Não foi possível baixar cotação aprovada OC {oc.numero}: HTTP {resp_cot.status_code}')
        except Exception as e:
            logger.warning(f'[Financeiro] Erro ao baixar cotação aprovada OC {oc.numero}: {e}')

    assunto = f'[Frota] Pagamento pendente — OC {oc.numero} · {_brl(oc.valor_total)} · {forn.razao_social if forn else ""}'
    ok = _enviar_email_financeiro(assunto, corpo, anexos)
    if ok:
        logger.info(f'[Financeiro] Notificação OC {oc.numero} enviada para {EMAIL_FINANCEIRO}')
    else:
        logger.error(f'[Financeiro] Falha ao notificar OC {oc.numero}')
    return ok


# ─────────────────────────────────────────────────────────
#  NOTIFICAÇÃO 2: OS CONCLUÍDA → FINANCEIRO COM PDFs
# ─────────────────────────────────────────────────────────

def notificar_financeiro_os_concluida(os_obj, pdf_de_acordo: bytes = None) -> bool:
    """
    Chamado ao concluir uma OS.
    Envia ao Financeiro:
      - PDF De Acordo (gerado automaticamente)
      - Todos os arquivos da OS do tipo 'nf' ou 'comprovante' (se tiverem url no SharePoint)
    """
    veiculo_txt = ''
    if os_obj.veiculo:
        veiculo_txt = f'{os_obj.veiculo.placa} — {os_obj.veiculo.descricao or os_obj.veiculo.modelo or ""}'

    aprovador_nome = '—'
    if os_obj.aprovador:
        aprovador_nome = os_obj.aprovador.nome
    elif os_obj.aprovacao_obs:
        aprovador_nome = 'Via e-mail'

    custo = float(os_obj.custo_total or 0)
    link_os = f'{BASE_URL}/os/{os_obj.id}'

    # Monta lista de NFs/comprovantes para exibir no corpo
    fotos_lista = list(os_obj.fotos.filter_by()) if hasattr(os_obj.fotos, 'filter_by') else list(os_obj.fotos)
    nfs = [f for f in fotos_lista if f.tipo in ('nf', 'comprovante') and f.url_sharepoint]
    # Todos os arquivos aprovados/anexados na OS (com link no SharePoint)
    todos_arquivos = [f for f in fotos_lista if f.url_sharepoint]
    fotos_doc = [f for f in fotos_lista if f.tipo not in ('nf', 'comprovante') and f.url_sharepoint]

    # Agrupa todos os arquivos por tipo para exibição no corpo do e-mail
    TIPO_LABEL = {
        'nf': 'Notas Fiscais', 'comprovante': 'Comprovantes',
        'foto': 'Fotos', 'laudo': 'Laudos', 'outros': 'Outros',
    }
    grupos: dict = {}
    for f in todos_arquivos:
        label = TIPO_LABEL.get(f.tipo, f.tipo.capitalize() if f.tipo else 'Outros')
        grupos.setdefault(label, []).append(f)

    nfs_html = ''
    for label, arquivos in grupos.items():
        nfs_html += f'<div style="margin-bottom:12px;"><strong style="font-size:12px;color:#636366;text-transform:uppercase;letter-spacing:.05em;">{label}</strong><ul style="margin:6px 0;padding-left:20px;">'
        for f in arquivos:
            nfs_html += f'<li style="font-size:13px;margin:4px 0;"><a href="{f.url_sharepoint}" style="color:#F7931E;">{f.nome_arquivo}</a></li>'
        nfs_html += '</ul></div>'

    corpo = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;background:#F2F2F7;margin:0;padding:32px 16px;">
<table width="600" align="center" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
<tr><td style="background:#1C1C1E;padding:24px 32px;">
  <div style="font-size:22px;font-weight:700;color:#fff;">🔧 OS Concluída — Solicitação de Pagamento</div>
  <div style="font-size:13px;color:rgba(255,255,255,.7);margin-top:4px;">
    OS <strong style="color:#F7931E;">{os_obj.numero}</strong> — documentos em anexo para processamento
  </div>
</td></tr>
<tr><td style="padding:24px 32px;">

  <table width="100%" cellpadding="0" cellspacing="8" style="font-size:13px;margin-bottom:20px;">
    <tr>
      <td style="color:#636366;font-weight:600;width:38%;">Número OS</td>
      <td style="font-weight:700;font-family:monospace;font-size:15px;">{os_obj.numero}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Veículo</td>
      <td style="font-weight:600;color:#F7931E;">{veiculo_txt or '—'}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Tipo</td>
      <td>{(os_obj.tipo_manutencao or '').capitalize()} — {os_obj.tipo_os or ''}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Fornecedor</td>
      <td>{os_obj.fornecedor.razao_social if os_obj.fornecedor else 'Interno'}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Data abertura</td>
      <td>{_fmt_date(os_obj.data_abertura)}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Data conclusão</td>
      <td>{_fmt_date(os_obj.data_conclusao)}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Aprovada por</td>
      <td>{aprovador_nome}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Concluída por</td>
      <td>{os_obj.baixador.nome if os_obj.baixador else "—"}</td>
    </tr>
  </table>

  <!-- CUSTO DESTAQUE -->
  <div style="background:#1C1C1E;border-radius:12px;padding:18px 24px;
              justify-content:space-between;display:flex;align-items:center;margin-bottom:24px;">
    <span style="color:#fff;font-size:14px;font-weight:600;">CUSTO TOTAL DA OS</span>
    <span style="color:#F7931E;font-size:26px;font-weight:700;font-family:monospace;">
      {_brl(custo)}
    </span>
  </div>

  {nfs_html}

  <div style="background:#E8F9EE;border:1px solid #B7EDD0;border-radius:8px;
              padding:12px 16px;font-size:13px;color:#1a6e35;margin-bottom:20px;">
    <strong>📎 Documentos em anexo:</strong><br>
    • PDF De Acordo (aprovação da OS)<br>
    {"".join(f"• {f.nome_arquivo}<br>" for f in todos_arquivos) or "• Nenhum arquivo adicional anexado"}
  </div>

  <p style="font-size:13px;color:#636366;">
    Segue em anexo o <strong>PDF De Acordo</strong> com a aprovação da OS e todos os arquivos vinculados
    (notas fiscais, comprovantes, fotos, laudos) para processamento do pagamento.
  </p>

  <div style="text-align:center;margin:24px 0;">
    <a href="{link_os}"
       style="display:inline-block;background:#F7931E;color:#fff;font-size:14px;font-weight:700;
              padding:14px 28px;border-radius:10px;text-decoration:none;">
      Ver OS no sistema →
    </a>
  </div>

</td></tr>
<tr><td style="background:#F2F2F7;padding:14px 32px;text-align:center;font-size:11px;color:#8E8E93;">
  Empresa Exemplo · Sistema de Frotas · Enviado por TI@empresaexemplo.com.br
</td></tr>
</table>
</body></html>"""

    # Monta anexos: PDF De Acordo + NFs do sistema
    anexos = []

    if pdf_de_acordo:
        anexos.append({
            'name': f'DeAcordo_OS_{os_obj.numero}.pdf',
            'content_type': 'application/pdf',
            'bytes': pdf_de_acordo,
        })

    # Baixa e anexa TODOS os arquivos da OS que têm URL no SharePoint
    # (NFs, comprovantes, fotos, laudos, etc. — tudo que foi aprovado/salvo)
    for foto in todos_arquivos:
        try:
            resp = requests.get(foto.url_sharepoint, timeout=20)
            if resp.status_code == 200:
                ext = foto.nome_arquivo.rsplit('.', 1)[-1].lower() if '.' in foto.nome_arquivo else 'bin'
                if ext in ('jpg', 'jpeg'):
                    ct = 'image/jpeg'
                elif ext == 'png':
                    ct = 'image/png'
                elif ext == 'pdf':
                    ct = 'application/pdf'
                else:
                    ct = 'application/octet-stream'
                anexos.append({
                    'name': foto.nome_arquivo,
                    'content_type': ct,
                    'bytes': resp.content,
                })
                logger.info(f'[Financeiro] Arquivo OS anexado: {foto.nome_arquivo} (tipo: {foto.tipo})')
            else:
                logger.warning(f'[Financeiro] Não foi possível baixar {foto.nome_arquivo}: HTTP {resp.status_code}')
        except Exception as e:
            logger.warning(f'[Financeiro] Erro ao baixar {foto.nome_arquivo}: {e}')

    assunto = (f'[Frota] OS Concluída — {os_obj.numero} · {_brl(custo)} · '
               f'{os_obj.veiculo.placa if os_obj.veiculo else ""}')
    ok = _enviar_email_financeiro(assunto, corpo, anexos)
    if ok:
        logger.info(f'[Financeiro] Notificação OS {os_obj.numero} enviada para {EMAIL_FINANCEIRO}')
    else:
        logger.error(f'[Financeiro] Falha ao notificar OS {os_obj.numero}')
    return ok
