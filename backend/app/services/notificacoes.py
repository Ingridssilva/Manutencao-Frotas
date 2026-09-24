"""
Notificações por e-mail via Microsoft Graph API — Frota Empresa Exemplo
Usa o cliente MSAL singleton para reutilizar cache de token.

IMPORTANTE: executar_todas_notificacoes() NÃO deve ser chamado dentro de
um request HTTP — use o comando CLI `flask enviar-notificacoes` ou um scheduler.
"""
import os
import requests
import logging
from datetime import date, timedelta
from flask import current_app
from app.services.msal_client import get_graph_token
from app.models.usuario import Veiculo, OrdemServico, Motorista, CRLV, Pneu, PneuVeiculo

logger = logging.getLogger(__name__)


def _enviar(destinatarios: list, assunto: str, corpo_html: str) -> bool:
    token     = get_graph_token()
    remetente = os.environ.get('EMAIL_REMETENTE', 'TI@empresaexemplo.com.br')
    if not token:
        logger.error(
            'Notificação NÃO enviada: token Microsoft Graph não obtido. '
            'Verifique AZURE_CLIENT_ID, AZURE_CLIENT_SECRET e AZURE_TENANT_ID. '
            f'Destinatários afetados: {destinatarios} | Assunto: {assunto}'
        )
        return False
    resp = requests.post(
        f'https://graph.microsoft.com/v1.0/users/{remetente}/sendMail',
        json={
            'message': {
                'subject': assunto,
                'body': {'contentType': 'HTML', 'content': corpo_html},
                'toRecipients': [{'emailAddress': {'address': d}} for d in destinatarios],
            },
            'saveToSentItems': 'true',
        },
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=15,
    )
    if resp.status_code == 202:
        logger.info(f'Notificação enviada → {destinatarios} | {assunto}')
        return True
    logger.error(
        f'Graph sendMail falhou {resp.status_code} | '
        f'Remetente: {remetente} | Destinatários: {destinatarios} | '
        f'Resposta: {resp.text[:300]}'
    )
    return False


def _html(titulo: str, subtitulo: str, itens: list, cor: str = '#F7931E') -> str:
    cores_bg  = {'vermelho': '#FFE5E5', 'laranja': '#FFF3E0', 'verde': '#E8F5E9'}
    cores_brd = {'vermelho': '#C62828', 'laranja': '#E65100', 'verde': '#2E7D32'}
    linhas = ''.join(
        f'<tr><td style="padding:12px 16px;border-left:4px solid {cores_brd.get(i.get("nivel","laranja"),"#E65100")};'
        f'background:{cores_bg.get(i.get("nivel","laranja"),"#FFF3E0")};border-radius:0 6px 6px 0;">'
        f'<div style="font-weight:600;font-size:14px;">{i["titulo"]}</div>'
        f'<div style="font-size:13px;color:#636366;margin-top:4px;">{i["desc"]}</div>'
        f'</td></tr><tr><td style="height:8px;"></td></tr>'
        for i in itens
    )
    return (
        f'<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F2F2F7;font-family:system-ui,sans-serif;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">'
        f'<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0"'
        f' style="background:#fff;border-radius:16px;overflow:hidden;">'
        f'<tr><td style="background:{cor};padding:24px 32px;">'
        f'<div style="font-size:22px;font-weight:700;color:#fff;">{titulo}</div>'
        f'<div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:6px;">{subtitulo}</div>'
        f'</td></tr>'
        f'<tr><td style="padding:24px 32px;"><table width="100%">{linhas}</table></td></tr>'
        f'<tr><td style="padding:16px 32px 24px;border-top:1px solid #E5E5EA;">'
        f'<div style="font-size:12px;color:#8E8E93;">Sistema de Frota — Empresa Exemplo · '
        f'<a href="https://seu-app.onrender.com" style="color:{cor};">seu-app.onrender.com</a></div>'
        f'</td></tr></table></td></tr></table></body></html>'
    )


