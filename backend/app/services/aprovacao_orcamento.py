"""
Serviço de aprovação de Orçamentos — Frota Empresa Exemplo

Regra de negócio (igual à OS):
  valor >= R$ 1.000 → Diretoria (owner@empresaexemplo.com.br)
  valor <  R$ 1.000 → Gestor de Frotas

Fluxo:
  1. Orçamento em rascunho → solicitar() → e-mail com botões Aprovar/Rejeitar
  2. Aprovador clica no e-mail → /orcamentos/aprovar/<token> → sem precisar logar
  3. Sistema registra aprovação e redireciona para o detalhe
"""
import os
import secrets
import logging
import requests
from datetime import datetime, timedelta
from flask import url_for
from app.services.msal_client import get_graph_token

logger = logging.getLogger(__name__)

LIMITE_APROVACAO = float(os.environ.get('OS_LIMITE_APROVACAO', '1000'))
BASE_URL = os.environ.get('BASE_URL', 'https://seu-app.onrender.com')

APROVADORES = {
    'diretoria': 'owner@empresaexemplo.com.br',
    'gestor1':   'gestor1@empresaexemplo.com.br',
    'gestor2':   'gestor2@empresaexemplo.com.br',
}

# TI recebe cópia obrigatória em todos os e-mails de aprovação de orçamento
EMAIL_COPIA_TI = os.environ.get('EMAIL_COPIA_TI', 'TI@empresaexemplo.com.br')


def _brl(v) -> str:
    try:
        return f'R$ {float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return 'R$ 0,00'


def aprovadores_para_orc(valor: float) -> list:
    if valor >= LIMITE_APROVACAO:
        return [APROVADORES['diretoria']]
    return [APROVADORES['gestor1']]


def _gerar_token(orc) -> str:
    from app import db
    token = secrets.token_urlsafe(48)
    orc.aprovacao_token     = token
    orc.aprovacao_token_exp = datetime.utcnow() + timedelta(days=7)
    db.session.commit()
    return token


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


def solicitar_aprovacao(orc) -> bool:
    """
    Envia e-mail aos aprovadores corretos com botões Aprovar/Rejeitar inline.
    """
    valor         = float(orc.valor_total_estimado or 0)
    destinatarios = aprovadores_para_orc(valor)
    # TI sempre recebe cópia quando a diretoria for a aprovadora
    if APROVADORES['diretoria'] in destinatarios and EMAIL_COPIA_TI not in destinatarios:
        destinatarios = list(destinatarios) + [EMAIL_COPIA_TI]
    nivel_txt     = ('Diretoria (acima de R$ 1.000)'
                     if valor >= LIMITE_APROVACAO else 'Gestor de Frotas')

    token        = _gerar_token(orc)
    link_aprovar = f'{BASE_URL}/orcamentos/aprovar/{token}'
    link_rejeitar= f'{BASE_URL}/orcamentos/rejeitar/{token}'
    link_sistema = f'{BASE_URL}/orcamentos/{orc.id}'

    veiculo_txt = ''
    if orc.veiculo:
        veiculo_txt = f'{orc.veiculo.placa} — {orc.veiculo.descricao or orc.veiculo.modelo or ""}'

    # Tabela de itens
    itens_html = ''
    for i in orc.itens:
        nome = ''
        if i.tipo_item == 'servico':
            nome = i.servico.nome if i.servico else (i.descricao_livre or '—')
        else:
            nome = i.material.nome if i.material else (i.descricao_livre or '—')
        total = float(i.quantidade or 1) * float(i.valor_unitario or 0)
        itens_html += (
            f'<tr>'
            f'<td style="padding:5px 0;font-size:13px;">{nome}</td>'
            f'<td style="text-align:right;padding:5px 8px;font-size:13px;color:#636366;">{float(i.quantidade):.0f}x</td>'
            f'<td style="text-align:right;padding:5px 0;font-size:13px;">{_brl(total)}</td>'
            f'</tr>'
        )

    solicitante_nome = orc.solicitante.nome if orc.solicitante else '—'
    fornecedor_nome  = orc.fornecedor.razao_social if orc.fornecedor else '—'

    corpo = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;background:#F2F2F7;margin:0;padding:32px 16px;">
<table width="600" align="center" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
<tr><td style="background:#F7931E;padding:24px 32px;">
  <div style="font-size:22px;font-weight:700;color:#fff;">🔔 Autorização — ORC {orc.numero}</div>
  <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:6px;">Nível: {nivel_txt}</div>
