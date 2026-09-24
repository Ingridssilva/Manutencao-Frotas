"""Rotas — Orçamentos, Cotações e Ordens de Compra"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from datetime import datetime
from app import db
from app.models.usuario import (
    Orcamento, OrcamentoItem, OrcamentoCotacao, OrcamentoCotacaoItem, OrdemCompra,
    Veiculo, Fornecedor, OrdemServico,
    CatalogoServico, CatalogoMaterial, CatalogoImplemento,
    OSItemServico, OSItemMaterial, OSItemImplemento,
)
from app.services.negocio import gerar_numero_orc, gerar_numero_oc
from app.services import aprovacao_orcamento as svc_orc

bp = Blueprint('orcamentos', __name__, url_prefix='/orcamentos')


def _servicos_json():
    return [
        {'id': s.id, 'nome': s.nome,
         'valor_referencia': float(s.valor_referencia or 0),
         'tempo_estimado_h': float(s.tempo_estimado_h or 0)}
        for s in CatalogoServico.query.filter_by(ativo=True).order_by(CatalogoServico.nome).all()
    ]

def _materiais_json():
    return [
        {'id': m.id, 'nome': m.nome,
         'valor_referencia': float(m.valor_referencia or 0),
         'unidade': m.unidade}
        for m in CatalogoMaterial.query.filter_by(ativo=True).order_by(CatalogoMaterial.nome).all()
    ]

def _implementos_json():
    return [
        {'id': i.id, 'nome': i.nome,
         'valor_referencia': float(i.valor_referencia or 0),
         'fabricante': i.fabricante or ''}
        for i in CatalogoImplemento.query.filter_by(ativo=True).order_by(CatalogoImplemento.nome).all()
    ]


@bp.route('/')
@login_required
def lista():
    status   = request.args.get('status', '')
    tipo     = request.args.get('tipo', '')
    data_de  = request.args.get('data_de', '')
    data_ate = request.args.get('data_ate', '')
    q        = request.args.get('q', '').strip()
    page     = request.args.get('page', 1, type=int)
    query  = Orcamento.query.options(
        joinedload(Orcamento.veiculo),
        joinedload(Orcamento.solicitante),
        joinedload(Orcamento.os_vinculada),
        joinedload(Orcamento.cotacoes),
    )
    if status:
        query = query.filter_by(status=status)
    if tipo == 'servico':
        query = query.filter_by(tipo_solicitacao='aquisicao_servico')
    elif tipo == 'peca_os':
        query = query.filter_by(tipo_solicitacao='aquisicao_peca_os')
    elif tipo == 'peca_sem_os':
        query = query.filter_by(tipo_solicitacao='compra_peca_sem_os')
    if data_de:
        query = query.filter(Orcamento.data_solicitacao >= data_de)
    if data_ate:
        query = query.filter(Orcamento.data_solicitacao <= data_ate + ' 23:59:59')
    if q:
        query = query.join(Veiculo, Orcamento.veiculo_id == Veiculo.id).filter(
            db.or_(Orcamento.numero.ilike(f'%{q}%'), Veiculo.placa.ilike(f'%{q}%'),
                   Orcamento.descricao.ilike(f'%{q}%'))
        )
    orcs = query.order_by(Orcamento.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('orcamentos/lista.html', orcs=orcs, status=status, tipo=tipo,
                           data_de=data_de, data_ate=data_ate, q=q)


@bp.route('/<int:id>')
@login_required
def detalhe(id):
    o = (Orcamento.query
         .options(
             joinedload(Orcamento.veiculo),
             joinedload(Orcamento.solicitante),
             joinedload(Orcamento.aprovador),
             joinedload(Orcamento.os_vinculada),
             joinedload(Orcamento.itens).joinedload(OrcamentoItem.servico),
             joinedload(Orcamento.itens).joinedload(OrcamentoItem.material),
             joinedload(Orcamento.cotacoes).joinedload(OrcamentoCotacao.fornecedor),
         )
         .get_or_404(id))
    cotacao_aprovada = next((c for c in o.cotacoes if c.status == 'aprovada'), None)
    oc = OrdemCompra.query.filter_by(orcamento_id=id).first()
    return render_template('orcamentos/detalhe.html', o=o,
                           cotacao_aprovada=cotacao_aprovada, oc=oc)



@bp.route('/novo-da-os/<int:os_id>', methods=['GET', 'POST'])
@login_required
def novo_da_os(os_id):
    """Cria orçamento de peça já vinculado a uma OS específica."""
    os_obj = OrdemServico.query.get_or_404(os_id)
    veiculos       = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    fornecedores   = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    ordens_abertas = OrdemServico.query.filter(
        OrdemServico.status.in_(['aberta', 'em_execucao', 'aguardando_peca'])
    ).order_by(OrdemServico.numero.desc()).all()

    if request.method == 'POST':
        f = request.form
        try:
            o = Orcamento(
                numero=gerar_numero_orc(),
                veiculo_id=os_obj.veiculo_id,
                fornecedor_id=f.get('fornecedor_id') or None,
                tipo_os='externa',
                tipo_solicitacao='aquisicao_peca_os',
                os_vinculada_id=os_id,
                descricao=f['descricao'],
                status='em_elaboracao',
                solicitado_por=current_user.id,
                observacoes=f.get('observacoes'),
            )
            db.session.add(o)
            db.session.flush()
            total = _salvar_itens(o.id, f)
            o.valor_total_estimado = total
            db.session.commit()
            flash(f'Orçamento {o.numero} criado e vinculado à {os_obj.numero}. Agora cadastre as cotações.', 'success')
            return redirect(url_for('orcamentos.detalhe', id=o.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar orçamento: {e}', 'danger')

    return render_template('orcamentos/form.html',
        os_fixada=os_obj,
        veiculos=veiculos, fornecedores=fornecedores, ordens_abertas=ordens_abertas,
        servicos=_servicos_json(), materiais=_materiais_json(), implementos=_implementos_json())


@bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    veiculos       = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    fornecedores   = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    ordens_abertas = OrdemServico.query.filter(
        OrdemServico.status.in_(['aberta', 'em_execucao', 'aguardando_peca'])
    ).order_by(OrdemServico.numero.desc()).all()
    if request.method == 'POST':
        f = request.form
        tipo_sol   = f.get('tipo_solicitacao', 'aquisicao_servico')
        os_vinc_id = f.get('os_vinculada_id') or None

        if tipo_sol == 'aquisicao_peca_os' and not os_vinc_id:
            flash('Para "Peça para OS", é obrigatório informar a OS vinculada.', 'danger')
            return render_template('orcamentos/form.html',
                veiculos=veiculos, fornecedores=fornecedores, ordens_abertas=ordens_abertas,
                servicos=_servicos_json(), materiais=_materiais_json(), implementos=_implementos_json())
        if tipo_sol not in ('aquisicao_servico', 'aquisicao_peca_os', 'compra_peca_sem_os'):
            tipo_sol = 'aquisicao_servico'
        try:
            o = Orcamento(
                numero=gerar_numero_orc(),
                veiculo_id=int(f['veiculo_id']),
                fornecedor_id=f.get('fornecedor_id') or None,
                tipo_os=f.get('tipo_os', 'externa'),
                tipo_solicitacao=tipo_sol,
                os_vinculada_id=int(os_vinc_id) if os_vinc_id else None,
                descricao=f['descricao'],
                status='em_elaboracao',
                solicitado_por=current_user.id,
                observacoes=f.get('observacoes'),
            )
            db.session.add(o)
            db.session.flush()
            total = _salvar_itens(o.id, f)
            o.valor_total_estimado = total
            db.session.commit()
            flash(f'Orçamento {o.numero} criado. Agora cadastre as cotações dos fornecedores.', 'success')
            return redirect(url_for('orcamentos.detalhe', id=o.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar orçamento: {e}', 'danger')

    return render_template('orcamentos/form.html',
        veiculos=veiculos, fornecedores=fornecedores, ordens_abertas=ordens_abertas,
        servicos=_servicos_json(), materiais=_materiais_json(), implementos=_implementos_json())


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    o = Orcamento.query.get_or_404(id)
    if o.status not in ('em_elaboracao', 'rascunho'):
        flash('Somente orçamentos em elaboração podem ser editados.', 'warning')
        return redirect(url_for('orcamentos.detalhe', id=id))

    veiculos       = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()
    fornecedores   = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
    ordens_abertas = OrdemServico.query.filter(
        OrdemServico.status.in_(['aberta', 'em_execucao', 'aguardando_peca'])
    ).order_by(OrdemServico.numero.desc()).all()

    if request.method == 'POST':
        f = request.form
        tipo_sol   = f.get('tipo_solicitacao', 'aquisicao_servico')
        os_vinc_id = f.get('os_vinculada_id') or None
        if tipo_sol == 'aquisicao_peca_os' and not os_vinc_id:
            flash('Para "Peça para OS", é obrigatório informar a OS vinculada.', 'danger')
            return render_template('orcamentos/form.html', o=o,
                veiculos=veiculos, fornecedores=fornecedores, ordens_abertas=ordens_abertas,
                servicos=_servicos_json(), materiais=_materiais_json(), implementos=_implementos_json())
        if tipo_sol not in ('aquisicao_servico', 'aquisicao_peca_os', 'compra_peca_sem_os'):
            tipo_sol = 'aquisicao_servico'
        try:
            o.veiculo_id       = int(f['veiculo_id'])
            o.fornecedor_id    = f.get('fornecedor_id') or None
            o.tipo_os          = f.get('tipo_os', 'externa')
            o.tipo_solicitacao = tipo_sol
            o.os_vinculada_id  = int(os_vinc_id) if os_vinc_id else None
            o.descricao        = f['descricao']
            o.observacoes      = f.get('observacoes')
            for item in o.itens:
                db.session.delete(item)
            db.session.flush()
            o.valor_total_estimado = _salvar_itens(o.id, f)
            db.session.commit()
            flash('Orçamento atualizado.', 'success')
            return redirect(url_for('orcamentos.detalhe', id=o.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('orcamentos/form.html', o=o,
        veiculos=veiculos, fornecedores=fornecedores, ordens_abertas=ordens_abertas,
        servicos=_servicos_json(), materiais=_materiais_json(), implementos=_implementos_json())


# ── COTAÇÕES ──────────────────────────────────────────────

@bp.route('/<int:id>/cotacoes/ler-pdf', methods=['POST'])
@login_required
def ler_pdf_cotacao(id):
    """Lê PDF do fornecedor via Claude API e extrai itens com valores finais."""
    import base64, json, os, requests as req_http
    o = Orcamento.query.get_or_404(id)
    arquivo = request.files.get('pdf_arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify({'ok': False, 'erro': 'Nenhum arquivo enviado.'}), 400

    conteudo = arquivo.read()
    b64 = base64.standard_b64encode(conteudo).decode('utf-8')

    # Monta lista dos itens do orçamento para o Claude comparar
    itens_orc = []
    for item in o.itens:
        if item.tipo_item in ('material', 'implemento'):
            nome = (item.material.nome if item.material
                    else item.descricao_livre or 'Item')
            itens_orc.append({
                'id': item.id,
                'descricao': nome,
                'quantidade': float(item.quantidade or 1),
                'valor_unitario_orc': float(item.valor_unitario or 0),
            })

    prompt = f"""Você receberá um PDF de orçamento/proposta de fornecedor de peças automotivas.

