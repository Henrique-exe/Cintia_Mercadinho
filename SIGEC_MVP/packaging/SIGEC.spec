# Build Windows nativo; onedir interno, distribuído dentro de UM instalador.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata

if sys.platform != 'win32':
    raise SystemExit('Este spec gera somente Windows x64. Execute build.ps1 no Windows.')
root = Path(SPECPATH).parent
version = (root / 'VERSION').read_text().strip()
metadata = []
for package in ('flask', 'waitress', 'werkzeug', 'jinja2', 'markupsafe', 'click', 'blinker', 'itsdangerous', 'colorama', 'pyinstaller'):
    metadata += copy_metadata(package)
assets = [(str(root / 'sigec' / 'templates'), 'sigec/templates'),
          (str(root / 'sigec' / 'static'), 'sigec/static'),
          (str(root / 'VERSION'), '.'),
          (str(root / 'packaging' / 'THIRD-PARTY.txt'), 'licenses'),
          (str(Path(sys.base_prefix) / 'LICENSE.txt'), 'licenses/python')]
a = Analysis([str(root / 'launcher.py')], pathex=[str(root)],
             binaries=[], datas=assets + metadata,
             hiddenimports=['sqlite3', '_sqlite3'], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['tkinter', 'pytest', 'unittest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SIGEC', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, version=str(root / 'build' / 'version_info.txt'),
          icon=str(root / 'packaging' / 'sigec.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SIGEC')
