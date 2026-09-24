"""Rotas — Troca de Fluidos (óleo, água, etc.)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from app import db
from app.models.usuario import Veiculo, Fornecedor, TrocaFluido

bp = Blueprint('fluidos', __name__, url_prefix='/fluidos')


@bp.route('/')
@login_required
def lista():
    from sqlalchemy import func
    sub = (db.session.query(
        TrocaFluido.veiculo_id,
        TrocaFluido.tipo_fluido,
        func.max(TrocaFluido.data_troca).label('ultima')
    ).group_by(TrocaFluido.veiculo_id, TrocaFluido.tipo_fluido).subquery())

    page = request.args.get('page', 1, type=int)
    tipo = request.args.get('tipo', '')

    query = (TrocaFluido.query
             .join(sub, (TrocaFluido.veiculo_id == sub.c.veiculo_id) &
                        (TrocaFluido.tipo_fluido == sub.c.tipo_fluido) &
                        (TrocaFluido.data_troca == sub.c.ultima))
             .order_by(TrocaFluido.km_proxima_troca.asc().nullslast()))
    if tipo:
        query = query.filter(TrocaFluido.tipo_fluido == tipo)

    trocas = query.paginate(page=page, per_page=30, error_out=False)
    return render_template('fluidos/lista.html',
                           trocas=trocas, tipo=tipo,
                           TIPOS=TrocaFluido.TIPOS, hoje=date.today())


@bp.route('/veiculo/<int:veiculo_id>')
@login_required
def veiculo(veiculo_id):
    v     = Veiculo.query.get_or_404(veiculo_id)
    tipo  = request.args.get('tipo', '')
    query = TrocaFluido.query.filter_by(veiculo_id=veiculo_id)
    if tipo:
        query = query.filter_by(tipo_fluido=tipo)
    historico = query.order_by(TrocaFluido.data_troca.desc()).all()
    ultimas = {}
    for t in TrocaFluido.TIPOS:
        ultimas[t] = (TrocaFluido.query
                      .filter_by(veiculo_id=veiculo_id, tipo_fluido=t)
                      .order_by(TrocaFluido.data_troca.desc()).first())
    return render_template('fluidos/veiculo.html',
                           v=v, historico=historico, ultimas=ultimas,
                           tipo=tipo, TIPOS=TrocaFluido.TIPOS, hoje=date.today())


@bp.route('/nova', methods=['GET', 'POST'])
@bp.route('/nova/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def nova(veiculo_id=None):
    veiculos     = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    veiculo_sel  = Veiculo.query.get(veiculo_id) if veiculo_id else None

    if request.method == 'POST':
        f = request.form
        try:
            vid      = int(f['veiculo_id'])
            v        = Veiculo.query.get_or_404(vid)
            km_troca = int(f['km_troca']) if f.get('km_troca') else v.km_atual
            intv_km  = int(f['intervalo_km']) if f.get('intervalo_km') else 5000
            intv_dias= int(f['intervalo_dias']) if f.get('intervalo_dias') else None
            prox_data= (date.fromisoformat(f['data_troca']) + timedelta(days=intv_dias)) if intv_dias and f.get('data_troca') else None

            troca = TrocaFluido(
                veiculo_id        = vid,
                tipo_fluido       = f['tipo_fluido'],
                data_troca        = f['data_troca'] or date.today(),
                km_troca          = km_troca,
                km_proxima_troca  = km_troca + intv_km if km_troca else None,
                intervalo_km      = intv_km,
                intervalo_dias    = intv_dias,
                proxima_data      = prox_data,
                marca_produto     = f.get('marca_produto') or None,
                viscosidade       = f.get('viscosidade') or None,
                quantidade_litros = float(f['quantidade_litros']) if f.get('quantidade_litros') else None,
                custo             = float(f['custo']) if f.get('custo') else None,
                fornecedor_id     = f.get('fornecedor_id') or None,
                observacoes       = f.get('observacoes') or None,
                created_by        = current_user.id,
            )
            db.session.add(troca)
            if km_troca and v.km_atual and km_troca > v.km_atual:
                v.km_atual = km_troca
            db.session.commit()
            flash('Troca registrada com sucesso.', 'success')
            return redirect(url_for('fluidos.veiculo', veiculo_id=vid))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('fluidos/form.html',
                           veiculos=veiculos, fornecedores=fornecedores,
                           veiculo_sel=veiculo_sel, TIPOS=TrocaFluido.TIPOS, hoje=date.today())


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    troca        = TrocaFluido.query.get_or_404(id)
    veiculos     = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()

    if request.method == 'POST':
        f = request.form
        try:
            km_troca  = int(f['km_troca']) if f.get('km_troca') else None
            intv_km   = int(f['intervalo_km']) if f.get('intervalo_km') else 5000
            intv_dias = int(f['intervalo_dias']) if f.get('intervalo_dias') else None
            prox_data = (date.fromisoformat(f['data_troca']) + timedelta(days=intv_dias)) if intv_dias and f.get('data_troca') else None

            troca.tipo_fluido       = f['tipo_fluido']
            troca.data_troca        = f['data_troca']
            troca.km_troca          = km_troca
            troca.km_proxima_troca  = km_troca + intv_km if km_troca else None
            troca.intervalo_km      = intv_km
            troca.intervalo_dias    = intv_dias
            troca.proxima_data      = prox_data
            troca.marca_produto     = f.get('marca_produto') or None
            troca.viscosidade       = f.get('viscosidade') or None
            troca.quantidade_litros = float(f['quantidade_litros']) if f.get('quantidade_litros') else None
            troca.custo             = float(f['custo']) if f.get('custo') else None
            troca.fornecedor_id     = f.get('fornecedor_id') or None
            troca.observacoes       = f.get('observacoes') or None
            db.session.commit()
            flash('Troca atualizada.', 'success')
            return redirect(url_for('fluidos.veiculo', veiculo_id=troca.veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('fluidos/form.html',
                           troca=troca, veiculos=veiculos, fornecedores=fornecedores,
                           TIPOS=TrocaFluido.TIPOS, hoje=date.today())
