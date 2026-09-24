"""Dashboard principal — com cache de 3 minutos para reduzir carga no BD"""
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import text
from datetime import date, timedelta
from app import db, cache
from app.models.usuario import Veiculo, OrdemServico, Motorista, Alerta, CRLV, Pneu, PneuVeiculo, DisponibilidadeDiaria

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@bp.route('/')
@login_required
def index():
    hoje    = date.today()
    mes_ini = hoje.replace(day=1)
    mes_ant = (mes_ini - timedelta(days=1)).replace(day=1)

    dados = _dados_cached(str(mes_ini), str(mes_ant), str(hoje))

    alertas_venc = []
    crlvs = (CRLV.query.join(Veiculo)
             .filter(Veiculo.status != 'inativo')
             .filter(CRLV.data_vencimento <= hoje + timedelta(days=60))
             .filter(CRLV.data_vencimento >= hoje)
             .order_by(CRLV.data_vencimento).limit(5).all())
    for c in crlvs:
        dias = (c.data_vencimento - hoje).days
        alertas_venc.append({'tipo': 'CRLV', 'desc': c.veiculo.placa,
                             'data': c.data_vencimento, 'dias': dias,
                             'nivel': 'vermelho' if dias <= 15 else 'laranja'})

    mots = (Motorista.query.filter_by(ativo=True)
            .filter(Motorista.cnh_validade.isnot(None))
            .filter(Motorista.cnh_validade <= hoje + timedelta(days=60))
            .filter(Motorista.cnh_validade >= hoje)
            .order_by(Motorista.cnh_validade).limit(5).all())
    for m in mots:
        dias = (m.cnh_validade - hoje).days
        alertas_venc.append({'tipo': 'CNH',
                             'desc': m.nome.split()[0] + ' ' + m.nome.split()[-1],
                             'data': m.cnh_validade, 'dias': dias,
                             'nivel': 'vermelho' if dias <= 15 else 'laranja'})
    alertas_venc.sort(key=lambda x: x['dias'])

    os_paradas = (OrdemServico.query
                  .filter(OrdemServico.status.in_(['aberta','em_execucao','aguardando_peca']))
                  .filter(OrdemServico.data_abertura <= hoje - timedelta(days=7))
                  .order_by(OrdemServico.data_abertura).limit(5).all())

    total_alertas = Alerta.query.filter_by(lido=False, nivel='critico').count()

    # ── Disponibilidade diária real (via DisponibilidadeDiaria de hoje) ──
    # Busca registros de hoje para todos os veículos
    registros_hoje = {
        r.veiculo_id: r
        for r in DisponibilidadeDiaria.query.filter_by(data=hoje).all()
    }
    todos_veiculos = Veiculo.query.filter(Veiculo.status != 'inativo').order_by(Veiculo.placa).all()

    veiculos_indisponiveis_hoje = []
    veiculos_disponiveis_hoje   = 0
    for v in todos_veiculos:
        reg = registros_hoje.get(v.id)
        if reg and not reg.disponivel:
            veiculos_indisponiveis_hoje.append({
                'veiculo': v,
                'motivo': reg.motivo_indisponibilidade or 'Indisponível',
                'observacoes': reg.observacoes,
            })
        else:
            veiculos_disponiveis_hoje += 1

    total_v_hoje = len(todos_veiculos)
    pct_disp_diaria = round(veiculos_disponiveis_hoje / total_v_hoje * 100) if total_v_hoje else 0

    custo_por_veiculo = db.session.execute(text("""
        SELECT v.id, v.placa, v.descricao,
               COUNT(os.id) AS qtd_os,
               COUNT(os.id) FILTER (WHERE os.tipo_manutencao='preventiva') AS qtd_prev,
               COUNT(os.id) FILTER (WHERE os.tipo_manutencao='corretiva')  AS qtd_corr,
               COALESCE(SUM(os.custo_total) FILTER (WHERE os.status='concluida'), 0) AS custo
        FROM veiculos v
        LEFT JOIN ordens_servico os ON os.veiculo_id = v.id
            AND os.data_abertura >= :mes_ini
        WHERE v.status != 'inativo'
        GROUP BY v.id, v.placa, v.descricao
        HAVING COUNT(os.id) > 0
        ORDER BY custo DESC
        LIMIT 15
    """), {'mes_ini': mes_ini}).mappings().all()

    return render_template('dashboard/index.html',
        hoje                   = hoje,
        total_veiculos         = dados['total_veiculos'],
        em_manutencao          = dados['em_manutencao'],
        pct_disponivel         = dados['pct_disponivel'],
        os_abertas             = dados['os_abertas'],
        os_execucao            = dados['os_execucao'],
        os_aguardando          = dados['os_aguardando'],
        os_mes                 = dados['os_mes'],
        oc_abertas             = dados['oc_abertas'],
        oc_valor_aberto        = dados['oc_valor_aberto'],
        os_paradas             = os_paradas,
        custo_mes              = dados['custo_mes'],
        custo_mes_ant          = dados['custo_mes_ant'],
        var_custo              = dados['var_custo'],
        os_por_mes             = dados['os_por_mes'],
        top_corretivas         = dados['top_corretivas'],
        alertas_venc           = alertas_venc,
        total_alertas_criticos = total_alertas,
        pneus_criticos         = dados['pneus_criticos'],
        mtbf                   = dados['mtbf'],
        mttr                   = dados['mttr'],
        disponibilidade_pct    = dados['disponibilidade_pct'],
        total_falhas_90d       = dados['total_falhas_90d'],
        veiculos_indisponiveis_hoje = veiculos_indisponiveis_hoje,
        pct_disp_diaria             = pct_disp_diaria,
        veiculos_disponiveis_hoje   = veiculos_disponiveis_hoje,
        total_veiculos_ativos       = total_v_hoje,
        mtbf_por_veiculo       = dados['mtbf_por_veiculo'],
    )


