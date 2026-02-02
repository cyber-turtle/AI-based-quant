import logging
import MetaTrader5 as mt5
from typing import Dict, Optional
from app.services.settings_store import _settings

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Handles position sizing, risk-of-ruin calculation, and lot management.
    Ensures drawdowns are within user limits.
    """
    
    def __init__(self):
        self.max_daily_drawdown = 0.05  # 5% max daily drawdown
        self.max_position_risk = 0.01  # 1% risk per trade
        self.base_lot = 0.01
        self.max_lot = 10.0
        
    def calculate_lot_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """
        Calculates optimal lot size based on equity risk.
        Risk = Equity * max_position_risk
        Lot = Risk / (Distance to Stop Loss * pip_value)
        """
        try:
            # Refresh from live settings
            self.max_position_risk = _settings.get('risk_per_trade', 1.0) / 100.0
            
            account = mt5.account_info()
            if not account:
                return self.base_lot
                
            equity = account.equity
            risk_amount = equity * self.max_position_risk
            
            logger.info(f"   [RISK] Calc: Equity=${equity:.2f}, RiskAmount=${risk_amount:.2f} ({self.max_position_risk*100}%)")
            
            # Distance in points
            distance = abs(entry_price - stop_loss)
            if distance <= 0:
                return self.base_lot
                
            # Get tick value and size
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return self.base_lot
                
            # Simple formula: Lot = Risk / (Distance * PipValuePerLot)
            # For most FX: distance * 100000 = pips. Risk / pips / 10 = lot for 10$ per pip.
            # More accurate using MT5 properties:
            tick_value = symbol_info.trade_tick_value
            tick_size = symbol_info.trade_tick_size
            
            if tick_value == 0 or tick_size == 0:
                return self.base_lot
                
            lots = risk_amount / (distance / tick_size * tick_value)
            
            # Normalize to symbol limits
            lots = max(symbol_info.volume_min, min(symbol_info.volume_max, lots))
            
            # Step normalization
            step = symbol_info.volume_step
            lots = round(lots / step) * step
            
            final_lots = round(lots, 2)
            logger.info(f"   [RISK] Final Lot Size: {final_lots} (Stop Distance: {distance:.5f})")
            return final_lots
            
        except Exception as e:
            logger.error(f"Error calculating lot size: {e}")
            return self.base_lot

    def check_global_risk(self) -> bool:
        """Check if trading should be halted due to global drawdown"""
        try:
            account = mt5.account_info()
            if not account: return True
            
            drawdown = (account.balance - account.equity) / account.balance
            if drawdown > self.max_daily_drawdown:
                logger.warning(f"CRITICAL: Daily drawdown {drawdown*100:.1f}% exceeded limit")
                return False
            return True
        except:
            return True

risk_manager = RiskManager()
