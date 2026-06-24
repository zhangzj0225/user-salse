"""SEC-1: 生产环境密钥默认值启动校验（fail-closed）。

ENV 默认 production（见 config.py），测试环境由 conftest 设 ENV=dev 降级。
本文件用 monkeypatch 显式控制 ENV 验证 validate_security_secrets 的分支逻辑。
"""

import pytest

from app.core import config
from app.core.config import Settings


def test_env_field_defaults_to_production():
    """D3: ENV 字段默认 production（fail-closed），生产忘设 ENV 也会强校验。
    读字段定义默认值，不受运行时环境变量覆盖影响。"""
    assert Settings.model_fields["ENV"].default == "production"


def test_dev_env_with_defaults_only_warns(monkeypatch):
    """dev 环境用默认密钥不抛错（仅 warning）。需显式设 ENV=dev。"""
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
    monkeypatch.setattr(config.settings, "PAYMENT_CALLBACK_SECRET", "secure-callback-secret")
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
