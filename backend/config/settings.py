import os
from dotenv import load_dotenv

load_dotenv()

_ENV = os.environ.get('FLASK_ENV', 'development')


class Config:
    # ── SECRET_KEY ───────────────────────────────────────────────────────────
    # Em produção DEVE vir do env — nunca usa fallback inseguro
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if _ENV == 'production':
            raise RuntimeError(
                "[SEGURANÇA] SECRET_KEY não definida. "
                "Configure a variável de ambiente no Render antes de iniciar."
            )
        SECRET_KEY = 'dev-only-nao-usar-em-producao'

    # ── DATABASE_URL ─────────────────────────────────────────────────────────
    # Fallback SEM senha hardcoded — desenvolvedor precisa criar .env local
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql+psycopg://postgres@localhost:3333/Manutencao'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        # Supabase usa PgBouncer em Transaction Mode — NullPool é OBRIGATÓRIO.
        # QueuePool com conexões persistentes corrompe transações nesse modo.
        'connect_args': {
            'prepare_threshold': None,
            'connect_timeout': 8,       # falha rápida se o banco estiver lento
        },
        'poolclass': __import__('sqlalchemy.pool', fromlist=['NullPool']).NullPool,
    }

    # ── AZURE AD ─────────────────────────────────────────────────────────────
    AZURE_CLIENT_ID     = os.environ.get('AZURE_CLIENT_ID', '')
    AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET', '')
    AZURE_TENANT_ID     = os.environ.get('AZURE_TENANT_ID', '')
    AZURE_REDIRECT_URI  = os.environ.get('AZURE_REDIRECT_URI', 'http://localhost:5000/auth/callback')
    AZURE_AUTHORITY     = f"https://login.microsoftonline.com/{os.environ.get('AZURE_TENANT_ID', '')}"
    AZURE_SCOPE         = ['User.Read']

    # E-mails autorizados a entrar via Azure AD / MSAL
    # Pode ser sobrescrito via env AZURE_ALLOWED_EMAILS (separados por vírgula)
    _emails_env = os.environ.get('AZURE_ALLOWED_EMAILS', '')
    if _emails_env:
        AZURE_ALLOWED_EMAILS = {e.strip().lower() for e in _emails_env.split(',') if e.strip()}
    else:
        AZURE_ALLOWED_EMAILS = {
            'ti@empresaexemplo.com.br',
            'admin8@empresaexemplo.com.br',
            'gestor1@empresaexemplo.com.br',
            'admin2@empresaexemplo.com.br',
            'owner@empresaexemplo.com.br',
            'admin3@empresaexemplo.com.br',
            'admin4@empresaexemplo.com.br',
            'admin5@empresaexemplo.com.br',
            'admin6@empresaexemplo.com.br',
            'admin7@empresaexemplo.com.br',
        }

    # ── ALERTAS ──────────────────────────────────────────────────────────────
    ALERTA_DIAS_CRLV      = int(os.environ.get('ALERTA_DIAS_CRLV', 60))
    ALERTA_DIAS_CNH       = int(os.environ.get('ALERTA_DIAS_CNH', 60))
    ALERTA_DIAS_LAUDO     = int(os.environ.get('ALERTA_DIAS_LAUDO', 30))
    ALERTA_DIAS_TACOGRAFO = int(os.environ.get('ALERTA_DIAS_TACOGRAFO', 30))
    ALERTA_DIAS_SEGURO    = int(os.environ.get('ALERTA_DIAS_SEGURO', 45))

    EMAIL_REMETENTE            = os.environ.get('EMAIL_REMETENTE', 'TI@empresaexemplo.com.br')
    EMAIL_NOTIFICACAO_FALLBACK = os.environ.get('EMAIL_NOTIFICACAO_FALLBACK', 'owner@empresaexemplo.com.br')

    ITENS_POR_PAGINA = 20

    # ── LIMITE DE UPLOAD ─────────────────────────────────────────────────────
    # Sem isso, um upload muito grande (foto de OS, PDF de cotação, NF) é lido
    # inteiro na memória do worker antes de qualquer validação. 20MB cobre bem
    # fotos e PDFs de proposta; acima disso o Flask já recusa com 413 automático.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 20 * 1024 * 1024))

    # ── CACHE ────────────────────────────────────────────────────────────────
    # SimpleCache: in-process, não persiste entre workers — adequado para 1 worker (Render free)
    CACHE_TYPE            = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 120   # 2 minutos padrão


class DevelopmentConfig(Config):
    DEBUG           = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    # Em produção com múltiplos workers, trocar por RedisCache ou FileSystemCache
    CACHE_TYPE            = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 120


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
