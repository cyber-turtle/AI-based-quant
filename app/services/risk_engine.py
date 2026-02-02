import logging
import json
from datetime import datetime
from app import db
from app.models import RiskSettings, AccountSnapshot, AuditLog, UserPreferences

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.65

class RiskEngine:
    @staticmethod
    def get_risk_settings(user_id):
        settings = RiskSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            # Create Default
            settings = RiskSettings(
                user_id=user_id,
                max_drawdown_percent=10.0,
                position_size_percent=5.0,
                max_leverage=10.0,
                daily_loss_limit_percent=5.0,
                require_stop_loss=True,
                max_lines=3
            )
            db.session.add(settings)
            db.session.commit()
        return settings

    @staticmethod
    def validate_signal(user_id, signal, account_snapshot):
        settings = RiskEngine.get_risk_settings(user_id)
        
        # Check 1: Stop Loss
        if settings.require_stop_loss and not signal.get('stop_loss'):
            return {'valid': False, 'reason': 'Stop Loss Required'}

        # Check 2: Drawdown
        if account_snapshot.drawdown_percent >= settings.max_drawdown_percent:
            return {'valid': False, 'reason': f'Max drawdown {settings.max_drawdown_percent}% exceeded'}

        # Check 3: Daily Loss
        daily_loss_pct = abs(account_snapshot.daily_pnl / account_snapshot.equity * 100) if account_snapshot.daily_pnl < 0 else 0
        if daily_loss_pct >= settings.daily_loss_limit_percent:
             return {'valid': False, 'reason': f'Daily Loss Limit {settings.daily_loss_limit_percent}% exceeded'}

        # Check 4: Confidence
        if signal.get('confidence', 0) < MIN_CONFIDENCE:
             return {'valid': False, 'reason': f'Confidence {signal.get("confidence")} below min {MIN_CONFIDENCE}'}
        
        return {'valid': True}

    @staticmethod
    def calculate_position_size(user_id, entry_price, stop_loss, account_equity):
        settings = RiskEngine.get_risk_settings(user_id)
        
        risk_amount = account_equity * (settings.position_size_percent / 100)
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0.01

        # Lots (Standard 100k)
        position_size = risk_amount / (risk_per_unit * 100000)
        
        # Min/Max logic
        position_size = max(0.01, round(position_size, 2))
        
        return position_size

    @staticmethod
    def check_kill_switch(user_id):
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        if prefs and not prefs.trading_enabled:
            return {'pause': True, 'reason': prefs.pause_reason}
        return {'pause': False}
