"""SEC-1: 生产环境密钥默认值启动校验。"""

import pytest

from app.core import config


def test_dev_env_with_defaults_only_warns(monkeypatch):
    """dev 环境（默认）用默认密钥不抛错（仅 warning）。"""
    monkeypatch.setattr(config.settings, "ENV", "dev")
    monkeypatch.setattr(config.settings, "SECRET_KEY", config._DEFAULT_SECRET_KEY)
    monkeypatch.setattr(config.settings, "INVITE_CODE_SECRET", config._DEFAULT_INVITE_SECRET)
    monkeypatch.setattr(config.settings, "LICENSE_SECRET", config._DEFAULT_LICENSE_SECRET)
    monkeypatch.setattr(config.settings, "LICENSE_API_KEY", config._DEFAULT_LICENSE_API_KEY)
    # 不抛错
    config.validate_security_secrets()


def test_production_env_with_defaults_raises(monkeypatch):
    """production 环境用默认密钥必须抛 RuntimeError。"""
    monkeypatch.setattr(config.settings, "ENV", "production")
    monkeypatch.setattr(config.settings, "SECRET_KEY", config._DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="默认密钥"):
        config.validate_security_secrets()


def test_production_env_with_secure_secrets_passes(monkeypatch):
    """production 环境配置了安全密钥则通过。"""
    monkeypatch.setattr(config.settings, "ENV", "production")
    monkeypatch.setattr(config.settings, "SECRET_KEY", "a-very-secure-random-key-32bytes")
    monkeypatch.setattr(config.settings, "INVITE_CODE_SECRET", "secure-invite-secret")
    monkeypatch.setattr(config.settings, "LICENSE_SECRET", "secure-license-secret")
    monkeypatch.setattr(config.settings, "LICENSE_API_KEY", "secure-api-key")
    config.validate_security_secrets()


def test_production_env_partial_defaults_raises(monkeypatch):
    """production 环境只要有一个密钥是默认值就抛错。"""
    monkeypatch.setattr(config.settings, "ENV", "production")
    monkeypatch.setattr(config.settings, "SECRET_KEY", "secure-key")
    monkeypatch.setattr(config.settings, "INVITE_CODE_SECRET", config._DEFAULT_INVITE_SECRET)
    monkeypatch.setattr(config.settings, "LICENSE_SECRET", "secure-license")
    monkeypatch.setattr(config.settings, "LICENSE_API_KEY", "secure-api-key")
    with pytest.raises(RuntimeError, match="INVITE_CODE_SECRET"):
        config.validate_security_secrets()
