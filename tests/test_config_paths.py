import sys
from importlib import reload
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_resolve_path_relative(monkeypatch):
    import bot.config as config

    monkeypatch.delenv("LOG_DIR", raising=False)
    reload(config)

    expected = Path(config.__file__).resolve().parent.parent / "logs"
    assert config._resolve_path("logs") == str(expected)


def test_log_dir_env_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    import bot.config as config

    reload(config)

    assert config.LOG_DIR == str(tmp_path)


def test_log_dir_env_relative(monkeypatch):
    monkeypatch.setenv("LOG_DIR", "custom_logs")

    import bot.config as config

    reload(config)

    expected = Path(config.__file__).resolve().parent.parent / "custom_logs"
    assert config.LOG_DIR == str(expected)
