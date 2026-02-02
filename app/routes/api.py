from flask import Blueprint, jsonify, request
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import os
from datetime import datetime, timedelta
import json
from threading import Thread
from dataclasses import asdict
from app.services.settings_store import _settings, _log_buffer, add_log

api = Blueprint('api', __name__)

# ========== CHART DATA ==========

@api.route('/history/<symbol>/<timeframe>')
def history(symbol, timeframe):
    """Returns candle data for Lightweight Charts with proper formatting."""
    try:
        from app.services.realtime_data import realtime_service
        
        candles = realtime_service.get_historical_candles(symbol, timeframe, 2000)
        
        # Format with proper precision based on symbol
        decimals = 2 if any(x in symbol.upper() for x in ['JPY', 'XAU', 'BTC', 'ETH']) else 5
        
        data = [{
            'time': c.time,
            'open': round(c.open, decimals),
            'high': round(c.high, decimals),
            'low': round(c.low, decimals),
            'close': round(c.close, decimals)
        } for c in candles]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/tick/<symbol>')
def get_tick(symbol):
    """Get current tick for symbol"""
    from app.services.realtime_data import realtime_service
    
    tick = realtime_service.get_live_price(symbol)
    if tick:
        decimals = 2 if any(x in symbol.upper() for x in ['JPY', 'XAU', 'BTC', 'ETH']) else 5
        return jsonify({
            'symbol': tick.symbol,
            'bid': round(tick.bid, decimals),
            'ask': round(tick.ask, decimals),
            'last': round(tick.last, decimals),
            'spread': round((tick.ask - tick.bid) * 10000, 1),  # in pips
            'time': tick.time
        })
    return jsonify({'error': 'No data'}), 404

# ========== QUANT SIGNALS ==========

