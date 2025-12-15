import multiprocessing

import pytest


def pytest_configure(config):
    import sys
    sys._called_from_pytest = True


def pytest_unconfigure(config):
    import sys
    del sys._called_from_pytest


@pytest.fixture(scope="session", autouse=True)
def use_multiprocessing_fork_on_linux():
    import sys
    if sys.platform != "linux":
        # Windows and macOS use 'spawn' by default
        return

    # 'forkserver' is default since Python 3.14, but can't pickle everything.
    multiprocessing.set_start_method("fork")
