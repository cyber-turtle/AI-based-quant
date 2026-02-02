import os
from typing import Dict, List, Optional

class VectorUtility:
    """
    Lightweight utility for Managing Strategy Playbooks.
    Acts as a simple conceptual index for RAG injection.
    """
    
    def __init__(self, data_path: str = None):
        import os
        # Try multiple possible paths
        if data_path is None:
            possible_paths = [
                "DATA/playbooks",
                "intelligent_trading_system/DATA/playbooks",
                "intelligent_trading_system/data/playbooks",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "DATA", "playbooks")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    data_path = path
                    break
            if data_path is None:
                data_path = "DATA/playbooks"  # Default fallback
        self.data_path = data_path
        self.playbooks = {}
        self._load_local_playbooks()
        
    def _load_local_playbooks(self):
        """Scan directory for markdown playbooks"""
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path, exist_ok=True)
            return

        for file in os.listdir(self.data_path):
            if file.endswith(".md"):
                name = file.replace(".md", "").upper()
                with open(os.path.join(self.data_path, file), 'r', encoding='utf-8') as f:
                    self.playbooks[name] = f.read()

    def get_relevant_context(self, strategies: List[str]) -> str:
        """Retrieve playbook content for active strategies"""
        context = []
        for strat in strategies:
            # Match strategy names (e.g. EMA_CROSS)
            for key in self.playbooks:
                if key in strat:
                    context.append(f"### {key} PLAYBOOK\n{self.playbooks[key]}")
        
        if not context:
            return "General guidance: Priority is capital preservation and trend alignment."
            
        return "\n\n".join(context)

# Singleton
vector_util = VectorUtility()
