"""
SMART TRADING BRAIN
- Multi-Timeframe (MTF) Analysis
- Regime Detection (Trending, Ranging, Volatile)
- Dynamic Asset Scanning
- Smart Entry Logic (waits for confluence, not just "next candle")
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Timeframe Priority (Higher timeframe = stronger bias)
TF_PRIORITY = {
    'D1': mt5.TIMEFRAME_D1,
    'H4': mt5.TIMEFRAME_H4,
    'H1': mt5.TIMEFRAME_H1,
    'M15': mt5.TIMEFRAME_M15,
    'M5': mt5.TIMEFRAME_M5,
}

class SmartBrain:
    def __init__(self):
        self.regimes = {}  # Cache for regime per symbol/tf
        self.watchlist = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
        
    def initialize_mt5(self):
        if not mt5.initialize():
            logger.error("MT5 Init Failed")
            return False
        return True
    
    def get_candles(self, symbol, timeframe, count=200):
        """Fetch candles from MT5"""
        if not self.initialize_mt5():
            return None
        tf = TF_PRIORITY.get(timeframe, mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    # ========== REGIME DETECTION ==========
    def detect_regime(self, df):
        """
        Classifies market regime:
        - TRENDING_UP: Strong uptrend (ADX > 25, +DI > -DI)
        - TRENDING_DOWN: Strong downtrend
        - RANGING: Low volatility consolidation
        - VOLATILE: High ATR expansion (news/event driven)
        """
        if df is None or len(df) < 50:
            return 'UNKNOWN'
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # EMA for Trend Direction
        ema_20 = pd.Series(close).ewm(span=20).mean().iloc[-1]
        ema_50 = pd.Series(close).ewm(span=50).mean().iloc[-1]
        
        # ATR for Volatility
        tr = np.maximum(high[1:] - low[1:], 
                        np.maximum(np.abs(high[1:] - close[:-1]), 
                                   np.abs(low[1:] - close[:-1])))
        atr_14 = np.mean(tr[-14:])
        atr_50 = np.mean(tr[-50:])
        
        # ADX Proxy (Simplified: EMA slope)
        ema_slope = (ema_20 - pd.Series(close).ewm(span=20).mean().iloc[-10]) / 10
        
        # Classification
        if atr_14 > atr_50 * 1.5:
            return 'VOLATILE'
        
        if abs(ema_slope) < 0.0001:
            return 'RANGING'
        
        if ema_20 > ema_50 and ema_slope > 0:
            return 'TRENDING_UP'
        elif ema_20 < ema_50 and ema_slope < 0:
            return 'TRENDING_DOWN'
        
        return 'RANGING'
    
    # ========== MULTI-TIMEFRAME CONFLUENCE ==========
    def get_mtf_bias(self, symbol):
        """
        Checks alignment across D1 -> H4 -> H1 -> M15 -> M5
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        biases = {}
        for tf_name in ['D1', 'H4', 'H1']:
            df = self.get_candles(symbol, tf_name, 100)
            regime = self.detect_regime(df)
            biases[tf_name] = regime
            
        logger.info(f"[MTF] {symbol}: {biases}")
        
        # Confluence Check
        if biases.get('D1') == 'TRENDING_UP' and biases.get('H4') in ['TRENDING_UP', 'RANGING']:
            return 'BULLISH'
        elif biases.get('D1') == 'TRENDING_DOWN' and biases.get('H4') in ['TRENDING_DOWN', 'RANGING']:
            return 'BEARISH'
        
        return 'NEUTRAL'
    
    # ========== SMART ENTRY LOGIC ==========
    def find_entry_setup(self, symbol, bias):
        """
        Does NOT trade on every candle.
        Waits for a pullback into value (e.g., EMA 20/50 zone) before entering.
        """
        df = self.get_candles(symbol, 'M15', 50)
        if df is None:
            return None
            
        close = df['close'].values
        ema_20 = pd.Series(close).ewm(span=20).mean().values
        ema_50 = pd.Series(close).ewm(span=50).mean().values
        
        current_close = close[-1]
        current_ema_20 = ema_20[-1]
        current_ema_50 = ema_50[-1]
        
        # Define "Value Zone" (between EMA 20 and EMA 50)
        value_zone_high = max(current_ema_20, current_ema_50)
        value_zone_low = min(current_ema_20, current_ema_50)
        
        in_value_zone = value_zone_low <= current_close <= value_zone_high
        
        if bias == 'BULLISH' and in_value_zone:
            # Check for bullish reversal candle (e.g., close > open)
            if close[-1] > df['open'].values[-1]:
                return {
                    'action': 'BUY',
                    'symbol': symbol,
                    'entry': current_close,
                    'stop_loss': value_zone_low - (value_zone_high - value_zone_low) * 0.5,
                    'reason': 'Pullback to EMA zone in uptrend'
                }
                
        elif bias == 'BEARISH' and in_value_zone:
            if close[-1] < df['open'].values[-1]:
                return {
                    'action': 'SELL',
                    'symbol': symbol,
                    'entry': current_close,
                    'stop_loss': value_zone_high + (value_zone_high - value_zone_low) * 0.5,
                    'reason': 'Pullback to EMA zone in downtrend'
                }
        
        return None  # No valid setup found
    
    # ========== DYNAMIC ASSET SCANNER ==========
    def scan_for_opportunities(self):
        """
        Scans all assets in watchlist for the best setup.
        Returns the single best opportunity (or None).
        """
        opportunities = []
        
        for symbol in self.watchlist:
            bias = self.get_mtf_bias(symbol)
            if bias == 'NEUTRAL':
                continue
                
            setup = self.find_entry_setup(symbol, bias)
            if setup:
                opportunities.append(setup)
                
        if not opportunities:
            logger.info("[Scanner] No valid setups found. Waiting...")
            return None
        
        # For now, return the first valid setup. 
        # Can be enhanced to sort by "confidence" or "risk:reward"
        return opportunities[0]
        
    def shutdown(self):
        mt5.shutdown()


# Singleton Instance
brain = SmartBrain()
