"""Rotas — Multas"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date
from app import db
from app.models.usuario import Multa, Veiculo, Motorista

bp = Blueprint('multas', __name__, url_prefix='/multas')


@bp.route('/')
@login_required
def lista():
    status    = request.args.get('status', '')
    veiculo_id= request.args.get('veiculo_id', '')
    page      = request.args.get('page', 1, type=int)
    query     = Multa.query
    if status:
        query = query.filter_by(status=status)
    if veiculo_id:
        query = query.filter_by(veiculo_id=int(veiculo_id))
    multas   = query.order_by(Multa.data_infracao.desc()).paginate(page=page, per_page=25, error_out=False)
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    return render_template('multas/lista.html', multas=multas, veiculos=veiculos,
                           status=status, veiculo_id=veiculo_id)


@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    veiculos   = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    motoristas = Motorista.query.filter_by(ativo=True).order_by(Motorista.nome).all()
    if request.method == 'POST':
        f = request.form
        try:
            m = Multa(
                veiculo_id=int(f['veiculo_id']),
                motorista_id=f.get('motorista_id') or None,
                auto_infracao=f.get('auto_infracao'),
                data_infracao=f['data_infracao'],
                local_infracao=f.get('local_infracao'),
                municipio=f.get('municipio'),
                descricao=f.get('descricao'),
                pontos=int(f.get('pontos') or 0),
                valor_original=float(f['valor_original']),
                valor_desconto=float(f['valor_desconto']) if f.get('valor_desconto') else None,
                data_vencimento=f.get('data_vencimento') or None,
                responsavel=f.get('responsavel', 'empresa'),
                observacoes=f.get('observacoes'),
                created_by=current_user.id,
            )
            db.session.add(m)
            db.session.commit()
            flash('Multa registrada.', 'success')
            return redirect(url_for('multas.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('multas/form.html', m=None, veiculos=veiculos, motoristas=motoristas)


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    m          = Multa.query.get_or_404(id)
    veiculos   = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    motoristas = Motorista.query.filter_by(ativo=True).order_by(Motorista.nome).all()
    if request.method == 'POST':
        f = request.form
        try:
            m.veiculo_id    = int(f['veiculo_id'])
            m.motorista_id  = f.get('motorista_id') or None
            m.auto_infracao = f.get('auto_infracao')
            m.data_infracao = f['data_infracao']
            m.local_infracao= f.get('local_infracao')
            m.municipio     = f.get('municipio')
            m.descricao     = f.get('descricao')
            m.pontos        = int(f.get('pontos') or 0)
            m.valor_original= float(f['valor_original'])
            m.valor_desconto= float(f['valor_desconto']) if f.get('valor_desconto') else None
            m.data_vencimento = f.get('data_vencimento') or None
            m.responsavel   = f.get('responsavel', 'empresa')
            m.status        = f.get('status', m.status)
            m.observacoes   = f.get('observacoes')
            db.session.commit()
            flash('Multa atualizada.', 'success')
            return redirect(url_for('multas.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    return render_template('multas/form.html', m=m, veiculos=veiculos, motoristas=motoristas)


@bp.route('/<int:id>/pagar', methods=['POST'])
@login_required
def pagar(id):
    m = Multa.query.get_or_404(id)
    try:
        m.status        = 'pago'
        m.data_pagamento= date.today()
        m.valor_pago    = float(request.form.get('valor_pago') or m.valor_efetivo)
        db.session.commit()
        flash('Pagamento registrado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
    return redirect(url_for('multas.lista'))
