import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Global settings store (in production, this would be in DB)
_settings = {
    "risk_per_trade": 1.0,
    "max_drawdown": 5.0,
    "ml_threshold": 60,
    "quant_confidence": 40,
    "risk_reward_min": 1.5,
    "target_risk_reward": 1.5,
    "news_buffer": 30,
    "paper_mode": False,
    "telegram_enabled": True,
    "telegram_bot_token": "",
    "telegram_chat_id": ""
}

# Log buffer for terminal view
_log_buffer = []

def add_log(source: str, message: str, level: str = "info"):
    """Add log to buffer for API exposure"""
    _log_buffer.insert(0, {
        "time": datetime.now().isoformat(),
        "source": source,
        "message": message,
        "level": level
    })
    if len(_log_buffer) > 100:
        _log_buffer.pop()

def get_settings():
    return _settings

def update_settings(new_settings: dict):
    global _settings
    _settings.update(new_settings)
    return _settings
