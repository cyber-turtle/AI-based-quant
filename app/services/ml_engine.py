import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, List
import os
import json

logger = logging.getLogger(__name__)

class MLEngine:
    """
    ML ENGINE - Asset Growth & Probability Layer
    - Predicts probability of trade success
    - Optimizes risk scaling based on model confidence
    - Handles automated compounding logic
    """
    
    def __init__(self):
        self.model_path = "intelligent_trading_system/app/ml_models"
        self.performance_cache = {}
        self._ensure_dirs()
        
    def _ensure_dirs(self):
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path, exist_ok=True)

    def predict_probability(self, symbol: str, features: Dict) -> float:
        """
        Returns a probability score (0.0 to 1.0) for a trade setup.
        In Phase 10, this will transition from heuristic-based to model-based.
        """
        # Placeholder: Intelligent Heuristic for now, replaced by model.predict() after train.py runs
        # We factor in: Time of day, volatility, and trend strength
        
        # Example Logic: Boost probability if we are in core trading hours
        hour = features.get('hour', 0)
        if 8 <= hour <= 18: # Extended London/NY session
            prob += 0.1
            
        # Factoring in volatility (Normalized ATR)
        vol = features.get('volatility', 0)
        if 0.3 < vol < 3.0: # Wider healthy volatility range
            prob += 0.1
        elif vol > 5.0: # Extreme volatility protection
            prob -= 0.1
            
        return min(0.95, max(0.05, prob))

    def calculate_compounding_lot(self, base_lot: float, equity: float, drawdown: float) -> float:
        """
        Calculates dynamic lot size for automated compounding.
        Scales aggressively during win streaks and protects capital during drawdown.
        """
        # Simple Compounding: Increase lot by 1% for every 5% equity growth
        growth_factor = 1.0
        if equity > 10000: # Threshold for aggressive scaling
             growth_factor = (equity / 10000) ** 0.5
             
        # Drawdown protection: Reduce scaling if drawdown > 2%
        if drawdown > 2.0:
            growth_factor *= (1 - (drawdown / 100))
            
        return round(base_lot * growth_factor, 2)

# Singleton
ml_engine = MLEngine()
