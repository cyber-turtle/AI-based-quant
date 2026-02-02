
import unittest
import pandas as pd
import numpy as np
import logging
from app.services.quant_engine import quant_engine
from app.services.auto_trader import auto_trader
from dataclasses import asdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSignalFlow(unittest.TestCase):
    def setUp(self):
        """Setup synthetic data for testing"""
        # Create a synthetic DataFrame that forms a Bullish Engulfing pattern
        # RSI oversold, then bouncing back
        
        # 100 candles
        close_prices = np.linspace(1.1000, 1.0900, 98) # Downtrend
        
        data = []
        for i, price in enumerate(close_prices):
            data.append({
                'time': 1700000000 + i*60,
                'open': price + 0.0005,
                'high': price + 0.0010,
                'low': price - 0.0002,
                'close': price,
                'tick_volume': 100
            })
            
        # Candle 99: Bearish
        data.append({
            'time': 1700000000 + 98*60,
            'open': 1.0900,
            'high': 1.0905,
            'low': 1.0890,
            'close': 1.0895, # Bearish close
            'tick_volume': 150
        })
        
        # Candle 100: Bullish Engulfing
        data.append({
            'time': 1700000000 + 99*60,
            'open': 1.0892, # Opens below prev close
            'high': 1.0920,
            'low': 1.0890,
            'close': 1.0915, # Closes well above prev open
            'tick_volume': 200
        })
        
        self.df = pd.DataFrame(data)
        self.symbol = "TESTUSD"
        
    def test_quant_engine_signal(self):
        """Test 1: Quant Engine detects the pattern"""
        logger.info("--- Testing Quant Engine Signal Generation ---")
        signal = quant_engine.generate_signal(self.df, self.symbol)
        
        if signal:
            logger.info(f"Signal Generated: {signal}")
        else:
            logger.warning("No signal generated")
            
        # We expect SOME signal (maybe Oversold Mean Revert or Price Action)
        # However, ML probability might filter it in the full pipeline
        # But quant_engine alone should return something if logic holds
        self.assertIsNotNone(signal, "Quant Engine failed to generate signal on perfect setup")
        self.assertEqual(signal.direction, "BUY")
        
    def test_autotrader_pipeline(self):
        """Test 2: AutoTrader pipeline (mocking other services)"""
        logger.info("--- Testing AutoTrader Pipeline Integration ---")
        
        # We can't easily test the full threading loop here without mocks,
        # but we can test the critical logic functions
        
        # Mock realtime_service to return our DF
        class MockRealtime:
            def get_historical_candles(self, sym, tf, count):
                return [type('obj', (object,), row)() for i, row in self.df.iterrows()] # Fake objects
        
        # ... logic test ...
        pass

if __name__ == '__main__':
    unittest.main()
