"""Rotas — Planos de Manutenção Preventiva/Preditiva"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from app import db
from app.models.usuario import PlanoManutencao, Veiculo, CatalogoServico

bp = Blueprint('manutencao', __name__, url_prefix='/manutencao')


@bp.route('/')
@login_required
def lista():
    veiculo_id = request.args.get('veiculo_id', '')
    tipo       = request.args.get('tipo', '')
    page       = request.args.get('page', 1, type=int)
    query      = PlanoManutencao.query.filter_by(ativo=True)
    if veiculo_id:
        query = query.filter_by(veiculo_id=int(veiculo_id))
    if tipo:
        query = query.filter_by(tipo=tipo)
    planos   = query.join(Veiculo).order_by(Veiculo.placa, PlanoManutencao.proxima_data).paginate(
                   page=page, per_page=25, error_out=False)
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    hoje     = date.today()
    return render_template('manutencao/lista.html', planos=planos, veiculos=veiculos,
                           veiculo_id=veiculo_id, tipo=tipo, hoje=hoje)


@bp.route('/novo', methods=['GET', 'POST'])
@bp.route('/novo/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def novo(veiculo_id=None):
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    servicos = CatalogoServico.query.filter_by(ativo=True).order_by(CatalogoServico.nome).all()
    veiculo_sel = Veiculo.query.get(veiculo_id) if veiculo_id else None

    if request.method == 'POST':
        f = request.form
        try:
            int_km   = int(f['intervalo_km']) if f.get('intervalo_km') else None
            int_dias = int(f['intervalo_dias']) if f.get('intervalo_dias') else None
            km_ref   = int(f['km_referencia']) if f.get('km_referencia') else None
            dt_ref   = f.get('data_referencia') or None

            proximo_km   = (km_ref + int_km) if (km_ref and int_km) else None
            proxima_data = None
            if dt_ref and int_dias:
                from datetime import datetime
                proxima_data = datetime.strptime(dt_ref, '%Y-%m-%d').date() + timedelta(days=int_dias)

            p = PlanoManutencao(
                veiculo_id=int(f['veiculo_id']),
                servico_id=int(f['servico_id']),
                tipo=f['tipo'],
                gatilho_tipo=f['gatilho_tipo'],
                intervalo_km=int_km,
                intervalo_dias=int_dias,
                km_referencia=km_ref,
                data_referencia=dt_ref or None,
                proximo_km=proximo_km,
                proxima_data=proxima_data,
                alerta_km_antes=int(f.get('alerta_km_antes') or 500),
                alerta_dias_antes=int(f.get('alerta_dias_antes') or 15),
                observacoes=f.get('observacoes'),
                created_by=current_user.id,
            )
            db.session.add(p)
            db.session.commit()
            flash('Plano de manutenção criado.', 'success')
            return redirect(url_for('manutencao.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('manutencao/form.html', p=None, veiculos=veiculos,
                           servicos=servicos, veiculo_sel=veiculo_sel)


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    p        = PlanoManutencao.query.get_or_404(id)
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    servicos = CatalogoServico.query.filter_by(ativo=True).order_by(CatalogoServico.nome).all()

    if request.method == 'POST':
        f = request.form
        try:
            p.veiculo_id       = int(f['veiculo_id'])
            p.servico_id       = int(f['servico_id'])
            p.tipo             = f['tipo']
            p.gatilho_tipo     = f['gatilho_tipo']
            p.intervalo_km     = int(f['intervalo_km']) if f.get('intervalo_km') else None
            p.intervalo_dias   = int(f['intervalo_dias']) if f.get('intervalo_dias') else None
            p.km_referencia    = int(f['km_referencia']) if f.get('km_referencia') else None
            p.data_referencia  = f.get('data_referencia') or None
            p.alerta_km_antes  = int(f.get('alerta_km_antes') or 500)
            p.alerta_dias_antes= int(f.get('alerta_dias_antes') or 15)
            p.observacoes      = f.get('observacoes')
            # Recalcular próximos
            if p.km_referencia and p.intervalo_km:
                p.proximo_km = p.km_referencia + p.intervalo_km
            if p.data_referencia and p.intervalo_dias:
                p.proxima_data = p.data_referencia + timedelta(days=p.intervalo_dias)
            db.session.commit()
            flash('Plano atualizado.', 'success')
            return redirect(url_for('manutencao.lista'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('manutencao/form.html', p=p, veiculos=veiculos, servicos=servicos)


@bp.route('/<int:id>/desativar', methods=['POST'])
@login_required
def desativar(id):
    p = PlanoManutencao.query.get_or_404(id)
    p.ativo = False
    db.session.commit()
    flash('Plano desativado.', 'warning')
    return redirect(url_for('manutencao.lista'))
