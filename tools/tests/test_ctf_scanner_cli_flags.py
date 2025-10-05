import importlib


def test_import_and_flags():
    mod = importlib.import_module('tools.ctf_scanner')
    # smoke: ensure the main function exists and our expected globals are present
    assert hasattr(mod, 'main')
    assert hasattr(mod, 'CHROMEDRIVER_PATH')
    assert hasattr(mod, 'BROWSER_BINARY')