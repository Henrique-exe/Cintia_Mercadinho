"""Execução do código-fonte no Linux/Windows, com console e Ctrl+C."""
from launcher import main

if __name__ == '__main__':
    print('SIGEC em http://127.0.0.1:5000 (somente neste PC).')
    print('Pressione Ctrl+C para encerrar. Não feche durante uma operação.')
    raise SystemExit(main(['--no-browser', '--no-dialog']))
