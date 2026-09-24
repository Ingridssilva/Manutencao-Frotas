"""
Migration: adiciona colunas de token de aprovação na tabela orcamentos
Rodar UMA VEZ no Shell do Render: python add_orcamento_token.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'production'))

with app.app_context():
    with db.engine.connect() as conn:
        # Verifica se coluna já existe
        existe = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'orcamentos' AND column_name = 'aprovacao_token'
        """)).fetchone()

        if existe:
            print("Colunas de token já existem na tabela orcamentos.")
        else:
            conn.execute(text("""
                ALTER TABLE orcamentos
                  ADD COLUMN aprovacao_token     VARCHAR(100),
                  ADD COLUMN aprovacao_token_exp TIMESTAMP
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX ix_orcamentos_aprovacao_token
                ON orcamentos(aprovacao_token)
                WHERE aprovacao_token IS NOT NULL
            """))
            conn.commit()
            print("Colunas aprovacao_token e aprovacao_token_exp adicionadas!")
    print("Pronto.")
