# Código-fonte do SIGEC

Veja a [apresentação e as instruções de instalação](../README.md) na raiz do repositório.

## Rodar pelo código-fonte

Na pasta `SIGEC_MVP`, crie um ambiente virtual, instale `requirements.txt` e execute `python run.py`. Abra `http://127.0.0.1:5000` no navegador. Este modo usa Python e, por padrão, guarda os dados em `data/sigec.sqlite3`. No Windows, `instalar_windows.bat` e `iniciar_sigec.bat` preparam e iniciam o ambiente de desenvolvimento.

Para verificar o projeto, execute `python -m unittest discover -s tests -v` e `node tests/check_ui_node.js`. Os testes Python usam bancos temporários.

O build Windows usa `packaging/build.ps1`, PyInstaller e Inno Setup. O workflow do repositório gera o instalador com as dependências incluídas, verifica o atalho e disponibiliza o executável como artefato.
