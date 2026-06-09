import pytest

from .common import db


def _insert_grille_stoc():
    grille = [
        {"centre": {"type": "Point", "coordinates": [2.551195605, 51.0423964]}, "numero": "590017"},
        {"centre": {"type": "Point", "coordinates": [2.181529126, 51.0245531]}, "numero": "590018"},
        {"centre": {"type": "Point", "coordinates": [2.209959021, 51.02458538]}, "numero": "590019"},
        {"centre": {"type": "Point", "coordinates": [2.238388948, 51.02461118]}, "numero": "590020"},
        {"centre": {"type": "Point", "coordinates": [2.266818902, 51.0246305]}, "numero": "590021"}
    ]
    for cell in grille:
        db.grille_stoc.insert(cell)
    return grille


@pytest.fixture
def grille_stoc(request):
    grille = _insert_grille_stoc()

    def finalizer():
        db.grille_stoc.remove()

    request.addfinalizer(finalizer)
    return grille


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="run slow tests")
    parser.addoption("--with-r-support", action="store_true", help="run test needing R")


def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getoption("--runslow"):
        pytest.skip("need --runslow option to run")
    if 'rtest' in item.keywords and not item.config.getoption("--with-r-support"):
        pytest.skip("need --with-r-support option to run")
