from app.services.vector_util import vector_util
import logging
import requests
import json
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AIAgent:
    """
    The Brain of the system. 
    Validates quantitative signals using LLM reasoning and RAG context.
    """
    
    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.ollama_tags_url = "http://127.0.0.1:11434/api/tags"
        self.ollama_ready = False
        self.loaded_models = []
        self._check_ollama_health()
    
    def start_ollama_service(self) -> bool:
        """Attempts to start Ollama service if not running"""
        import subprocess
        import time
        try:
            logger.info("Attempting to start Ollama service...")
            # Start in new console so it persists
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Wait a bit for startup
            logger.info("Waiting 5s for Ollama to initialize...")
            time.sleep(5)
            
            # Recheck health
            self._check_ollama_health()
            return self.ollama_ready
        except Exception as e:
            logger.error(f"Failed to auto-start Ollama: {e}")
            return False

    def _check_ollama_health(self):
        """Verify Ollama is running and has models loaded"""
        try:
            response = requests.get(self.ollama_tags_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.loaded_models = [m.get('name', '') for m in data.get('models', [])]
                if self.loaded_models:
                    self.ollama_ready = True
                    logger.info(f"Ollama READY: Models loaded - {self.loaded_models}")
                else:
                    self.ollama_ready = False
                    logger.warning("Ollama running but NO MODELS loaded. Run: ollama pull llama3.1:8b")
            else:
                self.ollama_ready = False
                logger.warning("Ollama not responding correctly")
        except Exception as e:
            self.ollama_ready = False
            logger.error(f"AI Agent: Ollama connectivity error! Is the service bound to 127.0.0.1:11434? Error: {e}")
            logger.warning("Tip: Run 'ollama serve' if not running.")
    
    def get_status(self) -> Dict:
        """Return AI health status for API exposure"""
        return {
            "ollama_ready": self.ollama_ready,
            "loaded_models": self.loaded_models,
            "model_in_use": self.model,
            "status": "ACTIVE" if self.ollama_ready else "OFFLINE"
        }
        
    def validate_signal(self, symbol: str, signal_data: Dict, regime: str) -> Dict:
        """
        Takes a raw quant signal and returns an AI-validated decision.
        REQUIRES Ollama to be ready - returns rejection if not ready.
        """
        logger.info(f"AI Agent: Validating {signal_data.get('direction')} signal for {symbol}")
        
        # CRITICAL: Check if Ollama is ready before proceeding
        if not self.ollama_ready:
            logger.warning("AI Agent: Ollama not ready - REJECTING signal (AI validation required)")
            return {
                "decision": "HOLD",
                "confidence": 0.0,
                "reason": "AI Brain offline - Ollama models not loaded. Cannot validate signal."
            }
        
        # Ensure model is loaded
        if self.model not in self.loaded_models:
            logger.warning(f"AI Agent: Model {self.model} not loaded - attempting to load...")
            self._check_ollama_health()  # Re-check
            if self.model not in self.loaded_models:
                return {
                    "decision": "HOLD",
                    "confidence": 0.0,
                    "reason": f"Model {self.model} not available. Run: ollama pull {self.model}"
                }
        
        # 1. Fetch relevant playbook via RAG-lite
        reasons = signal_data.get('reasoning', [])
        playbook = vector_util.get_relevant_context(reasons)
        
        # 2. Build the prompt
        prompt = self._build_validation_prompt(symbol, signal_data, regime, playbook)
        
        logger.info(f"🧠 [BRAIN] Consulting with Llama 3.1 for {symbol}...")
        logger.info(f"   Context: {len(playbook)} chars from playbooks")
        
        # 3. Query Llama
        try:
            response = requests.post(self.ollama_url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }, timeout=30)
            
            if response.status_code == 200:
                result = response.json().get('response', '{}')
                try:
                    validation = json.loads(result)
                    logger.info(f"   Response: {validation.get('decision')} (Conf: {validation.get('confidence', 0)*100:.0f}%)")
                    logger.info(f"   Reason: {validation.get('reason')}")
                    logger.info(f"AI Agent: Validation complete. Result: {validation.get('decision')}")
                    return validation
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract decision from text
                    logger.warning(f"AI Agent: Failed to parse JSON response: {result}")
                    # Try to extract decision from text response
                    if "BUY" in result.upper():
                        return {"decision": "BUY", "confidence": 0.5, "reason": "AI approved (parsed from text)"}
                    elif "SELL" in result.upper():
                        return {"decision": "SELL", "confidence": 0.5, "reason": "AI approved (parsed from text)"}
                    else:
                        return {"decision": "HOLD", "confidence": 0.0, "reason": "AI response unclear"}
        except requests.exceptions.RequestException as e:
            logger.error(f"AI Agent validation failed (connection error): {e}")
        except Exception as e:
            logger.error(f"AI Agent validation failed: {e}")
            
        # Fallback: REJECT if AI fails (don't trade without AI validation)
        return {
            "decision": "HOLD",
            "confidence": 0.0,
            "reason": "AI validation failed - cannot proceed without AI Brain approval."
        }

    def _build_validation_prompt(self, symbol: str, signal: Dict, regime: str, playbook: str) -> str:
        return f"""
        [CONTEXT]
        You are a Senior AI Trading Assistant. Your goal is to grow the user's asset capital by validating signals.
        
        [MARKET DATA]
        Symbol: {symbol}
        Direction: {signal.get('direction')}
        Regime: {regime}
        Confidence: {signal.get('confidence')}
        Quant Reasoning: {", ".join(signal.get('reasoning', []))}
        
        [STRATEGY PLAYBOOK]
        {playbook}
        
        [INSTRUCTION]
        Analyze the setup. If it matches the playbook and regime, output BUY or SELL. 
        If too risky or contradictory, output HOLD.
        
        Respond ONLY with JSON:
        {{
            "decision": "BUY" | "SELL" | "HOLD",
            "confidence": 0.0-1.0,
            "reason": "One concise sentence explaining your logic."
        }}
        """

# Singleton
ai_agent = AIAgent()