def _gestores() -> list:
    from app.models.usuario import Usuario, PerfilAcesso

    # Gestores fixos sempre incluídos (configurável via env EMAILS_GESTORES_FIXOS,
    # separados por vírgula, ou usa os padrões abaixo)
    _fixos_env = os.environ.get('EMAILS_GESTORES_FIXOS', '')
    if _fixos_env:
        fixos = {e.strip().lower() for e in _fixos_env.split(',') if e.strip()}
    else:
        fixos = {
            'ti@empresaexemplo.com.br',
            'gestor2@empresaexemplo.com.br',
            'admin2@empresaexemplo.com.br',
        }

    # Completa com quem estiver no banco com perfil admin/gestor
    try:
        usuarios = (Usuario.query.join(PerfilAcesso)
                    .filter(Usuario.ativo == True)
                    .filter(PerfilAcesso.nome.in_(['admin', 'gestor'])).all())
        db_emails = {u.email.lower() for u in usuarios if u.email and '@' in u.email}
    except Exception:
        db_emails = set()

    todos = fixos | db_emails

    if not todos:
        fb = os.environ.get('EMAIL_NOTIFICACAO_FALLBACK', '')
        if fb:
            todos = {fb}

    if not todos:
        logger.warning('_gestores: nenhum destinatário encontrado para notificações.')

    return sorted(todos)


def notificar_crlv_vencendo(dias: int = 30) -> int:
    hoje  = date.today()
    crlvs = (CRLV.query.join(Veiculo)
              .filter(Veiculo.status != 'inativo')
              .filter(CRLV.data_vencimento <= hoje + timedelta(days=dias))
              .filter(CRLV.data_vencimento >= hoje)
              .order_by(CRLV.data_vencimento).all())
    if not crlvs:
        return 0
    itens = [{'titulo': f'{c.veiculo.placa} — CRLV {c.exercicio}',
               'desc':  f'Vence em {c.data_vencimento.strftime("%d/%m/%Y")} ({(c.data_vencimento-hoje).days} dias)',
               'nivel': 'vermelho' if (c.data_vencimento-hoje).days <= 10 else 'laranja'}
             for c in crlvs]
    dest = _gestores()
    if not dest:
        logger.warning('CRLV: sem destinatários.')
        return 0
    ok = _enviar(dest, f'[Frota] {len(crlvs)} CRLV(s) vencendo',
                 _html('⚠ CRLVs Vencendo',
                       f'{len(crlvs)} documento(s) vencendo nos próximos {dias} dias',
                       itens, '#E65100'))
    return len(crlvs) if ok else 0


def notificar_cnh_vencendo(dias: int = 60) -> int:
    hoje = date.today()
    mots = (Motorista.query.filter_by(ativo=True)
            .filter(Motorista.cnh_validade.isnot(None))
            .filter(Motorista.cnh_validade <= hoje + timedelta(days=dias))
            .filter(Motorista.cnh_validade >= hoje)
            .order_by(Motorista.cnh_validade).all())
    if not mots:
        return 0
    itens = [{'titulo': m.nome,
               'desc':  f'CNH {m.cnh_categoria or ""} · Vence em {m.cnh_validade.strftime("%d/%m/%Y")} ({(m.cnh_validade-hoje).days} dias)',
               'nivel': 'vermelho' if (m.cnh_validade-hoje).days <= 15 else 'laranja'}
             for m in mots]
    dest = _gestores()
    if not dest:
        return 0
    ok = _enviar(dest, f'[Frota] {len(mots)} CNH(s) vencendo',
                 _html('⚠ CNHs Vencendo', f'{len(mots)} motorista(s) com CNH vencendo', itens, '#C62828'))
    return len(mots) if ok else 0


