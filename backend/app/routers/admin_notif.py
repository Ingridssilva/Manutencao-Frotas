"""
Adicionar estas rotas ao backend/app/routes/admin.py existente
(ou criar um novo arquivo admin_notif.py e registrar o blueprint)
"""
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from app.services.notificacoes import executar_todas_notificacoes

bp_notif = Blueprint('notificacoes', __name__, url_prefix='/admin/notificacoes')


@bp_notif.route('/')
@login_required
def index():
    """Página de controle de notificações."""
    if not current_user.is_admin:
        return 'Acesso negado', 403
    return render_template('admin/notificacoes.html')


@bp_notif.route('/disparar', methods=['POST'])
@login_required
def disparar():
    """Dispara todas as notificações manualmente."""
    if not current_user.is_admin:
        return jsonify({'erro': 'Acesso negado'}), 403
    resultado = executar_todas_notificacoes()
    return jsonify({'ok': True, 'resultado': resultado})
