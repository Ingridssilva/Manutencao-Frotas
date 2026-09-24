"""
Upload de fotos para o SharePoint via Microsoft Graph API — Frota Empresa Exemplo
Usa o cliente MSAL singleton para reutilizar cache de token.
"""
import os
import re
import requests
from datetime import date
from flask import current_app
from app.services.msal_client import get_graph_token

SITE_ID   = os.environ.get('SHAREPOINT_SITE_ID', '')
DRIVE_ID  = os.environ.get('SHAREPOINT_DRIVE_ID', '')
PASTA_RAZ = os.environ.get('SHAREPOINT_PASTA_FROTA', 'Departamento de Frotas/SETOR DE FROTA/SISTEMA DE MANUTENÇÃO')

# ── Whitelist de extensões e MIME types permitidos ───────────────────────────
EXTENSOES_OK = frozenset({'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'pdf'})
MIMES_OK     = frozenset({
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'image/heic', 'image/heif', 'application/pdf',
})


def validar_arquivo(filename: str, mime_type: str = '') -> tuple[bool, str]:
    """Valida extensão e MIME type. Retorna (ok, erro)."""
    if not filename or '.' not in filename:
        return False, 'Nome de arquivo inválido ou sem extensão.'
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in EXTENSOES_OK:
        exts = ', '.join(sorted(EXTENSOES_OK))
        return False, f'Extensão .{ext} não permitida. Use: {exts}'
    if mime_type and mime_type.split(';')[0].strip() not in MIMES_OK:
        return False, f'Tipo de conteúdo não permitido: {mime_type}'
    return True, ''


def _sanitizar_nome(filename: str) -> str:
    """Remove path traversal e caracteres perigosos do nome de arquivo."""
    nome = os.path.basename(filename)           # remove /../../ etc.
    nome = re.sub(r'[^\w.\-]', '_', nome)       # só letras, números, ., -, _
    nome = nome.lstrip('.')                      # não começa com ponto
    return (nome or 'arquivo')[:120]


def upload_foto_os(os_numero: str, veiculo_placa: str,
                   filename: str, content: bytes,
                   mime_type: str = 'application/octet-stream') -> dict:
    """
    Faz upload seguro para o SharePoint.
    Valida extensão/MIME antes de qualquer operação de rede.
    """
    filename = _sanitizar_nome(filename)
    ok, erro = validar_arquivo(filename, mime_type)
    if not ok:
        return {'ok': False, 'erro': erro}

    token = get_graph_token()
    if not token:
        return {'ok': False, 'erro': 'Token Graph não obtido. Verifique credenciais Azure.'}

    mes_pasta  = date.today().strftime('%Y-%m')
    os_safe    = re.sub(r'[^\w\-]', '_', os_numero or 'OS')
    placa_safe = re.sub(r'[^\w]',   '_', veiculo_placa or 'VEICULO')
    caminho    = f'{PASTA_RAZ}/{mes_pasta}/{os_safe}_{placa_safe}/{filename}'

    if DRIVE_ID:
        url = f'https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{caminho}:/content'
    elif SITE_ID:
        url = f'https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:/{caminho}:/content'
    else:
        url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{caminho}:/content'

    resp = requests.put(
        url, data=content,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': mime_type},
        timeout=30,
    )

    if resp.status_code in (200, 201):
        data    = resp.json()
        web_url = data.get('webUrl', '')
        share   = _share_link(token, data.get('id', ''))
        return {'ok': True, 'url': share or web_url, 'nome': filename, 'id': data.get('id', '')}

    current_app.logger.error(
        f'SharePoint upload falhou {resp.status_code}: {resp.text[:300]}'
    )
    return {'ok': False, 'erro': f'Erro {resp.status_code} ao enviar para SharePoint.'}


def upload_documento_motorista(motorista_nome: str, tipo: str,
                                filename: str, content: bytes,
                                mime_type: str = 'application/octet-stream') -> dict:
    """
    Faz upload seguro de um documento do motorista (CNH, termos, etc.) para o SharePoint.
    Mesma validação de extensão/MIME e sanitização de nome do upload de fotos de OS.
    """
    filename = _sanitizar_nome(filename)
    ok, erro = validar_arquivo(filename, mime_type)
    if not ok:
        return {'ok': False, 'erro': erro}

    token = get_graph_token()
    if not token:
        return {'ok': False, 'erro': 'Token Graph não obtido. Verifique credenciais Azure.'}

    nome_safe = re.sub(r'[^\w\-]', '_', motorista_nome or 'MOTORISTA')[:60]
    tipo_safe = re.sub(r'[^\w\-]', '_', tipo or 'documento')
    caminho   = f'{PASTA_RAZ}/Motoristas/{nome_safe}/{tipo_safe}_{filename}'

    if DRIVE_ID:
        url = f'https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{caminho}:/content'
    elif SITE_ID:
        url = f'https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/root:/{caminho}:/content'
    else:
        url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{caminho}:/content'

    resp = requests.put(
        url, data=content,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': mime_type},
        timeout=30,
    )

    if resp.status_code in (200, 201):
        data    = resp.json()
        web_url = data.get('webUrl', '')
        share   = _share_link(token, data.get('id', ''))
        return {'ok': True, 'url': share or web_url, 'nome': filename, 'id': data.get('id', '')}

    current_app.logger.error(
        f'SharePoint upload doc motorista falhou {resp.status_code}: {resp.text[:300]}'
    )
    return {'ok': False, 'erro': f'Erro {resp.status_code} ao enviar para SharePoint.'}


def _share_link(token: str, item_id: str) -> str:
    if not item_id:
        return ''
    if DRIVE_ID:
        url = f'https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{item_id}/createLink'
    elif SITE_ID:
        url = f'https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/items/{item_id}/createLink'
    else:
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/createLink'
    resp = requests.post(url,
        json={'type': 'view', 'scope': 'organization'},
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        timeout=10)
    return resp.json().get('link', {}).get('webUrl', '') if resp.status_code == 200 else ''


def deletar_foto(item_id: str) -> bool:
    token = get_graph_token()
    if not token or not item_id:
        return False
    if DRIVE_ID:
        url = f'https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/items/{item_id}'
    elif SITE_ID:
        url = f'https://graph.microsoft.com/v1.0/sites/{SITE_ID}/drive/items/{item_id}'
    else:
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    resp = requests.delete(url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    return resp.status_code == 204
