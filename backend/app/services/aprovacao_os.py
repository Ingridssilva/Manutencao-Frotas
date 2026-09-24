"""
Serviço de aprovação de OS — Frota Empresa Exemplo

Regra de negócio:
  custo >= R$ 1.000 → Diretoria (owner@empresaexemplo.com.br)
  custo <  R$ 1.000 → Gestores de Frotas

Fluxo:
  1. OS criada → solicitar_aprovacao() → e-mail com token + botões Aprovar/Rejeitar
  2. Aprovador clica em Aprovar no e-mail → /aprovar/<token> → sem precisar logar
  3. Sistema registra aprovação, gera PDF, envia para a diretoria como cópia
"""
import os
import secrets
import logging
import base64
import requests
from datetime import datetime, timedelta
from io import BytesIO
from flask import url_for, current_app
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

LIMITE_APROVACAO = float(os.environ.get('OS_LIMITE_APROVACAO', '1000'))
BASE_URL = os.environ.get('BASE_URL', 'https://seu-app.onrender.com')

APROVADORES = {
    'diretoria': 'owner@empresaexemplo.com.br',  # também notificado via WhatsApp (ver WHATSAPP_APROVADOR)
    'gestor1':   'gestor1@empresaexemplo.com.br',
    'gestor2':   'gestor2@empresaexemplo.com.br',
}

WHATSAPP_APROVADOR = os.environ.get('WHATSAPP_APROVADOR', '')  # formato internacional sem + (ex: 5599999999999)

LARANJA  = colors.HexColor('#F7931E')
PRETO    = colors.HexColor('#1C1C1E')
CINZA_50 = colors.HexColor('#F2F2F7')
CINZA_200= colors.HexColor('#C7C7CC')
BRANCO   = colors.white


def _brl(v) -> str:
    try:
        return f'R$ {float(v):,.2f}'.replace(',','X').replace('.', ',').replace('X','.')
    except Exception:
        return 'R$ 0,00'


def _fmt_date(d) -> str:
    if not d:
        return '—'
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


def aprovadores_para_os(custo: float) -> list:
    if custo >= LIMITE_APROVACAO:
        return [APROVADORES['diretoria']]
    return [APROVADORES['gestor1']]


def _gerar_token(os_obj) -> str:
    """Gera token único para aprovação via e-mail e salva na OS."""
    from app import db
    token = secrets.token_urlsafe(48)
    os_obj.aprovacao_token     = token
    os_obj.aprovacao_token_exp = datetime.utcnow() + timedelta(days=7)
    db.session.commit()
    return token


def _enviar_whatsapp(numero: str, mensagem: str) -> bool:
    """
    Envia mensagem WhatsApp via UltraMsg.
    Variáveis de ambiente necessárias:
      ULTRAMSG_INSTANCE — instance id do painel ultramsg.com
      ULTRAMSG_TOKEN    — token do painel ultramsg.com
    """
    instance = os.environ.get('ULTRAMSG_INSTANCE', '')
    token    = os.environ.get('ULTRAMSG_TOKEN', '')
    if not instance or not token:
        logger.warning('ULTRAMSG_INSTANCE ou ULTRAMSG_TOKEN não configurados — WhatsApp não enviado.')
        return False
    try:
        url  = f'https://api.ultramsg.com/{instance}/messages/chat'
        payload = {
            'token': token,
            'to':    f'+{numero}',
            'body':  mensagem,
        }
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get('sent') == 'true' or data.get('id'):
            logger.info(f'WhatsApp UltraMsg enviado para {numero}')
            return True
        logger.error(f'UltraMsg erro: {data}')
        return False
    except Exception as e:
        logger.error(f'Erro ao enviar WhatsApp UltraMsg: {e}')
        return False


