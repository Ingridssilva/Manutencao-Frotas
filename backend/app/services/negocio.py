"""
Serviços de negócio — alertas, numeração, km, plano PDF
"""
from datetime import date, timedelta
from sqlalchemy import text
from app import db
from app.models.usuario import (
    Veiculo, Motorista, CRLV, LaudoAcustico, Tacografo, SeguroVeiculo,
    PlanoManutencao, Alerta, OrdemServico, Orcamento, LogKm, DisponibilidadeDiaria
)

# ─────────────────────────────────────────────
#  NUMERAÇÃO SEQUENCIAL (atômica, sem race condition)
# ─────────────────────────────────────────────
# Antes: "busca o último número → soma 1" — se dois usuários criassem uma OS/
# orçamento/OC ao mesmo tempo, ambos podiam calcular o mesmo próximo número
# (só a constraint UNIQUE no banco evitava duplicata, mas um dos dois recebia
# um erro genérico sem entender o motivo).
#
# Agora usamos uma tabela de contadores (contadores_sequencia) com
# INSERT ... ON CONFLICT DO UPDATE ... RETURNING, que o Postgres executa de
# forma atômica (row-lock implícito do upsert) — elimina a corrida mesmo com
# requisições concorrentes. Requer rodar backend/add_contador_sequencia.py
# uma vez (cria a tabela), igual aos outros scripts de migração do projeto.
def _proximo_numero_sequencial(prefixo: str) -> int:
    ano = date.today().year
    chave = f'{prefixo}-{ano}'
    resultado = db.session.execute(text("""
        INSERT INTO contadores_sequencia (chave, valor)
        VALUES (:chave, 1)
        ON CONFLICT (chave) DO UPDATE SET valor = contadores_sequencia.valor + 1
        RETURNING valor
    """), {'chave': chave}).first()
    return resultado[0]


def gerar_numero_os():
    ano = date.today().year
    seq = _proximo_numero_sequencial('OS')
    return f'OS-{ano}-{seq:04d}'

def gerar_numero_orc():
    ano = date.today().year
    seq = _proximo_numero_sequencial('ORC')
    return f'ORC-{ano}-{seq:04d}'

def gerar_numero_oc():
    ano = date.today().year
    seq = _proximo_numero_sequencial('OC')
    return f'OC-{ano}-{seq:04d}'

# ─────────────────────────────────────────────
#  ATUALIZAÇÃO DE KM
# ─────────────────────────────────────────────
def registrar_km(veiculo_id, km_novo, origem='manual', referencia_id=None, user_id=None):
    v = Veiculo.query.get(veiculo_id)
    if not v or km_novo <= v.km_atual:
        return False

    log = LogKm(
        veiculo_id=veiculo_id,
        km_anterior=v.km_atual,
        km_novo=km_novo,
        origem=origem,
        referencia_id=referencia_id,
        registrado_por=user_id,
    )
    v.km_atual = km_novo
    db.session.add(log)
    db.session.flush()
    _checar_alertas_km(v)
    return True

def _checar_alertas_km(veiculo):
    planos = PlanoManutencao.query.filter_by(
        veiculo_id=veiculo.id, ativo=True
    ).all()
    for p in planos:
        if p.gatilho_tipo not in ('km', 'ambos'):
            continue
        if p.proximo_km and veiculo.km_atual >= (p.proximo_km - p.alerta_km_antes):
            # evita duplicar alerta recente
            existe = Alerta.query.filter_by(
                veiculo_id=veiculo.id,
                tipo='preventiva_km',
                lido=False
            ).filter(Alerta.created_at >= date.today() - timedelta(days=7)).first()
            if not existe:
                nivel = 'critico' if veiculo.km_atual >= p.proximo_km else 'atencao'
                db.session.add(Alerta(
                    tipo='preventiva_km',
                    veiculo_id=veiculo.id,
                    titulo=f'Manutenção preventiva — {p.servico.nome}',
                    mensagem=(f'Veículo {veiculo.placa} atingiu km próximo ao '
                              f'limite de manutenção ({p.proximo_km} km).'),
                    nivel=nivel,
                ))

# ─────────────────────────────────────────────
#  POPULAR DISPONIBILIDADE DO DIA
# ─────────────────────────────────────────────
def popular_disponibilidade_hoje():
    hoje = date.today()
    veiculos = Veiculo.query.filter_by(status='ativo').all()
    if not veiculos:
        return 0

    # Checagem rápida: se todos os veículos ativos já têm registro hoje,
    # sai sem tocar mais no banco. Evita custo repetido em chamadas frequentes
    # (ex: tela de indicadores, que consulta essa função a cada carregamento).
    ids_com_registro = {
        vid for (vid,) in db.session.query(DisponibilidadeDiaria.veiculo_id)
            .filter(DisponibilidadeDiaria.data == hoje).all()
    }
    faltantes = [v for v in veiculos if v.id not in ids_com_registro]
    if not faltantes:
        return 0

    inseridos = 0
    for v in faltantes:
        # Verifica se há plano de manutenção vencido ou previsto para hoje
        plano_pendente = PlanoManutencao.query.filter_by(
            veiculo_id=v.id, ativo=True
        ).filter(
            PlanoManutencao.proxima_data <= hoje
        ).first()

        em_manutencao = plano_pendente is not None
        motivo = (
            f'Plano de manutenção — {plano_pendente.servico.nome}'
            if em_manutencao else None
        )

        db.session.add(DisponibilidadeDiaria(
            veiculo_id=v.id,
            data=hoje,
            disponivel=not em_manutencao,
            motivo_indisponibilidade=motivo,
        ))
        inseridos += 1
    db.session.commit()
    return inseridos

