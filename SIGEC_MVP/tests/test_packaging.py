"""Caminhos, cópias, identidade e ciclo de vida verificáveis no SO do teste."""
import hashlib
import http.client
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PathsAndStorageTests(unittest.TestCase):
    def setUp(self):
        from sigec.paths import AppPaths
        self.temp = tempfile.TemporaryDirectory(prefix='sigec testes ç ')
        self.root = Path(self.temp.name)
        self.paths = AppPaths(self.root / 'destino')

    def tearDown(self): self.temp.cleanup()

    def make_database(self):
        from sigec import create_app
        source = self.root / 'antigo' / 'sigec.sqlite3'
        app = create_app({'TESTING': True, 'DATABASE': str(source)})
        app.test_client().post('/api/products', json={'name': 'Arroz fictício', 'unit': 'UN', 'price': '6', 'stock': '10'})
        return source

    def test_source_paths_do_not_depend_on_cwd(self):
        from sigec.paths import get_paths
        before = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(get_paths().database, ROOT / 'data' / 'sigec.sqlite3')
        finally: os.chdir(before)

    def test_installed_paths_never_use_bundle_or_executable_directory(self):
        from sigec.paths import get_paths
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', '/unusable/bundle', create=True), patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': str(self.root)}):
            paths = get_paths()
            self.assertEqual(paths.database, self.root / 'SIGEC' / 'data' / 'sigec.sqlite3')
            self.assertEqual(paths.backups, self.root / 'SIGEC' / 'backups')
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LOCALAPPDATA': ''}):
            with self.assertRaises(RuntimeError): get_paths()

    def test_explicit_import_preserves_source_and_data(self):
        from sigec.storage_tools import import_legacy
        source = self.make_database()
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = import_legacy(self.paths, str(source), source_closed=True)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        with closing(sqlite3.connect(result)) as conn:
            self.assertEqual(conn.execute('SELECT name FROM products').fetchone()[0], 'Arroz fictício')
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_v10_backup_and_import_leave_source_untouched_and_upgrade_copy(self):
        from sigec import create_app
        from sigec.storage_tools import consistent_copy, import_legacy
        source = self.make_database()
        client = create_app({'TESTING': True, 'DATABASE': str(source)}).test_client()
        self.assertEqual(client.post('/api/cash/open', json={'opening': '100'}).status_code, 201)
        self.assertEqual(client.post('/api/sales', json={
            'token': 'legacy-sale-test-001', 'items': [{'product_id': 1, 'quantity': '2'}],
            'payments': [{'method': 'PIX', 'applied': '12'}],
        }).status_code, 201)
        with closing(sqlite3.connect(source)) as conn:
            conn.execute('ALTER TABLE sale_items DROP COLUMN cost_cents')
            conn.commit()
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        backup = consistent_copy(source, self.root / 'copia-v10.sqlite3')
        result = import_legacy(self.paths, str(source), source_closed=True)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        upgraded = create_app({'TESTING': True, 'DATABASE': str(result)}).test_client()
        self.assertEqual(len(upgraded.get('/api/sales').json), 1)
        self.assertEqual(upgraded.get('/api/products').json[0]['stock_base'], 8)
        with closing(sqlite3.connect(result)) as conn:
            self.assertIsNone(conn.execute('SELECT cost_cents FROM sale_items').fetchone()[0])
        with closing(sqlite3.connect(backup)) as conn:
            self.assertNotIn('cost_cents', {r[1] for r in conn.execute('PRAGMA table_info(sale_items)')})

    def test_import_requires_closed_source_and_absolute_path(self):
        from sigec.storage_tools import import_legacy
        with self.assertRaises(ValueError): import_legacy(self.paths, self.make_database())
        with self.assertRaises(ValueError): import_legacy(self.paths, 'relative.sqlite3', True)
        self.assertFalse(self.paths.database.exists())

    def test_existing_destination_is_never_overwritten(self):
        from sigec.storage_tools import import_legacy
        source = self.make_database()
        self.paths.database.parent.mkdir(parents=True)
        self.paths.database.write_bytes(b'nao alterar')
        with self.assertRaises(FileExistsError): import_legacy(self.paths, source, True)
        self.assertEqual(self.paths.database.read_bytes(), b'nao alterar')

    def test_race_creating_destination_does_not_overwrite(self):
        from sigec.storage_tools import consistent_copy
        source = self.make_database()
        target = self.paths.database
        real_link = os.link
        def racing_link(temp, dest):
            Path(dest).write_bytes(b'outro processo')
            real_link(temp, dest)
        with patch('sigec.storage_tools.os.link', side_effect=racing_link):
            with self.assertRaises(FileExistsError): consistent_copy(source, target)
        self.assertEqual(target.read_bytes(), b'outro processo')
        self.assertEqual(list(target.parent.glob('.sigec-copy-*')), [])

    def test_invalid_or_foreign_database_not_published(self):
        from sigec.storage_tools import import_legacy
        source = self.root / 'invalid.sqlite3'
        source.write_bytes(b'not a database')
        with self.assertRaises(sqlite3.DatabaseError): import_legacy(self.paths, source, True)
        source.unlink()
        with closing(sqlite3.connect(source)) as conn: conn.execute('CREATE TABLE alien(x)')
        with self.assertRaises(ValueError): import_legacy(self.paths, source, True)
        self.assertFalse(self.paths.database.exists())
        self.assertEqual(list(self.paths.database.parent.glob('.sigec-copy-*')), [])

    def test_missing_source_not_created(self):
        from sigec.storage_tools import import_legacy
        source = self.root / 'missing.sqlite3'
        with self.assertRaises(FileNotFoundError): import_legacy(self.paths, source, True)
        self.assertFalse(source.exists())
        self.assertFalse(self.paths.database.exists())

    def test_backups_are_consistent_unique_and_use_selected_path(self):
        from sigec.storage_tools import create_backup, import_legacy
        import_legacy(self.paths, self.make_database(), True)
        first, second = create_backup(self.paths), create_backup(self.paths)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, self.paths.backups)
        with closing(sqlite3.connect(first)) as conn:
            self.assertEqual(conn.execute('SELECT stock_base FROM products').fetchone()[0], 10)
        with patch('backup.get_paths', return_value=self.paths):
            import backup
            self.assertEqual(backup.backup(), 0)
        self.assertEqual(len(list(self.paths.backups.glob('*.sqlite3'))), 3)

    def test_wal_live_backup_and_import_guard(self):
        from sigec.storage_tools import consistent_copy, import_legacy
        source = self.make_database()
        conn = sqlite3.connect(source)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute("UPDATE products SET stock_base=9")
            conn.commit()
            with self.assertRaises(ValueError): import_legacy(self.paths, source, True)
            target = consistent_copy(source, self.root / 'online-backup.sqlite3')
            with closing(sqlite3.connect(target)) as dst:
                self.assertEqual(dst.execute('SELECT stock_base FROM products').fetchone()[0], 9)
        finally: conn.close()