def solicitar_aprovacao(os_obj) -> bool:
    """
    Envia e-mail com botões Aprovar/Rejeitar inline.
    O aprovador pode decidir sem precisar entrar no sistema.
    """
    from app import db

    custo         = float(os_obj.custo_total or 0)
    destinatarios = aprovadores_para_os(custo)
    nivel_txt     = ('Diretoria (acima de R$ 1.000)'
                     if custo >= LIMITE_APROVACAO else 'Gestor de Frotas')

    # Gera token para aprovação sem login
    token = _gerar_token(os_obj)
    link_token    = f'{BASE_URL}/aprovar/{token}'
    link_sistema  = f'{BASE_URL}/os/{os_obj.id}/aprovar'

    veiculo_txt = ''
    if os_obj.veiculo:
        veiculo_txt = f'{os_obj.veiculo.placa} — {os_obj.veiculo.descricao or os_obj.veiculo.modelo or ""}'

    # Monta tabela de serviços
    servicos_html = ''
    if os_obj.itens_servico:
        servicos_html += '<tr><td colspan="3" style="padding:8px 0 4px;font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;">Serviços</td></tr>'
        for i in os_obj.itens_servico:
            nome = i.servico.nome if i.servico else (i.descricao_livre or '—')
            servicos_html += f'<tr><td style="padding:4px 0;font-size:13px;">{nome}</td><td style="text-align:right;padding:4px 8px;font-size:13px;color:#636366;">{i.quantidade}x</td><td style="text-align:right;padding:4px 0;font-size:13px;">{_brl(i.valor_unitario)}</td></tr>'

    if os_obj.itens_material:
        servicos_html += '<tr><td colspan="3" style="padding:10px 0 4px;font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;">Materiais</td></tr>'
        for i in os_obj.itens_material:
            nome = i.material.nome if i.material else (i.descricao_livre or '—')
            servicos_html += f'<tr><td style="padding:4px 0;font-size:13px;">{nome}</td><td style="text-align:right;padding:4px 8px;font-size:13px;color:#636366;">{i.quantidade}x</td><td style="text-align:right;padding:4px 0;font-size:13px;">{_brl(i.valor_unitario)}</td></tr>'

    # Parcelas
    parcelas_html = ''
    if os_obj.pagamentos:
        parcelas_html = '<tr><td colspan="3" style="padding:10px 0 4px;font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;">Parcelas</td></tr>'
        for p in os_obj.pagamentos:
            parcelas_html += (
                f'<tr><td style="padding:4px 0;font-size:13px;">Venc. {_fmt_date(p.data_vencimento)}</td>'
                f'<td style="text-align:right;padding:4px 0;font-size:13px;font-weight:600;" colspan="2">{_brl(p.valor)}</td></tr>'
            )

    tabela_itens = ''
    if servicos_html or parcelas_html:
        tabela_itens = f'''
        <tr><td style="padding:0 0 16px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            {servicos_html}
            {parcelas_html}
            <tr><td colspan="3" style="border-top:1px solid #E5E5EA;padding-top:8px;"></td></tr>
            <tr>
              <td style="font-size:14px;font-weight:700;">TOTAL</td>
              <td colspan="2" style="text-align:right;font-size:18px;font-weight:700;color:#F7931E;">{_brl(custo)}</td>
            </tr>
          </table>
        </td></tr>'''

    corpo = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;background:#F2F2F7;margin:0;padding:32px 16px;">
<table width="600" align="center" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
<tr><td style="background:#F7931E;padding:24px 32px;">
  <div style="font-size:22px;font-weight:700;color:#fff;">🔔 Autorização — OS {os_obj.numero}</div>
  <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:6px;">Nível: {nivel_txt}</div>
