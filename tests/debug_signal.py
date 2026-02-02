
import pandas as pd
import numpy as np
import logging
from app.services.quant_engine import quant_engine

logging.basicConfig(level=logging.INFO)

# Create a synthetic DataFrame that forms a Bullish Engulfing pattern
close_prices = np.linspace(1.1000, 1.0900, 98) # Downtrend

data = []
for i, price in enumerate(close_prices):
    data.append({
        'time': 1700000000 + i*60,
        'open': price + 0.0005,
        'high': price + 0.0010,
        'low': price - 0.0002,
        'close': price,
        'volume': 100
    })
    
# Candle 99: Bearish
data.append({
    'time': 1700000000 + 98*60,
    'open': 1.0900,
    'high': 1.0905,
    'low': 1.0890,
    'close': 1.0895, # Bearish close
    'volume': 150
})

# Candle 100: Bullish Engulfing
data.append({
    'time': 1700000000 + 99*60,
    'open': 1.0892, # Opens below prev close
    'high': 1.0920,
    'low': 1.0890,
    'close': 1.0915, # Closes well above prev open
    'volume': 200
})

df = pd.DataFrame(data)
symbol = "TESTUSD"

print("--- Calling generate_signal ---")
signal = quant_engine.generate_signal(df, symbol)
print(f"--- Result: {signal} ---")
