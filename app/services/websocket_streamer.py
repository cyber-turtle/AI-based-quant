"""
WEBSOCKET REAL-TIME STREAMING
- Live price updates via SocketIO
- Auto-updating chart candles
- Trade execution notifications
- Account updates
"""
from flask_socketio import SocketIO, emit
from threading import Thread, Event
import time
import logging
from dataclasses import asdict

logger = logging.getLogger(__name__)

# Global SocketIO instance (initialized in app factory)
socketio = None

class RealtimeStreamer:
    """
    Handles WebSocket streaming for live data.
    Pushes updates to all connected clients.
    """
    
    def __init__(self):
        self.running = False
        self.stop_event = Event()
        self.thread = None
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
        self.last_candle_time = {}
    
    def start(self):
        """Start the streaming thread"""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._stream_loop, daemon=True)
        self.thread.start()
        logger.info("Real-time streamer started")
    
    def stop(self):
        """Stop streaming"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Real-time streamer stopped")
    
    def _stream_loop(self):
        """Main streaming loop - pushes data every 500ms"""
        from app.services.realtime_data import realtime_service
        
        while not self.stop_event.is_set():
            try:
                for symbol in self.symbols:
                    tick = realtime_service.get_live_price(symbol)
                    if tick and socketio:
                        decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
                        
                        # Emit tick update
                        socketio.emit('tick', {
                            'symbol': tick.symbol,
                            'bid': round(tick.bid, decimals),
                            'ask': round(tick.ask, decimals),
                            'spread': round((tick.ask - tick.bid) * (100 if symbol in ['XAUUSD', 'BTCUSD'] else 10000), 1),
                            'time': tick.time
                        })
                
                # Check for new candles every 5 seconds
                if int(time.time()) % 5 == 0:
                    self._check_new_candles()
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
            
            time.sleep(0.5)  # 500ms update interval
    
    def _check_new_candles(self):
        """Check if new candles are available and push them"""
        from app.services.realtime_data import realtime_service
        
        for symbol in self.symbols:
            try:
                candles = realtime_service.get_historical_candles(symbol, 'M1', 2)
                if candles and len(candles) > 0:
                    latest = candles[-1]
                    last_time = self.last_candle_time.get(symbol, 0)
                    
                    if latest.time > last_time and socketio:
                        decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
                        socketio.emit('candle', {
                            'symbol': symbol,
                            'time': latest.time,
                            'open': round(latest.open, decimals),
                            'high': round(latest.high, decimals),
                            'low': round(latest.low, decimals),
                            'close': round(latest.close, decimals)
                        })
                        self.last_candle_time[symbol] = latest.time
            except Exception as e:
                logger.error(f"Candle check error for {symbol}: {e}")
    
    def broadcast_trade(self, trade_data):
        """Broadcast trade execution to all clients"""
        if socketio:
            socketio.emit('trade', trade_data)
    
    def broadcast_signal(self, signal_data):
        """Broadcast new signal to all clients"""
        if socketio:
            socketio.emit('signal', signal_data)
    
    def broadcast_log(self, source, message, log_type='info'):
        """Broadcast log message to brain log"""
        if socketio:
            socketio.emit('log', {
                'source': source,
                'message': message,
                'type': log_type,
                'time': int(time.time())
            })

# Singleton
streamer = RealtimeStreamer()
