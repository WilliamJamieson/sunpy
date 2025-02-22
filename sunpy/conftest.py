import os
import logging
import tempfile
import importlib

import pytest

import astropy
import astropy.config.paths

from sunpy.util import SunpyUserWarning

# Force MPL to use non-gui backends for testing.
try:
    import matplotlib
    import matplotlib.pyplot as plt
except ImportError:
    HAVE_MATPLOTLIB = False
else:
    HAVE_MATPLOTLIB = True
    matplotlib.use('Agg')

# Don't actually import pytest_remotedata because that can do things to the
# entrypoints code in pytest.
remotedata_spec = importlib.util.find_spec("pytest_remotedata")
HAVE_REMOTEDATA = remotedata_spec is not None


# Do not collect the sample data file because this would download the sample data.
collect_ignore = ["data/sample.py"]


console_logger = logging.getLogger()
console_logger.setLevel('INFO')


@pytest.fixture
def jsoc_test_email():
    return "nabil.freij@gmail.com"


@pytest.fixture(scope='session', autouse=True)
def tmp_config_dir(request):
    """
    Globally set the default config for all tests.
    """
    tmpdir = tempfile.TemporaryDirectory()

    os.environ["SUNPY_CONFIGDIR"] = str(tmpdir.name)
    astropy.config.paths.set_temp_config._temp_path = str(tmpdir.name)
    astropy.config.paths.set_temp_cache._temp_path = str(tmpdir.name)

    yield

    del os.environ["SUNPY_CONFIGDIR"]
    tmpdir.cleanup()
    astropy.config.paths.set_temp_config._temp_path = None
    astropy.config.paths.set_temp_cache._temp_path = None


@pytest.fixture()
def sunpy_cache(mocker, tmp_path):
    """
    Provide a way to add local files to the cache. This can be useful when mocking
    remote requests.
    """
    from types import MethodType

    from sunpy.data.data_manager.cache import Cache
    from sunpy.data.data_manager.downloader import ParfiveDownloader
    from sunpy.data.data_manager.storage import InMemStorage
    cache = Cache(
        ParfiveDownloader(),
        InMemStorage(),
        tmp_path,
        None
    )

    def add(self, url, path):
        self._storage.store({
            'url': url,
            'file_path': path,
            'file_hash': 'none',  # hash doesn't matter
        })
    cache.add = MethodType(add, cache)

    def func(mocked):
        mocker.patch(mocked, cache)
        return cache
    yield func


@pytest.fixture()
def undo_config_dir_patch():
    """
    Provide a way for certain tests to not have the config dir.
    """
    oridir = os.environ["SUNPY_CONFIGDIR"]
    del os.environ["SUNPY_CONFIGDIR"]
    yield
    os.environ["SUNPY_CONFIGDIR"] = oridir


@pytest.fixture(scope='session', autouse=True)
def hide_parfive_progress(request):
    """
    Globally set the HIDE_PARFIVE_PROGESS to hide the parfive progress bar in tests.
    Used by the parfive helper class only.
    """
    os.environ["HIDE_PARFIVE_PROGESS"] = "True"
    yield
    del os.environ["HIDE_PARFIVE_PROGESS"]


@pytest.fixture(scope='session', autouse=True)
def tmp_dl_dir(request):
    """
    Globally set the default download directory for the test run to a tmp dir.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SUNPY_DOWNLOADDIR"] = tmpdir
        yield tmpdir
        del os.environ["SUNPY_DOWNLOADDIR"]


@pytest.fixture(scope='session', autouse=True)
def set_columns(request):
    orig_columns = os.environ.get("COLUMNS", None)
    os.environ['COLUMNS'] = '180'
    yield
    if orig_columns is not None:
        os.environ['COLUMNS'] = orig_columns


@pytest.fixture()
def undo_download_dir_patch():
    """
    Provide a way for certain tests to not have tmp download dir.
    """
    oridir = os.environ["SUNPY_DOWNLOADDIR"]
    del os.environ["SUNPY_DOWNLOADDIR"]
    yield
    os.environ["SUNPY_DOWNLOADDIR"] = oridir


def pytest_runtest_setup(item):
    """
    pytest hook to skip all tests that have the mark 'remotedata' if the
    pytest_remotedata plugin is not installed.
    """
    if isinstance(item, pytest.Function):
        if 'remote_data' in item.keywords and not HAVE_REMOTEDATA:
            pytest.skip("skipping remotedata tests as pytest-remotedata is not installed")

    # Confirm that the pyplot figure stack is empty before the test
    if HAVE_MATPLOTLIB and plt.get_fignums():
        raise SunpyUserWarning(f"There are stale pyplot figures prior to running {item.name}")


def pytest_runtest_teardown(item):
    # Clear the pyplot figure stack if it is not empty after the test
    # You can see these log messages by passing "-o log_cli=true" to pytest on the command line
    if HAVE_MATPLOTLIB and plt.get_fignums():
        console_logger.info(f"Removing {len(plt.get_fignums())} pyplot figure(s) "
                            f"left open by {item.name}")
        plt.close('all')