Os itens do orçamento interno que precisam ser encontrados no PDF são:
{json.dumps(itens_orc, ensure_ascii=False, indent=2)}

Sua tarefa:
1. Encontre cada item da lista acima no PDF (por similaridade de descrição)
2. Extraia o VALOR FINAL (com desconto já aplicado, coluna P.Final ou similar)
3. Use o valor unitário final = P.Final / quantidade

Responda SOMENTE com JSON válido, sem texto antes ou depois, neste formato exato:
{{
  "itens": [
    {{
      "orcamento_item_id": <id do item>,
      "descricao": "<descricao encontrada no PDF>",
      "quantidade": <qtd>,
      "valor_unitario": <valor unitario final com desconto>
    }}
  ],
  "observacoes": "<qualquer observação relevante, ex: itens não encontrados>"
}}

Se um item do orçamento não for encontrado no PDF, inclua-o mesmo assim com o valor_unitario = 0."""

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({
            'ok': False,
            'erro': 'ANTHROPIC_API_KEY não configurada no ambiente. '
                    'Configure a variável de ambiente no Render para habilitar a leitura automática de PDF.'
        }), 500

    try:
        resp = req_http.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': 'claude-sonnet-4-6',
                'max_tokens': 2000,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'document',
                            'source': {
                                'type': 'base64',
                                'media_type': 'application/pdf',
                                'data': b64,
                            }
                        },
                        {'type': 'text', 'text': prompt}
                    ]
                }]
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        texto = data['content'][0]['text'].strip()
        # Remove possíveis blocos de código markdown
        if texto.startswith('```'):
            texto = texto.split('```')[1]
            if texto.startswith('json'):
                texto = texto[4:]
        resultado = json.loads(texto)
        return jsonify({'ok': True, 'itens': resultado.get('itens', []),
                        'observacoes': resultado.get('observacoes', '')})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500


@bp.route('/<int:id>/cotacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_cotacao(id):
    o = Orcamento.query.get_or_404(id)
    if o.status not in ('em_elaboracao', 'rascunho', 'aguardando_cotacao'):
        flash('Não é possível adicionar cotações neste status.', 'warning')
        return redirect(url_for('orcamentos.detalhe', id=id))

    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()

    if request.method == 'POST':
        f = request.form
        try:
            # Upload do arquivo da proposta para o SharePoint
            anexo_url = f.get('anexo_url', '').strip()
            arquivo = request.files.get('anexo_arquivo')
            if arquivo and arquivo.filename:
                from app.services.sharepoint_upload import upload_foto_os, validar_arquivo, _sanitizar_nome
                nome_safe = _sanitizar_nome(arquivo.filename)
                ok_val, erro_val = validar_arquivo(nome_safe, arquivo.mimetype)
                if not ok_val:
                    flash(f'Arquivo inválido: {erro_val}', 'danger')
                    fornecedores = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.razao_social).all()
                    return render_template('orcamentos/cotacao_form.html', o=o, fornecedores=fornecedores)
                conteudo = arquivo.read()
                fornecedor = Fornecedor.query.get(int(f['fornecedor_id']))
                fornecedor_nome = re.sub(r'[^\w]', '_', fornecedor.razao_social[:30]) if fornecedor else 'FORNECEDOR'
                resultado = upload_foto_os(
                    os_numero=f'ORC-{o.numero}-{fornecedor_nome}',
                    veiculo_placa=o.veiculo.placa if o.veiculo else 'SEM_PLACA',
                    filename=nome_safe,
                    content=conteudo,
                    mime_type=arquivo.mimetype or 'application/octet-stream',
                )
                if resultado.get('ok'):
                    anexo_url = resultado['url']
                else:
                    flash(f'Aviso: arquivo não enviado ao SharePoint ({resultado.get("erro")}). Cotação salva sem anexo.', 'warning')

            cot = OrcamentoCotacao(
                orcamento_id=id,
                fornecedor_id=int(f['fornecedor_id']),
                valor=float(f['valor'].replace('.', '').replace(',', '.')),
                prazo_dias=int(f['prazo_dias']) if f.get('prazo_dias') else None,
                condicoes=f.get('condicoes'),
                observacoes=f.get('observacoes'),
                anexo_url=anexo_url or None,
                status='pendente',
                cadastrada_por=current_user.id,
            )
            db.session.add(cot)
            db.session.flush()

            # ── Salva itens detalhados da cotação (valores reais por peça) ──
            _salvar_itens_cotacao(cot.id, f)

            if o.status in ('em_elaboracao', 'rascunho'):
                o.status = 'aguardando_cotacao'
            db.session.commit()
            flash('Cotação cadastrada com sucesso.', 'success')
            return redirect(url_for('orcamentos.detalhe', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar cotação: {e}', 'danger')

    return render_template('orcamentos/cotacao_form.html', o=o, fornecedores=fornecedores)


@bp.route('/<int:id>/cotacoes/<int:cot_id>/excluir', methods=['POST'])
@login_required
def excluir_cotacao(id, cot_id):
    o   = Orcamento.query.get_or_404(id)
    cot = OrcamentoCotacao.query.get_or_404(cot_id)
    if cot.orcamento_id != id or cot.status == 'aprovada':
        flash('Operação não permitida.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))
    db.session.delete(cot)
    db.session.flush()
    remaining = OrcamentoCotacao.query.filter_by(orcamento_id=id).count()
    if remaining == 0:
        o.status = 'em_elaboracao'
    db.session.commit()
    flash('Cotação excluída.', 'info')
    return redirect(url_for('orcamentos.detalhe', id=id))


@bp.route('/<int:id>/itens/<int:item_id>/excluir', methods=['POST'])
@login_required
def excluir_item(id, item_id):
    """Remove um item do orçamento — permitido até o status 'em_aprovacao'."""
    o    = Orcamento.query.get_or_404(id)
    item = OrcamentoItem.query.get_or_404(item_id)

    if item.orcamento_id != id:
        flash('Item não pertence a este orçamento.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))

    BLOQUEADOS = ('em_aprovacao', 'aprovado', 'cancelado', 'reprovado')
    if o.status in BLOQUEADOS:
        flash('Não é possível remover itens neste estágio do orçamento.', 'warning')
        return redirect(url_for('orcamentos.detalhe', id=id))

    try:
        db.session.delete(item)
        db.session.flush()
        # Recalcula total
        o.valor_total_estimado = sum(
            float(i.quantidade or 1) * float(i.valor_unitario or 0)
            for i in OrcamentoItem.query.filter_by(orcamento_id=id).all()
        )
        db.session.commit()
        flash('Item removido do orçamento.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover item: {e}', 'danger')

    return redirect(url_for('orcamentos.detalhe', id=id))


def _transferir_itens_para_os(orc, os_obj, cotacao):
    """
    Copia os itens do orçamento aprovado direto para a OS vinculada.
    Chamada apenas quando tipo_solicitacao == 'aquisicao_peca_os'.
    Usa TAG no descricao_livre para evitar duplicatas.

    Prioridade de valor:
      1. Itens detalhados da cotação (OrcamentoCotacaoItem) — valor real negociado
      2. Fator proporcional (valor_cotacao / total_orc) — fallback para cotações antigas
    Retorna o número de itens transferidos.
    """
    if not orc.itens:
        return 0

    TAG = f'[ORC {orc.numero}]'

    # Anti-duplicata
    ja_existe = (
        OSItemServico.query.filter(
            OSItemServico.os_id == os_obj.id,
            OSItemServico.descricao_livre.like(f'%{TAG}%')
        ).first()
        or OSItemMaterial.query.filter(
            OSItemMaterial.os_id == os_obj.id,
            OSItemMaterial.descricao_livre.like(f'%{TAG}%')
        ).first()
    )
    if ja_existe:
        return 0

    # ── Monta índice de valores reais por item da cotação ─────────────
    # {orcamento_item_id: valor_unitario_real}
    valores_reais = {}
    if cotacao.itens:
        for ci in cotacao.itens:
            if ci.orcamento_item_id and float(ci.valor_unitario or 0) > 0:
                valores_reais[ci.orcamento_item_id] = float(ci.valor_unitario)

    # ── Fallback: fator proporcional ──────────────────────────────────
    total_orc = sum(
        float(item.quantidade or 1) * float(item.valor_unitario or 0)
        for item in orc.itens
    )
    valor_cotacao  = float(cotacao.valor or 0)
    fator_desconto = (valor_cotacao / total_orc) if total_orc > 0 else 1.0

    fornecedor_nome = cotacao.fornecedor.razao_social if cotacao.fornecedor else None
    transferidos    = 0

    for item in orc.itens:
        qtd = float(item.quantidade or 1)

        # Usa valor real da cotação se disponível, senão aplica fator
        if item.id in valores_reais:
            val = valores_reais[item.id]
        else:
            val = round(float(item.valor_unitario or 0) * fator_desconto, 2)

        if item.tipo_item == 'servico':
            db.session.add(OSItemServico(
                os_id           = os_obj.id,
                servico_id      = item.servico_id,
                descricao_livre = (f'{item.descricao_livre or "Serviço"} {TAG}'
                                   if not item.servico_id else TAG),
                quantidade      = qtd,
                valor_unitario  = val,
                executado_por   = fornecedor_nome,
            ))
            transferidos += 1

        elif item.tipo_item == 'material':
            db.session.add(OSItemMaterial(
                os_id           = os_obj.id,
                material_id     = item.material_id,
                descricao_livre = (f'{item.descricao_livre or "Material"} {TAG}'
                                   if not item.material_id else TAG),
                quantidade      = qtd,
                valor_unitario  = val,
            ))
            transferidos += 1

        elif item.tipo_item == 'implemento':
            imp_id = getattr(item, 'implemento_id', None)
            db.session.add(OSItemImplemento(
                os_id           = os_obj.id,
                implemento_id   = imp_id,
                descricao_livre = (f'{item.descricao_livre or "Implemento"} {TAG}'
                                   if not imp_id else TAG),
                quantidade      = qtd,
                valor_unitario  = val,
            ))
            transferidos += 1

    return transferidos


@bp.route('/<int:id>/cotacoes/<int:cot_id>/aprovar', methods=['POST'])
@login_required
def aprovar_cotacao(id, cot_id):
    if not current_user.pode_aprovar:
        flash('Sem permissão para aprovar.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))

    o   = Orcamento.query.get_or_404(id)
    cot = OrcamentoCotacao.query.get_or_404(cot_id)

    if cot.orcamento_id != id:
        flash('Cotação inválida.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))

    cotacoes_pendentes = [c for c in o.cotacoes if c.status == 'pendente']
    if not cotacoes_pendentes:
        flash('Nenhuma cotação disponível para aprovação.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))

    justificativa = request.form.get('justificativa', '').strip()

    # Se não for a mais barata, exige justificativa
    menor_valor = min(float(c.valor) for c in o.cotacoes if c.status != 'recusada')
    if float(cot.valor) > menor_valor and not justificativa:
        flash('Esta não é a proposta de menor valor. Informe uma justificativa para a escolha.', 'warning')
        return redirect(url_for('orcamentos.detalhe', id=id))

    try:
        agora = datetime.utcnow()
        for c in o.cotacoes:
            if c.id == cot_id:
                c.status       = 'aprovada'
                c.aprovada_por = current_user.id
                c.aprovada_em  = agora
                c.justificativa= justificativa
            elif c.status == 'pendente':
                c.status = 'recusada'

        o.status        = 'aprovado'
        o.aprovado_por  = current_user.id
        o.data_aprovacao= agora

        oc = OrdemCompra(
            numero=gerar_numero_oc(),
            orcamento_id=id,
            cotacao_id=cot_id,
            os_id=o.os_vinculada_id,
            fornecedor_id=cot.fornecedor_id,
            valor_total=cot.valor,
            prazo_dias=cot.prazo_dias,
            condicoes=cot.condicoes,
            observacoes=cot.observacoes,
            status='gerada',
            gerada_por=current_user.id,
            gerada_em=agora,
        )
        db.session.add(oc)

        # ── Transfere itens automaticamente para a OS vinculada ──
        itens_transferidos = 0
        if o.os_vinculada_id:
            os_vinc = OrdemServico.query.get(o.os_vinculada_id)
            if os_vinc and os_vinc.status not in ('concluida', 'cancelada'):
                itens_transferidos = _transferir_itens_para_os(o, os_vinc, cot)

        db.session.commit()

        msg = f'Cotação aprovada! Ordem de Compra {oc.numero} gerada automaticamente.'
        if itens_transferidos:
            msg += f' ✓ {itens_transferidos} item(ns) adicionado(s) direto na OS vinculada.'
        flash(msg, 'success')

        # Notifica Financeiro para solicitar pagamento
        try:
            from app.services.financeiro import notificar_financeiro_oc_aprovada
            notificar_financeiro_oc_aprovada(oc)
        except Exception as e_fin:
            import logging
            logging.getLogger(__name__).warning(f'Notif. financeiro OC {oc.numero} falhou: {e_fin}')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar cotação: {e}', 'danger')

    return redirect(url_for('orcamentos.detalhe', id=id))


# ── ORDENS DE COMPRA ──────────────────────────────────────

@bp.route('/ordens-compra/')
@login_required
def lista_oc():
    status   = request.args.get('status', '')
    data_de  = request.args.get('data_de', '')
    data_ate = request.args.get('data_ate', '')
    q        = request.args.get('q', '').strip()
    page     = request.args.get('page', 1, type=int)
    query  = OrdemCompra.query.options(
        joinedload(OrdemCompra.orcamento),
        joinedload(OrdemCompra.fornecedor),
        joinedload(OrdemCompra.os),
    )
    if status:
        query = query.filter_by(status=status)
    if data_de:
        query = query.filter(OrdemCompra.gerada_em >= data_de)
    if data_ate:
        query = query.filter(OrdemCompra.gerada_em <= data_ate + ' 23:59:59')
    if q:
        query = query.join(Fornecedor, OrdemCompra.fornecedor_id == Fornecedor.id).filter(
            db.or_(OrdemCompra.numero.ilike(f'%{q}%'), Fornecedor.razao_social.ilike(f'%{q}%'))
        )
    ocs = query.order_by(OrdemCompra.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('orcamentos/oc_lista.html', ocs=ocs, status=status,
                           data_de=data_de, data_ate=data_ate, q=q)


@bp.route('/ordens-compra/<int:oc_id>')
@login_required
def detalhe_oc(oc_id):
    oc = OrdemCompra.query.get_or_404(oc_id)
    return render_template('orcamentos/oc_detalhe.html', oc=oc)


@bp.route('/ordens-compra/<int:oc_id>/status', methods=['POST'])
@login_required
def atualizar_status_oc(oc_id):
    oc = OrdemCompra.query.get_or_404(oc_id)
    novo = request.form.get('status')
    validos = ('enviada_fornecedor', 'em_aquisicao', 'finalizada', 'cancelada')
    if novo not in validos:
        flash('Status inválido.', 'danger')
        return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))
    oc.status = novo
    if novo == 'enviada_fornecedor':
        oc.enviada_em = datetime.utcnow()
    elif novo == 'finalizada':
        oc.finalizada_em    = datetime.utcnow()
        oc.comprovante_url  = request.form.get('comprovante_url') or oc.comprovante_url
    db.session.commit()
    flash(f'Status da OC atualizado para "{oc.status_label}".', 'success')
    return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))


# ── SOLICITAR / CANCELAR / REJEITAR (legado) ──────────────

@bp.route('/<int:id>/solicitar', methods=['POST'])
@login_required
def solicitar(id):
    o = Orcamento.query.get_or_404(id)
    if o.status not in ('em_elaboracao', 'rascunho', 'aguardando_cotacao'):
        flash('Orçamento já foi enviado para aprovação.', 'warning')
    elif not o.cotacoes:
        flash('Cadastre ao menos 1 cotação antes de enviar para aprovação.', 'danger')
    else:
        o.status = 'em_aprovacao'
        db.session.commit()
        try:
            svc_orc.solicitar_aprovacao(o)
        except Exception as e_mail:
            import logging
            logging.getLogger(__name__).warning(f'E-mail aprovação ORC falhou: {e_mail}')
        flash('Orçamento enviado para aprovação.', 'info')
    return redirect(url_for('orcamentos.detalhe', id=id))


@bp.route('/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar(id):
    o = Orcamento.query.get_or_404(id)
    o.status = 'cancelado'
    db.session.commit()
    flash('Orçamento cancelado.', 'warning')
    return redirect(url_for('orcamentos.detalhe', id=id))


@bp.route('/<int:id>/rejeitar', methods=['POST'])
@login_required
def rejeitar(id):
    if not current_user.pode_aprovar:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.detalhe', id=id))
    o = Orcamento.query.get_or_404(id)
    motivo = request.form.get('motivo', '')
    svc_orc.registrar_rejeicao(o, current_user, motivo)
    flash('Orçamento rejeitado.', 'warning')
    return redirect(url_for('orcamentos.detalhe', id=id))


# ── HELPER ────────────────────────────────────────────────

def _salvar_itens(orcamento_id, form):
    total = 0
    i = 0
    while True:
        tipo = form.get(f'item_tipo_{i}')
        if tipo is None:
            break
        try:
            qty = float(form.get(f'item_qty_{i}') or 1)
            val = float(form.get(f'item_val_{i}') or 0)
        except (ValueError, TypeError):
            qty, val = 1.0, 0.0
        sid  = form.get(f'item_servico_id_{i}')   or None
        mid  = form.get(f'item_material_id_{i}')   or None
        iid  = form.get(f'item_implemento_id_{i}') or None
        desc = form.get(f'item_desc_{i}')           or None
        mat_id = mid or iid
        item = OrcamentoItem(
            orcamento_id    = orcamento_id,
            tipo_item       = tipo,
            servico_id      = int(sid)    if sid    and sid.isdigit()    else None,
            material_id     = int(mat_id) if mat_id and mat_id.isdigit() else None,
            descricao_livre = desc,
            quantidade      = qty,
            valor_unitario  = val,
        )
        db.session.add(item)
        total += qty * val
        i += 1
    return total


def _salvar_itens_cotacao(cotacao_id, form):
    """Salva os itens detalhados de uma cotação (valores reais por peça)."""
    i = 0
    while True:
        orc_item_id = form.get(f'cot_item_orc_id_{i}')
        if orc_item_id is None:
            break
        desc = form.get(f'cot_item_desc_{i}', '')
        try:
            qty = float(form.get(f'cot_item_qty_{i}') or 1)
            val = float(
                (form.get(f'cot_item_val_{i}') or '0')
                .replace('.', '').replace(',', '.')
            )
        except (ValueError, TypeError):
            qty, val = 1.0, 0.0

        if desc or val > 0:
            ci = OrcamentoCotacaoItem(
                cotacao_id        = cotacao_id,
                orcamento_item_id = int(orc_item_id) if orc_item_id and str(orc_item_id).isdigit() else None,
                descricao         = desc or 'Item',
                quantidade        = qty,
                valor_unitario    = val,
            )
            db.session.add(ci)
        i += 1


# ── PDF DA ORDEM DE COMPRA ────────────────────────────────

@bp.route('/ordens-compra/<int:oc_id>/pdf')
@login_required
def pdf_oc(oc_id):
    """Gera e retorna o PDF da Ordem de Compra."""
    from flask import send_file
    from app.services.pdf_oc import gerar_pdf_oc
    oc = OrdemCompra.query.get_or_404(oc_id)
    try:
        buf = gerar_pdf_oc(oc)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'{oc.numero}.pdf',
        )
    except Exception as e:
        flash(f'Erro ao gerar PDF: {e}', 'danger')
        return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))


# ── UPLOAD AVULSO DA NOTA FISCAL ─────────────────────────

@bp.route('/ordens-compra/<int:oc_id>/upload-nf', methods=['POST'])
@login_required
def upload_nf_oc(oc_id):
    """Faz upload avulso da nota fiscal de uma OC e salva no SharePoint."""
    oc = OrdemCompra.query.get_or_404(oc_id)
    arquivo = request.files.get('nota_fiscal_arquivo')

    if not arquivo or not arquivo.filename:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))

    try:
        from app.services.sharepoint_upload import upload_foto_os, validar_arquivo, _sanitizar_nome
        nome_safe = _sanitizar_nome(arquivo.filename)
        ok_val, erro_val = validar_arquivo(nome_safe, arquivo.mimetype)
        if not ok_val:
            flash(f'Arquivo inválido: {erro_val}', 'danger')
            return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))

        conteudo = arquivo.read()
        resultado = upload_foto_os(
            os_numero=f'NF-{oc.numero}',
            veiculo_placa=oc.orcamento.veiculo.placa if oc.orcamento and oc.orcamento.veiculo else 'SEM_PLACA',
            filename=nome_safe,
            content=conteudo,
            mime_type=arquivo.mimetype or 'application/pdf',
        )
        if resultado.get('ok'):
            oc.nota_fiscal_url           = resultado['url']
            oc.nota_fiscal_nome          = nome_safe
            oc.nota_fiscal_sharepoint_id = resultado.get('sharepoint_id') or resultado.get('id')
            db.session.commit()
            flash('Nota fiscal enviada com sucesso.', 'success')
        else:
            flash(f'Erro ao enviar NF ao SharePoint: {resultado.get("erro")}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar upload: {e}', 'danger')

    return redirect(url_for('orcamentos.detalhe_oc', oc_id=oc_id))
