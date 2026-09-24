"""Rotas — Documentos dos Veículos (CRLV, Laudo, Tacógrafo, Seguro)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.usuario import Veiculo, CRLV, LaudoAcustico, Tacografo, SeguroVeiculo, Fornecedor

bp = Blueprint('documentos', __name__, url_prefix='/documentos')


# ── CRLV ────────────────────────────────────────────────
@bp.route('/crlv/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def crlv(veiculo_id):
    v = Veiculo.query.get_or_404(veiculo_id)
    doc = v.crlv
    if request.method == 'POST':
        f = request.form
        try:
            if doc:
                doc.exercicio       = int(f['exercicio'])
                doc.data_vencimento = f['data_vencimento']
                doc.emplacamento    = f.get('emplacamento')
                doc.proprietario    = f.get('proprietario')
                doc.link_documento  = f.get('link_documento')
                doc.status          = f.get('status', 'regular')
            else:
                doc = CRLV(
                    veiculo_id=veiculo_id,
                    exercicio=int(f['exercicio']),
                    data_vencimento=f['data_vencimento'],
                    emplacamento=f.get('emplacamento'),
                    proprietario=f.get('proprietario'),
                    link_documento=f.get('link_documento'),
                    status=f.get('status', 'regular'),
                )
                db.session.add(doc)
            db.session.commit()
            flash('CRLV salvo.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('documentos/crlv.html', v=v, doc=doc)


# ── LAUDO ACÚSTICO ──────────────────────────────────────
@bp.route('/laudo/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def laudo(veiculo_id):
    v   = Veiculo.query.get_or_404(veiculo_id)
    doc = v.laudo_atual
    if request.method == 'POST':
        f = request.form
        try:
            novo = LaudoAcustico(
                veiculo_id=veiculo_id,
                data_emissao=f['data_emissao'],
                data_vencimento=f['data_vencimento'],
                empresa_emissora=f.get('empresa_emissora'),
                numero_laudo=f.get('numero_laudo'),
                resultado=f.get('resultado'),
                link_documento=f.get('link_documento'),
                observacoes=f.get('observacoes'),
            )
            db.session.add(novo)
            db.session.commit()
            flash('Laudo acústico salvo.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    historico = v.laudos.order_by(LaudoAcustico.data_emissao.desc()).all()
    return render_template('documentos/laudo.html', v=v, doc=doc, historico=historico)


# ── TACÓGRAFO ───────────────────────────────────────────
@bp.route('/tacografo/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def tacografo(veiculo_id):
    v   = Veiculo.query.get_or_404(veiculo_id)
    doc = v.tacografo_atual
    if request.method == 'POST':
        f = request.form
        try:
            novo = Tacografo(
                veiculo_id=veiculo_id,
                numero_serie=f.get('numero_serie'),
                marca=f.get('marca'),
                modelo=f.get('modelo'),
                data_instalacao=f.get('data_instalacao') or None,
                data_ultima_calibracao=f.get('data_ultima_calibracao') or None,
                data_proxima_calibracao=f['data_proxima_calibracao'],
                empresa_calibradora=f.get('empresa_calibradora'),
                link_certificado=f.get('link_certificado'),
                status=f.get('status', 'regular'),
            )
            db.session.add(novo)
            db.session.commit()
            flash('Tacógrafo salvo.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    historico = v.tacografos.order_by(Tacografo.data_proxima_calibracao.desc()).all()
    return render_template('documentos/tacografo.html', v=v, doc=doc, historico=historico)


# ── SEGURO ──────────────────────────────────────────────
@bp.route('/seguro/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def seguro(veiculo_id):
    v            = Veiculo.query.get_or_404(veiculo_id)
    doc          = v.seguro_ativo
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    if request.method == 'POST':
        f = request.form
        try:
            novo = SeguroVeiculo(
                veiculo_id=veiculo_id,
                fornecedor_id=f.get('fornecedor_id') or None,
                numero_apolice=f.get('numero_apolice'),
                tipo_cobertura=f.get('tipo_cobertura'),
                data_inicio=f['data_inicio'],
                data_vencimento=f['data_vencimento'],
                valor_premio=float(f['valor_premio']) if f.get('valor_premio') else None,
                franquia=float(f['franquia']) if f.get('franquia') else None,
                link_apolice=f.get('link_apolice'),
                status='ativo',
                observacoes=f.get('observacoes'),
            )
            if doc:
                doc.status = 'encerrado'
            db.session.add(novo)
            db.session.commit()
            flash('Seguro cadastrado.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    historico = v.seguros.order_by(SeguroVeiculo.data_vencimento.desc()).all()
    return render_template('documentos/seguro.html', v=v, doc=doc,
                           historico=historico, fornecedores=fornecedores)


# ── CONTRATOS ───────────────────────────────────────────
@bp.route('/contrato/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def contrato(veiculo_id):
    from app.models.usuario import ContratoVeiculo
    from flask_login import current_user
    v            = Veiculo.query.get_or_404(veiculo_id)
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()

    if request.method == 'POST':
        f = request.form
        try:
            c = ContratoVeiculo(
                veiculo_id      = veiculo_id,
                fornecedor_id   = f.get('fornecedor_id') or None,
                tipo_contrato   = f['tipo_contrato'],
                numero_contrato = f.get('numero_contrato') or None,
                descricao       = f.get('descricao') or None,
                data_inicio     = f['data_inicio'],
                data_fim        = f.get('data_fim') or None,
                valor_mensal    = float(f['valor_mensal']) if f.get('valor_mensal') else None,
                valor_total     = float(f['valor_total'])  if f.get('valor_total')  else None,
                link_contrato   = f.get('link_contrato') or None,
                status          = f.get('status', 'ativo'),
                observacoes     = f.get('observacoes') or None,
                created_by      = current_user.id,
            )
            db.session.add(c)
            db.session.commit()
            flash('Contrato salvo com sucesso.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar contrato: {e}', 'danger')

    return render_template('documentos/contrato.html', v=v, c=None, fornecedores=fornecedores)


@bp.route('/contrato/<int:veiculo_id>/<int:contrato_id>/editar', methods=['GET', 'POST'])
@login_required
def contrato_editar(veiculo_id, contrato_id):
    from app.models.usuario import ContratoVeiculo
    v            = Veiculo.query.get_or_404(veiculo_id)
    c            = ContratoVeiculo.query.get_or_404(contrato_id)
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()

    if request.method == 'POST':
        f = request.form
        try:
            c.fornecedor_id   = f.get('fornecedor_id') or None
            c.tipo_contrato   = f['tipo_contrato']
            c.numero_contrato = f.get('numero_contrato') or None
            c.descricao       = f.get('descricao') or None
            c.data_inicio     = f['data_inicio']
            c.data_fim        = f.get('data_fim') or None
            c.valor_mensal    = float(f['valor_mensal']) if f.get('valor_mensal') else None
            c.valor_total     = float(f['valor_total'])  if f.get('valor_total')  else None
            c.link_contrato   = f.get('link_contrato') or None
            c.status          = f.get('status', 'ativo')
            c.observacoes     = f.get('observacoes') or None
            db.session.commit()
            flash('Contrato atualizado.', 'success')
            return redirect(url_for('veiculos.detalhe', id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('documentos/contrato.html', v=v, c=c, fornecedores=fornecedores)


@bp.route('/contrato/<int:contrato_id>/encerrar', methods=['POST'])
@login_required
def contrato_encerrar(contrato_id):
    from app.models.usuario import ContratoVeiculo
    c = ContratoVeiculo.query.get_or_404(contrato_id)
    veiculo_id = c.veiculo_id
    c.status = 'encerrado'
    db.session.commit()
    flash('Contrato encerrado.', 'warning')
    return redirect(url_for('veiculos.detalhe', id=veiculo_id))