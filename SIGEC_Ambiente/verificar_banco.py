from contextlib import closing
import tempfile, sqlite3
from pathlib import Path
from banco import preparar, consultar

def verificar():
    with tempfile.TemporaryDirectory() as pasta:
        db = Path(pasta) / "teste.sqlite3"
        preparar(db)
        produtos, clientes = consultar(db)
        assert len(produtos)==2 and len(clientes)==1
        assert ("Mortadela","KG",1890,2500) in produtos
        with closing(sqlite3.connect(db)) as con, con:
            con.execute("UPDATE produtos SET saldo_base=7 WHERE codigo='DEMO-01'")
        preparar(db)
        produtos, clientes = consultar(db)
        assert len(produtos)==2 and len(clientes)==1
        assert ("Arroz 1 kg","UN",699,7) in produtos
    print("OK: SQLite, produtos UN/KG, cliente fictício, persistência e carga sem duplicação.")

if __name__ == "__main__":
    verificar()