</td></tr>
<tr><td style="padding:24px 32px 0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="padding:0 0 16px;border-bottom:1px solid #F2F2F7;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-size:12px;color:#636366;font-weight:600;text-transform:uppercase;padding-bottom:4px;">Número</td>
          <td style="font-size:12px;color:#636366;font-weight:600;text-transform:uppercase;padding-bottom:4px;">Veículo</td>
          <td style="font-size:12px;color:#636366;font-weight:600;text-transform:uppercase;padding-bottom:4px;">Tipo OS</td>
        </tr>
        <tr>
          <td style="font-size:15px;font-weight:700;font-family:monospace;">{orc.numero}</td>
          <td style="font-size:15px;font-weight:700;color:#F7931E;">{orc.veiculo.placa if orc.veiculo else '—'}</td>
          <td style="font-size:14px;">{orc.tipo_os}</td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="padding:16px 0;">
      <div style="font-size:12px;color:#636366;font-weight:600;text-transform:uppercase;margin-bottom:6px;">Descrição</div>
      <div style="font-size:14px;">{orc.descricao}</div>
    </td></tr>
    {'<tr><td style="padding:0 0 12px;"><div style="font-size:12px;color:#636366;font-weight:600;text-transform:uppercase;margin-bottom:6px;">Fornecedor</div><div style="font-size:14px;">' + fornecedor_nome + '</div></td></tr>' if orc.fornecedor else ''}
    <tr><td style="padding:0 0 16px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        {itens_html}
        <tr><td colspan="3" style="border-top:1px solid #E5E5EA;padding-top:8px;"></td></tr>
        <tr>
          <td style="font-size:14px;font-weight:700;">VALOR ESTIMADO</td>
          <td colspan="2" style="text-align:right;font-size:22px;font-weight:700;color:#F7931E;">{_brl(valor)}</td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="padding:0 0 8px;font-size:12px;color:#636366;">
      Solicitado por <strong>{solicitante_nome}</strong> em {orc.data_solicitacao.strftime('%d/%m/%Y') if orc.data_solicitacao else '—'}
    </td></tr>
    <tr><td style="padding:24px 0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td width="48%" style="text-align:center;">
            <a href="{link_aprovar}"
               style="display:inline-block;background:#34C759;color:#fff;font-size:16px;font-weight:700;
                      padding:16px 32px;border-radius:12px;text-decoration:none;">
              ✓ Aprovar
            </a>
          </td>
          <td width="4%"></td>
          <td width="48%" style="text-align:center;">
            <a href="{link_rejeitar}"
               style="display:inline-block;background:#FF3B30;color:#fff;font-size:16px;font-weight:700;
                      padding:16px 32px;border-radius:12px;text-decoration:none;">
              ✕ Rejeitar
            </a>
          </td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="padding:0 0 24px;text-align:center;">
      <a href="{link_sistema}" style="font-size:12px;color:#636366;">Ver no sistema</a>
    </td></tr>
  </table>
</td></tr>
<tr><td style="background:#F2F2F7;padding:16px 32px;text-align:center;font-size:11px;color:#8E8E93;">
  Empresa Exemplo · Sistema de Frotas · Este link expira em 7 dias