def notificar_os_paradas(dias: int = 3) -> int:
    """
    Envia alertas de OS paradas.
    Roda diariamente — notifica nos marcos de 3, 7 e 15 dias.
    No dia exato do marco envia alerta com nível crescente de urgência.
    """
    hoje = date.today()
    marcos = [
        (3,  'laranja',  '⏰ OS Paradas — Atenção'),
        (7,  'laranja',  '⚠ OS Paradas — Urgente'),
        (15, 'vermelho', '🔴 OS Paradas — Crítico'),
    ]
    total_enviadas = 0
    dest = _gestores()
    if not dest:
        logger.warning('notificar_os_paradas: sem destinatários.')
        return 0

    for marco, nivel_default, titulo in marcos:
        # OS que completam EXATAMENTE o marco de dias hoje
        data_limite = hoje - timedelta(days=marco)
        os_marco = (OrdemServico.query
            .filter(OrdemServico.status.in_(['aberta', 'em_execucao', 'aguardando_peca']))
            .filter(OrdemServico.data_abertura == data_limite)
            .order_by(OrdemServico.data_abertura).all())

        if not os_marco:
            continue

        itens = []
        for o in os_marco:
            dias_aberta = (hoje - o.data_abertura).days
            nivel = 'vermelho' if dias_aberta >= 15 else 'laranja' if dias_aberta >= 7 else nivel_default
            status_label = {'aberta': 'Aberta', 'em_execucao': 'Em execução',
                            'aguardando_peca': 'Aguardando peça'}.get(o.status, o.status)
            itens.append({
                'titulo': f'{o.numero} — {o.veiculo.placa if o.veiculo else "?"}',
                'desc':   (
                    f'{status_label} · Aberta em {o.data_abertura.strftime("%d/%m/%Y")} '
                    f'({dias_aberta} dias) · '
                    f'{o.tipo_manutencao.capitalize() if o.tipo_manutencao else ""}'
                    + (f' · {o.descricao_problema[:60]}' if o.descricao_problema else '')
                ),
                'nivel': nivel,
            })

        cor = '#C62828' if marco >= 15 else '#E65100' if marco >= 7 else '#1565C0'
        subtitulo = (
            f'{len(os_marco)} OS completou {marco} dias sem conclusão hoje — '
            f'{"AÇÃO IMEDIATA NECESSÁRIA" if marco >= 15 else "verificar urgente" if marco >= 7 else "verificar"}'
        )
        ok = _enviar(
            dest,
            f'[Frota] OS parada há {marco} dias — {len(os_marco)} veículo(s)',
            _html(titulo, subtitulo, itens, cor),
        )
        if ok:
            total_enviadas += len(os_marco)
            logger.info(f'Alerta OS paradas {marco}d enviado → {dest} ({len(os_marco)} OS)')

    return total_enviadas


def notificar_pneus_desgaste(pct: int = 80) -> int:
    alert = []
    if Pneu.query.filter_by(status='ativo').limit(1).first():
        for p in (Pneu.query.filter_by(status='ativo')
                  .join(PneuVeiculo, (PneuVeiculo.pneu_id == Pneu.id) & (PneuVeiculo.ativo == True))
                  .all()):
            if p.pct_vida >= pct:
                alert.append(p)
    if not alert:
        return 0
    itens = []
    for p in sorted(alert, key=lambda x: x.pct_vida, reverse=True):
        pos = p.posicao_atual
        vei = f'{pos.veiculo.placa} — {pos.posicao_display}' if pos and pos.veiculo else 'Desmontado'
        itens.append({'titulo': f'{p.nome_display} — {p.pct_vida}% desgaste',
                      'desc':   f'{vei} · {p.km_rodado:,} de {p.km_limite or 0:,} km'.replace(',', '.'),
                      'nivel':  'vermelho' if p.pct_vida >= 95 else 'laranja'})
    dest = _gestores()
    if not dest:
        return 0
    ok = _enviar(dest, f'[Frota] {len(alert)} pneu(s) com desgaste elevado',
                 _html('🔴 Pneus com Desgaste Elevado',
                       f'{len(alert)} pneu(s) com mais de {pct}% de vida consumida',
                       itens, '#B71C1C'))
    return len(alert) if ok else 0


def executar_todas_notificacoes() -> dict:
    """
    Executa todas as verificações e envia e-mails.
    DEVE ser chamado via CLI `flask enviar-notificacoes` ou scheduler.
    NÃO chamar dentro de um request HTTP — bloqueia o servidor.
    """
    resultado = {
        'crlv':  notificar_crlv_vencendo(30),
        'cnh':   notificar_cnh_vencendo(60),
        'os_3d': notificar_os_paradas(3),
        'os_7d': notificar_os_paradas(7),
        'os_15d':notificar_os_paradas(15),
        'pneus': notificar_pneus_desgaste(80),
    }
    logger.info(f'Notificações enviadas: {resultado}')
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
#  RESERVAS DE VEÍCULO
# ─────────────────────────────────────────────────────────────────────────────

def _html_reserva_simples(titulo: str, subtitulo: str, corpo_html: str, cor: str = '#F7931E') -> str:
    """HTML de e-mail limpo para notificações de reserva."""
    return (
        f'<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F2F2F7;font-family:system-ui,sans-serif;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">'
        f'<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0"'
        f' style="background:#fff;border-radius:16px;overflow:hidden;">'
        f'<tr><td style="background:{cor};padding:24px 32px;">'
        f'<div style="font-size:22px;font-weight:700;color:#fff;">{titulo}</div>'
        f'<div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:6px;">{subtitulo}</div>'
        f'</td></tr>'
        f'<tr><td style="padding:28px 32px;">{corpo_html}</td></tr>'
        f'<tr><td style="padding:16px 32px 24px;border-top:1px solid #E5E5EA;">'
        f'<div style="font-size:12px;color:#8E8E93;">Sistema de Frota — Empresa Exemplo · '
        f'<a href="https://seu-app.onrender.com" style="color:{cor};">seu-app.onrender.com</a></div>'
        f'</td></tr></table></td></tr></table></body></html>'
    )


