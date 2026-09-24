"""
Migration: garante que todas as colunas de aprovação existem na tabela ordens_servico
Rodar UMA VEZ no Shell do Render:
  python add_aprovacao_os.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'production'))

COLUNAS = [
    # (nome_coluna, definição SQL)
    ('aprovacao_status',    "VARCHAR(20) DEFAULT 'pendente'"),
    ('aprovacao_token',     "VARCHAR(120) UNIQUE"),
    ('aprovacao_token_exp', "TIMESTAMP"),
    ('aprovacao_obs',       "TEXT"),
    ('aprovado_por',        "VARCHAR(36) REFERENCES usuarios(id)"),
    ('aprovado_em',         "TIMESTAMP"),
    ('motivo_rejeicao',     "TEXT"),
]

with app.app_context():
    with db.engine.connect() as conn:
        for coluna, definicao in COLUNAS:
            existe = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ordens_servico'
                  AND column_name = :col
            """), {"col": coluna}).fetchone()

            if existe:
                print(f"  ✓ {coluna} já existe — pulando")
            else:
                conn.execute(text(
                    f"ALTER TABLE ordens_servico ADD COLUMN {coluna} {definicao}"
                ))
                conn.commit()
                print(f"  + {coluna} adicionada!")

        # Corrige registros existentes com aprovacao_status NULL → 'pendente'
        resultado = conn.execute(text("""
            UPDATE ordens_servico
            SET aprovacao_status = 'pendente'
            WHERE aprovacao_status IS NULL
        """))
        conn.commit()
        print(f"  ~ {resultado.rowcount} OS com status NULL corrigidas para 'pendente'")

    print("\nMigração concluída.")
