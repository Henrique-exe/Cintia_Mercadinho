"""Fábrica carregada sob demanda, inclusive pelo inicializador empacotado."""

def create_app(test_config=None):
    from .app import create_app as factory
    return factory(test_config)