def _linha(label: str, valor: str) -> str:
    return (
        f'<tr>'
        f'<td style="padding:8px 0;font-size:13px;font-weight:600;color:#636366;width:140px;">{label}</td>'
        f'<td style="padding:8px 0;font-size:13px;color:#1C1C1E;">{valor}</td>'
        f'</tr>'
    )


def _gestores_reserva() -> list:
    """
    Destinatários para notificações de reserva de veículo.
    Rafael e Pedro não recebem emails de reserva — apenas o time operacional.
    """
    EXCLUIR = {
        'owner@empresaexemplo.com.br',
        'gestor1@empresaexemplo.com.br',
    }
    todos = _gestores()
    filtrados = [e for e in todos if e.lower() not in EXCLUIR]
    return filtrados if filtrados else todos  # fallback: se remover todos, mantém lista original


def notificar_nova_reserva(reserva) -> bool:
    """
    Avisa os gestores internos que uma nova reserva foi solicitada.
    Chamado logo após salvar a reserva no banco.
    Rafael e Pedro não recebem este email.
    """
    dest = _gestores_reserva()
    if not dest:
        logger.warning('notificar_nova_reserva: sem destinatários gestores.')
        return False

    veiculo_str = (
        f'{reserva.veiculo.placa} — {reserva.veiculo.descricao or reserva.veiculo.modelo or ""}'
        if reserva.veiculo else 'A definir pela equipe'
    )

    linhas = ''.join([
        _linha('👤 Solicitante', reserva.nome_solicitante),
        _linha('🏢 Setor / Obra', reserva.setor_solicitante or '—'),
        _linha('📞 Contato', reserva.contato or '—'),
        _linha('📅 Saída', reserva.data_inicio.strftime('%d/%m/%Y')),
        _linha('🔙 Retorno', reserva.data_fim.strftime('%d/%m/%Y')),
        _linha('📍 Destino', reserva.destino),
        _linha('👥 Passageiros', str(reserva.n_passageiros or 1)),
        _linha('🚗 Veículo pref.', reserva.tipo_veiculo_pref or '—'),
        _linha('🚘 Veículo solicitado', veiculo_str),
    ])

    finalidade_bloco = ''
    if reserva.finalidade:
        finalidade_bloco = (
            f'<div style="margin-top:16px;padding:14px 16px;background:#F2F2F7;border-radius:10px;'
            f'font-size:13px;color:#1C1C1E;line-height:1.6;">'
            f'<strong>📝 Finalidade:</strong><br>{reserva.finalidade}</div>'
        )

    corpo = (
        f'<table width="100%" cellpadding="0" cellspacing="0">{linhas}</table>'
        f'{finalidade_bloco}'
        f'<div style="margin-top:24px;">'
        f'<a href="https://seu-app.onrender.com/disponibilidade/reservas?status=pendente" '
        f'style="display:inline-block;background:#F7931E;color:#000;font-weight:700;font-size:13px;'
        f'padding:12px 24px;border-radius:10px;text-decoration:none;">Ver e Aprovar Reserva →</a>'
        f'</div>'
    )

    html = _html_reserva_simples(
        '🚗 Nova Solicitação de Reserva',
        f'Reserva #{reserva.id} — {reserva.nome_solicitante} · {reserva.data_inicio.strftime("%d/%m")} a {reserva.data_fim.strftime("%d/%m/%Y")}',
        corpo,
        '#F7931E',
    )

    ok = _enviar(dest, f'[Frota] Nova reserva de veículo — {reserva.nome_solicitante}', html)
    if ok:
        logger.info(f'notificar_nova_reserva #{reserva.id} enviado → {dest}')
    return ok


