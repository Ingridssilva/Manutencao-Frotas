"""Rotas — Auth (somente Azure AD / MSAL — sem formulário de senha)"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.usuario import Usuario, PerfilAcesso
from app.services.msal_client import get_msal_app
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
bp     = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login')
def login():
    """Redireciona direto para Azure AD — sem formulário de senha."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.azure_login'))


@bp.route('/azure')
def azure_login():
    msal_app = get_msal_app()
    if not msal_app:
        return render_template('auth/erro_login.html')
    flow = msal_app.initiate_auth_code_flow(
        current_app.config['AZURE_SCOPE'],
        redirect_uri=current_app.config['AZURE_REDIRECT_URI'],
    )
    session['flow'] = flow
    return redirect(flow['auth_uri'])


@bp.route('/callback')
def callback():
    msal_app = get_msal_app()
    if not msal_app:
        return render_template('auth/erro_login.html')
    try:
        result = msal_app.acquire_token_by_auth_code_flow(
            session.get('flow', {}), request.args
        )
        oid   = result['id_token_claims']['oid']
        email = result['id_token_claims'].get('preferred_username', '').lower()
        nome  = result['id_token_claims'].get('name', email)

        allowed = current_app.config.get('AZURE_ALLOWED_EMAILS', set())
        if allowed and email not in allowed:
            logger.warning(f'Login negado: {email}')
            return render_template('auth/acesso_negado.html', email=email)

        u = Usuario.query.filter_by(azure_oid=oid).first()
        if not u:
            u = Usuario.query.filter_by(email=email).first()
            if u:
                u.azure_oid = oid
            else:
                perfil = PerfilAcesso.query.filter_by(nome='visualizador').first()
                u = Usuario(nome=nome, email=email, azure_oid=oid,
                            perfil_id=perfil.id if perfil else None, ativo=True)
                db.session.add(u)

        u.ultimo_acesso = datetime.utcnow()
        db.session.commit()
        login_user(u)
        logger.info(f'Login bem-sucedido: {email}')

    except Exception as e:
        logger.error(f'Erro na autenticação Azure: {e}', exc_info=True)
        return render_template('auth/erro_login.html', erro=str(e))

    next_url = session.pop('next_after_login', None)
    return redirect(next_url or url_for('dashboard.index'))


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.kanban'))
