-- Migração: Reservas de Veículo
CREATE TABLE IF NOT EXISTS reservas_veiculo (
    id                  SERIAL PRIMARY KEY,
    veiculo_id          INTEGER REFERENCES veiculos(id) ON DELETE SET NULL,
    nome_solicitante    VARCHAR(120) NOT NULL,
    setor_solicitante   VARCHAR(100),
    contato             VARCHAR(80),
    data_inicio         DATE NOT NULL,
    data_fim            DATE NOT NULL,
    destino             VARCHAR(200) NOT NULL,
    finalidade          TEXT,
    n_passageiros       SMALLINT DEFAULT 1,
    tipo_veiculo_pref   VARCHAR(80),
    status              VARCHAR(30) DEFAULT 'pendente',
    obs_admin           TEXT,
    aprovado_por        VARCHAR(36) REFERENCES usuarios(id) ON DELETE SET NULL,
    aprovado_em         TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reservas_status      ON reservas_veiculo(status);
CREATE INDEX IF NOT EXISTS idx_reservas_data_inicio ON reservas_veiculo(data_inicio);
CREATE INDEX IF NOT EXISTS idx_reservas_veiculo     ON reservas_veiculo(veiculo_id);
