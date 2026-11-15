"""Backup consistente do mesmo banco escolhido pela aplicação."""
import sys
from sigec.paths import get_paths
from sigec.storage_tools import create_backup


def backup():
    try:
        target = create_backup(get_paths())
        print('Backup verificado em:', target)
        print('Copie para outro dispositivo e teste a restauração em uma pasta de teste.')
        return 0
    except Exception as exc:
        print('Falha no backup:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(backup())