</td></tr>
<tr><td style="padding:24px 32px 0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="padding:0 0 12px;border-bottom:1px solid #F2F2F7;">
      <div style="font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;margin-bottom:4px;">Veículo</div>
      <div style="font-size:16px;font-weight:600;">{veiculo_txt}</div>
    </td></tr>
    <tr><td style="padding:10px 0 12px;border-bottom:1px solid #F2F2F7;">
      <div style="font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;margin-bottom:4px;">Tipo</div>
      <div style="font-size:15px;">{(os_obj.tipo_manutencao or '').capitalize()} — {os_obj.tipo_os or ''}</div>
    </td></tr>
    {'<tr><td style="padding:10px 0 12px;border-bottom:1px solid #F2F2F7;"><div style="font-size:11px;font-weight:600;color:#636366;text-transform:uppercase;margin-bottom:4px;">Descrição</div><div style="font-size:14px;color:#48484A;">' + (os_obj.descricao_problema or '')[:300] + '</div></td></tr>' if os_obj.descricao_problema else ''}
    <tr><td style="padding:16px 0;">{tabela_itens}</td></tr>
  </table>
</td></tr>

<!-- BOTÕES APROVAR / REJEITAR -->
<tr><td style="padding:0 32px 28px;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td width="48%" align="center">
        <a href="{link_token}?acao=aprovar"
           style="display:block;background:#30D158;color:#fff;padding:14px 20px;
                  border-radius:10px;font-weight:700;font-size:15px;text-decoration:none;
                  text-align:center;">
          ✓ Aprovar OS
        </a>
      </td>
      <td width="4%"></td>
      <td width="48%" align="center">
        <a href="{link_token}?acao=rejeitar"
           style="display:block;background:#FF453A;color:#fff;padding:14px 20px;
                  border-radius:10px;font-weight:700;font-size:15px;text-decoration:none;
                  text-align:center;">
          ✕ Rejeitar OS
        </a>
      </td>
    </tr>
    <tr><td colspan="3" style="padding-top:12px;text-align:center;">
      <a href="{link_sistema}"
         style="font-size:12px;color:#8E8E93;text-decoration:none;">
        Ver OS completa no sistema →
      </a>
    </td></tr>
  </table>
</td></tr>

<tr><td style="padding:16px 32px 24px;border-top:1px solid #E5E5EA;">
  <div style="font-size:12px;color:#8E8E93;">
    Link expira em 7 dias · Sistema de Frota — Empresa Exemplo ·
    <a href="{BASE_URL}" style="color:#F7931E;">seu-app.onrender.com</a>
  </div>
