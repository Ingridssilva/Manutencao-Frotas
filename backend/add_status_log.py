"""
Migration: cria tabela os_status_log
Rodar UMA VEZ no Shell do Render: python add_status_log.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'production'))

with app.app_context():
    with db.engine.connect() as conn:
        existe = conn.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'os_status_log'
        """)).fetchone()

        if existe:
            print("Tabela os_status_log já existe.")
        else:
            conn.execute(text("""
                CREATE TABLE os_status_log (
                    id          SERIAL PRIMARY KEY,
                    os_id       INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE CASCADE,
                    status_de   VARCHAR(30),
                    status_para VARCHAR(30) NOT NULL,
                    usuario_id  VARCHAR(36) REFERENCES usuarios(id),
                    obs         VARCHAR(300),
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX ix_os_status_log_os_id ON os_status_log(os_id)"))
            conn.commit()
            print("Tabela os_status_log criada!")
    print("Pronto.")
