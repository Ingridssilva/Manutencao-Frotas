"""
Rotas de exportação Excel — adicionar ao __init__.py como blueprint
ou incluir as rotas em cada arquivo de rotas existente.
"""
from flask import Blueprint, request
from flask_login import login_required
from app.models.usuario import (
    OrdemServico, Veiculo, Motorista, Pneu, TrocaFluido, Multa
)
from app.services.excel_export import (
    exportar_os, exportar_veiculos, exportar_motoristas,
    exportar_pneus, exportar_fluidos, exportar_multas
)

bp_export = Blueprint('export', __name__, url_prefix='/export')


@bp_export.route('/os')
@login_required
def os():
    status    = request.args.get('status', '')
    tipo      = request.args.get('tipo', '')
    veiculo   = request.args.get('veiculo_id', '')

    query = OrdemServico.query
    if status:
        query = query.filter_by(status=status)
    if tipo:
        query = query.filter_by(tipo_manutencao=tipo)
    if veiculo:
        query = query.filter_by(veiculo_id=int(veiculo))

    os_list = query.order_by(OrdemServico.data_abertura.desc()).all()
    return exportar_os(os_list)


@bp_export.route('/veiculos')
@login_required
def veiculos():
    status = request.args.get('status', '')
    query  = Veiculo.query.filter(Veiculo.status != 'inativo')
    if status:
        query = query.filter_by(status=status)
    return exportar_veiculos(query.order_by(Veiculo.placa).all())


@bp_export.route('/motoristas')
@login_required
def motoristas():
    ativo = request.args.get('ativo', '')
    query = Motorista.query
    if ativo == '1':
        query = query.filter_by(ativo=True)
    return exportar_motoristas(query.order_by(Motorista.nome).all())


@bp_export.route('/pneus')
@login_required
def pneus():
    status = request.args.get('status', '')
    query  = Pneu.query
    if status:
        query = query.filter_by(status=status)
    return exportar_pneus(query.order_by(Pneu.created_at.desc()).all())


@bp_export.route('/fluidos')
@login_required
def fluidos():
    tipo  = request.args.get('tipo', '')
    query = TrocaFluido.query
    if tipo:
        query = query.filter_by(tipo_fluido=tipo)
    return exportar_fluidos(query.order_by(TrocaFluido.data_troca.desc()).all())


@bp_export.route('/multas')
@login_required
def multas():
    status = request.args.get('status', '')
    query  = Multa.query
    if status:
        query = query.filter_by(status=status)
    return exportar_multas(query.order_by(Multa.data_infracao.desc()).all())
