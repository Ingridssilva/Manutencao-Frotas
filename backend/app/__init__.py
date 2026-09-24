import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from datetime import date
from config.settings import config

db        = SQLAlchemy()
migrate   = Migrate()
login_mgr = LoginManager()
csrf      = CSRFProtect()
cache     = Cache()


def create_app(config_name='default'):
    _here     = os.path.dirname(os.path.abspath(__file__))
    _backend  = os.path.dirname(_here)
    _root     = os.path.dirname(_backend)
    _frontend = os.path.join(_root, 'frontend')

    app = Flask(
        __name__,
        template_folder=os.path.join(_frontend, 'templates'),
        static_folder=os.path.join(_frontend, 'static'),
    )
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_mgr.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)   # ← flask-caching

    login_mgr.login_view           = 'auth.azure_login'
    login_mgr.login_message        = ''
    login_mgr.login_message_category = 'info'

    with app.app_context():
        from app.models import usuario as _models  # noqa

    from app.routes.auth              import bp as auth_bp
    from app.routes.dashboard         import bp as dash_bp
    from app.routes.veiculos          import bp as vei_bp
    from app.routes.motoristas        import bp as mot_bp
    from app.routes.manutencao        import bp as man_bp
    from app.routes.os                import bp as os_bp
    from app.routes.orcamentos        import bp as orc_bp
    from app.routes.disponibilidade   import bp as disp_bp
    from app.routes.documentos        import bp as doc_bp
    from app.routes.multas            import bp as mul_bp
    from app.routes.checklist         import bp as chk_bp
    from app.routes.relatorios        import bp as rel_bp
    from app.routes.api               import bp as api_bp
    from app.routes.admin             import bp as adm_bp
    from app.routes.fluidos           import bp as flu_bp
    from app.routes.pneus             import bp as pneu_bp
    from app.routes.os_fotos          import bp_fotos
    from app.routes.export            import bp_export
    from app.routes.admin_notif       import bp_notif      # ← CORRIGIDO: estava faltando
    from app.routes.relatorio_veiculo import bp as rel_vei_bp
    from app.routes.public            import bp as pub_bp
    from app.routes.reservas          import bp as res_bp

    for _bp in [
        auth_bp, dash_bp, vei_bp, mot_bp, man_bp, os_bp,
        orc_bp, disp_bp, doc_bp, mul_bp, chk_bp, rel_bp,
        api_bp, adm_bp,
        flu_bp, pneu_bp,
        bp_fotos, bp_export,
        bp_notif,       # ← registrado
        rel_vei_bp,
        pub_bp,
        res_bp,         # 2190 reservas de ve00edculo
    ]:
        app.register_blueprint(_bp)

    @login_mgr.user_loader
    def load_user(user_id):
        from app.models.usuario import Usuario
        return db.session.get(Usuario, user_id)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.models.usuario import Alerta
        count = 0
        try:
            if current_user.is_authenticated:
                cache_key   = f'alertas_criticos_{current_user.id}'
                count_cache = cache.get(cache_key)
                if count_cache is None:
                    count = Alerta.query.filter_by(nivel='critico', lido=False).count()
                    cache.set(cache_key, count, timeout=60)  # cache 60s por usuário
                else:
                    count = count_cache
        except Exception:
            # Se a query falhar (ex: banco indisponível), mantém count=0 em vez de
            # deixar None vazar pro template — "None > 0" quebraria toda página que
            # estende base.html.
            count = 0
        return dict(alertas_criticos=count, hoje=date.today())

    return app