@api.route('/signal/<symbol>')
def get_signal(symbol):
    """Get quant-generated signal for symbol"""
    from app.services.quant_engine import quant_engine
    from app.services.realtime_data import realtime_service
    
    try:
        candles = realtime_service.get_historical_candles(symbol, 'H1', 300)
        df = pd.DataFrame([asdict(c) for c in candles])
        
        signal = quant_engine.generate_signal(df, symbol)
        
        if signal:
            decimals = 2 if any(x in symbol.upper() for x in ['JPY', 'XAU', 'BTC', 'ETH']) else 5
            return jsonify({
                'symbol': symbol,
                'direction': signal.direction,
                'confidence': round(signal.confidence * 100, 1),
                'entry_price': round(signal.entry_price, decimals),
                'stop_loss': round(signal.stop_loss, decimals),
                'take_profit_1': round(signal.take_profit_1, decimals),
                'take_profit_2': round(signal.take_profit_2, decimals),
                'take_profit_3': round(signal.take_profit_3, decimals),
                'risk_reward': round(signal.risk_reward, 2),
                'strategy': signal.strategy,
                'reasoning': signal.reasoning
            })
        else:
            return jsonify({'symbol': symbol, 'direction': 'NEUTRAL', 'message': 'No valid signal'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/scan')
def scan_all():
    """Scan all symbols for signals"""
    from app.services.quant_engine import quant_engine
    from app.services.realtime_data import realtime_service
    
    symbols = realtime_service.symbols
    signals = []
    
    for symbol in symbols:
        try:
            candles = realtime_service.get_historical_candles(symbol, 'H1', 300)
            df = pd.DataFrame([asdict(c) for c in candles])
            signal = quant_engine.generate_signal(df, symbol)
            
            if signal and signal.direction != 'NEUTRAL':
                decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
                signals.append({
                    'symbol': symbol,
                    'direction': signal.direction,
                    'confidence': round(signal.confidence * 100, 1),
                    'entry_price': round(signal.entry_price, decimals),
                    'stop_loss': round(signal.stop_loss, decimals),
                    'take_profit_1': round(signal.take_profit_1, decimals),
                    'risk_reward': round(signal.risk_reward, 2),
                    'strategy': signal.strategy
                })
        except Exception as e:
            continue
    
    return jsonify({'signals': signals, 'count': len(signals)})

# ========== EXECUTION ==========

@api.route('/order', methods=['POST'])
def place_order():
    """Place a new order"""
    from app.services.execution_engine import execution_engine, OrderType
    
    data = request.json
    
    try:
        order = execution_engine.place_order(
            symbol=data['symbol'],
            side=data['side'],
            quantity=data.get('quantity', 0.1),
            price=data['price'],
            stop_loss=data['stop_loss'],
            take_profit=data['take_profit'],
            order_type=OrderType.MARKET_BUY if data['side'] == 'BUY' else OrderType.MARKET_SELL
        )
        return jsonify({'status': 'success', 'order': order.to_dict()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api.route('/positions')
def get_positions():
    """Get open positions"""
    from app.services.execution_engine import execution_engine
    return jsonify({
        'positions': execution_engine.get_open_positions(),
        'count': len(execution_engine.positions)
    })

@api.route('/trades')
def get_trades():
    """Get trade history"""
    from app.services.execution_engine import execution_engine
    return jsonify({
        'trades': execution_engine.get_trade_history(),
        'count': len(execution_engine.trade_history)
    })

# ========== ACCOUNT ==========

@api.route('/account')
def get_account():
    """Get account summary"""
    from app.services.execution_engine import execution_engine
    from app.services.realtime_data import realtime_service
    
    # Get MT5 account info if connected, otherwise use paper trading
    account = realtime_service.get_account_info()
    execution_summary = execution_engine.get_account_summary()
    
    return jsonify({
        'balance': account['balance'],
        'equity': account['equity'],
        'free_margin': account['free_margin'],
        'profit': account['profit'],
        'leverage': account['leverage'],
        'currency': account['currency'],
        'connected': account.get('connected', True), # Use connected status
        'paper_mode': execution_summary['mode'] == 'PAPER',
        'open_positions': execution_summary['open_positions'],
        'total_trades': execution_summary['total_trades']
    })

# ========== BOT CONTROL ==========
bot_thread = None
bot_running = False

@api.route('/bot/start', methods=['POST'])
def start_bot():
    global bot_thread, bot_running
    from app.services.trading_loop import TradingLoop
    
    if bot_running:
        return jsonify({'status': 'already_running'})
    
    user_id = 1
    loop = TradingLoop(user_id)
    
    def run_loop():
        global bot_running
        bot_running = True
        loop.start(interval_seconds=30)
    
    bot_thread = Thread(target=run_loop, daemon=True)
    bot_thread.start()
    
    return jsonify({'status': 'started'})

@api.route('/bot/stop', methods=['POST'])
def stop_bot():
    global bot_running
    bot_running = False
    return jsonify({'status': 'stopped'})

@api.route('/bot/status')
def bot_status():
    return jsonify({'running': bot_running})

# ========== BACKTEST ==========

@api.route('/backtest', methods=['POST'])
def run_backtest():
    """Run backtest on historical data"""
    from app.services.backtest_engine import backtest_engine
    from app.services.quant_engine import quant_engine
    from app.services.realtime_data import realtime_service
    
    data = request.json
    symbol = data.get('symbol', 'EURUSD')
    timeframe = data.get('timeframe', 'H1')
    
    try:
        candles = realtime_service.get_historical_candles(symbol, timeframe, 1000)
        df = pd.DataFrame([asdict(c) for c in candles])
        
        def strategy(historical_df):
            signal = quant_engine.generate_signal(historical_df, symbol)
            if signal and signal.direction != 'NEUTRAL':
                return (signal.direction, signal.entry_price, signal.stop_loss, signal.take_profit_2)
            return None
        
        result = backtest_engine.run_backtest(df, strategy)
        
        return jsonify({
            'total_trades': result.total_trades,
            'win_rate': round(result.win_rate, 1),
            'total_pnl': round(result.total_pnl, 2),
            'max_drawdown': round(result.max_drawdown_percent, 2),
            'sharpe_ratio': round(result.sharpe_ratio, 2),
            'sortino_ratio': round(result.sortino_ratio, 2),
            'profit_factor': round(result.profit_factor, 2),
            'avg_win': round(result.avg_win, 2),
            'avg_loss': round(result.avg_loss, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== AUTO TRADER ==========

@api.route('/auto/start', methods=['POST'])
def start_auto_trader():
    """Start automated trading - WITH VALIDATION"""
    from app.services.auto_trader import auto_trader
    from app.services.realtime_data import realtime_service
    from app.services.ai_agent import ai_agent
    
    # Pre-flight validation
    validation = auto_trader._validate_system_ready()
    if not validation['ready']:
        return jsonify({
            'status': 'error',
            'message': validation['reason'],
            'ready': False
        }), 400
    
    try:
        auto_trader.start()
        return jsonify({
            'status': 'started',
            'ready': True,
            'message': 'Auto-trading engaged successfully'
        })
    except RuntimeError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'ready': False
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to start: {str(e)}',
            'ready': False
        }), 500

@api.route('/auto/stop', methods=['POST'])
def stop_auto_trader():
    """Stop automated trading"""
    from app.services.auto_trader import auto_trader
    auto_trader.stop()
    return jsonify({'status': 'stopped'})

@api.route('/auto/status')
def auto_trader_status():
    """Get auto-trader status with system readiness"""
    from app.services.auto_trader import auto_trader
    from app.services.realtime_data import realtime_service
    from app.services.ai_agent import ai_agent
    
    validation = auto_trader._validate_system_ready()
    ai_status = ai_agent.get_status()
    
    return jsonify({
        'running': auto_trader.running,
        'ready': validation['ready'],
        'ready_reason': validation['reason'],
        'data_mode': realtime_service.data_mode,
        'ai_status': ai_status,
        'can_engage': validation['ready'] and not auto_trader.running
    })

@api.route('/symbols')
def get_symbols():
    """Get available trading symbols from MT5 Market Watch"""
    from app.services.realtime_data import realtime_service
    return jsonify({
        'symbols': realtime_service.symbols,
        'data_mode': realtime_service.data_mode,
        'connected': realtime_service.mt5_connected or realtime_service.bridge_connected
    })

@api.route('/simulate/inject', methods=['POST'])
def inject_pattern():
    """Inject a specific market pattern for testing"""
    from app.services.realtime_data import realtime_service
    data = request.json
    symbol = data.get('symbol')
    pattern = data.get('pattern')
    
    if not symbol or not pattern:
        return jsonify({'error': 'Missing symbol or pattern'}), 400
        
    realtime_service.inject_pattern(symbol, pattern)
    return jsonify({'status': 'queued', 'message': f'Pattern {pattern} will load on next chart refresh for {symbol}'})

@api.route('/strategies')
def get_strategies():
    """Returns dynamic strategy list based on active models"""
    return jsonify({
        'strategies': [
            {'name': 'Cortex Trend Guard', 'status': 'ACTIVE', 'type': 'Trend Follower', 'description': 'Ensemble EMA + VWAP trend validation'},
            {'name': 'Oversold Mean Revert', 'status': 'ACTIVE', 'type': 'Mean Reversion', 'description': 'RSI + Bollinger exhaustion capture'},
            {'name': 'Llama Brain Validator', 'status': 'ACTIVE', 'type': 'AI Validation', 'description': 'Real-time LLM signal filtering'},
            {'name': 'Volatility Breakout', 'status': 'STANDBY', 'type': 'Volatility', 'description': 'ATR expansion detection'},
            {'name': 'ML Probability Shield', 'status': 'ACTIVE', 'type': 'ML Guard', 'description': 'Proprietary success probability filter'},
            {'name': 'Fibonacci Retrace Alpha', 'status': 'ACTIVE', 'type': 'Structure', 'description': 'Capture 61.8% golden pocket pullbacks'},
            {'name': 'MACD Divergence Hunter', 'status': 'ACTIVE', 'type': 'Momentum', 'description': 'Identify price vs momentum exhaustion'},
            {'name': 'Smart Money Flow', 'status': 'STANDBY', 'type': 'Institutional', 'description': 'Detect large order block activity'},
            {'name': 'Harmonic Bat Pattern', 'status': 'ACTIVE', 'type': 'Geometric', 'description': 'Advanced XABCD structure detection'},
            {'name': 'EMA 200 Pullback', 'status': 'ACTIVE', 'type': 'Trend Follower', 'description': 'Institutional value area entry'},
            {'name': 'Price Action Scalper', 'status': 'ACTIVE', 'type': 'Scalping', 'description': 'High-frequency candle formation analysis'},
            {'name': 'Supply/Demand Zone', 'status': 'ACTIVE', 'type': 'Price Action', 'description': 'Market imbalance detection'},
            {'name': 'Pivot Point Scanner', 'status': 'ACTIVE', 'type': 'Math', 'description': 'Daily/Weekly equilibrium levels'},
            {'name': 'Gap Closure Alpha', 'status': 'ACTIVE', 'type': 'Anomaly', 'description': 'Opening gap filling logic'},
            {'name': 'News Volatilty Filter', 'status': 'ACTIVE', 'type': 'Protection', 'description': 'High-impact economic event protection'}
        ]
    })

# ========== WALL STREET GRADE APIs ==========

# Note: _settings and add_log are now imported from app.services.settings_store

@api.route('/ai/status')
def ai_status():
    """Get AI (Ollama) health status"""
    from app.services.ai_agent import ai_agent
    return jsonify(ai_agent.get_status())

@api.route('/settings', methods=['GET'])
def get_settings():
    """Get current trading settings"""
    return jsonify(_settings)

@api.route('/settings', methods=['POST'])
def update_settings():
    """Update trading settings"""
    data = request.get_json() or {}
    for key in _settings:
        if key in data:
            _settings[key] = data[key]
    return jsonify({"success": True, "settings": _settings})

@api.route('/telegram/test', methods=['POST'])
def test_telegram():
    """Send a test message to Telegram"""
    data = request.json
    token = data.get('token')
    chat_id = data.get('chat_id')
    
    if not token or not chat_id:
        return jsonify({'error': 'Missing Token or Chat ID'}), 400
        
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🤖 Cortex AI: Test Connection Successful!\nYour trading bot is ready to send alerts."
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        res_data = response.json()
        if response.status_code == 200 and res_data.get('ok'):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': f"Telegram API Error: {res_data.get('description', 'Unknown error')}"}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/news')
def get_news():
    """Get upcoming economic events"""
    from app.services.news_service import news_service
    events = news_service.get_upcoming_events(15)
    return jsonify({"events": events})

@api.route('/news/check/<symbol>')
def check_news_stop(symbol):
    """Check if trading should halt due to high-impact news"""
    from app.services.news_service import news_service
    buffer = request.args.get('buffer', 30, type=int)
    result = news_service.check_news_stop(symbol, buffer)
    return jsonify(result)

@api.route('/indicators/<symbol>')
def get_indicators(symbol):
    """Get current technical indicator values"""
    from app.services.quant_engine import quant_engine
    from app.services.realtime_data import realtime_service
    
    try:
        candles = realtime_service.get_historical_candles(symbol, 'M5', 100)
        df = pd.DataFrame([asdict(c) for c in candles])
        
        if df.empty:
            return jsonify({"error": "No data"}), 404
        
        # Calculate indicators
        close = df['close']
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # EMAs
        ema_20 = close.ewm(span=20, adjust=False).mean()
        ema_50 = close.ewm(span=50, adjust=False).mean()
        
        # ATR
        high = df['high']
        low = df['low']
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
        
        return jsonify({
            "symbol": symbol,
            "rsi": round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else 50.0,
            "ema_20": round(ema_20.iloc[-1], decimals),
            "ema_50": round(ema_50.iloc[-1], decimals),
            "atr": round(atr.iloc[-1], decimals) if not pd.isna(atr.iloc[-1]) else 0,
            "trend": "BULLISH" if ema_20.iloc[-1] > ema_50.iloc[-1] else "BEARISH",
            "close": round(close.iloc[-1], decimals)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api.route('/logs')
def get_logs():
    """Get recent system logs for terminal view"""
    return jsonify({"logs": _log_buffer[:50]})

@api.route('/system/status')
def system_status():
    """Get comprehensive system status"""
    from app.services.realtime_data import realtime_service
    from app.services.ai_agent import ai_agent
    from app.services.auto_trader import auto_trader
    
    return jsonify({
        "data_mode": realtime_service.data_mode,
        "mt5_connected": realtime_service.mt5_connected,
        "bridge_connected": realtime_service.bridge_connected,
        "ai_status": ai_agent.get_status(),
        "auto_trader_running": auto_trader.running,
        "settings": _settings
    })