def notificar_reserva_aprovada(reserva) -> bool:
    """
    Avisa o solicitante que a reserva foi aprovada.
    Só envia se o campo `contato` contiver um e-mail válido.
    """
    email_dest = _extrair_email(reserva.contato)
    if not email_dest:
        logger.info(f'notificar_reserva_aprovada #{reserva.id}: contato não é e-mail, pulando.')
        return False

    veiculo_str = (
        f'{reserva.veiculo.placa} — {reserva.veiculo.descricao or reserva.veiculo.modelo or ""}'
        if reserva.veiculo else 'A ser definido — aguarde contato da equipe'
    )

    linhas = ''.join([
        _linha('📅 Saída', reserva.data_inicio.strftime('%d/%m/%Y')),
        _linha('🔙 Retorno', reserva.data_fim.strftime('%d/%m/%Y')),
        _linha('📍 Destino', reserva.destino),
        _linha('🚘 Veículo', veiculo_str),
    ])

    obs_bloco = ''
    if reserva.obs_admin:
        obs_bloco = (
            f'<div style="margin-top:16px;padding:14px 16px;background:#E8F5E9;border-radius:10px;'
            f'border-left:4px solid #2E7D32;font-size:13px;color:#1C1C1E;line-height:1.6;">'
            f'<strong>💬 Observação da equipe:</strong><br>{reserva.obs_admin}</div>'
        )

    corpo = (
        f'<p style="font-size:15px;color:#1C1C1E;margin:0 0 20px;">Olá, <strong>{reserva.nome_solicitante}</strong>!</p>'
        f'<p style="font-size:14px;color:#1C1C1E;margin:0 0 20px;">Sua solicitação de reserva de veículo foi <strong style="color:#2E7D32;">✅ aprovada</strong>.</p>'
        f'<table width="100%" cellpadding="0" cellspacing="0">{linhas}</table>'
        f'{obs_bloco}'
        f'<p style="margin-top:20px;font-size:13px;color:#636366;">Em caso de dúvidas, entre em contato com a equipe de frota.</p>'
    )

    html = _html_reserva_simples(
        '✅ Reserva Aprovada',
        f'Reserva #{reserva.id} — {reserva.data_inicio.strftime("%d/%m")} a {reserva.data_fim.strftime("%d/%m/%Y")}',
        corpo,
        '#2E7D32',
    )

    ok = _enviar([email_dest], f'[Frota Empresa Exemplo] Sua reserva foi aprovada — {reserva.data_inicio.strftime("%d/%m/%Y")}', html)
    if ok:
        logger.info(f'notificar_reserva_aprovada #{reserva.id} → {email_dest}')
    return ok


def notificar_reserva_rejeitada(reserva) -> bool:
    """
    Avisa o solicitante que a reserva foi rejeitada.
    Só envia se o campo `contato` contiver um e-mail válido.
    """
    email_dest = _extrair_email(reserva.contato)
    if not email_dest:
        logger.info(f'notificar_reserva_rejeitada #{reserva.id}: contato não é e-mail, pulando.')
        return False

    obs_bloco = ''
    if reserva.obs_admin:
        obs_bloco = (
            f'<div style="margin-top:16px;padding:14px 16px;background:#FFE5E5;border-radius:10px;'
            f'border-left:4px solid #C62828;font-size:13px;color:#1C1C1E;line-height:1.6;">'
            f'<strong>💬 Motivo:</strong><br>{reserva.obs_admin}</div>'
        )

    corpo = (
        f'<p style="font-size:15px;color:#1C1C1E;margin:0 0 20px;">Olá, <strong>{reserva.nome_solicitante}</strong>!</p>'
        f'<p style="font-size:14px;color:#1C1C1E;margin:0 0 20px;">Infelizmente sua solicitação de reserva de veículo '
        f'(<strong>{reserva.data_inicio.strftime("%d/%m/%Y")}</strong> a <strong>{reserva.data_fim.strftime("%d/%m/%Y")}</strong> — {reserva.destino}) '
        f'foi <strong style="color:#C62828;">❌ não aprovada</strong>.</p>'
        f'{obs_bloco}'
        f'<p style="margin-top:20px;font-size:13px;color:#636366;">Para mais informações, entre em contato com a equipe de frota.</p>'
    )

    html = _html_reserva_simples(
        '❌ Reserva Não Aprovada',
        f'Reserva #{reserva.id} — {reserva.data_inicio.strftime("%d/%m")} a {reserva.data_fim.strftime("%d/%m/%Y")}',
        corpo,
        '#C62828',
    )

    ok = _enviar([email_dest], f'[Frota Empresa Exemplo] Atualização sobre sua solicitação de veículo', html)
    if ok:
        logger.info(f'notificar_reserva_rejeitada #{reserva.id} → {email_dest}')
    return ok


def _extrair_email(contato: str) -> str | None:
    """Retorna o e-mail encontrado na string de contato, ou None."""
    if not contato:
        return None
    import re
    m = re.search(r'[\w.\-+]+@[\w.\-]+\.\w{2,}', contato.strip())
    return m.group(0).lower() if m else None
