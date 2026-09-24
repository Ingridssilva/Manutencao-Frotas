"""
Migration: adiciona campos de "apto a dirigir" na tabela motoristas
           e cria a tabela motoristas_documentos (CNH, termos, etc.)
Rodar UMA VEZ no Shell do Render:
  python add_motorista_docs.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'production'))

COLUNAS_MOTORISTA = [
    # (nome_coluna, definição SQL)
    ('apto_dirigir',        "BOOLEAN NOT NULL DEFAULT TRUE"),
    ('apto_motivo',         "VARCHAR(200)"),
    ('apto_atualizado_em',  "TIMESTAMP"),
    ('apto_atualizado_por', "VARCHAR(36) REFERENCES usuarios(id)"),
]

with app.app_context():
    with db.engine.connect() as conn:
        for coluna, definicao in COLUNAS_MOTORISTA:
            existe = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'motoristas'
                  AND column_name = :col
            """), {"col": coluna}).fetchone()

            if existe:
                print(f"  ✓ motoristas.{coluna} já existe — pulando")
            else:
                conn.execute(text(
                    f"ALTER TABLE motoristas ADD COLUMN {coluna} {definicao}"
                ))
                conn.commit()
                print(f"  + motoristas.{coluna} adicionada!")

        existe_tabela = conn.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'motoristas_documentos'
        """)).fetchone()

        if existe_tabela:
            print("  ✓ Tabela motoristas_documentos já existe — pulando")
        else:
            conn.execute(text("""
                CREATE TABLE motoristas_documentos (
                    id             SERIAL PRIMARY KEY,
                    motorista_id   INTEGER NOT NULL REFERENCES motoristas(id) ON DELETE CASCADE,
                    tipo           VARCHAR(30) NOT NULL,
                    nome_arquivo   VARCHAR(180),
                    url_sharepoint TEXT,
                    sharepoint_id  VARCHAR(150),
                    uploaded_by    VARCHAR(36) REFERENCES usuarios(id),
                    created_at     TIMESTAMP DEFAULT NOW(),
                    CONSTRAINT uq_motorista_doc_tipo UNIQUE (motorista_id, tipo)
                )
            """))
            conn.execute(text(
                "CREATE INDEX ix_motoristas_documentos_motorista_id ON motoristas_documentos(motorista_id)"
            ))
            conn.commit()
            print("  + Tabela motoristas_documentos criada!")

    print("\nMigração concluída.")
