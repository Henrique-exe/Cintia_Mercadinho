"""Caminhos independentes do CWD e dos recursos extraídos pelo PyInstaller."""
import os
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def database(self): return self.root / 'data' / 'sigec.sqlite3'

    @property
    def backups(self): return self.root / 'backups'

    @property
    def logs(self): return self.root / 'logs'

    @property
    def runtime(self): return self.root / 'runtime'

    def prepare_runtime(self):
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)


def get_paths():
    if getattr(sys, 'frozen', False):
        local = os.environ.get('LOCALAPPDATA')
        if sys.platform != 'win32' or not local or not Path(local).is_absolute():
            raise RuntimeError('Não foi possível localizar a pasta LOCALAPPDATA do usuário.')
        return AppPaths(Path(local) / 'SIGEC')
    return AppPaths(SOURCE_ROOT)
