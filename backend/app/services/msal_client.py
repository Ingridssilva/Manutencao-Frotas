"""
Singleton do cliente MSAL — reutiliza instância e cache de token.
Evita criar ConfidentialClientApplication a cada requisição.
"""
import msal
from flask import current_app

_token_cache = msal.SerializableTokenCache()
_msal_instance: msal.ConfidentialClientApplication | None = None
_msal_client_id: str = ''


def get_msal_app() -> msal.ConfidentialClientApplication | None:
    """Retorna o cliente MSAL singleton, recriando só se as credenciais mudaram."""
    global _msal_instance, _msal_client_id, _token_cache

    client_id     = current_app.config.get('AZURE_CLIENT_ID', '')
    client_secret = current_app.config.get('AZURE_CLIENT_SECRET', '')
    tenant_id     = current_app.config.get('AZURE_TENANT_ID', '')

    if not all([client_id, client_secret, tenant_id]):
        return None

    if _msal_instance is None or _msal_client_id != client_id:
        _msal_client_id = client_id
        _msal_instance  = msal.ConfidentialClientApplication(
            client_id,
            authority=f'https://login.microsoftonline.com/{tenant_id}',
            client_credential=client_secret,
            token_cache=_token_cache,
        )
    return _msal_instance


def get_graph_token() -> str | None:
    """Obtém token do Microsoft Graph reutilizando cache MSAL."""
    app = get_msal_app()
    if not app:
        return None

    # Tenta cache primeiro (evita nova requisição de rede)
    result = app.acquire_token_silent(
        scopes=['https://graph.microsoft.com/.default'],
        account=None,
    )
    if not result:
        result = app.acquire_token_for_client(
            scopes=['https://graph.microsoft.com/.default']
        )

    if 'access_token' in result:
        return result['access_token']

    current_app.logger.error(
        f"MSAL token error: {result.get('error')} — {result.get('error_description', '')}"
    )
    return None
