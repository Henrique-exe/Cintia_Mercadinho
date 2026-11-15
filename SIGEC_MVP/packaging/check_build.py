"""Pré-condições do runtime de build; sem instalar nem alterar Python global."""
import platform
import struct
import sys
import sysconfig

if not (sys.platform == 'win32' and sys.version_info[:3] == (3, 14, 10)
        and platform.python_implementation() == 'CPython'
        and struct.calcsize('P') == 8 and platform.machine() == 'AMD64'
        and not sysconfig.get_config_var('Py_GIL_DISABLED')):
    raise SystemExit('Use exatamente CPython 3.14.10 Windows x64 padrão (com GIL).')
print('Runtime de build confirmado: CPython 3.14.10 x64.')
