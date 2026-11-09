from flask import Flask, render_template_string
from banco import preparar, consultar, BASE

def criar_app(path=BASE):
    preparar(path)
    app = Flask(__name__)
    @app.get("/")
    def inicio():
        produtos, clientes = consultar(path)
        linhas = [(nome, un, f"R$ {centavos//100},{centavos%100:02d}",
                   f"{q//1000},{q%1000:03d} kg" if un == "KG" else f"{q} un")
                  for nome, un, centavos, q in produtos]
        return render_template_string("""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
        <title>SIGEC | Ambiente de teste</title><style>body{font:18px system-ui;max-width:52rem;margin:4rem auto;padding:1rem}
        table{border-collapse:collapse}td,th{text-align:left;padding:.6rem;border-bottom:1px solid #ccc}</style>
        <h1>SIGEC · Ambiente de teste</h1><p>Flask em execução local. Dados fictícios lidos do SQLite.</p>
        <h2>Produtos</h2><table><tr><th>Produto</th><th>Unidade</th><th>Preço por unidade/kg</th><th>Saldo</th></tr>
        {% for linha in linhas %}<tr>{% for valor in linha %}<td>{{valor}}</td>{% endfor %}</tr>{% endfor %}</table>
        <h2>Clientes de demonstração</h2><ul>{% for cliente in clientes %}<li>{{ cliente[0] }}</li>{% endfor %}</ul></html>""",
                                      linhas=linhas, clientes=clientes)
    return app

if __name__ == "__main__":
    criar_app().run(host="127.0.0.1", port=5000, debug=False)
