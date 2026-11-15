"""Entrada windowed para o PyInstaller e ferramentas locais do SIGEC."""
import argparse
import logging
import sys
from sigec.paths import get_paths
from sigec.locking import FileLock
from sigec.desktop import (configure_logging, ensure_not_maintaining, message,
                           run_application, stop_application)


def main(argv=None):
    parser = argparse.ArgumentParser(description='SIGEC local')
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--stop', action='store_true')
    commands.add_argument('--self-test', action='store_true')
    commands.add_argument('--backup', action='store_true')
    commands.add_argument('--migrate', metavar='CAMINHO_ABSOLUTO')
    parser.add_argument('--source-closed', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-dialog', action='store_true')
    args = parser.parse_args(argv)
    paths = handler = None
    try:
        if args.self_test:
            # Testa recursos empacotados e SQLite SEM criar o banco permanente.
            import tempfile
            from pathlib import Path
            from sigec import create_app
            with tempfile.TemporaryDirectory(prefix='sigec-self-test-') as tmp:
                app = create_app({'TESTING': True, 'DATABASE': str(Path(tmp) / 'test.sqlite3')})
                client = app.test_client()
                assert client.get('/api/health').json['status'] == 'ok'
                assert b'SIGEC' in client.get('/').data
                for asset in ('app.js', 'style.css'):
                    response = client.get('/static/' + asset)
                    assert response.status_code == 200 and len(response.data) > 100
                    response.close()
                assert client.get('/api/products').json == []
            return 0
        paths = get_paths()
        handler = configure_logging(paths)
        if args.stop:
            stop_application(paths)
        elif args.backup or args.migrate:
            from sigec.storage_tools import create_backup, import_legacy
            with FileLock(paths.runtime / 'startup.lock'):
                ensure_not_maintaining(paths)
                if args.backup:
                    result = create_backup(paths)
                else:
                    lock = FileLock(paths.runtime / 'server.lock')
                    if not lock.acquire():
                        raise RuntimeError('Encerre o SIGEC de destino antes de importar o banco antigo.')
                    try:
                        result = import_legacy(paths, args.migrate, args.source_closed)
                    finally:
                        lock.release()
            logging.info('Cópia verificada em %s', result)
            if not args.no_dialog: message('Cópia verificada em:\n' + str(result))
        else:
            return run_application(paths, browser=not args.no_browser)
        return 0
    except Exception as exc:
        logging.exception('Falha no SIGEC')
        location = str(paths.logs / 'sigec.log') if paths else r'%LOCALAPPDATA%\SIGEC\logs\sigec.log'
        text = str(exc) + '\n\nLog: ' + location
        if not args.no_dialog: message(text, error=True)
        elif sys.stderr: print(text, file=sys.stderr)
        return 1
    finally:
        if handler:
            logging.getLogger().removeHandler(handler)
            handler.close()


if __name__ == '__main__': sys.exit(main())
