"""Tests for config module."""

import os
import pytest
from pathlib import Path


class TestLoadConfig:
    """Test load_config function."""

    def test_returns_defaults_when_no_config(self, tmp_path, monkeypatch):
        """Should return defaults when config.yaml doesn't exist."""
        # Point HOME to temp dir (no config.yaml there)
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Clear any env override
        monkeypatch.delenv("DENG_CATALOG_DIR", raising=False)

        # Force reimport to pick up new HOME
        import importlib
        import config

        importlib.reload(config)

        result = config.load_config()

        assert "catalog_dir" in result
        assert result["catalog_dir"].endswith("data-catalog")
        assert result["catalog_remote"] == ""

    def test_reads_config_yaml(self, tmp_path, monkeypatch):
        """Should read catalog_dir from config.yaml."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        toolkit_dir = fake_home / ".deng-toolkit"
        toolkit_dir.mkdir()

        config_yaml = toolkit_dir / "config.yaml"
        config_yaml.write_text("""
catalog_dir: /custom/catalog/path
catalog_remote: git@github.com:test/repo.git
""")

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("DENG_CATALOG_DIR", raising=False)

        import importlib
        import config

        importlib.reload(config)

        result = config.load_config()

        assert result["catalog_dir"] == "/custom/catalog/path"
        assert result["catalog_remote"] == "git@github.com:test/repo.git"

    def test_expands_tilde_in_path(self, tmp_path, monkeypatch):
        """Should expand ~ in catalog_dir."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        toolkit_dir = fake_home / ".deng-toolkit"
        toolkit_dir.mkdir()

        config_yaml = toolkit_dir / "config.yaml"
        config_yaml.write_text("catalog_dir: ~/my-catalog")

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("DENG_CATALOG_DIR", raising=False)

        import importlib
        import config

        importlib.reload(config)

        result = config.load_config()

        # Should be expanded (not contain ~)
        assert "~" not in result["catalog_dir"]
        assert result["catalog_dir"].endswith("my-catalog")


class TestGetCatalogDir:
    """Test get_catalog_dir function."""

    def test_env_var_overrides_config(self, tmp_path, monkeypatch):
        """Environment variable should take precedence."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        toolkit_dir = fake_home / ".deng-toolkit"
        toolkit_dir.mkdir()

        config_yaml = toolkit_dir / "config.yaml"
        config_yaml.write_text("catalog_dir: /from/config")

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("DENG_CATALOG_DIR", "/from/env")

        import importlib
        import config

        importlib.reload(config)

        result = config.get_catalog_dir()

        assert str(result) == "/from/env"

    def test_returns_path_object(self, tmp_path, monkeypatch):
        """Should return a Path object, not string."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("DENG_CATALOG_DIR", raising=False)

        import importlib
        import config

        importlib.reload(config)

        result = config.get_catalog_dir()

        assert isinstance(result, Path)


class TestGetCatalogRemote:
    """Test get_catalog_remote function."""

    def test_returns_none_when_not_configured(self, tmp_path, monkeypatch):
        """Should return None when catalog_remote is empty."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        monkeypatch.setenv("HOME", str(fake_home))

        import importlib
        import config

        importlib.reload(config)

        result = config.get_catalog_remote()

        assert result is None

    def test_returns_remote_when_configured(self, tmp_path, monkeypatch):
        """Should return the remote URL when configured."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        toolkit_dir = fake_home / ".deng-toolkit"
        toolkit_dir.mkdir()

        config_yaml = toolkit_dir / "config.yaml"
        config_yaml.write_text("catalog_remote: git@github.com:team/catalog.git")

        monkeypatch.setenv("HOME", str(fake_home))

        import importlib
        import config

        importlib.reload(config)

        result = config.get_catalog_remote()

        assert result == "git@github.com:team/catalog.git"