# ─────────────────────────────────────────────
#  VARREDURA DIÁRIA DE VENCIMENTOS
# ─────────────────────────────────────────────
def varrer_vencimentos():
    hoje = date.today()

    from flask import current_app
    cfg = current_app.config

    def _alerta(tipo, veiculo_id, titulo, msg, nivel, mot_id=None):
        existe = Alerta.query.filter_by(
            veiculo_id=veiculo_id, tipo=tipo, lido=False
        ).first()
        if not existe:
            db.session.add(Alerta(
                tipo=tipo, veiculo_id=veiculo_id, motorista_id=mot_id,
                titulo=titulo, mensagem=msg, nivel=nivel,
            ))

    # CRLV
    for crlv in CRLV.query.filter(
        CRLV.data_vencimento <= hoje + timedelta(days=cfg['ALERTA_DIAS_CRLV'])
    ).all():
        dias = (crlv.data_vencimento - hoje).days
        nivel = 'critico' if dias <= 15 else 'atencao'
        _alerta('crlv_vencendo', crlv.veiculo_id,
                f'CRLV vencendo — {crlv.veiculo.placa}',
                f'CRLV vence em {dias} dias ({crlv.data_vencimento}).', nivel)

    # Laudos acústicos
    for laudo in (LaudoAcustico.query
                  .filter(LaudoAcustico.data_vencimento <= hoje + timedelta(days=cfg['ALERTA_DIAS_LAUDO']))
                  .all()):
        dias = (laudo.data_vencimento - hoje).days
        nivel = 'critico' if dias <= 10 else 'atencao'
        _alerta('laudo_vencendo', laudo.veiculo_id,
                f'Laudo acústico vencendo — {laudo.veiculo.placa}',
                f'Laudo vence em {dias} dias ({laudo.data_vencimento}).', nivel)

    # Tacógrafo
    for tac in (Tacografo.query
                .filter(Tacografo.data_proxima_calibracao <= hoje + timedelta(days=cfg['ALERTA_DIAS_TACOGRAFO']))
                .all()):
        dias = (tac.data_proxima_calibracao - hoje).days
        nivel = 'critico' if dias <= 10 else 'atencao'
        _alerta('tacografo_vencendo', tac.veiculo_id,
                f'Calibração tacógrafo — {tac.veiculo.placa}',
                f'Calibração vence em {dias} dias.', nivel)

    # Seguro
    for seg in (SeguroVeiculo.query
                .filter(SeguroVeiculo.status == 'ativo')
                .filter(SeguroVeiculo.data_vencimento <= hoje + timedelta(days=cfg['ALERTA_DIAS_SEGURO']))
                .all()):
        dias = (seg.data_vencimento - hoje).days
        nivel = 'critico' if dias <= 15 else 'atencao'
        _alerta('seguro_vencendo', seg.veiculo_id,
                f'Seguro vencendo — {seg.veiculo.placa}',
                f'Apólice vence em {dias} dias.', nivel)

    # CNH motoristas
    for mot in (Motorista.query
                .filter(Motorista.ativo == True)
                .filter(Motorista.cnh_validade <= hoje + timedelta(days=cfg['ALERTA_DIAS_CNH']))
                .all()):
        dias = (mot.cnh_validade - hoje).days
        nivel = 'critico' if dias <= 15 else 'atencao'
        vid = mot.veiculo_principal_id
        _alerta('cnh_vencendo', vid,
                f'CNH vencendo — {mot.nome}',
                f'CNH de {mot.nome} vence em {dias} dias.', nivel, mot_id=mot.id)

    # Preventiva por data — cada plano usa seu próprio alerta_dias_antes
    planos_data = (PlanoManutencao.query
                   .filter(PlanoManutencao.ativo == True)
                   .filter(PlanoManutencao.gatilho_tipo.in_(['dias', 'ambos']))
                   .filter(PlanoManutencao.proxima_data.isnot(None))
                   .all())
    for plano in planos_data:
        if plano.proxima_data > hoje + timedelta(days=plano.alerta_dias_antes):
            continue
        dias = (plano.proxima_data - hoje).days
        nivel = 'critico' if dias <= 5 else 'atencao'
        existe = Alerta.query.filter_by(
            veiculo_id=plano.veiculo_id, tipo='preventiva_data', lido=False
        ).filter(Alerta.created_at >= hoje - timedelta(days=3)).first()
        if not existe:
            db.session.add(Alerta(
                tipo='preventiva_data',
                veiculo_id=plano.veiculo_id,
                titulo=f'Preventiva por data — {plano.servico.nome}',
                mensagem=f'Manutenção prevista para {plano.proxima_data} ({dias} dias).',
                nivel=nivel,
            ))

    db.session.commit()
