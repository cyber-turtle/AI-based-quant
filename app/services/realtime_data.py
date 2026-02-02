"""
REAL-TIME DATA SERVICE
- MT5 direct connection with auto-reconnect
- Dynamic symbol fetching from MT5 Market Watch
- Proper error state handling (no fake data when disconnected)
- Tick-by-tick updates
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from threading import Thread, Event, Lock
import time
import json
import logging
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, asdict
from app.services.mt5_bridge_client import mt5_bridge, BridgeTick, BridgeCandle

logger = logging.getLogger(__name__)

@dataclass
class Tick:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    time: int

@dataclass 
class OHLC:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int

class RealTimeDataService:
    """
    Manages real-time market data streaming.
    Priority: MT5 Direct > MT5 Bridge
    Auto-reconnects when MT5 goes down.
    """
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False
        self.thread: Optional[Thread] = None
        self.reconnect_thread: Optional[Thread] = None
        self.stop_event = Event()
        self.last_prices: Dict[str, float] = {}
        self.candle_buffer: Dict[str, List[OHLC]] = {}
        self.mt5_connected = False
        self.bridge_connected = False
        self.data_mode = "DISCONNECTED"  # LIVE_MT5, LIVE_BRIDGE, or DISCONNECTED
        self.connection_lock = Lock()
        self.last_reconnect_attempt = 0
        self.reconnect_interval = 10  # seconds between reconnect attempts
        
        # Symbols fetched dynamically from MT5
        self.symbols: List[str] = []
        self.default_symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD', 'XAUUSD']
        
        # Pattern Injection for testing
        self.pattern_overrides: Dict[str, str] = {}
        self.demo_mode = False # Explicit demo mode flag
        
        # Initialize data sources
        self._init_data_sources()
        
        # Start reconnection monitor
        self._start_reconnect_monitor()
    
    def _init_data_sources(self):
        """Initialize MT5 direct or Bridge fallback"""
        with self.connection_lock:
            # Try direct MT5 first
            try:
                if mt5.initialize():
                    self.mt5_connected = True
                    self.data_mode = "LIVE_MT5"
                    self._fetch_mt5_symbols()
                    account_info = mt5.account_info()
                    if account_info:
                        logger.info(f"✓ MT5 LIVE: Account {account_info.login}, Balance: {account_info.balance}")
                    return True
            except Exception as e:
                logger.warning(f"MT5 direct init failed: {e}")
                self.mt5_connected = False
            
            # Fallback to Bridge
            mt5_bridge._check_connection()  # Re-check bridge
            if mt5_bridge.connected:
                self.bridge_connected = True
                self.data_mode = "LIVE_BRIDGE"
                self.symbols = self.default_symbols
                logger.info("✓ MT5 Bridge LIVE: Fetching data from mt5-bridge server")
                return True
            
            # No connection available
            self.data_mode = "DISCONNECTED"
            self.symbols = self.default_symbols
            logger.warning("⚠️ MT5 DISCONNECTED - Waiting for connection...")
            return False
    
    def _fetch_mt5_symbols(self):
        """Fetch symbols from MT5 Market Watch and select Top 10"""
        try:
            # 1. Get all visible symbols (Market Watch)
            visible_symbols = mt5.symbols_get(group="*,!*") # Try to get visible ones
            if not visible_symbols:
                visible_symbols = mt5.symbols_get() # Fallback to all
                
            if visible_symbols:
                all_names = [s.name for s in visible_symbols]
                
                # Sort to prioritize Majors (EURUSD, GBPUSD, etc.)
                majors = [s for s in all_names if s in self.default_symbols]
                others = [s for s in all_names if s not in self.default_symbols]
                
                # Combine and take Top 10
                final_list = (majors + others)[:10]
                
                self.symbols = final_list
                logger.info(f"Dynamically loaded Top 10 MT5 Pairs: {self.symbols}")
            else:
                self.symbols = self.default_symbols
        except Exception as e:
            logger.error(f"Error fetching MT5 symbols: {e}")
            self.symbols = self.default_symbols
    
    def _start_reconnect_monitor(self):
        """Start background thread to monitor and reconnect MT5"""
        def monitor_loop():
            while not self.stop_event.is_set():
                time.sleep(5)  # Check every 5 seconds
                
                if self.data_mode == "DISCONNECTED":
                    now = time.time()
                    if now - self.last_reconnect_attempt >= self.reconnect_interval:
                        self.last_reconnect_attempt = now
                        logger.info("Attempting MT5 reconnection...")
                        self._init_data_sources()
                
                # Also verify existing connection is still alive
                elif self.data_mode == "LIVE_MT5":
                    try:
                        # Quick health check
                        if not mt5.terminal_info():
                            logger.warning("MT5 connection lost - entering reconnect mode")
                            self.mt5_connected = False
                            self.data_mode = "DISCONNECTED"
                    except:
                        self.mt5_connected = False
                        self.data_mode = "DISCONNECTED"
        
        self.reconnect_thread = Thread(target=monitor_loop, daemon=True)
        self.reconnect_thread.start()
    
    def get_live_price(self, symbol: str) -> Optional[Tick]:
        """Get current tick - Returns None if disconnected (no fake data)"""
        # Try direct MT5
        if self.data_mode == "LIVE_MT5":
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    return Tick(
                        symbol=symbol,
                        bid=tick.bid,
                        ask=tick.ask,
                        last=tick.last,
                        volume=tick.volume,
                        time=tick.time
                    )
            except Exception as e:
                logger.error(f"MT5 tick error: {e}")
        
        # Try Bridge
        if self.data_mode == "LIVE_BRIDGE" or (self.data_mode == "LIVE_MT5" and self.bridge_connected):
            bridge_tick = mt5_bridge.get_tick(symbol)
            if bridge_tick:
                return Tick(
                    symbol=symbol,
                    bid=bridge_tick.bid,
                    ask=bridge_tick.ask,
                    last=bridge_tick.last,
                    volume=bridge_tick.volume,
                    time=bridge_tick.time
                )
        
        # No simulated fallback unless in demo_mode
        if self.demo_mode:
            return self._simulate_tick(symbol)
            
        return None
    
    def _simulate_tick(self, symbol: str) -> Tick:
        """Generate simulated tick for demo mode"""
        base_prices = {
            'EURUSD': 1.0850, 'GBPUSD': 1.2650, 'USDJPY': 148.50,
            'XAUUSD': 2050.00, 'BTCUSD': 100000.00
        }
        
        last_price = self.last_prices.get(symbol, base_prices.get(symbol, 1.0))
        
        # Random walk
        change = np.random.normal(0, last_price * 0.0001)
        new_price = last_price + change
        self.last_prices[symbol] = new_price
        
        spread = new_price * 0.00005  # 0.5 pip spread
        
        return Tick(
            symbol=symbol,
            bid=new_price - spread/2,
            ask=new_price + spread/2,
            last=new_price,
            volume=int(np.random.exponential(1000)),
            time=int(datetime.now().timestamp())
        )
    
    def get_historical_candles(self, symbol: str, timeframe: str, count: int = 500) -> List[OHLC]:
        """Get historical OHLC data - Priority: MT5 Direct > Bridge > Simulated"""
        tf_map = {
            'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }
        
        # Check for Pattern Overrides (for testing)
        if symbol in self.pattern_overrides:
            pattern = self.pattern_overrides.pop(symbol)
            logger.info(f"Injecting simulated pattern: {pattern} for {symbol}")
            return self._generate_pattern_candles(symbol, timeframe, count, pattern)

        # Try direct MT5
        if self.data_mode == "LIVE_MT5":
            try:
                tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
                if rates is not None and len(rates) > 0:
                    return [
                        OHLC(
                            time=int(r['time']),
                            open=float(r['open']),
                            high=float(r['high']),
                            low=float(r['low']),
                            close=float(r['close']),
                            volume=int(r['tick_volume'])
                        ) for r in rates
                    ]
            except Exception as e:
                logger.error(f"MT5 candle error: {e}")
        
        # Try Bridge
        if self.data_mode == "LIVE_BRIDGE" or self.bridge_connected:
            bridge_candles = mt5_bridge.get_candles(symbol, timeframe, count)
            if bridge_candles:
                return [
                    OHLC(
                        time=c.time,
                        open=c.open,
                        high=c.high,
                        low=c.low,
                        close=c.close,
                        volume=c.volume
                    ) for c in bridge_candles
                ]
        
        # Simulated fallback (only if demo_mode or pattern injected)
        if self.demo_mode:
            return self._simulate_candles(symbol, timeframe, count)
            
        return []
    
    def _generate_pattern_candles(self, symbol: str, timeframe: str, count: int, pattern: str) -> List[OHLC]:
        """Generate a series of candles that match a specific technical pattern"""
        now = int(datetime.now().timestamp())
        interval = 60 if timeframe == 'M1' else 300
        candles = []
        
        # Base price
        price = 1.0850 if symbol == 'EURUSD' else 100000.00 if symbol == 'BTCUSD' else 100.0
        
        for i in range(count):
            t = now - (count - i) * interval
            
            # Simple trend + pattern logic
            if pattern == 'BULLISH_ENGULFING' and i > count - 5:
                # Last 5 candles form an engulfing
                if i == count - 2: # Small red
                    o, h, l, c = price, price + 0.0005, price - 0.0010, price - 0.0008
                elif i == count - 1: # Big green engulfing
                    o, h, l, c = price - 0.0009, price + 0.0020, price - 0.0010, price + 0.0018
                else:
                    o = price; c = price + 0.0001; h = o + 0.0002; l = c - 0.0002
            elif pattern == 'BEARISH_DIVERGENCE' and i > count - 10:
                # Rising price but we want to simulate a reversal
                price += 0.0010
                o, h, l, c = price, price + 0.0005, price - 0.0002, price + 0.0003
            else:
                # Noise
                price += np.random.normal(0, 0.0001)
                o, h, l, c = price, price + 0.0002, price - 0.0002, price + 0.0001
            
            candles.append(OHLC(time=t, open=o, high=h, low=l, close=c, volume=100))
            price = c

        return candles

    def inject_pattern(self, symbol: str, pattern: str):
        """Inject a pattern to be returned on next candle fetch"""
        self.pattern_overrides[symbol] = pattern
        logger.info(f"Pattern {pattern} QUEUED for {symbol}")

    def _simulate_candles(self, symbol: str, timeframe: str, count: int) -> List[OHLC]:
        """Generate realistic simulated candles for deep history"""
        base_prices = {
            'EURUSD': 1.0850, 'GBPUSD': 1.2650, 'USDJPY': 148.50,
            'AUDUSD': 0.6550, 'NZDUSD': 0.6150, 'USDCAD': 1.3550,
            'USDCHF': 0.8850, 'XAUUSD': 2050.00, 'BTCUSD': 100000.00
        }
        
        tf_minutes = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440}
        minutes = tf_minutes.get(timeframe, 5)
        
        # Start time is 'count' candles ago
        now = datetime.now()
        start_time = now - timedelta(minutes=minutes * count)
        
        base = base_prices.get(symbol, 1.0)
        volatility = base * 0.002
        
        candles = []
        price = base
        
        for i in range(count):
            candle_time = start_time + timedelta(minutes=minutes * i)
            
            # Trend + noise
            trend = np.sin(i / 50) * volatility * 0.5
            noise = np.random.normal(0, volatility)
            
            o = price
            change = trend + noise
            c = o + change
            h = max(o, c) + abs(np.random.normal(0, volatility * 0.3))
            l = min(o, c) - abs(np.random.normal(0, volatility * 0.3))
            
            candles.append(OHLC(
                time=int(candle_time.timestamp()),
                open=round(o, 5),
                high=round(h, 5),
                low=round(l, 5),
                close=round(c, 5),
                volume=int(np.random.exponential(5000))
            ))
            
            price = c
        
        return candles
    
    def subscribe(self, symbol: str, callback: Callable):
        """Subscribe to real-time updates for a symbol"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
    
    def unsubscribe(self, symbol: str, callback: Callable):
        """Unsubscribe from updates"""
        if symbol in self.subscribers:
            self.subscribers[symbol] = [cb for cb in self.subscribers[symbol] if cb != callback]
    
    def start_streaming(self):
        """Start background streaming thread"""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._stream_loop, daemon=True)
        self.thread.start()
        logger.info("Real-time streaming started")
    
    def stop_streaming(self):
        """Stop streaming"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Real-time streaming stopped")
    
    def _stream_loop(self):
        """Main streaming loop"""
        while not self.stop_event.is_set():
            for symbol in self.symbols:
                if symbol in self.subscribers and self.subscribers[symbol]:
                    tick = self.get_live_price(symbol)
                    if tick:
                        for callback in self.subscribers[symbol]:
                            try:
                                callback(tick)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")
                    
                    # Also notify AutoTrader
                    from app.services.auto_trader import auto_trader
                    auto_trader.on_tick(tick)
            
            time.sleep(0.5)  # 500ms update interval
    
    def get_account_info(self) -> Dict:
        """Get MT5 account information - returns error state if disconnected"""
        if self.data_mode == "LIVE_MT5" and self.mt5_connected:
            try:
                info = mt5.account_info()
                if info:
                    return {
                        'connected': True,
                        'balance': info.balance,
                        'equity': info.equity,
                        'margin': info.margin,
                        'free_margin': info.margin_free,
                        'profit': info.profit,
                        'leverage': info.leverage,
                        'currency': info.currency,
                        'mode': 'LIVE_MT5'
                    }
            except Exception as e:
                logger.error(f"Error getting account info: {e}")
        
        # Try Bridge
        if self.data_mode == "LIVE_BRIDGE" and self.bridge_connected:
            account = mt5_bridge.get_account()
            if account:
                account['connected'] = True
                account['mode'] = 'LIVE_BRIDGE'
                return account
        
        # Disconnected - return error state (NOT fake data)
        return {
            'connected': False,
            'balance': None,
            'equity': None,
            'margin': None,
            'free_margin': None,
            'profit': None,
            'leverage': None,
            'currency': None,
            'mode': self.data_mode,
            'error': 'MT5 Disconnected - Waiting for connection...'
        }

# Singleton
realtime_service = RealTimeDataService()