</td></tr>
</table>
</body></html>"""

    ok = _enviar_email(
        destinatarios,
        f'[Frota] Autorização — OS {os_obj.numero} · {_brl(custo)}',
        corpo,
    )
    # Seta pendente independente do e-mail ter sido enviado —
    # o formulário de aprovação deve aparecer mesmo se o e-mail falhou
    os_obj.aprovacao_status = 'pendente'
    db.session.commit()
    if ok:
        logger.info(f'Aprovação solicitada → {destinatarios} OS {os_obj.numero}')
    else:
        logger.error(f'FALHA ao enviar aprovação OS {os_obj.numero} → {destinatarios}')

    # Notifica a diretoria também via WhatsApp para OS de alto valor (>= R$1.000)
    if custo >= LIMITE_APROVACAO:
        msg_wpp = (
            f'🔔 *Nova OS para aprovação*\n'
            f'OS: *{os_obj.numero}*\n'
            f'Veículo: *{veiculo_txt}*\n'
            f'Tipo: {(os_obj.tipo_manutencao or "").capitalize()}\n'
            f'Valor: *{_brl(custo)}*\n'
            f'🔗 Aprovar: {link_token}?acao=aprovar\n'
            f'❌ Rejeitar: {link_token}?acao=rejeitar'
        )
        _enviar_whatsapp(WHATSAPP_APROVADOR, msg_wpp)

    return ok


def registrar_aprovacao(os_obj, aprovador_user, obs: str = '') -> bytes:
    from app import db
    os_obj.aprovacao_status   = 'aprovada'
    os_obj.aprovado_por       = aprovador_user.id
    os_obj.aprovado_em        = datetime.utcnow()
    os_obj.aprovacao_obs      = obs
    os_obj.aprovacao_token    = None
    os_obj.aprovacao_token_exp= None
    db.session.commit()
    pdf_bytes = gerar_pdf_de_acordo(os_obj, aprovador_user)
    _enviar_pdf_aprovacao(os_obj, aprovador_user.nome, aprovador_user.email, pdf_bytes)
    logger.info(f'OS {os_obj.numero} aprovada por {aprovador_user.email}')
    return pdf_bytes


def registrar_rejeicao(os_obj, aprovador_user, motivo: str) -> bool:
    from app import db
    os_obj.aprovacao_status   = 'rejeitada'
    os_obj.aprovado_por       = aprovador_user.id
    os_obj.aprovado_em        = datetime.utcnow()
    os_obj.aprovacao_obs      = motivo
    os_obj.status             = 'aberta'
    os_obj.aprovacao_token    = None
    os_obj.aprovacao_token_exp= None
    db.session.commit()
    criador_email = os_obj.criador.email if os_obj.criador else None
    dest = list({e for e in [criador_email, APROVADORES['diretoria']] if e})
    if dest:
        _enviar_email(dest,
            f'[Frota] OS {os_obj.numero} Rejeitada',
            f'<html><body style="font-family:system-ui;padding:24px;">'
            f'<h2 style="color:#FF453A;">OS {os_obj.numero} Rejeitada</h2>'
            f'<p><strong>Motivo:</strong> {motivo}</p>'
            f'<p><strong>Por:</strong> {aprovador_user.nome}</p>'
            f'<p>A OS foi reaberta para correção.</p></body></html>')
    return True


def _enviar_pdf_sem_usuario(os_obj, nome_aprovador: str, pdf_bytes: bytes) -> bool:
    """Envia PDF de aprovação quando aprovado via token (sem usuário logado)."""
    dest = list({APROVADORES['diretoria']})
    if os_obj.criador and os_obj.criador.email:
        dest.append(os_obj.criador.email)
    return _enviar_pdf_aprovacao(os_obj, nome_aprovador or 'Aprovador', '', pdf_bytes, dest)


def _notificar_rejeicao_email(os_obj, nome_aprovador: str, motivo: str) -> bool:
    criador_email = os_obj.criador.email if os_obj.criador else None
    dest = list({e for e in [criador_email, APROVADORES['diretoria']] if e})
    if not dest:
        return False
    return _enviar_email(dest,
        f'[Frota] OS {os_obj.numero} Rejeitada',
        f'<html><body style="font-family:system-ui;padding:24px;">'
        f'<h2 style="color:#FF453A;">OS {os_obj.numero} Rejeitada</h2>'
        f'<p><strong>Motivo:</strong> {motivo}</p>'
        f'<p><strong>Por:</strong> {nome_aprovador}</p>'
        f'<p>A OS foi reaberta para correção.</p></body></html>')


def gerar_pdf_de_acordo(os_obj, aprovador_user=None, nome_aprovador: str = '') -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = []

    h2    = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11,
                            textColor=PRETO, spaceAfter=4, spaceBefore=12)
    small = ParagraphStyle('sm', fontName='Helvetica', fontSize=9,
                            textColor=colors.HexColor('#636366'), leading=13)
    body  = ParagraphStyle('bd', fontName='Helvetica', fontSize=10,
                            textColor=PRETO, leading=14)
    ctr   = ParagraphStyle('ct', fontName='Helvetica-Bold', fontSize=13,
                            alignment=TA_CENTER, textColor=PRETO)

    def _tbl(data, widths):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',(1,0),(1,-1),'Helvetica'),
            ('FONTSIZE',(0,0),(-1,-1),10),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[BRANCO, CINZA_50]),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
            ('GRID',(0,0),(-1,-1),0.3,CINZA_200),
        ]))
        return t

    # Cabeçalho
    hdr = [[
        Paragraph('<b><font color="#F7931E">Empresa</font> Exemplo</b>',
                  ParagraphStyle('lg', fontName='Helvetica-Bold', fontSize=20, textColor=PRETO)),
        Paragraph(f'<b>DE ACORDO</b><br/><font color="#636366" size="9">OS {os_obj.numero}</font>',
                  ParagraphStyle('rt', fontName='Helvetica-Bold', fontSize=13,
                                 textColor=PRETO, alignment=TA_RIGHT, leading=18)),
    ]]
    ht = Table(hdr, colWidths=['60%','40%'])
    ht.setStyle(TableStyle([
        ('ALIGN',(0,0),(0,0),'LEFT'),('ALIGN',(1,0),(1,0),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(ht)
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph('TERMO DE APROVAÇÃO DE ORDEM DE SERVIÇO', ctr))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=CINZA_200))

    custo = float(os_obj.custo_total or 0)
    nivel = 'Diretoria (≥ R$ 1.000)' if custo >= LIMITE_APROVACAO else 'Gestor de Frotas'

    story.append(Paragraph('Dados da OS', h2))
    story.append(_tbl([
        ['Número',         os_obj.numero or '—'],
        ['Veículo',        f'{os_obj.veiculo.placa} — {os_obj.veiculo.descricao or os_obj.veiculo.modelo or ""}' if os_obj.veiculo else '—'],
        ['Tipo',           f'{(os_obj.tipo_manutencao or "").capitalize()} — {os_obj.tipo_os or ""}'],
        ['Data abertura',  _fmt_date(os_obj.data_abertura)],
        ['Data conclusão', _fmt_date(os_obj.data_conclusao)],
        ['Fornecedor',     os_obj.fornecedor.razao_social if os_obj.fornecedor else 'Interno'],
        ['Aprovação por',  nivel],
    ], ['35%','65%']))

    if os_obj.descricao_problema:
        story.append(Paragraph('Descrição', h2))
        story.append(Paragraph(os_obj.descricao_problema, body))

    if os_obj.itens_servico or os_obj.itens_material:
        story.append(Paragraph('Itens', h2))
        rows = [['Descrição','Qtd','Valor Unit.','Total']]
        for i in os_obj.itens_servico:
            rows.append([i.descricao_display, str(i.quantidade),
                         _brl(i.valor_unitario), _brl(i.valor_total)])
        for i in os_obj.itens_material:
            rows.append([i.descricao_display, str(i.quantidade),
                         _brl(i.valor_unitario), _brl(i.valor_total)])
        it = Table(rows, colWidths=['50%','12%','19%','19%'])
        it.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),PRETO),('TEXTCOLOR',(0,0),(-1,0),BRANCO),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[BRANCO, CINZA_50]),
            ('ALIGN',(1,0),(3,-1),'RIGHT'),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('GRID',(0,0),(-1,-1),0.3,CINZA_200),
        ]))
        story.append(it)

    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width='100%', thickness=2, color=LARANJA))
    story.append(Spacer(1, 0.2*cm))
    tot = Table([['CUSTO TOTAL', _brl(custo)]], colWidths=['70%','30%'])
    tot.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PRETO),
        ('TEXTCOLOR',(0,0),(0,0),BRANCO),('TEXTCOLOR',(1,0),(1,0),LARANJA),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),13),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
        ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),
    ]))
    story.append(tot)

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph('Aprovação', h2))
    nome_ap = (aprovador_user.nome if aprovador_user else nome_aprovador) or '—'
    email_ap= aprovador_user.email if aprovador_user else '(via e-mail)'
    if os_obj.aprovacao_status == 'aprovada':
        story.append(_tbl([
            ['Status',       'APROVADA ✓'],
            ['Aprovado por', nome_ap],
            ['E-mail',       email_ap],
            ['Data/Hora',    os_obj.aprovado_em.strftime('%d/%m/%Y %H:%M') if os_obj.aprovado_em else '—'],
        ] + ([['Observações', os_obj.aprovacao_obs]] if os_obj.aprovacao_obs else []),
        ['35%','65%']))
    else:
        story.append(Paragraph('Aguardando assinatura:', body))
        story.append(Spacer(1, 2*cm))
        sig = Table([[
            Table([['_'*36],['Nome / Cargo'],['Data: ____/____/______']], colWidths=['100%']),
            Table([['_'*36],['Assinatura'],[' ']], colWidths=['100%']),
        ]], colWidths=['50%','50%'])
        sig.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),9),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'TOP'),
        ]))
        story.append(sig)

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=CINZA_200))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f'Gerado em {datetime.utcnow().strftime("%d/%m/%Y %H:%M")} UTC · '
        f'Empresa Exemplo · CNPJ 00.000.000/0001-00 · seu-app.onrender.com', small))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def _enviar_pdf_aprovacao(os_obj, nome_ap: str, email_ap: str,
                          pdf_bytes: bytes, dest: list = None) -> bool:
    token     = get_graph_token()
    remetente = os.environ.get('EMAIL_REMETENTE', 'TI@empresaexemplo.com.br')
    if not token:
        logger.warning('Envio PDF: token Graph não obtido.')
        return False
    custo = float(os_obj.custo_total or 0)
    if dest is None:
        dest = list({email_ap, APROVADORES['diretoria']} - {''})
    payload = {
        'message': {
            'subject': f'[Frota] De Acordo — OS {os_obj.numero} · {_brl(custo)} — APROVADA ✓',
            'body': {
                'contentType': 'HTML',
                'content': (
                    f'<p style="font-family:system-ui;font-size:15px;">'
                    f'OS <strong>{os_obj.numero}</strong> aprovada por <strong>{nome_ap}</strong>.<br>'
                    f'Veículo: <strong>{os_obj.veiculo.placa if os_obj.veiculo else "—"}</strong><br>'
                    f'Custo: <strong style="color:#F7931E;">{_brl(custo)}</strong><br>'
                    f'Segue o PDF De Acordo em anexo.</p>'
                ),
            },
            'toRecipients': [{'emailAddress': {'address': d}} for d in dest if d],
            'attachments': [{
                '@odata.type':  '#microsoft.graph.fileAttachment',
                'name':         f'DeAcordo_OS_{os_obj.numero}.pdf',
                'contentType':  'application/pdf',
                'contentBytes': base64.b64encode(pdf_bytes).decode(),
            }],
        },
        'saveToSentItems': 'true',
    }
    resp = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{remetente}/sendMail',
        json=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=20,
    )
    if resp.status_code == 202:
        return True
    logger.error(f'PDF e-mail {resp.status_code}: {resp.text[:200]}')
    return False


def notificar_conclusao(os_obj) -> bool:
    """
    Chamado quando uma OS é marcada como concluída.
    Notifica o aprovador da OS + a diretoria com e-mail informando a conclusão,
    incluindo o PDF De Acordo em anexo.

    Destinatários:
      - Quem aprovou a OS (os_obj.aprovador.email, se existir)
      - Diretoria (sempre como cópia)
      - Criador da OS (se diferente dos anteriores)
    """
    custo = float(os_obj.custo_total or 0)

    # Monta lista de destinatários
    dest_set = set()
    dest_set.add(APROVADORES['diretoria'])

    if os_obj.aprovador and os_obj.aprovador.email:
        dest_set.add(os_obj.aprovador.email)

    if os_obj.criador and os_obj.criador.email:
        dest_set.add(os_obj.criador.email)

    dest = [e for e in dest_set if e]
    if not dest:
        logger.warning(f'notificar_conclusao: sem destinatários para OS {os_obj.numero}')
        return False

    # Gera PDF De Acordo
    try:
        pdf_bytes = gerar_pdf_de_acordo(os_obj, os_obj.aprovador)
    except Exception as e:
        logger.error(f'notificar_conclusao: erro ao gerar PDF OS {os_obj.numero}: {e}')
        pdf_bytes = None

    veiculo_txt = ''
    if os_obj.veiculo:
        veiculo_txt = f'{os_obj.veiculo.placa} — {os_obj.veiculo.descricao or os_obj.veiculo.modelo or ""}'

    aprovador_nome = '—'
    if os_obj.aprovador:
        aprovador_nome = os_obj.aprovador.nome
    elif os_obj.aprovacao_obs:
        aprovador_nome = 'Via e-mail'

    baixador_nome = os_obj.baixador.nome if os_obj.baixador else '—'
    link_os = f'{BASE_URL}/os/{os_obj.id}'

    corpo = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;background:#F2F2F7;margin:0;padding:32px 16px;">
<table width="600" align="center" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
<tr><td style="background:#30D158;padding:24px 32px;">
  <div style="font-size:22px;font-weight:700;color:#fff;">✅ OS Concluída</div>
  <div style="font-size:13px;color:rgba(255,255,255,.9);margin-top:4px;">
    OS <strong>{os_obj.numero}</strong> foi finalizada e encaminhada ao Financeiro
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
      <td style="color:#636366;font-weight:600;">Aprovada por</td>
      <td>{aprovador_nome}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Concluída por</td>
      <td>{baixador_nome}</td>
    </tr>
    <tr>
      <td style="color:#636366;font-weight:600;">Data conclusão</td>
      <td>{_fmt_date(os_obj.data_conclusao)}</td>
    </tr>
  </table>

  <!-- CUSTO DESTAQUE -->
  <div style="background:#1C1C1E;border-radius:12px;padding:18px 24px;
              display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
    <span style="color:#fff;font-size:14px;font-weight:600;">CUSTO TOTAL DA OS</span>
    <span style="color:#F7931E;font-size:26px;font-weight:700;font-family:monospace;">
      {_brl(custo)}
    </span>
  </div>

  <div style="background:#E8F9EE;border:1px solid #B7EDD0;border-radius:8px;
              padding:12px 16px;font-size:13px;color:#1a6e35;margin-bottom:20px;">
    <strong>📋 Próximos passos:</strong><br>
    O PDF De Acordo está em anexo. O Financeiro já foi notificado separadamente
    com todos os documentos para processamento do pagamento.
  </div>

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

    # Envia via Microsoft Graph com PDF em anexo
    token     = get_graph_token()
    remetente = os.environ.get('EMAIL_REMETENTE', 'TI@empresaexemplo.com.br')
    if not token:
        logger.error(f'notificar_conclusao: token Graph não obtido para OS {os_obj.numero}')
        return False

    attachments = []
    if pdf_bytes:
        attachments.append({
            '@odata.type':  '#microsoft.graph.fileAttachment',
            'name':         f'DeAcordo_OS_{os_obj.numero}.pdf',
            'contentType':  'application/pdf',
            'contentBytes': base64.b64encode(pdf_bytes).decode(),
        })

    payload = {
        'message': {
            'subject': f'[Frota] OS Concluída — {os_obj.numero} · {_brl(custo)} · {veiculo_txt}',
            'body': {'contentType': 'HTML', 'content': corpo},
            'toRecipients': [{'emailAddress': {'address': d}} for d in dest if d],
            'attachments': attachments,
        },
        'saveToSentItems': 'true',
    }

    resp = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{remetente}/sendMail',
        json=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=20,
    )
    if resp.status_code == 202:
        logger.info(f'notificar_conclusao: e-mail enviado → {dest} (OS {os_obj.numero})')
        return True
    logger.error(f'notificar_conclusao: Graph {resp.status_code}: {resp.text[:200]}')
    return False


def _enviar_email(dest: list, assunto: str, corpo: str) -> bool:
    token     = get_graph_token()
    remetente = os.environ.get('EMAIL_REMETENTE', 'TI@empresaexemplo.com.br')
    if not token:
        logger.error('E-mail cancelado: token Graph não obtido.')
        return False
    resp = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{remetente}/sendMail',
        json={
            'message': {
                'subject': assunto,
                'body': {'contentType': 'HTML', 'content': corpo},
                'toRecipients': [{'emailAddress': {'address': d}} for d in dest if d],
            },
            'saveToSentItems': 'true',
        },
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=15,
    )
    if resp.status_code == 202:
        return True
    logger.error(f'Graph sendMail {resp.status_code}: {resp.text[:300]}')
    return False
