"""Coordena a aplicação WEB local. Não contém telas nem regras de negócio."""
import ctypes
import hashlib
import hmac
import http.client
import json
import logging
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs
from .locking import FileLock

HOST, PORT = '127.0.0.1', 5000
MAINTENANCE_MUTEX = 'Local\\SIGEC.Maintenance.7A8549B2'
PROTOCOL = 'sigec-local-v1'


def windows_api():
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    api.OpenMutexW.restype = wintypes.HANDLE
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api


def maintenance_active():
    if os.name != 'nt': return False
    api = windows_api()
    handle = api.OpenMutexW(0x00100000, False, MAINTENANCE_MUTEX)
    if handle:
        api.CloseHandle(handle)
        return True
    error = ctypes.get_last_error()
    if error not in (0, 2):
        raise RuntimeError('Não foi possível verificar a manutenção do SIGEC.')
    return False


def ensure_not_maintaining(paths=None):
    locked = False
    if paths is not None:
        try:
            with open(paths.runtime / 'maintenance.lock', 'a+b'):
                pass
        except OSError:
            locked = True
    if locked or maintenance_active():
        raise RuntimeError('Há uma instalação ou desinstalação do SIGEC em andamento. Aguarde sua conclusão.')


def configure_logging(paths):
    paths.prepare_runtime()
    handler = RotatingFileHandler(paths.logs / 'sigec.log', maxBytes=2_000_000,
                                  backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return handler


def message(text, error=False):
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None, text, 'SIGEC', 0x10 if error else 0x40)
    elif sys.stderr:
        print(text, file=sys.stderr)


def signature(secret, challenge):
    return hmac.new(secret.encode('ascii'), (PROTOCOL + ':' + challenge).encode('ascii'), hashlib.sha256).hexdigest()


def request_local(port, method, path, headers=None, json_body=True):
    # http.client usa somente o loopback; ignora proxies configurados no sistema.
    conn = http.client.HTTPConnection(HOST, port, timeout=0.8)
    try:
        conn.request(method, path, body=b'' if method == 'POST' else None, headers=headers or {})
        response = conn.getresponse()
        data = response.read(8192)
        return response.status, json.loads(data) if json_body else data
    finally:
        conn.close()


def verify_instance(state, port=PORT):
    challenge = secrets.token_hex(32)
    try:
        status, body = request_local(port, 'GET', '/_sigec/identity?challenge=' + challenge)
        expected = signature(state['secret'], challenge)
        return (status == 200 and isinstance(body, dict) and body.get('protocol') == PROTOCOL
                and hmac.compare_digest(body.get('proof', ''), expected)
                and body.get('ready') is True)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        return False


def read_state(paths):
    try:
        state = json.loads((paths.runtime / 'instance.json').read_text('utf-8'))
        if not isinstance(state, dict) or not isinstance(state.get('secret'), str) or len(state['secret']) != 64: return None
        return state
    except (OSError, ValueError, KeyError, TypeError):
        return None


def resources_ready(port):
    try:
        status, health = request_local(port, 'GET', '/api/health')
        if status != 200 or not isinstance(health, dict) or health.get('status') != 'ok':
            return False
        for path in ('/', '/static/app.js', '/static/style.css'):
            status, data = request_local(port, 'GET', path, json_body=False)
            if status != 200 or len(data) < 100: return False
        return True
    except (OSError, ValueError, TypeError, http.client.HTTPException):
        return False