class LocalControlTests(unittest.TestCase):
    def test_identity_cannot_be_replayed_with_another_challenge(self):
        from sigec.desktop import signature, verify_instance, PROTOCOL
        secret = 'a' * 64
        stale = signature(secret, '0' * 64)
        with patch('sigec.desktop.request_local', return_value=(200, {'protocol': PROTOCOL, 'proof': stale, 'ready': True})):
            self.assertFalse(verify_instance({'secret': secret}))
        with patch('sigec.desktop.request_local', return_value=(200, {'status': 'ok', 'storage': 'SQLite local'})):
            self.assertFalse(verify_instance({'secret': secret}))

    def test_readiness_requires_health_page_and_local_assets(self):
        from sigec.desktop import resources_ready
        valid = [(200, {'status': 'ok'}), (200, b'x' * 200), (200, b'j' * 200), (200, b'c' * 200)]
        with patch('sigec.desktop.request_local', side_effect=valid):
            self.assertTrue(resources_ready(12345))
        with patch('sigec.desktop.request_local', side_effect=valid[:2] + [(404, b'absent')]):
            self.assertFalse(resources_ready(12345))
        with patch('sigec.desktop.request_local', return_value=(500, {'error': 'falhou'})):
            self.assertFalse(resources_ready(12345))

    def test_stop_is_authenticated_and_blocks_new_work_while_draining(self):
        from sigec.desktop import LocalControl
        started, finish = threading.Event(), threading.Event()
        def application(env, start):
            started.set()
            finish.wait(5)
            start('200 OK', [])
            return [b'done']
        control = LocalControl(application, 'secret')
        def work(): return list(control({'PATH_INFO': '/'}, lambda *a: None))
        with ThreadPoolExecutor(max_workers=2) as pool:
            work_future = pool.submit(work)
            self.assertTrue(started.wait(2))
            status = []
            control({'PATH_INFO': '/_sigec/stop', 'REQUEST_METHOD': 'POST', 'HTTP_X_SIGEC_CONTROL': 'wrong'}, lambda s, h: status.append(s))
            self.assertEqual(status[-1], '403 Forbidden')
            self.assertFalse(control.draining)
            control({'PATH_INFO': '/_sigec/stop', 'REQUEST_METHOD': 'POST', 'HTTP_X_SIGEC_CONTROL': 'secret', 'HTTP_ORIGIN': 'http://other'}, lambda s, h: status.append(s))
            self.assertEqual(status[-1], '403 Forbidden')
            control({'PATH_INFO': '/_sigec/stop', 'REQUEST_METHOD': 'POST', 'HTTP_X_SIGEC_CONTROL': 'secret'}, lambda s, h: status.append(s))
            self.assertEqual(status[-1], '202 Accepted')
            idle = pool.submit(control.wait_idle)
            self.assertFalse(idle.done())
            control({'PATH_INFO': '/'}, lambda s, h: status.append(s))
            self.assertEqual(status[-1], '503 Service Unavailable')
            finish.set()
            self.assertEqual(work_future.result(3), [b'done'])
            idle.result(3)

    def test_lock_contention_across_processes_and_release_after_crash(self):
        from sigec.locking import FileLock
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lock'
            code = 'import sys,time; from pathlib import Path; from sigec.locking import FileLock; l=FileLock(Path(sys.argv[1])); assert l.acquire(); print("locked",flush=True); time.sleep(30)'
            proc = subprocess.Popen([sys.executable, '-c', code, str(path)], cwd=ROOT, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(proc.stdout.readline().strip(), 'locked')
                lock = FileLock(path)
                self.assertFalse(lock.acquire())
                proc.kill()  # Somente processo de teste, sem servidor/banco.
                proc.wait(5)
                self.assertTrue(lock.acquire(timeout=2))
                lock.release()
            finally:
                if proc.poll() is None: proc.kill(); proc.wait(5)
                proc.stdout.close()


class RealServerTests(unittest.TestCase):
    def setUp(self):
        from sigec.paths import AppPaths
        self.temp = tempfile.TemporaryDirectory(prefix='sigec servidor ç ')
        self.paths = AppPaths(Path(self.temp.name))
        self.paths.prepare_runtime()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.procs = []

    def tearDown(self):
        from sigec.desktop import stop_application
        try: stop_application(self.paths, self.port, timeout=5)
        except Exception: pass
        for proc in self.procs:
            try: proc.wait(8)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(3)
            if proc.stdout: proc.stdout.close()
        self.temp.cleanup()

    def start(self, browser=False):
        code = '''import sys
from pathlib import Path
from sigec.paths import AppPaths
from sigec.desktop import configure_logging,run_application
p=AppPaths(Path(sys.argv[1])); configure_logging(p)
raise SystemExit(run_application(p,browser=False,port=int(sys.argv[2])))
'''
        proc = subprocess.Popen([sys.executable, '-c', code, str(self.paths.root), str(self.port)],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.procs.append(proc)
        return proc

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        try:
            conn.request(method, path, json.dumps(body) if body is not None else None,
                         {'Content-Type': 'application/json'} if body is not None else {})
            response = conn.getresponse()
            return response.status, response.read()
        finally: conn.close()

    def test_simultaneous_start_single_server_persistence_and_graceful_stop(self):
        from sigec.desktop import wait_ready, read_state, stop_application
        a, b = self.start(), self.start()
        wait_ready(self.paths, self.port, timeout=8)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and a.poll() is None and b.poll() is None: time.sleep(.05)
        self.assertEqual(sum(p.poll() is None for p in (a, b)), 1)
        self.assertIn(0, (a.poll(), b.poll()))
        first_pid = read_state(self.paths)['pid']
        # No Windows o python.exe do venv e um lancador com PID proprio.
        if sys.platform == 'win32':
            self.assertGreater(first_pid, 0)
        else:
            self.assertIn(first_pid, (a.pid, b.pid))
        for path in ('/', '/static/app.js', '/static/style.css', '/api/health'):
            self.assertEqual(self.call('GET', path)[0], 200)
        product = json.loads(self.call('POST', '/api/products', {'name': 'Arroz teste', 'unit': 'UN', 'stock': '10', 'price': '6'})[1])
        self.assertEqual(self.call('POST', '/api/cash/open', {'opening': '100'})[0], 201)
        sale = {'token': 'packaging-sale-001', 'items': [{'product_id': product['id'], 'quantity': '2'}], 'payments': [{'method': 'CASH', 'applied': '12', 'tendered': '20'}]}
        self.assertEqual(self.call('POST', '/api/sales', sale)[0], 201)
        c = self.start(); self.assertEqual(c.wait(5), 0)
        self.assertEqual(read_state(self.paths)['pid'], first_pid)
        stop_application(self.paths, self.port, timeout=8)
        for proc in (a, b): self.assertEqual(proc.wait(5), 0)
        restarted = self.start()
        wait_ready(self.paths, self.port, timeout=8)
        self.assertEqual(json.loads(self.call('GET', '/api/products')[1])[0]['stock_base'], 8)
        self.assertEqual(json.loads(self.call('GET', '/api/cash')[1])['expected_cents'], 11200)
        self.assertEqual(len(json.loads(self.call('GET', '/api/sales')[1])), 1)
        stop_application(self.paths, self.port, timeout=8)
        self.assertEqual(restarted.wait(5), 0)

    def test_browser_is_opened_only_after_authenticated_readiness(self):
        from sigec.desktop import run_application, read_state, verify_instance, stop_application
        stopped = []
        def browser(port):
            self.assertTrue(verify_instance(read_state(self.paths), port))
            self.assertEqual(self.call('GET', '/')[0], 200)
            stop_thread = threading.Thread(target=lambda: stop_application(self.paths, port, timeout=5))
            stopped.append(stop_thread)
            stop_thread.start()
        with patch('sigec.desktop.open_browser', side_effect=browser) as opened:
            self.assertEqual(run_application(self.paths, browser=True, port=self.port), 0)
            opened.assert_called_once_with(self.port)
        stopped[0].join(5)
        self.assertFalse(stopped[0].is_alive())

    def test_occupied_port_does_not_open_browser_or_kill_other_program(self):
        from sigec.desktop import run_application, stop_application
        from sigec.locking import FileLock
        with socket.socket() as other:
            other.bind(('127.0.0.1', self.port)); other.listen()
            with patch('sigec.desktop.open_browser') as browser:
                with self.assertRaisesRegex(RuntimeError, 'ocupada'):
                    run_application(self.paths, browser=True, port=self.port)
                browser.assert_not_called()
            stop_application(self.paths, self.port)
            self.assertEqual(other.getsockname()[1], self.port)
            self.assertFalse(self.paths.database.exists())
            lock = FileLock(self.paths.runtime / 'server.lock')
            self.assertTrue(lock.acquire()); lock.release()

    def test_fake_health_with_stale_state_and_lock_never_opens_browser(self):
        from sigec.desktop import run_application
        from sigec.locking import FileLock
        self.paths.runtime.joinpath('instance.json').write_text(json.dumps({'secret': 'a' * 64}))
        lock = FileLock(self.paths.runtime / 'server.lock')
        self.assertTrue(lock.acquire())
        try:
            with patch('sigec.desktop.wait_ready', side_effect=RuntimeError('não respondeu')), patch('sigec.desktop.open_browser') as browser:
                with self.assertRaises(RuntimeError): run_application(self.paths, port=self.port)
                browser.assert_not_called()
        finally: lock.release()


class PayloadSafetyTests(unittest.TestCase):
    def test_windows_shortcut_uses_windowless_launcher_and_brand_icon(self):
        import struct
        spec = (ROOT / 'packaging' / 'SIGEC.spec').read_text(encoding='utf-8')
        installer = (ROOT / 'packaging' / 'installer.iss').read_text(encoding='utf-8')
        asset = (ROOT / 'packaging' / 'sigec.ico').read_bytes()
        self.assertEqual(struct.unpack_from('<HH', asset), (0, 1))
        self.assertGreaterEqual(struct.unpack_from('<H', asset, 4)[0], 4)
        shortcut = next(line for line in installer.splitlines() if line.startswith('Name: "{userdesktop}'))
        self.assertIn('SIGEC.exe', shortcut)
        self.assertIn('IconIndex: 0', shortcut)
        self.assertNotIn('Parameters:', shortcut)
        self.assertIn('SetupIconFile=sigec.ico', installer)
        self.assertIn("icon=str(root / 'packaging' / 'sigec.ico')", spec)
        self.assertIn('console=False', spec)

    def test_payload_rejects_databases_and_publishes_exact_hashes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('sigec_prepare_payload', ROOT / 'packaging' / 'prepare_payload.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module.ROOT = root
            (root / 'VERSION').write_text('1.0.0')
            payload = root / 'dist' / 'SIGEC'
            payload.mkdir(parents=True)
            (payload / 'SIGEC.exe').write_bytes(b'test fixture; not a Windows executable')
            (payload / 'sigec.sqlite3').write_bytes(b'never ship')
            with self.assertRaisesRegex(ValueError, 'permitido'): module.prepare_manifest()
            self.assertFalse((root / 'build' / 'payload-files.iss').exists())
            (payload / 'sigec.sqlite3').unlink()
            module.prepare_version()
            module.prepare_manifest()
            manifest = json.loads((root / 'build' / 'payload.json').read_text())
            self.assertEqual(manifest['files'][0]['sha256'], hashlib.sha256((payload / 'SIGEC.exe').read_bytes()).hexdigest())
            self.assertIn('Check: NeedsFile', (root / 'build' / 'payload-files.iss').read_text())
            self.assertIn('1, 0, 0, 0', (root / 'build' / 'version_info.txt').read_text())
