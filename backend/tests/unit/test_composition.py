import os

from composition import container as cmod


def test_local_builds_mocks(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    c = cmod.build_container()
    assert c.public_service.get_entrance_page("x")["mock"] is True


def test_nonlocal_builds_real_with_patched_deps(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("USE_MOCKS", "false")
    monkeypatch.setenv("YDB_ENDPOINT", "grpc://fake")
    monkeypatch.setenv("YDB_DATABASE", "/ru/fake")

    class FakeSession:
        pass

    class FakeClient:
        def __init__(self, cfg):
            self.cfg = cfg

        def session(self):
            return FakeSession()

    class FakeSecret:
        def __init__(self, env):
            self.env = env

        def get_secret(self, key):
            return "x"

    class FakeMaxClient:
        def __init__(self, *args, **kwargs):
            pass

    class FakeMaxChannel:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(cmod, "YdbClient", FakeClient)
    monkeypatch.setattr(cmod, "YandexLockboxSecretProvider", FakeSecret)
    monkeypatch.setattr(cmod, "MaxClient", FakeMaxClient)
    monkeypatch.setattr(cmod, "MaxNotificationChannel", FakeMaxChannel)

    container = cmod.build_container()
    assert container.public_service is not None
    assert container.admin_service is not None
    assert container.bot_service is not None
