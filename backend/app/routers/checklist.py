"""Rotas — Checklist pré-operação"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date
from app import db
from app.models.usuario import Checklist, ChecklistResposta, ChecklistItemConfig, Veiculo, Motorista
from app.services.negocio import registrar_km

bp = Blueprint('checklist', __name__, url_prefix='/checklist')


@bp.route('/')
@login_required
def lista():
    page      = request.args.get('page', 1, type=int)
    veiculo_id= request.args.get('veiculo_id', '')
    query     = Checklist.query
    if veiculo_id:
        query = query.filter_by(veiculo_id=int(veiculo_id))
    checklists = query.order_by(Checklist.data_checklist.desc(), Checklist.id.desc()) \
                      .paginate(page=page, per_page=30, error_out=False)
    veiculos   = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    return render_template('checklist/lista.html', checklists=checklists,
                           veiculos=veiculos, veiculo_id=veiculo_id)


@bp.route('/novo', methods=['GET', 'POST'])
@bp.route('/novo/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def novo(veiculo_id=None):
    veiculos   = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    motoristas = Motorista.query.filter_by(ativo=True).order_by(Motorista.nome).all()
    itens      = ChecklistItemConfig.query.filter_by(ativo=True).order_by(ChecklistItemConfig.ordem).all()
    veiculo_sel= Veiculo.query.get(veiculo_id) if veiculo_id else None

    if request.method == 'POST':
        f = request.form
        try:
            # Determinar status geral
            nao_conformes = [k for k in f if k.startswith('item_') and f[k] == 'nao']
            itens_obrig   = [i for i in itens if i.obrigatorio]
            ids_obrig     = {str(i.id) for i in itens_obrig}
            reprovado = any(k.replace('item_', '') in ids_obrig for k in f if k.startswith('item_') and f[k] == 'nao')
            tem_ressalva  = len(nao_conformes) > 0

            status_geral = 'reprovado' if reprovado else ('aprovado_com_ressalvas' if tem_ressalva else 'aprovado')

            chk = Checklist(
                veiculo_id    = int(f['veiculo_id']),
                motorista_id  = f.get('motorista_id') or None,
                data_checklist= f.get('data_checklist') or date.today(),
                km_atual      = int(f['km_atual']) if f.get('km_atual') else None,
                turno         = f.get('turno', 'manha'),
                status_geral  = status_geral,
                observacoes   = f.get('observacoes'),
                realizado_por = current_user.id,
            )
            db.session.add(chk)
            db.session.flush()

            for item in itens:
                val = f.get(f'item_{item.id}', 'sim')
                obs = f.get(f'obs_{item.id}', '')
                db.session.add(ChecklistResposta(
                    checklist_id=chk.id,
                    item_id=item.id,
                    conforme=(val == 'sim'),
                    observacao=obs or None,
                ))

            # Registrar KM se informado
            if chk.km_atual:
                registrar_km(chk.veiculo_id, chk.km_atual, 'checklist', chk.id, current_user.id)

            db.session.commit()
            flash(f'Checklist registrado — Status: {status_geral.replace("_", " ").title()}.', 'success')
            return redirect(url_for('checklist.detalhe', id=chk.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('checklist/form.html',
        veiculos=veiculos, motoristas=motoristas, itens=itens,
        veiculo_sel=veiculo_sel, hoje=date.today())


@bp.route('/<int:id>')
@login_required
def detalhe(id):
    chk = Checklist.query.get_or_404(id)
    return render_template('checklist/detalhe.html', chk=chk)