</td></tr>
</table>
</body></html>"""

    assunto = f'[Frota] Aprovação necessária — ORC {orc.numero} · {_brl(valor)}'
    ok = _enviar_email(destinatarios, assunto, corpo)
    if ok:
        logger.info(f'E-mail aprovação ORC {orc.numero} enviado para {destinatarios}')
    else:
        logger.error(f'Falha ao enviar e-mail aprovação ORC {orc.numero}')
    return ok


def registrar_aprovacao(orc, aprovador_user) -> bool:
    """Registra aprovação feita dentro do sistema (usuário logado) e notifica TI."""
    from app import db
    orc.status         = 'aprovado'
    orc.aprovado_por   = aprovador_user.id
    orc.data_aprovacao = datetime.utcnow()
    orc.aprovacao_token     = None
    orc.aprovacao_token_exp = None
    db.session.commit()

    custo_txt = _brl(orc.valor_total_estimado or 0)
    criador_email = orc.solicitante.email if orc.solicitante else None
    dest = list({APROVADORES['diretoria'], EMAIL_COPIA_TI, *([criador_email] if criador_email else [])})
    corpo = (
        f'<html><body style="font-family:system-ui;padding:24px;">'
        f'<h2 style="color:#34C759;">✓ Orçamento {orc.numero} Aprovado</h2>'
        f'<p><strong>Aprovado por:</strong> {aprovador_user.nome}<br>'
        f'<strong>Veículo:</strong> {orc.veiculo.placa if orc.veiculo else "—"}<br>'
        f'<strong>Valor:</strong> <span style="color:#F7931E;font-size:18px;font-weight:700;">{custo_txt}</span></p>'
        f'<p><a href="{BASE_URL}/orcamentos/{orc.id}" style="color:#F7931E;">Ver orçamento no sistema →</a></p>'
        f'</body></html>'
    )
    _enviar_email(dest, f'[Frota] Orçamento {orc.numero} APROVADO · {custo_txt}', corpo)
    logger.info(f'ORC {orc.numero} aprovado por {aprovador_user.email}')
    return True


def registrar_rejeicao(orc, aprovador_user, motivo: str) -> bool:
    """Registra rejeição feita dentro do sistema (usuário logado) e notifica."""
    from app import db
    orc.status          = 'rejeitado'
    orc.motivo_rejeicao = motivo
    orc.aprovacao_token     = None
    orc.aprovacao_token_exp = None
    db.session.commit()

    custo_txt = _brl(orc.valor_total_estimado or 0)
    criador_email = orc.solicitante.email if orc.solicitante else None
    dest = list({APROVADORES['diretoria'], EMAIL_COPIA_TI, *([criador_email] if criador_email else [])})
    corpo = (
        f'<html><body style="font-family:system-ui;padding:24px;">'
        f'<h2 style="color:#FF3B30;">✕ Orçamento {orc.numero} Rejeitado</h2>'
        f'<p><strong>Rejeitado por:</strong> {aprovador_user.nome}<br>'
        f'<strong>Veículo:</strong> {orc.veiculo.placa if orc.veiculo else "—"}<br>'
        f'<strong>Valor:</strong> {custo_txt}</p>'
        f'<p><strong>Motivo:</strong> {motivo}</p>'
        f'<p><a href="{BASE_URL}/orcamentos/{orc.id}" style="color:#F7931E;">Ver orçamento no sistema →</a></p>'
        f'</body></html>'
    )
    _enviar_email(dest, f'[Frota] Orçamento {orc.numero} REJEITADO', corpo)
    logger.info(f'ORC {orc.numero} rejeitado por {aprovador_user.email}')
    return True


def registrar_aprovacao_token(orc, nome_aprovador: str) -> bool:
    """Registra aprovação via token do e-mail (sem login) e notifica TI."""
    from app import db
    orc.status         = 'aprovado'
    orc.data_aprovacao = datetime.utcnow()
    orc.aprovacao_token     = None
    orc.aprovacao_token_exp = None
    db.session.commit()

    custo_txt = _brl(orc.valor_total_estimado or 0)
    criador_email = orc.solicitante.email if orc.solicitante else None
    dest = list({APROVADORES['diretoria'], EMAIL_COPIA_TI, *([criador_email] if criador_email else [])})
    corpo = (
        f'<html><body style="font-family:system-ui;padding:24px;">'
        f'<h2 style="color:#34C759;">✓ Orçamento {orc.numero} Aprovado</h2>'
        f'<p><strong>Aprovado por:</strong> {nome_aprovador or "Aprovador (via e-mail)"}<br>'
        f'<strong>Veículo:</strong> {orc.veiculo.placa if orc.veiculo else "—"}<br>'
        f'<strong>Valor:</strong> <span style="color:#F7931E;font-size:18px;font-weight:700;">{custo_txt}</span></p>'
        f'<p><a href="{BASE_URL}/orcamentos/{orc.id}" style="color:#F7931E;">Ver orçamento no sistema →</a></p>'
        f'</body></html>'
    )
    _enviar_email(dest, f'[Frota] Orçamento {orc.numero} APROVADO · {custo_txt}', corpo)
    logger.info(f'ORC {orc.numero} aprovado via token por {nome_aprovador}')
    return True


def registrar_rejeicao_token(orc, nome_aprovador: str, motivo: str) -> bool:
    """Registra rejeição via token do e-mail (sem login) e notifica."""
    from app import db
    orc.status          = 'rejeitado'
    orc.motivo_rejeicao = motivo
    orc.aprovacao_token     = None
    orc.aprovacao_token_exp = None
    db.session.commit()

    custo_txt = _brl(orc.valor_total_estimado or 0)
    criador_email = orc.solicitante.email if orc.solicitante else None
    dest = list({APROVADORES['diretoria'], EMAIL_COPIA_TI, *([criador_email] if criador_email else [])})
    corpo = (
        f'<html><body style="font-family:system-ui;padding:24px;">'
        f'<h2 style="color:#FF3B30;">✕ Orçamento {orc.numero} Rejeitado</h2>'
        f'<p><strong>Rejeitado por:</strong> {nome_aprovador or "Aprovador (via e-mail)"}<br>'
        f'<strong>Veículo:</strong> {orc.veiculo.placa if orc.veiculo else "—"}<br>'
        f'<strong>Valor:</strong> {custo_txt}</p>'
        f'<p><strong>Motivo:</strong> {motivo}</p>'
        f'</body></html>'
    )
    _enviar_email(dest, f'[Frota] Orçamento {orc.numero} REJEITADO', corpo)
    logger.info(f'ORC {orc.numero} rejeitado via token por {nome_aprovador}')
    return True
