from tempfile import TemporaryDirectory
from pathlib import Path
from app import criar_app
from verificar_banco import verificar

verificar()
with TemporaryDirectory() as pasta:
    db = Path(pasta) / "demo.sqlite3"
    for _ in range(2):
        pagina = criar_app(db).test_client().get("/")
        assert pagina.status_code == 200
        html = pagina.get_data(as_text=True)
        assert all(item in html for item in ["Mortadela", "2,500 kg", "R$ 18,90", "Cliente de teste A"])
print("OK: Flask respondeu HTTP 200 e exibiu os dados do SQLite após recriar a aplicação.")
