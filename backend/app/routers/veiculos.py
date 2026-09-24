"""Rotas — Veículos"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import date
from app import db
from app.models.usuario import (
    Veiculo, Motorista, Fornecedor, ContratoVeiculo, CRLV,
    LaudoAcustico, Tacografo, SeguroVeiculo, PlanoManutencao,
    CatalogoServico, Alerta, OrdemServico, OSPagamento
)
from app.services.negocio import registrar_km
from app.services.pdf_plano import gerar_pdf_plano

bp = Blueprint('veiculos', __name__, url_prefix='/veiculos')

@bp.route('/')
@login_required
def lista():
    q = request.args.get('q', '')
    status = request.args.get('status', '')
    query = Veiculo.query
    if q:
        query = query.filter(
            db.or_(Veiculo.placa.ilike(f'%{q}%'), Veiculo.descricao.ilike(f'%{q}%'))
        )
    if status:
        query = query.filter_by(status=status)
    veiculos = query.order_by(Veiculo.placa).all()
    return render_template('veiculos/lista.html', veiculos=veiculos, q=q, status=status)

@bp.route('/<int:id>')
@login_required
def detalhe(id):
    v = Veiculo.query.get_or_404(id)
    alertas = Alerta.query.filter_by(veiculo_id=id, lido=False).all()
    planos  = PlanoManutencao.query.filter_by(veiculo_id=id, ativo=True).all()
    os_list = (OrdemServico.query.filter_by(veiculo_id=id)
               .order_by(OrdemServico.data_abertura.desc()).limit(10).all())
    return render_template('veiculos/detalhe.html',
        v=v, alertas=alertas, planos=planos, os_list=os_list, hoje=date.today()
    )

@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    fornecedores = Fornecedor.query.filter_by(ativo=True).all()
    if request.method == 'POST':
        f = request.form
        v = Veiculo(
            placa=f['placa'].upper().strip(),
            descricao=f.get('descricao'),
            marca=f.get('marca'), modelo=f.get('modelo'),
            ano_fabricacao=f.get('ano_fabricacao') or None,
            ano_modelo=f.get('ano_modelo') or None,
            cor=f.get('cor'), chassi=f.get('chassi') or None,
            renavam=f.get('renavam'), tipo_veiculo=f.get('tipo_veiculo'),
            tipo_propriedade=f.get('tipo_propriedade', 'proprio'),
            fornecedor_locacao_id=f.get('fornecedor_locacao_id') or None,
            municipio_base=f.get('municipio_base'),
            km_atual=int(f.get('km_atual', 0)),
            observacoes=f.get('observacoes'),
            created_by=current_user.id,
        )
        db.session.add(v)
        db.session.commit()
        flash('Veículo cadastrado com sucesso.', 'success')
        return redirect(url_for('veiculos.detalhe', id=v.id))
    return render_template('veiculos/form.html', v=None, fornecedores=fornecedores)

@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    v = Veiculo.query.get_or_404(id)
    fornecedores = Fornecedor.query.filter_by(ativo=True).all()
    if request.method == 'POST':
        f = request.form
        v.placa = f['placa'].upper().strip()
        v.descricao = f.get('descricao'); v.marca = f.get('marca')
        v.modelo = f.get('modelo')
        v.ano_fabricacao = f.get('ano_fabricacao') or None
        v.ano_modelo = f.get('ano_modelo') or None
        v.cor = f.get('cor'); v.chassi = f.get('chassi') or None
        v.renavam = f.get('renavam'); v.tipo_veiculo = f.get('tipo_veiculo')
        v.tipo_propriedade = f.get('tipo_propriedade', 'proprio')
        v.fornecedor_locacao_id = f.get('fornecedor_locacao_id') or None
        v.municipio_base = f.get('municipio_base')
        v.status = f.get('status', 'ativo')
        v.observacoes = f.get('observacoes')
        db.session.commit()
        flash('Veículo atualizado.', 'success')
        return redirect(url_for('veiculos.detalhe', id=v.id))
    return render_template('veiculos/form.html', v=v, fornecedores=fornecedores)

@bp.route('/<int:id>/km', methods=['POST'])
@login_required
def atualizar_km(id):
    km = int(request.form.get('km_novo', 0))
    ok = registrar_km(id, km, origem='manual', user_id=current_user.id)
    db.session.commit()
    if ok:
        flash('KM atualizado.', 'success')
    else:
        flash('KM inválido (deve ser maior que o atual).', 'warning')
    return redirect(url_for('veiculos.detalhe', id=id))

@bp.route('/<int:id>/plano-pdf')
@login_required
def plano_pdf(id):
    v = Veiculo.query.get_or_404(id)
    planos = PlanoManutencao.query.filter_by(veiculo_id=id, ativo=True).all()
    buf = gerar_pdf_plano(v, planos, current_user.nome)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f'plano_manutencao_{v.placa}.pdf')
