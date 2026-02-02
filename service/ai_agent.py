import os
import json
import logging
import chromadb
import ollama
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAgent:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AI Agent with ChromaDB and Ollama.
        """
        self.config = config
        self.collection_name = "trading_playbooks"
        self.model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        
        # Initialize ChromaDB
        # We use a persistent client to store data in the 'brain' folder
        db_path = os.path.join(os.getcwd(), "DATA", "brain")
        os.makedirs(db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
        
        logger.info(f"AIAgent initialized. Model: {self.model_name}. Brain Path: {db_path}")

    def add_playbook(self, situation: str, strategy: str, outcome: str):
        """
        Add a 'memory' or playbook entry to the RAG system.
        """
        doc = f"Situation: {situation}\nStrategy: {strategy}\nOutcome: {outcome}"
        self.collection.add(
            documents=[doc],
            metadatas=[{"outcome": outcome}],
            ids=[f"mem_{len(self.collection.get()['ids']) + 1}"]
        )
        logger.info("Added new playbook entry to memory.")

    def get_market_sentiment(self, signal_score: float, context_data: Dict[str, float]) -> str:
        """
        The core 'Thinking' function.
        1. Retrieves relevant past playbooks from ChromaDB based on current context.
        2. Constructs a prompt for Ollama.
        3. Returns the LLM's trading advice.
        """
        
        # 1. Retrieve Context (Simple RAG)
        # We query based on a text representation of the current state
        query_text = f"Signal Score: {signal_score:.2f}, RSI: {context_data.get('rsi', 0):.2f}"
        results = self.collection.query(
            query_texts=[query_text],
            n_results=3
        )
        
        retrieved_context = "\n".join(results['documents'][0]) if results['documents'] else "No prior memories found."

        # 2. Construct Prompt
        prompt = f"""
        You are an expert forex trading assistant.
        
        CURRENT MARKET DATA:
        - ML Signal Score: {signal_score:.2f} (Positive=Buy, Negative=Sell)
        - RSI (14): {context_data.get('rsi', 50):.2f}
        - ATR (14): {context_data.get('atr', 0):.4f}
        
        PAST KNOWLEDGE (RAG):
        {retrieved_context}
        
        TASK:
        Analyze the ML signal against the technical context and past knowledge.
        Is this a high-probability trade? Should we reduce risk?
        
        RESPONSE FORMAT:
        Action: [BUY / SELL / HOLD]
        Confidence: [0-100]%
        Reasoning: [One sentence explanation]
        """

        # 3. Ask Ollama
        try:
            response = ollama.chat(model=self.model_name, messages=[
                {'role': 'user', 'content': prompt},
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama inference failed: {e}")
            return "Error: Could not consult AI."

if __name__ == "__main__":
    # Test stub
    agent = AIAgent({})
    # Seed a dummy memory
    agent.add_playbook("RSI > 70 and Score > 0.05", "Fade the move", "Success")
    
    # Test query
    response = agent.get_market_sentiment(0.06, {"rsi": 72.5, "atr": 0.0012})
    print("\n--- AI Response ---")
    print(response)
