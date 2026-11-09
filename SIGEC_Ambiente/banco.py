"""Banco isolado de demonstração; todos os caminhos partem desta pasta."""
from contextlib import closing
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent / "dados" / "ambiente_demo.sqlite3"
PRODUTOS = [("DEMO-01", "Arroz 1 kg", "UN", 699, 8),
            ("DEMO-02", "Mortadela", "KG", 1890, 2500)]
CLIENTES = [("DEMO-C1", "Cliente de teste A")]

def preparar(path=BASE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS produtos (
          codigo TEXT PRIMARY KEY, nome TEXT NOT NULL,
          unidade TEXT NOT NULL CHECK(unidade IN ('UN','KG')),
          preco_centavos INTEGER NOT NULL CHECK(preco_centavos>=0),
          saldo_base INTEGER NOT NULL CHECK(saldo_base>=0));
        CREATE TABLE IF NOT EXISTS clientes (codigo TEXT PRIMARY KEY, nome TEXT NOT NULL);
        """)
        db.executemany("INSERT OR IGNORE INTO produtos VALUES (?,?,?,?,?)", PRODUTOS)
        db.executemany("INSERT OR IGNORE INTO clientes VALUES (?,?)", CLIENTES)

def consultar(path=BASE):
    with closing(sqlite3.connect(path)) as db, db:
        return (db.execute("SELECT nome,unidade,preco_centavos,saldo_base FROM produtos ORDER BY codigo").fetchall(),
                db.execute("SELECT nome FROM clientes ORDER BY codigo").fetchall())

if __name__ == "__main__":
    preparar()
    print("Banco de demonstração pronto:", BASE)
