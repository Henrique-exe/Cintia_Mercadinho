"""Cópias consistentes e importação explícita, sem sobrescrever o destino."""
import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from .db import SCHEMA


def validate_database(conn):
    rows = conn.execute('PRAGMA integrity_check').fetchall()
    if rows != [('ok',)]:
        raise ValueError('Falha na integridade SQLite: ' + str(rows[:3]))
    if conn.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Banco com referências inválidas (foreign_key_check).')
    reference = sqlite3.connect(':memory:')
    try:
        reference.executescript(SCHEMA)
        tables = reference.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (table,) in tables:
            required = {r[1] for r in reference.execute(f'PRAGMA table_info("{table}")')}
            if table == 'sale_items':
                # O custo histórico foi adicionado na v1.1. Cópias legítimas
                # da v1.0 ainda são aceitas e atualizadas na primeira abertura.
                required.discard('cost_cents')
            actual = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            if not required <= actual:
                raise ValueError('Este banco não tem o esquema esperado do SIGEC: ' + table)
    finally:
        reference.close()


def consistent_copy(source, target):
    source, target = Path(source).resolve(), Path(target).absolute()
    if not source.is_file():
        raise FileNotFoundError('Banco de origem não encontrado: ' + str(source))
    if target.exists():
        raise FileExistsError('O banco de destino já existe e não será sobrescrito: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.sigec-copy-', suffix='.tmp', dir=target.parent)
    os.close(fd)
    try:
        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)
        dst = sqlite3.connect(temp)
        try:
            deadline = time.monotonic() + 30
            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError('Tempo excedido ao copiar o banco. Tente novamente com o SIGEC encerrado.')
            src.backup(dst, pages=128, progress=progress, sleep=0.05)
            validate_database(dst)
        finally:
            dst.close()
            src.close()
        with open(temp, 'r+b') as f:
            os.fsync(f.fileno())
        # Hardlink publica atomicamente SEM substituir; NTFS no Windows.
        os.link(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return target


def create_backup(paths):
    name = f'sigec_{datetime.now():%Y%m%d_%H%M%S_%f}.sqlite3'
    return consistent_copy(paths.database, paths.backups / name)


def import_legacy(paths, source, source_closed=False):
    if not source_closed:
        raise ValueError('Encerre o SIGEC antigo e confirme com --source-closed.')
    source = Path(source)
    if not source.is_absolute():
        raise ValueError('Indique o caminho absoluto do banco antigo com --migrate.')
    for suffix in ('-wal', '-journal'):
        sidecar = Path(str(source) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('A origem possui WAL/journal pendente. Abra e encerre o SIGEC antigo normalmente antes de copiar.')
    return consistent_copy(source, paths.database)
