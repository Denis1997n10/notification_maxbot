import os
import pytest
from composition.container import build_container


def test_local_builds_mocks(monkeypatch):
    monkeypatch.setenv('ENV', 'local')
    c = build_container()
    assert c.public_service.get_entrance_page('x')['mock'] is True


def test_nonlocal_fails_fast(monkeypatch):
    monkeypatch.setenv('ENV', 'dev')
    monkeypatch.delenv('USE_MOCKS', raising=False)
    with pytest.raises(NotImplementedError):
        build_container()
