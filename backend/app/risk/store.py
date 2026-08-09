"""In-memory risk config store — no secrets / no broker keys."""

from __future__ import annotations

from typing import Optional

from app.risk.config import AccountRiskConfig

_CONFIG: AccountRiskConfig = AccountRiskConfig()


def get_risk_config() -> AccountRiskConfig:
    return _CONFIG.model_copy(deep=True)


def set_risk_config(cfg: AccountRiskConfig) -> AccountRiskConfig:
    global _CONFIG
    _CONFIG = cfg.model_copy(deep=True)
    return get_risk_config()


def reset_risk_config(cfg: Optional[AccountRiskConfig] = None) -> AccountRiskConfig:
    global _CONFIG
    _CONFIG = (cfg or AccountRiskConfig()).model_copy(deep=True)
    return get_risk_config()