def wait_ready(paths, port, timeout=30, thread=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = read_state(paths)
        if state and verify_instance(state, port) and resources_ready(port): return state
        if thread is not None and not thread.is_alive(): break
        time.sleep(0.1)
    raise RuntimeError('O SIGEC não respondeu à verificação de inicialização. A página não foi aberta.')


def open_browser(port):
    if not webbrowser.open(f'http://{HOST}:{port}/', new=2):
        raise RuntimeError(f'O SIGEC iniciou, mas o navegador não abriu. Acesse http://{HOST}:{port}/ no navegador padrão.')


class LocalControl:
    """Autentica identidade/parada e drena requisições antes de liberar arquivos."""
    def __init__(self, app, secret):
        self.app, self.secret = app, secret
        self.stop_event = threading.Event()
        self.condition = threading.Condition()
        self.active = 0
        self.draining = False

    def stop(self):
        with self.condition:
            self.draining = True
            self.stop_event.set()

    def wait_idle(self):
        # Sem kill por timeout: transações em andamento terminam antes de sair.
        with self.condition:
            self.condition.wait_for(lambda: self.active == 0)

    @staticmethod
    def reply(start_response, status, data):
        payload = json.dumps(data).encode('utf-8')
        start_response(status, [('Content-Type', 'application/json'), ('Content-Length', str(len(payload))),
                                ('Cache-Control', 'no-store')])
        return [payload]

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path == '/_sigec/identity':
            challenge = parse_qs(environ.get('QUERY_STRING', '')).get('challenge', [''])[0]
            if len(challenge) != 64 or any(c not in '0123456789abcdef' for c in challenge):
                return self.reply(start_response, '400 Bad Request', {})
            return self.reply(start_response, '200 OK', {'protocol': PROTOCOL,
                              'proof': signature(self.secret, challenge), 'ready': not self.draining})
        if path == '/_sigec/stop':
            token = environ.get('HTTP_X_SIGEC_CONTROL', '')
            if (environ.get('REQUEST_METHOD') != 'POST' or environ.get('HTTP_ORIGIN')
                    or not hmac.compare_digest(token, self.secret)):
                return self.reply(start_response, '403 Forbidden', {})
            self.stop()
            return self.reply(start_response, '202 Accepted', {'stopping': True})
        with self.condition:
            if self.draining:
                return self.reply(start_response, '503 Service Unavailable', {'error': 'SIGEC encerrando. Aguarde.'})
            self.active += 1
        def response():
            result = None
            try:
                result = self.app(environ, start_response)
                yield from result
            finally:
                try:
                    if hasattr(result, 'close'): result.close()
                finally:
                    with self.condition:
                        self.active -= 1
                        self.condition.notify_all()
        return response()


def reserve_socket(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            # Evita que outro bind Windows compartilhe nossa porta inadvertidamente.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((HOST, port))
        sock.listen(128)
        return sock
    except OSError as exc:
        sock.close()
        raise RuntimeError(f'A porta {port} está ocupada ou indisponível. Feche o programa que a utiliza e tente novamente. Nenhum outro programa foi encerrado.') from exc


def run_application(paths, browser=True, port=PORT):
    ensure_not_maintaining(paths)
    from waitress import create_server
    # A trava do servidor também é usada pela importação e pelo comando de parada.
    ownership = FileLock(paths.runtime / 'server.lock')
    gate = FileLock(paths.runtime / 'startup.lock')
    server = control = sock = thread = None
    try:
        with gate:
            ensure_not_maintaining(paths)
            if not ownership.acquire():
                wait_ready(paths, port)
                if browser: open_browser(port)
                return 0
            sock = reserve_socket(port)
            from . import create_app
            control = LocalControl(create_app({'DATABASE': str(paths.database)}), secrets.token_hex(32))
            server = create_server(control, sockets=[sock], threads=4, asyncore_loop_timeout=0.1)
            state_path = paths.runtime / 'instance.json'
            temp = paths.runtime / 'instance.tmp'
            temp.write_text(json.dumps({'secret': control.secret, 'pid': os.getpid()}), encoding='utf-8')
            if os.name != 'nt': temp.chmod(0o600)
            temp.replace(state_path)
            thread = threading.Thread(target=server.run, name='SIGEC-HTTP', daemon=True)
            thread.start()
            wait_ready(paths, port, thread=thread)
            logging.info('SIGEC pronto em http://%s:%s; banco=%s', HOST, port, paths.database)
            if browser:
                try: open_browser(port)
                except Exception as exc:
                    logging.exception('Falha ao abrir navegador')
                    message(str(exc), error=True)
        try:
            while not control.stop_event.wait(0.2):
                if not thread.is_alive():
                    raise RuntimeError('O servidor SIGEC parou inesperadamente.')
        except KeyboardInterrupt:
            control.stop()
        control.wait_idle()
        logging.info('Requisições concluídas; encerrando SIGEC.')
        return 0
    finally:
        # Também espera transações se houver falha após o servidor ficar disponível.
        if control:
            control.stop()
            control.wait_idle()
        if server:
            server.task_dispatcher.shutdown(cancel_pending=True, timeout=30)
            from waitress import wasyncore
            wasyncore.close_all(map=server._map)
        elif sock:
            sock.close()
        if thread: thread.join(timeout=2)
        if ownership.file is not None:
            (paths.runtime / 'instance.json').unlink(missing_ok=True)
        ownership.release()


def stop_application(paths, port=PORT, timeout=40):
    with FileLock(paths.runtime / 'startup.lock'):
        lock = FileLock(paths.runtime / 'server.lock')
        if lock.acquire():
            lock.release()
            return
        state = read_state(paths)
        if not state or not verify_instance(state, port):
            raise RuntimeError('Não foi possível confirmar a identidade do SIGEC. Encerre-o com segurança e tente novamente; nenhum processo será forçado.')
        # Abre somente direito de espera, nunca direito de terminar processo.
        handle = None
        if os.name == 'nt' and int(state['pid']) != os.getpid():
            handle = windows_api().OpenProcess(0x00100000, False, int(state['pid']))
            if not handle:
                raise RuntimeError('Não foi possível acompanhar o encerramento do SIGEC. Tente novamente.')
        try:
            status, _ = request_local(port, 'POST', '/_sigec/stop', {'X-SIGEC-Control': state['secret']})
            if status != 202: raise RuntimeError('O SIGEC recusou o encerramento.')
            if not lock.acquire(timeout=timeout):
                raise RuntimeError('O SIGEC ainda está concluindo operações. A manutenção foi cancelada; aguarde e tente novamente.')
            lock.release()
            # Espera a saída real no Windows para liberar também EXE e DLLs carregadas.
            if handle and windows_api().WaitForSingleObject(handle, 5000) != 0:
                raise RuntimeError('O processo SIGEC ainda está encerrando. Tente novamente.')
        finally:
            if handle: windows_api().CloseHandle(handle)
