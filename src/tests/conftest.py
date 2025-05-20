import pytest
from settings import CONVERSION_TIMEOUT

def pytest_configure(config):
    config.addinivalue_line("markers", "timeout: dynamically added timeout marker")

def pytest_collection_modifyitems(config, items):
    for item in items:
        marker = pytest.mark.timeout(CONVERSION_TIMEOUT + 10)
        item.add_marker(marker)
        print(f"Added marker: {marker} to {item.nodeid}")
