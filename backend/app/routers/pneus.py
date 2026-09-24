"""Rotas — Controle de Pneus"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date
from app import db
from app.models.usuario import Veiculo, Fornecedor, Pneu, PneuVeiculo, PneuRecapagem

bp = Blueprint('pneus', __name__, url_prefix='/pneus')


@bp.route('/')
@login_required
def lista():
    page   = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    query  = Pneu.query
    if status:
        query = query.filter_by(status=status)
    pneus = query.order_by(Pneu.created_at.desc()).paginate(page=page, per_page=30, error_out=False)
    return render_template('pneus/lista.html', pneus=pneus, status=status)


@bp.route('/<int:id>')
@login_required
def detalhe(id):
    pneu      = Pneu.query.get_or_404(id)
    historico = (PneuVeiculo.query
                 .filter_by(pneu_id=id)
                 .order_by(PneuVeiculo.data_inicio.desc()).all())
    return render_template('pneus/detalhe.html', pneu=pneu, historico=historico,
                           POSICOES=PneuVeiculo.POSICOES, hoje=date.today())


@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    veiculos     = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()

    if request.method == 'POST':
        f = request.form
        try:
            pneu = Pneu(
                codigo          = f.get('codigo') or None,
                marca           = f.get('marca') or None,
                modelo          = f.get('modelo') or None,
                dimensao        = f.get('dimensao') or None,
                tipo            = f.get('tipo', 'novo'),
                dot             = f.get('dot') or None,
                km_inicial      = int(f['km_inicial']) if f.get('km_inicial') else 0,
                km_limite       = int(f['km_limite']) if f.get('km_limite') else 80000,
                custo_aquisicao = float(f['custo_aquisicao']) if f.get('custo_aquisicao') else None,
                fornecedor_id   = f.get('fornecedor_id') or None,
                observacoes     = f.get('observacoes') or None,
            )
            db.session.add(pneu)
            db.session.flush()
            if f.get('veiculo_id') and f.get('posicao'):
                vid = int(f['veiculo_id'])
                v   = Veiculo.query.get(vid)
                anterior = PneuVeiculo.query.filter_by(veiculo_id=vid, posicao=f['posicao'], ativo=True).first()
                if anterior:
                    anterior.ativo    = False
                    anterior.data_fim = date.today()
                    anterior.km_fim   = v.km_atual if v else None
                db.session.add(PneuVeiculo(
                    pneu_id=pneu.id, veiculo_id=vid, posicao=f['posicao'],
                    data_inicio=date.today(), km_inicio=v.km_atual if v else None,
                ))
            db.session.commit()
            flash('Pneu cadastrado com sucesso.', 'success')
            return redirect(url_for('pneus.detalhe', id=pneu.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {e}', 'danger')

    return render_template('pneus/form.html',
                           fornecedores=fornecedores, veiculos=veiculos,
                           POSICOES=PneuVeiculo.POSICOES)


@bp.route('/<int:id>/montar', methods=['GET', 'POST'])
@login_required
def montar(id):
    pneu     = Pneu.query.get_or_404(id)
    veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()

    if request.method == 'POST':
        f = request.form
        try:
            vid = int(f['veiculo_id'])
            v   = Veiculo.query.get_or_404(vid)
            anterior = PneuVeiculo.query.filter_by(veiculo_id=vid, posicao=f['posicao'], ativo=True).first()
            if anterior:
                anterior.ativo    = False
                anterior.data_fim = date.today()
                anterior.km_fim   = v.km_atual
            pos_atual = pneu.posicao_atual
            if pos_atual:
                pos_atual.ativo    = False
                pos_atual.data_fim = date.today()
                pos_atual.km_fim   = v.km_atual
            db.session.add(PneuVeiculo(
                pneu_id=id, veiculo_id=vid, posicao=f['posicao'],
                data_inicio=date.today(), km_inicio=v.km_atual,
                observacoes=f.get('observacoes') or None,
            ))
            pneu.status = 'ativo'
            db.session.commit()
            flash('Pneu montado com sucesso.', 'success')
            return redirect(url_for('pneus.detalhe', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('pneus/montar.html', pneu=pneu, veiculos=veiculos,
                           POSICOES=PneuVeiculo.POSICOES)


@bp.route('/<int:id>/desmontar', methods=['POST'])
@login_required
def desmontar(id):
    pneu      = Pneu.query.get_or_404(id)
    pos_atual = pneu.posicao_atual
    if pos_atual:
        v = pos_atual.veiculo
        pos_atual.ativo    = False
        pos_atual.data_fim = date.today()
        pos_atual.km_fim   = v.km_atual if v else None
        db.session.commit()
        flash('Pneu desmontado.', 'warning')
    return redirect(url_for('pneus.detalhe', id=id))


@bp.route('/<int:id>/recapar', methods=['GET', 'POST'])
@login_required
def recapar(id):
    pneu         = Pneu.query.get_or_404(id)
    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()

    if request.method == 'POST':
        f = request.form
        try:
            pos_atual = pneu.posicao_atual
            if pos_atual:
                v = pos_atual.veiculo
                pos_atual.ativo    = False
                pos_atual.data_fim = date.today()
                pos_atual.km_fim   = v.km_atual if v else None
            db.session.add(PneuRecapagem(
                pneu_id      = id,
                data_envio   = f['data_envio'],
                km_envio     = int(f['km_envio']) if f.get('km_envio') else None,
                fornecedor_id= f.get('fornecedor_id') or None,
                custo        = float(f['custo']) if f.get('custo') else None,
                observacoes  = f.get('observacoes') or None,
                status       = 'enviado',
            ))
            pneu.status = 'recapando'
            db.session.commit()
            flash('Pneu enviado para recapagem.', 'info')
            return redirect(url_for('pneus.detalhe', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('pneus/recapar.html', pneu=pneu, fornecedores=fornecedores,
                           hoje=date.today())


@bp.route('/recapagem/<int:id>/concluir', methods=['POST'])
@login_required
def concluir_recapagem(id):
    rec              = PneuRecapagem.query.get_or_404(id)
    rec.status       = 'concluido'
    rec.data_retorno = date.today()
    rec.pneu.status  = 'ativo'
    rec.pneu.vezes_recapado = (rec.pneu.vezes_recapado or 0) + 1
    rec.pneu.tipo    = 'recapado'
    db.session.commit()
    flash('Recapagem concluída. Pneu disponível para montagem.', 'success')
    return redirect(url_for('pneus.detalhe', id=rec.pneu_id))


@bp.route('/veiculo/<int:veiculo_id>')
@login_required
def veiculo(veiculo_id):
    v        = Veiculo.query.get_or_404(veiculo_id)
    montados = PneuVeiculo.query.filter_by(veiculo_id=veiculo_id, ativo=True).all()
    mapa     = {p.posicao: p for p in montados}
    return render_template('pneus/veiculo.html', v=v, mapa=mapa,
                           POSICOES=PneuVeiculo.POSICOES, hoje=date.today())


@bp.route('/rodizio/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def rodizio(veiculo_id):
    v        = Veiculo.query.get_or_404(veiculo_id)
    montados = PneuVeiculo.query.filter_by(veiculo_id=veiculo_id, ativo=True).all()

    if request.method == 'POST':
        f = request.form
        try:
            trocas   = []
            de_list  = f.getlist('de[]')
            para_list= f.getlist('para[]')
            pos_map  = {p.posicao: p for p in montados}
            for de, para in zip(de_list, para_list):
                if de != para and de in pos_map:
                    trocas.append((pos_map[de], para))
            for pos_obj, nova_pos in trocas:
                pos_obj.ativo    = False
                pos_obj.data_fim = date.today()
                pos_obj.km_fim   = v.km_atual
                db.session.add(PneuVeiculo(
                    pneu_id=pos_obj.pneu_id, veiculo_id=veiculo_id,
                    posicao=nova_pos, data_inicio=date.today(),
                    km_inicio=v.km_atual, observacoes='Rodízio',
                ))
            db.session.commit()
            flash(f'Rodízio registrado — {len(trocas)} pneu(s) movido(s).', 'success')
            return redirect(url_for('pneus.veiculo', veiculo_id=veiculo_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('pneus/rodizio.html', v=v, montados=montados,
                           POSICOES=PneuVeiculo.POSICOES)
