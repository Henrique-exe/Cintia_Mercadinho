"""Manifesto de reparo e recursos de versão. Executado somente pelo build."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare_version():
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION deve usar MAJOR.MINOR.PATCH.')
    parts = tuple(map(int, version.split('.'))) + (0,)
    if any(p > 65535 for p in parts): raise ValueError('Versão fora do intervalo Windows.')
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'build' / 'version_info.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={parts}, prodvers={parts}, mask=0x3f, flags=0x0,
                   OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041604b0', [
    StringStruct('CompanyName', 'SIGEC - Projeto Mercadinho da Cíntia'),
    StringStruct('FileDescription', 'SIGEC - aplicação web local'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('ProductName', 'SIGEC'),
    StringStruct('ProductVersion', '{version}'),
    StringStruct('OriginalFilename', 'SIGEC.exe')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])])''', encoding='utf-8')


def prepare_manifest():
    payload = ROOT / 'dist' / 'SIGEC'
    files = sorted(p for p in payload.rglob('*') if p.is_file())
    if not (payload / 'SIGEC.exe').is_file(): raise ValueError('Payload Windows ausente.')
    entries = []
    for file in files:
        relative = file.relative_to(payload).as_posix()
        # Garante que o payload jamais entregue bancos/backups/demo ou caracteres de script.
        if file.suffix.lower() in ('.sqlite3', '.db') or any(c in relative for c in "'\"{};\n\r"):
            raise ValueError('Arquivo não permitido no payload: ' + relative)
        entries.append({'path': relative, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    version = (ROOT / 'VERSION').read_text().strip()
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    payload_id = version + '-' + digest[:16]
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    (build / 'payload.json').write_text(json.dumps({'version': version, 'payload_id': payload_id, 'files': entries}, indent=2), encoding='utf-8')
    lines = []
    for entry in entries:
        rel = entry['path'].replace('/', '\\')
        parent = str(Path(entry['path']).parent).replace('/', '\\')
        dest = '{app}\\versions\\{#PayloadId}' + (('\\' + parent) if parent != '.' else '')
        lines.append(f'Source: "..\\dist\\SIGEC\\{rel}"; DestDir: "{dest}"; Flags: ignoreversion; Check: NeedsFile(\'{rel}\', \'{entry["sha256"]}\')')
    (build / 'payload-files.iss').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (build / 'payload-defines.iss').write_text(f'#define AppVersion "{version}"\n#define AppMajor {version.split(".")[0]}\n#define AppMinor {version.split(".")[1]}\n#define AppPatch {version.split(".")[2]}\n#define PayloadId "{payload_id}"\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', action='store_true')
    args = parser.parse_args()
    prepare_manifest() if args.manifest else prepare_version()
