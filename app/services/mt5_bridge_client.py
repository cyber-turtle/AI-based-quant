"""
MT5 BRIDGE CLIENT
Fallback data source when direct MT5 Python library fails.
Fetches real-time data from the running mt5-bridge Flask server.
"""
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BridgeTick:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    time: int

@dataclass
class BridgeCandle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int

class MT5BridgeClient:
    """
    HTTP client for the mt5-bridge Flask server.
    Used as fallback when MetaTrader5 Python library fails to initialize.
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url
        self.connected = False
        self._check_connection()
    
    def _check_connection(self):
        """Verify the bridge server is running"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=2)
            if response.status_code == 200:
                self.connected = True
                logger.info(f"MT5 Bridge connected at {self.base_url}")
            else:
                self.connected = False
        except Exception as e:
            self.connected = False
            logger.warning(f"MT5 Bridge not available: {e}")
    
    def get_tick(self, symbol: str) -> Optional[BridgeTick]:
        """Get latest tick from bridge"""
        if not self.connected:
            return None
        try:
            response = requests.get(f"{self.base_url}/tick/{symbol}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return BridgeTick(
                    symbol=symbol,
                    bid=data.get('bid', 0),
                    ask=data.get('ask', 0),
                    last=data.get('last', data.get('bid', 0)),
                    volume=data.get('volume', 0),
                    time=data.get('time', 0)
                )
        except Exception as e:
            logger.error(f"Bridge tick error: {e}")
        return None
    
    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> List[BridgeCandle]:
        """Get historical candles from bridge"""
        if not self.connected:
            return []
        try:
            response = requests.get(
                f"{self.base_url}/candles/{symbol}/{timeframe}/{count}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                candles = data.get('candles', data) if isinstance(data, dict) else data
                return [
                    BridgeCandle(
                        time=c.get('time', 0),
                        open=c.get('open', 0),
                        high=c.get('high', 0),
                        low=c.get('low', 0),
                        close=c.get('close', 0),
                        volume=c.get('tick_volume', c.get('volume', 0))
                    ) for c in candles
                ]
        except Exception as e:
            logger.error(f"Bridge candles error: {e}")
        return []
    
    def get_account(self) -> Dict:
        """Get account info from bridge"""
        if not self.connected:
            return {}
        try:
            response = requests.get(f"{self.base_url}/account", timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Bridge account error: {e}")
        return {}

# Singleton
mt5_bridge = MT5BridgeClient()
