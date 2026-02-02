"""
TRADING LOOP SERVICE
Connects:
- SmartBrain (MTF Analysis, Entry Logic)
- RiskEngine (Position Sizing, Drawdown Checks)
- StrategyEngine (User's Active Strategies)
- AI Agent (Ollama for Reasoning)

Runs on a schedule (e.g., every 5 minutes).
"""
import logging
import time
from datetime import datetime
from app.services.smart_brain import brain
from app.services.risk_engine import RiskEngine
from app.services.strategy_engine import StrategyEngine
# from service.ai_agent import AIAgent  # Optional: Add AI reasoning

logger = logging.getLogger(__name__)

class TradingLoop:
    def __init__(self, user_id):
        self.user_id = user_id
        self.running = False
        self.last_signal = None
        
    def run_cycle(self):
        """
        Single iteration of the trading loop.
        1. Check if trading is paused (Kill Switch)
        2. Scan for opportunities (SmartBrain)
        3. Validate against RiskEngine
        4. Execute or Log Signal
        """
        logger.info(f"[Loop] Running cycle for user {self.user_id}")
        
        # 1. Kill Switch Check
        pause_check = RiskEngine.check_kill_switch(self.user_id)
        if pause_check.get('pause'):
            logger.warning(f"[Loop] Trading Paused: {pause_check.get('reason')}")
            return {'status': 'PAUSED', 'reason': pause_check.get('reason')}
        
        # 2. Scan for Opportunities
        setup = brain.scan_for_opportunities()
        
        if not setup:
            return {'status': 'WAITING', 'message': 'No valid setup found. Waiting for confluence.'}
        
        logger.info(f"[Loop] Setup Found: {setup}")
        
        # 3. Risk Validation
        # Fake AccountSnapshot for now (should be fetched from DB/MT5)
        mock_snapshot = type('obj', (object,), {
            'equity': 10000,
            'drawdown_percent': 2.0,
            'daily_pnl': 50
        })()
        
        risk_check = RiskEngine.validate_signal(self.user_id, {
            'stop_loss': setup.get('stop_loss'),
            'confidence': 0.85  # Heuristic confidence for rule-based
        }, mock_snapshot)
        
        if not risk_check.get('valid'):
            logger.warning(f"[Loop] Risk Rejected: {risk_check.get('reason')}")
            return {'status': 'REJECTED', 'reason': risk_check.get('reason')}
        
        # 4. Calculate Position Size
        lot_size = RiskEngine.calculate_position_size(
            self.user_id,
            setup.get('entry'),
            setup.get('stop_loss'),
            mock_snapshot.equity
        )
        
        setup['lot_size'] = lot_size
        self.last_signal = setup
        
        # 5. Execute (Paper Trading Mode for now)
        logger.info(f"[Loop] SIGNAL READY: {setup}")
        
        return {'status': 'SIGNAL', 'data': setup}
    
    def start(self, interval_seconds=300):
        """
        Start the trading loop.
        Runs every `interval_seconds` (default 5 min).
        """
        self.running = True
        logger.info(f"[Loop] Starting trading loop with {interval_seconds}s interval")
        
        while self.running:
            try:
                result = self.run_cycle()
                logger.info(f"[Loop] Cycle Result: {result}")
            except Exception as e:
                logger.error(f"[Loop] Error: {e}")
            
            time.sleep(interval_seconds)
    
    def stop(self):
        self.running = False
        logger.info("[Loop] Trading loop stopped.")
