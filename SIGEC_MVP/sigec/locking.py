"""Locks liberados pelo SO inclusive em falha; o arquivo nunca é apagado."""
import os
import time


class FileLock:
    def __init__(self, path):
        self.path = path
        self.file = None

    def acquire(self, timeout=0):
        if self.file is not None:
            raise RuntimeError('Lock já adquirido por este objeto.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.path, 'a+b')
        if f.seek(0, 2) == 0:
            f.write(b'\0')
            f.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                f.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.file = f
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    f.close()
                    return False
                time.sleep(0.05)

    def release(self):
        if self.file is not None:
            f, self.file = self.file, None
            try:
                f.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f, fcntl.LOCK_UN)
            finally:
                f.close()

    def __enter__(self):
        if not self.acquire(timeout=45):
            raise RuntimeError('O SIGEC está iniciando ou em manutenção. Aguarde e tente novamente.')
        return self

    def __exit__(self, *args): self.release()
