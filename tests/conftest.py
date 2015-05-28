import pytest


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="run slow tests")
    parser.addoption("--with-r-support", action="store_true", help="run test needing R")


def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getoption("--runslow"):
        pytest.skip("need --runslow option to run")
    if 'rtest' in item.keywords and not item.config.getoption("--with-r-support"):
        pytest.skip("need --with-r-support option to run")
