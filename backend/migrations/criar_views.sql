-- ============================================================
--  Views do sistema de frota — Empresa Exemplo
--  Executar no banco PostgreSQL após init-db
--  Compatível com a estrutura de modelos do SQLAlchemy
-- ============================================================


-- ------------------------------------------------------------
--  1. vw_vencimentos_proximos
--     Unifica todos os documentos com data de vencimento
--     (CRLV, laudo acústico, tacógrafo, seguro)
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_vencimentos_proximos AS

    -- CRLV
    SELECT
        v.id              AS veiculo_id,
        v.placa           AS placa,
        v.descricao       AS descricao,
        'CRLV'            AS tipo_doc,
        c.data_vencimento AS data_vencimento,
        c.status          AS status
    FROM crlv c
    JOIN veiculos v ON v.id = c.veiculo_id
    WHERE v.status != 'inativo'

UNION ALL

    -- Laudo Acústico (mais recente por veículo)
    SELECT
        v.id              AS veiculo_id,
        v.placa           AS placa,
        v.descricao       AS descricao,
        'Laudo Acústico'  AS tipo_doc,
        la.data_vencimento AS data_vencimento,
        CASE
            WHEN la.data_vencimento < CURRENT_DATE THEN 'vencido'
            WHEN la.data_vencimento < CURRENT_DATE + INTERVAL '30 days' THEN 'critico'
            ELSE 'regular'
        END               AS status
    FROM laudos_acusticos la
    JOIN veiculos v ON v.id = la.veiculo_id
    JOIN (
        SELECT veiculo_id, MAX(data_emissao) AS ultima_emissao
        FROM laudos_acusticos
        GROUP BY veiculo_id
    ) lx ON lx.veiculo_id = la.veiculo_id AND lx.ultima_emissao = la.data_emissao
    WHERE v.status != 'inativo'

UNION ALL

    -- Tacógrafo (calibração mais recente por veículo)
    SELECT
        v.id                        AS veiculo_id,
        v.placa                     AS placa,
        v.descricao                 AS descricao,
        'Tacógrafo'                 AS tipo_doc,
        t.data_proxima_calibracao   AS data_vencimento,
        t.status                    AS status
    FROM tacografos t
    JOIN veiculos v ON v.id = t.veiculo_id
    JOIN (
        SELECT veiculo_id, MAX(data_proxima_calibracao) AS proxima
        FROM tacografos
        GROUP BY veiculo_id
    ) tx ON tx.veiculo_id = t.veiculo_id AND tx.proxima = t.data_proxima_calibracao
    WHERE v.status != 'inativo'

UNION ALL

    -- Seguro (ativo mais recente por veículo)
    SELECT
        v.id              AS veiculo_id,
        v.placa           AS placa,
        v.descricao       AS descricao,
        'Seguro'          AS tipo_doc,
        s.data_vencimento AS data_vencimento,
        s.status          AS status
    FROM seguros_veiculo s
    JOIN veiculos v ON v.id = s.veiculo_id
    WHERE s.status = 'ativo'
      AND v.status != 'inativo';


-- ------------------------------------------------------------
--  2. vw_bi_disponibilidade
--     Disponibilidade mensal por veículo com percentual e UPE
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_bi_disponibilidade AS
SELECT
    DATE_TRUNC('month', dd.data)::DATE         AS mes,
    v.placa                                     AS placa,
    v.descricao                                 AS descricao,
    v.municipio_base                            AS municipio_base,
    COUNT(*)                                    AS dias_no_mes,
    COUNT(*) FILTER (WHERE dd.disponivel = TRUE)    AS dias_disponivel,
    COUNT(*) FILTER (WHERE dd.disponivel = FALSE)   AS dias_indisponivel,
    ROUND(
        COUNT(*) FILTER (WHERE dd.disponivel = TRUE)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100,
        2
    )                                           AS pct_disponibilidade,
    COALESCE(SUM(dd.upe_impacto) FILTER (WHERE dd.disponivel = FALSE), 0)
                                                AS upe_total_perdido
FROM disponibilidade_diaria dd
JOIN veiculos v ON v.id = dd.veiculo_id
WHERE v.status != 'inativo'
GROUP BY
    DATE_TRUNC('month', dd.data),
    v.id,
    v.placa,
    v.descricao,
    v.municipio_base;


-- ------------------------------------------------------------
--  3. vw_bi_custo_veiculo
--     Custo mensal por veículo segmentado por tipo de manutenção
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_bi_custo_veiculo AS
SELECT
    v.id                                        AS veiculo_id,
    v.placa                                     AS placa,
    v.descricao                                 AS descricao,
    v.municipio_base                            AS municipio_base,
    v.tipo_propriedade                          AS tipo_propriedade,
    DATE_TRUNC('month', os.data_abertura)::DATE AS mes,
    os.tipo_manutencao                          AS tipo_manutencao,
    COUNT(os.id)                                AS qtd_os,
    COALESCE(SUM(os.custo_total), 0)            AS custo_total,
    COALESCE(SUM(os.custo_total) FILTER (WHERE os.tipo_manutencao = 'corretiva'),  0) AS custo_corretiva,
    COALESCE(SUM(os.custo_total) FILTER (WHERE os.tipo_manutencao = 'preventiva'), 0) AS custo_preventiva,
    COALESCE(SUM(os.custo_total) FILTER (WHERE os.tipo_manutencao = 'preditiva'),  0) AS custo_preditiva
FROM veiculos v
LEFT JOIN ordens_servico os
    ON os.veiculo_id = v.id
    AND os.status    = 'concluida'
    AND os.data_abertura IS NOT NULL
WHERE v.status != 'inativo'
GROUP BY
    v.id,
    v.placa,
    v.descricao,
    v.municipio_base,
    v.tipo_propriedade,
    DATE_TRUNC('month', os.data_abertura),
    os.tipo_manutencao;
