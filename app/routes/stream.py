from flask import Blueprint, Response, stream_with_context
import json
import time
import logging
from app.services.realtime_data import realtime_service

stream_bp = Blueprint('stream', __name__)
logger = logging.getLogger(__name__)

@stream_bp.route('/stream')
def stream():
    """Server-Sent Events stream for live market data"""
    def event_stream():
        # Keep track of last candle times to avoid duplicates
        last_candle_times = {}
        
        while True:
            try:
                # 1. Fetch Ticks for subscribed symbols
                data_packet = {
                    'type': 'tick_update',
                    'ticks': {}
                }
                
                for symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']:
                    tick = realtime_service.get_live_price(symbol)
                    if tick:
                        decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
                        data_packet['ticks'][symbol] = {
                            'bid': round(tick.bid, decimals),
                            'ask': round(tick.ask, decimals),
                            'spread': round((tick.ask - tick.bid) * (100 if symbol in ['XAUUSD', 'BTCUSD'] else 10000), 1),
                            'time': tick.time
                        }
                
                yield f"data: {json.dumps(data_packet)}\n\n"
                
                # 2. Check for new candles every 2 seconds
                if int(time.time()) % 2 == 0:
                    for symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']:
                        candles = realtime_service.get_historical_candles(symbol, 'M1', 1)
                        if candles:
                            latest = candles[-1]
                            if symbol not in last_candle_times or latest.time > last_candle_times[symbol]:
                                last_candle_times[symbol] = latest.time
                                candle_packet = {
                                    'type': 'candle_update',
                                    'symbol': symbol,
                                    'candle': {
                                        'time': latest.time,
                                        'open': latest.open,
                                        'high': latest.high,
                                        'low': latest.low,
                                        'close': latest.close
                                    }
                                }
                                yield f"data: {json.dumps(candle_packet)}\n\n"
                
                # 3. Heartbeat every 10 seconds to keep connection alive
                if int(time.time()) % 10 == 0:
                    yield "data: {\"type\": \"heartbeat\"}\n\n"
                
            except Exception as e:
                logger.error(f"SSE Stream error: {e}")
                break
                
            time.sleep(0.5)  # 500ms update frequency

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
