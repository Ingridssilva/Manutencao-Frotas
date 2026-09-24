"""Rotas — Fotos / Anexos de Ordens de Serviço"""
import uuid
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.usuario import OSFoto, OrdemServico
from app.services.sharepoint_upload import upload_foto_os, deletar_foto, validar_arquivo

logger      = logging.getLogger(__name__)
bp_fotos    = Blueprint('os_fotos', __name__, url_prefix='/os')
TAMANHO_MAX = 10 * 1024 * 1024   # 10 MB


@bp_fotos.route('/<int:os_id>/fotos', methods=['GET'])
@login_required
def listar_fotos(os_id):
    OrdemServico.query.get_or_404(os_id)
    fotos = OSFoto.query.filter_by(os_id=os_id).order_by(OSFoto.created_at.desc()).all()
    return jsonify([{
        'id':        f.id,
        'nome':      f.nome_arquivo,
        'url':       f.url_sharepoint,
        'descricao': f.descricao,
        'tipo':      f.tipo,
        'created_at': f.created_at.isoformat() if f.created_at else None,
    } for f in fotos])


@bp_fotos.route('/<int:os_id>/fotos', methods=['POST'])
@login_required
def adicionar_foto(os_id):
    o = OrdemServico.query.get_or_404(os_id)

    if 'file' not in request.files:
        return jsonify({'ok': False, 'erro': 'Nenhum arquivo enviado.'}), 400

    arquivo = request.files['file']
    if not arquivo.filename:
        return jsonify({'ok': False, 'erro': 'Nome de arquivo vazio.'}), 400

    # ── Validação de extensão e MIME type ────────────────────────────────────
    ok, erro = validar_arquivo(arquivo.filename, arquivo.mimetype or '')
    if not ok:
        return jsonify({'ok': False, 'erro': erro}), 400

    content = arquivo.read()
    if len(content) > TAMANHO_MAX:
        return jsonify({'ok': False, 'erro': 'Arquivo maior que 10 MB.'}), 400

    # Nome único + sanitizado — evita path traversal
    filename = f'{uuid.uuid4().hex[:8]}_{secure_filename(arquivo.filename)}'[:120]

    descricao = (request.form.get('descricao') or '')[:200]
    tipo      = request.form.get('tipo', 'foto')
    if tipo not in ('foto', 'nf', 'comprovante', 'documento'):
        tipo = 'foto'

    result = upload_foto_os(
        os_numero     = o.numero or str(os_id),
        veiculo_placa = o.veiculo.placa if o.veiculo else 'SEM_PLACA',
        filename      = filename,
        content       = content,
        mime_type     = arquivo.mimetype or 'application/octet-stream',
    )

    if not result['ok']:
        logger.error(f'Upload foto OS {os_id} falhou: {result["erro"]}')
        return jsonify({'ok': False, 'erro': result['erro']}), 500

    foto = OSFoto(
        os_id          = os_id,
        nome_arquivo   = filename,
        url_sharepoint = result.get('url', ''),
        sharepoint_id  = result.get('id', ''),
        descricao      = descricao,
        tipo           = tipo,
        uploaded_by    = current_user.id,
    )
    db.session.add(foto)
    db.session.commit()

    return jsonify({
        'ok':        True,
        'id':        foto.id,
        'url':       foto.url_sharepoint,
        'nome':      foto.nome_arquivo,
        'descricao': foto.descricao,
        'tipo':      foto.tipo,
    }), 201


@bp_fotos.route('/<int:os_id>/fotos/<int:foto_id>', methods=['DELETE'])
@login_required
def remover_foto(os_id, foto_id):
    foto = OSFoto.query.filter_by(id=foto_id, os_id=os_id).first_or_404()
    if foto.sharepoint_id:
        deletar_foto(foto.sharepoint_id)
    db.session.delete(foto)
    db.session.commit()
    return jsonify({'ok': True})
