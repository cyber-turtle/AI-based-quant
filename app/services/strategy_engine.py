from app import db
from app.models import Strategy
import logging

logger = logging.getLogger(__name__)

class StrategyEngine:
    @staticmethod
    def get_all_active_strategies(user_id):
        return Strategy.query.filter_by(user_id=user_id, is_active=True).all()

    @staticmethod
    def parse_rule(rule_string, context):
        """
        Parses legacy rule strings like "RSI > 70" or "EMA_CROSS"
        Context is a dict of Market features: {'rsi_14': 65, 'ema_20': 1.05, ...}
        """
        try:
            # Simple eval safe-guarding (Production should use AST or a proper parser)
            # Replacing variables with context values
            safe_rule = rule_string
            for key, value in context.items():
                if key in safe_rule:
                    safe_rule = safe_rule.replace(key, str(value))
            
            # Allow basic math and logic
            allowed_names = {"and": getattr, "or": getattr, "not": getattr}
            # This is risky, but for now we port the logic directly. 
            # In a real engine we'd build an Expression Tree.
            # Using eval for MVP but wrapping in try/except 
            
            # Since legacy format was often just "RSI > 70", we can try to interpret naturally
            # For now, let's implement the specific logic for Known Models
            
            if "EMA_CROSS" in rule_string:
                return context['ema_20'] > context['ema_50']
            
            if "RSI >" in rule_string:
                val = float(rule_string.split('>')[1])
                return context['rsi_14'] > val

            if "RSI <" in rule_string:
                val = float(rule_string.split('<')[1])
                return context['rsi_14'] < val
                
            return False
        except Exception as e:
            logger.error(f"Rule Parse Error: {e}")
            return False

    @staticmethod
    def apply_strategies(user_id, market_features):
        strategies = StrategyEngine.get_all_active_strategies(user_id)
        signals = []
        
        for strat in strategies:
            # Basic Logic Porting from strategy.service.ts
            action = "HOLD"
            
            if strat.name == "EMA_CROSS":
                if market_features['ema_20'] > market_features['ema_50'] and market_features['rsi_14'] > 55:
                    action = "BUY"
                elif market_features['ema_20'] < market_features['ema_50'] and market_features['rsi_14'] < 45:
                    action = "SELL"
            
            elif strat.name == "RSI_REVERSAL":
                if market_features['rsi_14'] < 30:
                    action = "BUY"
                elif market_features['rsi_14'] > 70:
                    action = "SELL"
            
            if action != "HOLD":
                signals.append({
                    'strategy': strat.name,
                    'action': action,
                    'confidence': 0.85 # Heuristic for rule-based
                })
        
        return signals
