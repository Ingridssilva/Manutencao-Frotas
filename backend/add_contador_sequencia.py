"""
Migration: cria a tabela contadores_sequencia e popula com os valores atuais,
para a numeração de OS/Orçamento/OC passar a ser atômica (sem race condition).

Rodar UMA VEZ no Shell do Render:
  python add_contador_sequencia.py
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app, db
from sqlalchemy import text

app = create_app(os.environ.get('FLASK_ENV', 'production'))


def _maior_sequencial(tabela: str, prefixo: str) -> dict:
    """Retorna {chave 'PREFIXO-ANO': maior_sequencial_usado} lendo a coluna `numero`."""
    rows = db.session.execute(text(
        f"SELECT numero FROM {tabela} WHERE numero LIKE :padrao"
    ), {'padrao': f'{prefixo}-%'}).scalars().all()

    maiores = {}
    padrao = re.compile(rf'^{re.escape(prefixo)}-(\d{{4}})-(\d+)$')
    for numero in rows:
        m = padrao.match(numero or '')
        if not m:
            continue
        ano, seq = m.group(1), int(m.group(2))
        chave = f'{prefixo}-{ano}'
        maiores[chave] = max(maiores.get(chave, 0), seq)
    return maiores


with app.app_context():
    with db.engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contadores_sequencia (
                chave VARCHAR(20) PRIMARY KEY,
                valor INTEGER NOT NULL DEFAULT 0
            )
        """))
        print("Tabela contadores_sequencia OK.")

    # Semeia com o maior número já em uso em cada tabela, para a numeração
    # não recomeçar do zero e colidir com registros existentes.
    todos = {}
    todos.update(_maior_sequencial('ordens_servico', 'OS'))
    todos.update(_maior_sequencial('orcamentos', 'ORC'))
    todos.update(_maior_sequencial('ordens_compra', 'OC'))

    for chave, valor in todos.items():
        existe = db.session.execute(text(
            "SELECT 1 FROM contadores_sequencia WHERE chave = :chave"
        ), {'chave': chave}).first()
        if existe:
            print(f"  {chave}: já existe, não sobrescrito.")
            continue
        db.session.execute(text("""
            INSERT INTO contadores_sequencia (chave, valor) VALUES (:chave, :valor)
        """), {'chave': chave, 'valor': valor})
        print(f"  {chave}: semeado com valor={valor}")

    db.session.commit()
    print("Contadores inicializados com sucesso.")