@cache.memoize(timeout=180)
def _dados_cached(mes_ini_str: str, mes_ant_str: str, hoje_str: str) -> dict:
    """Queries pesadas cacheadas por 3 minutos."""
    mes_ini = date.fromisoformat(mes_ini_str)
    mes_ant = date.fromisoformat(mes_ant_str)
    hoje    = date.fromisoformat(hoje_str)

    os_stats = db.session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status NOT IN ('concluida','cancelada')) AS abertas_total,
            COUNT(*) FILTER (WHERE status = 'em_execucao')                  AS em_execucao,
            COUNT(*) FILTER (WHERE status = 'aguardando_peca')              AS aguardando,
            COUNT(*) FILTER (WHERE data_abertura >= :mes_ini)               AS os_mes,
            COALESCE(SUM(custo_total) FILTER (
                WHERE status='concluida' AND data_conclusao >= :mes_ini), 0) AS custo_mes,
            COALESCE(SUM(custo_total) FILTER (
                WHERE status='concluida'
                AND data_conclusao >= :mes_ant
                AND data_conclusao < :mes_ini), 0)                           AS custo_mes_ant
        FROM ordens_servico
    """), {'mes_ini': mes_ini, 'mes_ant': mes_ant}).mappings().one()

    oc_stats = db.session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status NOT IN ('finalizada','cancelada'))       AS abertas,
            COALESCE(SUM(valor_total) FILTER (
                WHERE status NOT IN ('finalizada','cancelada')), 0)                AS valor_aberto
        FROM ordens_compra
    """)).mappings().one()

    frota = db.session.execute(text("""
        SELECT
            COUNT(*) AS total,
            (
                SELECT COUNT(DISTINCT veiculo_id)
                FROM ordens_servico
                WHERE status IN ('aberta', 'em_execucao', 'aguardando_peca')
                  AND veiculo_id IS NOT NULL
            ) AS em_manutencao
        FROM veiculos WHERE status != 'inativo'
    """)).mappings().one()

    top_corretivas = db.session.execute(text("""
        SELECT v.id, v.placa, v.descricao,
               COUNT(os.id) AS qtd,
               COALESCE(SUM(os.custo_total), 0) AS custo
        FROM veiculos v
        JOIN ordens_servico os ON os.veiculo_id = v.id
        WHERE os.tipo_manutencao = 'corretiva'
          AND os.data_abertura  >= :de
        GROUP BY v.id, v.placa, v.descricao
        ORDER BY qtd DESC LIMIT 5
    """), {'de': hoje - timedelta(days=90)}).mappings().all()

    os_por_mes = db.session.execute(text("""
        SELECT TO_CHAR(DATE_TRUNC('month', data_abertura), 'Mon/YY') AS mes,
               COUNT(*) AS qtd,
               COALESCE(SUM(custo_total) FILTER (WHERE status='concluida'), 0) AS custo
        FROM ordens_servico
        WHERE data_abertura >= :de
        GROUP BY DATE_TRUNC('month', data_abertura)
        ORDER BY DATE_TRUNC('month', data_abertura)
    """), {'de': hoje - timedelta(days=180)}).mappings().all()

    pneus_criticos = []
    if Pneu.query.filter_by(status='ativo').limit(1).first():
        for p in (Pneu.query.filter_by(status='ativo')
                  .join(PneuVeiculo, (PneuVeiculo.pneu_id == Pneu.id) & (PneuVeiculo.ativo == True))
                  .all()):
            if p.pct_vida >= 80:
                pos = p.posicao_atual
                pneus_criticos.append({'pneu': p,
                                       'veiculo': pos.veiculo if pos else None,
                                       'posicao': pos.posicao_display if pos else '—'})
        pneus_criticos.sort(key=lambda x: x['pneu'].pct_vida, reverse=True)
        pneus_criticos = pneus_criticos[:5]

    total     = int(frota['total']) or 1
    manut     = int(frota['em_manutencao'])
    custo_mes = float(os_stats['custo_mes'])
    custo_ant = float(os_stats['custo_mes_ant'])

    # ─────────────────────────────────────────────────────────────────
    #  INDICADORES MTBF / MTTR / DISPONIBILIDADE — últimos 90 dias
    #
    #  MTBF (Mean Time Between Failures) = Tempo Operando / Nº Paradas
    #       → Quanto maior, melhor. Indica confiabilidade da frota.
    #
    #  MTTR (Mean Time To Repair) = Tempo em Manutenção / Nº Paradas
    #       → Quanto menor, melhor. Indica eficiência do reparo.
    #
    #  Disponibilidade = MTBF / (MTBF + MTTR) × 100
    #
    #  Consideramos apenas OS corretivas concluídas (falhas reais),
    #  excluindo preventivas (que são planejadas e não são "falhas").
    # ─────────────────────────────────────────────────────────────────
    periodo_dias      = 90
    de_90d            = hoje - timedelta(days=periodo_dias)
    n_veiculos_ativos = max(total, 1)
    horas_totais      = n_veiculos_ativos * periodo_dias * 8   # 8h/dia de operação

    mtbf_raw = db.session.execute(text("""
        SELECT
            COUNT(*)                                                AS total_paradas,
            COALESCE(SUM(
                (COALESCE(data_conclusao, CURRENT_DATE) - data_abertura) * 8.0
            ), 0)                                                   AS horas_manutencao
        FROM ordens_servico
        WHERE tipo_manutencao = 'corretiva'
          AND status          = 'concluida'
          AND data_abertura  >= :de
    """), {'de': de_90d}).mappings().one()

    total_paradas    = int(mtbf_raw['total_paradas'])
    horas_manutencao = float(mtbf_raw['horas_manutencao'])
    horas_operando   = max(horas_totais - horas_manutencao, 0)

    if total_paradas > 0:
        mtbf_h   = round(horas_operando / total_paradas, 1)
        mttr_h   = round(horas_manutencao / total_paradas, 1)
        disp_pct = round(mtbf_h / (mtbf_h + mttr_h) * 100, 1) if (mtbf_h + mttr_h) > 0 else 100.0
    else:
        mtbf_h   = round(horas_operando, 1)
        mttr_h   = 0.0
        disp_pct = 100.0

    # MTBF por veículo — top 5 com mais falhas (para exibição na tabela)
    mtbf_por_veiculo_raw = db.session.execute(text("""
        SELECT
            v.id,
            v.placa,
            v.descricao,
            COUNT(os.id)                                             AS paradas,
            COALESCE(SUM(
                (COALESCE(os.data_conclusao, CURRENT_DATE) - os.data_abertura) * 8.0
            ), 0)                                                     AS horas_manut
        FROM veiculos v
        JOIN ordens_servico os ON os.veiculo_id = v.id
            AND os.tipo_manutencao = 'corretiva'
            AND os.status          = 'concluida'
            AND os.data_abertura  >= :de
        WHERE v.status != 'inativo'
        GROUP BY v.id, v.placa, v.descricao
        HAVING COUNT(os.id) >= 1
        ORDER BY paradas DESC, horas_manut DESC
        LIMIT 6
    """), {'de': de_90d}).mappings().all()

    hp = periodo_dias * 8    # horas do período por veículo (8h/dia de operação)
    mtbf_por_veiculo = []
    for row in mtbf_por_veiculo_raw:
        p   = int(row['paradas'])
        hm  = float(row['horas_manut'])
        hop = max(hp - hm, 0)
        vmt = round(hop / p, 1) if p > 0 else hp
        vtr = round(hm  / p, 1) if p > 0 else 0.0
        vdp = round(vmt / (vmt + vtr) * 100, 1) if (vmt + vtr) > 0 else 100.0
        mtbf_por_veiculo.append({
            'id':        row['id'],
            'placa':     row['placa'],
            'descricao': row['descricao'] or '',
            'paradas':   p,
            'mtbf':      vmt,
            'mttr':      vtr,
            'disponivel': vdp,
        })

    return {
        'total_veiculos':     total,
        'em_manutencao':      manut,
        'pct_disponivel':     round((total - manut) / total * 100, 1),
        'os_abertas':         int(os_stats['abertas_total']),
        'os_execucao':        int(os_stats['em_execucao']),
        'os_aguardando':      int(os_stats['aguardando']),
        'os_mes':             int(os_stats['os_mes']),
        'custo_mes':          custo_mes,
        'custo_mes_ant':      custo_ant,
        'oc_abertas':         int(oc_stats['abertas']),
        'oc_valor_aberto':    float(oc_stats['valor_aberto']),
        'var_custo':          round((custo_mes - custo_ant) / custo_ant * 100, 1) if custo_ant else 0,
        'os_por_mes':         [dict(r) for r in os_por_mes],
        'top_corretivas':     top_corretivas,
        'pneus_criticos':     pneus_criticos,
        'mtbf':               mtbf_h,
        'mttr':               mttr_h,
        'disponibilidade_pct': disp_pct,
        'total_falhas_90d':   total_paradas,
        'mtbf_por_veiculo':   mtbf_por_veiculo,
    }
