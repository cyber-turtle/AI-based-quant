from app import create_app
from app.services.realtime_data import realtime_service
from app.services.auto_trader import auto_trader
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

# Create database tables
with app.app_context():
    from app import db
    db.create_all()

if __name__ == '__main__':
    print("\n" + "="*50)
    print("      CORTEX ZERO-LATENCY TRADING SYSTEM")
    print("="*50)
    print(" > Dashboard: http://127.0.0.1:5000")
    print(" > Real-Time: SSE (Server-Sent Events) Active")
    print(" > Auto-Trader: Reactive Tick-Driven Engine")
    print("="*50 + "\n")
    
    # Start high-frequency data streamer
    realtime_service.start_streaming()
    
    # Housekeeping for auto-trader
    auto_trader.start()
    
    # Run Flask with multi-threading to handle SSE connections
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True, use_reloader=False)
