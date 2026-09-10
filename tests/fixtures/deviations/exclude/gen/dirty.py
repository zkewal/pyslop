"""Deliberately swallowing; silenced via [tool.pyslop] exclude."""


def load(path):
    try:
        return open(path).read()
    except OSError:
        pass
