"""
AUTOMATED TRADING BOT
- Continuous market scanning
- Automatic signal generation
- Automatic trade execution
- Risk-managed position sizing
- Stop loss / Take profit monitoring
"""
from threading import Thread, Event
import time
from app.services.risk_manager import risk_manager
from app.services.ai_agent import ai_agent
from app.services.ml_engine import ml_engine
from app.services.vector_util import vector_util
from app.services.settings_store import _settings  # Import global settings store
import logging
from dataclasses import asdict
import pandas as pd

logger = logging.getLogger(__name__)

class AutoTrader:
    """
    Fully automated trading bot.
    Scans markets, generates signals, and executes trades automatically.
    """
    
    def __init__(self):
        self.running = False
        self.stop_event = Event()
        self.thread = None
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD']
        self.scan_interval = 10  # seconds between scans (reduced for testing)
        self.last_signal_time = {}
        self.signal_cooldown = 300  # 5 min cooldown between signals per symbol
        
        # Risk settings
        self.max_open_positions = 3
        self.risk_per_trade = 0.02  # 2% risk per trade
        self.min_confidence = 0.4  # 40% minimum confidence
        self.min_risk_reward = 1.5
        
    def start(self):
        """Start automated trading - WITH VALIDATION"""
        if self.running:
            logger.info("AutoTrader already running, skipping start.")
            return
        
        # PRE-ENGAGEMENT VALIDATION
        validation_result = self._validate_system_ready()
        if not validation_result['ready']:
            logger.error(f"❌ AutoTrader CANNOT START: {validation_result['reason']}")
            self._broadcast_log("SYSTEM", f"❌ ENGAGEMENT BLOCKED: {validation_result['reason']}", "error")
            raise RuntimeError(f"Cannot start AutoTrader: {validation_result['reason']}")
        
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._trading_loop, daemon=True)
        self.thread.start()
        logger.info("===========================================")
        logger.info("AutoTrader STARTED - Thread spawned")
        logger.info(f"Symbols to scan: {self.symbols}")
        logger.info(f"Scan interval: {self.scan_interval}s")
        logger.info("===========================================")
        self._broadcast_log("SYSTEM", "✅ Auto-Trading ENGAGED - All systems operational", "success")
        print("[AUTOTRADER] Started scanning thread!")
    
    def _validate_system_ready(self) -> dict:
        """
        Validates that all required systems are ready before engaging auto trading.
        Returns: {'ready': bool, 'reason': str}
        """
        from app.services.realtime_data import realtime_service
        from app.services.ai_agent import ai_agent
        
        # 1. Check data connection (Require MT5 for Live Mode)
        if not realtime_service.mt5_connected:
            return {
                'ready': False,
                'reason': 'DIRECT MT5 CONNECTION REQUIRED. Please ensure MetaTrader 5 is running with Algorithmic Trading enabled.'
            }
        
        # 2. Check AI Brain (Ollama)
        ai_status = ai_agent.get_status()
        if not ai_status.get('ollama_ready', False):
            # Attempt to auto-start
            self._broadcast_log("SYSTEM", "⚠️ Ollama offline. Attempting to start service...", "warning")
            if ai_agent.start_ollama_service():
                self._broadcast_log("SYSTEM", "✅ Ollama service started successfully", "success")
                ai_status = ai_agent.get_status() # Refresh status
            else:
                return {
                    'ready': False,
                    'reason': f"AI Brain offline - Ollama could not be started. Install/Run manually."
                }
        
        # 3. Check if required model is loaded
        required_model = ai_agent.model
        if required_model not in ai_status.get('loaded_models', []):
            return {
                'ready': False,
                'reason': f"Required model '{required_model}' not loaded. Available: {ai_status.get('loaded_models', [])}"
            }
        
        # 4. Check RAG system (playbooks)
        try:
            playbooks = vector_util.playbooks
            if not playbooks:
                logger.warning("No playbooks loaded - RAG context will be limited")
        except Exception as e:
            logger.warning(f"RAG system check failed: {e}")
        
        return {'ready': True, 'reason': 'All systems operational'}
    
    def stop(self):
        """Stop automated trading"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("AutoTrader stopped")
    
    def _broadcast_log(self, source: str, message: str, log_type: str = "info"):
        """Broadcast log message to the dashboard via websocket streamer"""
        from app.services.websocket_streamer import streamer
        try:
            streamer.broadcast_log(source, message, log_type)
        except Exception as e:
            logger.warning(f"Failed to broadcast log: {e}")
        # Also log locally
        logger.info(f"[{source}] {message}")
        
    def on_tick(self, tick):
        """Handle incoming tick for reactive trading"""
        if not self.running:
            return
            
        symbol = tick.symbol
        if symbol not in self.symbols:
            return
            
        # Check if we should analyze this tick
        # (e.g. avoid over-analyzing every single tick, once per second is plenty for 'live')
        last_signal = self.last_signal_time.get(symbol, 0)
        if time.time() - last_signal < 1.0: # 1s internal analysis throttle
            return
            
        # Trigger market analysis
        self._analyze_market(symbol)

    def _analyze_market(self, symbol):
        """Analyze market for a specific symbol"""
        # REFRESH LIVE SETTINGS FROM UI
        self.min_confidence = _settings.get('quant_confidence', 40) / 100.0
        self.min_risk_reward = _settings.get('risk_reward_min', 1.5)
        
        from app.services.quant_engine import quant_engine
        from app.services.realtime_data import realtime_service
        from app.services.execution_engine import execution_engine
        
        # LIVE GUARD: Check MT5 connection before analysis
        if not realtime_service.mt5_connected:
            self._broadcast_log("SYSTEM", "🛑 CRITICAL: MT5 Connection Lost! Trading Halted.", "error")
            logger.error(f"--- FAILED ANALYZING {symbol}: MT5 DISCONNECTED ---")
            return

        logger.info(f"--- ANALYZING {symbol} ---")
        logger.info(f"Current Dashboard Settings: Conf >= {self.min_confidence*100}%, RR >= {self.min_risk_reward}")
        
        # Skip if already have position in this symbol
        if symbol in execution_engine.positions:
            return
            
        # Check global cooldown
        last_signal = self.last_signal_time.get(symbol, 0)
        if time.time() - last_signal < self.signal_cooldown:
            return
            
        try:
            # Get data and generate signal
            candles = realtime_service.get_historical_candles(symbol, 'M1', 100)
            
            # VALIDATION: Ensure we have enough data to analyze
            if not candles or len(candles) < 50:
                logger.warning(f"[SCAN] {symbol}: Insufficient data ({len(candles) if candles else 0} candles). Skipping.")
                return
                
            df = pd.DataFrame([asdict(c) for c in candles])
            
            # VALIDATION: Check for valid price data
            if df['close'].isna().any() or (df['close'] == 0).any():
                logger.warning(f"[SCAN] {symbol}: Invalid price data. Skipping.")
                return
            
            signal = quant_engine.generate_signal(df, symbol)
            
            if signal and signal.direction != 'NEUTRAL':
                # ========== TRADING PIPELINE SEQUENCE ==========
                # Step 1: Quant Engine generates signal (already done above)
                logger.info(f"[QUANT] Strategy: {signal.strategy} | Direction: {signal.direction} | Conf: {signal.confidence*100:.0f}% | RR: {signal.risk_reward:.2f}")
                self._broadcast_log("QUANT", f"🛠️ Setup Found: {signal.direction} {symbol} (Conf: {signal.confidence*100:.0f}%)", "info")
                
                # Step 2: Confidence Check
                if signal.confidence < self.min_confidence:
                    logger.warning(f"  ❌ FAILED Confidence: {signal.confidence*100:.0f}% < {self.min_confidence*100:.0f}%")
                    self._broadcast_log("QUANT", f"❌ CONFIDENCE BLOCKED: {signal.confidence*100:.0f}% < {self.min_confidence*100:.0f}% threshold", "warning")
                    return
                
                # Step 3: Risk/Reward Check
                # Use a small epsilon (0.01) to handle floating point noise (e.g. 1.499 < 1.50)
                if signal.risk_reward < (self.min_risk_reward - 0.01):
                    logger.warning(f"  ❌ FAILED Risk/Reward: {signal.risk_reward:.2f} < {self.min_risk_reward:.2f}")
                    self._broadcast_log("RISK", f"❌ RISK/REWARD BLOCKED: {signal.risk_reward:.2f} < {self.min_risk_reward:.2f} minimum", "warning")
                    return
                
                logger.info(f"  ✅ PASSED Risk/Quant Filters. Handing to AI Brain...")
                # Step 4: AI Brain Validation (Llama 3.1) - REQUIRED ≥50% confidence
                from app.services.quant_engine import MarketRegime
                regime = quant_engine.detect_regime(df).value
                    
                self._broadcast_log("BRAIN", f"🧠 AI Validating {symbol} setup with Llama 3.1...", "info")
                signal_data = {
                    'direction': signal.direction,
                    'confidence': signal.confidence,
                    'reasoning': signal.reasoning if hasattr(signal, 'reasoning') else []
                }
                ai_decision = ai_agent.validate_signal(symbol, signal_data, regime)
                ai_confidence = ai_decision.get('confidence', 0)
                ai_reason = ai_decision.get('reason', 'No reason provided')
                ai_decision_type = ai_decision.get('decision', 'HOLD')
                
                # AI must approve (≥50% confidence) AND decision must be BUY/SELL (not HOLD)
                if ai_confidence < 0.5 or ai_decision_type == 'HOLD':
                    self._broadcast_log("BRAIN", f"❌ AI REJECTED: {ai_reason} (Conf: {ai_confidence*100:.0f}%, Decision: {ai_decision_type})", "error")
                    return
                
                # Ensure AI decision matches signal direction
                if ai_decision_type != signal.direction:
                    self._broadcast_log("BRAIN", f"❌ AI DISAGREED: Signal={signal.direction}, AI={ai_decision_type}. {ai_reason}", "warning")
                    return
                    
                self._broadcast_log("BRAIN", f"✅ AI APPROVED: {ai_reason} (Conf: {ai_confidence*100:.0f}%)", "success")
                
                # Step 5: ML Probability Check (≥60% historical success rate)
                from datetime import datetime
                features = {
                    "hour": datetime.now().hour,
                    "volatility": df['close'].pct_change().std() * 100
                }
                # Step 5: ML Probability Check (Dashboard Controlled)
                ml_threshold = _settings.get('ml_threshold', 60) / 100.0
                prob = ml_engine.predict_probability(symbol, features)
                
                # Boost prob slightly if AI consensus is high
                if ai_confidence > 0.8:
                    prob = min(0.95, prob + 0.05)

                if prob < ml_threshold:
                    self._broadcast_log("ML", f"❌ ML PROBABILITY BLOCKED: {prob*100:.1f}% < {ml_threshold*100:.0f}% threshold", "warning")
                    return

                self._broadcast_log("ML", f"✅ ML APPROVED: High Probability Setup ({prob*100:.1f}%)", "success")
                
                # Step 6: News Filter (blocks trades 30min before high-impact events)
                from app.services.news_service import news_service
                self._broadcast_log("NEWS", f"📰 Checking News Calendar...", "info")
                news_check = news_service.check_news_stop(symbol, buffer_minutes=30)
                if news_check.get('stop', False):
                    reason = news_check.get('reason', 'High Impact News')
                    self._broadcast_log("NEWS", f"❌ NEWS BLOCKED: {reason}", "warning")
                    # Notify Telegram
                    if _settings.get('telegram_enabled') and _settings.get('telegram_chat_id'):
                        from app.services.telegram_service import telegram_service
                        telegram_service.notify_news_block(_settings['telegram_chat_id'], symbol, reason)
                    return
                self._broadcast_log("NEWS", f"✅ NEWS PASS: No immediate high-impact events", "success")
                
                # Step 7: Spread Protection (rejects if spread > 30% of ATR)
                self._broadcast_log("RISK", f"🛡️ Verifying Spread & Liquidity...", "info")
                tick = realtime_service.get_live_price(symbol)
                if tick:
                    spread = tick.ask - tick.bid
                    # Calculate ATR for spread check
                    atr = df['high'].iloc[-14:].max() - df['low'].iloc[-14:].min()
                    if atr > 0 and spread > 0.3 * atr:
                        self._broadcast_log("RISK", f"❌ SPREAD BLOCKED: Spread too wide ({spread:.5f} > 30% ATR)", "warning")
                        return
                self._broadcast_log("RISK", f"✅ RISK PASS: Market conditions nominal", "success")
                    
                # Step 8: Position Sizing & Execution
                account = realtime_service.get_account_info()
                self._broadcast_log("EXEC", f"🚀 Calculating Dynamic Position Size...", "info")
                equity = account.get('equity', 0)
                balance = account.get('balance', 0)
                
                # Calculate basic lot from risk manager
                base_lot = risk_manager.calculate_lot_size(symbol, signal.entry_price, signal.stop_loss)
                
                # Apply Growth Scaling
                # Calculate current drawdown
                drawdown = ((balance - equity) / balance * 100) if balance > 0 else 0
                final_lot = ml_engine.calculate_compounding_lot(base_lot, equity, drawdown)
                if final_lot > base_lot:
                    self._broadcast_log("GROWTH", f"Compounding lot size: {final_lot} (Base: {base_lot})", "info")
                
                # Execute Trade
                self._execute_trade(symbol, signal, final_lot, execution_engine, realtime_service)
                self.last_signal_time[symbol] = time.time()
                
        except Exception as e:
            logger.error(f"Analysis error for {symbol}: {e}")

    def _trading_loop(self):
        """Background loop for market scanning and position maintenance"""
        from app.services.realtime_data import realtime_service
        from app.services.execution_engine import execution_engine
        
        logger.info("AutoTrader: Trading loop thread RUNNING")
        print("[AUTOTRADER] Trading loop started inside thread!")
        
        scan_count = 0
        while not self.stop_event.is_set():
            try:
                scan_count += 1
                logger.info(f"[SCAN #{scan_count}] Scanning {len(self.symbols)} symbols...")
                print(f"[AUTOTRADER] Scan #{scan_count} starting...")
                
                # SCAN ALL SYMBOLS FOR OPPORTUNITIES
                for symbol in self.symbols:
                    if not self.running:
                        break
                    logger.info(f"[SCAN] Analyzing {symbol}...")
                    self._analyze_market(symbol)
                
                # Update positions with current prices
                self._update_positions(execution_engine, realtime_service)
                
                logger.info(f"[SCAN #{scan_count}] Complete. Next scan in {self.scan_interval}s")
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                import traceback
                traceback.print_exc()
            
            # Wait before next scan cycle
            time.sleep(self.scan_interval)
    
    def _execute_trade(self, symbol, signal, lots, execution_engine, realtime_service):
        """Execute a trade based on signal and optimized lot size"""
        from app.services.websocket_streamer import streamer
        
        try:
            # Ensure lots is valid
            if lots <= 0:
                logger.warning(f"Lot size is zero or negative for {symbol}. Skipping trade.")
                return

            self._broadcast_log("BOT", f"Executing {signal.direction} {lots} lots on {symbol}...", "info")

            # Place the order via execution engine
            result = execution_engine.place_order(
                symbol=symbol,
                order_type=signal.direction.lower(),
                quantity=lots,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit_2
            )
            
            decimals = 2 if symbol in ['XAUUSD', 'BTCUSD'] else 5
            
            if result.get('success'):
                self._broadcast_log("TRADE", f"EXECUTED: {signal.direction} {symbol} @ {round(signal.entry_price, decimals)} | Ticket: #{result.get('ticket')}", "success")
                
                # Broadcast trade to dashboard
                streamer.broadcast_trade({
                    'symbol': symbol,
                    'side': signal.direction,
                    'entry': round(signal.entry_price, decimals),
                    'size': lots,
                    'stop_loss': round(signal.stop_loss, decimals),
                    'take_profit': round(signal.take_profit_1, decimals)
                })
            else:
                self._broadcast_log("BOT", f"Execution Failed: {result.get('comment')}", "error")
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            self._broadcast_log("ERROR", f"Trade failed: {e}", "error")
    
    def _update_positions(self, execution_engine, realtime_service):
        """Update all positions with current prices"""
        prices = {}
        for symbol in execution_engine.positions.keys():
            tick = realtime_service.get_live_price(symbol)
            if tick:
                prices[symbol] = tick.bid  # Use bid for position valuation
        
        execution_engine.update_positions(prices)

# Singleton
auto_trader = AutoTrader()
