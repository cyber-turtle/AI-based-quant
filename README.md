# Intelligent Trading System v2: Cortex

**Cortex** is a next-generation automated trading system that combines high-frequency signal processing with a Retrieval-Augmented Generation (RAG) AI brain to make informed, context-aware trading decisions.

![Dashboard](docs/images/dashboard_preview.png)

## 🚀 Key Features

### 1. AI "Brain" (RAG Architecture)

Unlike traditional bots that rely solely on math, Cortex has a **Memory**.

- **ChromaDB**: Stores past trading scenarios, market setups, and outcomes ("Playbooks").
- **Ollama (LLM)**: Analyzes current ML signals against this historical context to detect hallucinations or weak setups.
- **RAG Process**:
  1.  **Retrieve**: Finds similar past market conditions.
  2.  **Augment**: Feeds current technicals + past outcomes to the AI.
  3.  **Generate**: AI outputs a "Confidence Score" and reasoning (Buy/Sell/Hold).

### 2. Zero-Latency Dashboard

A modern, dark-mode UI built with **Flask** and **Server-Sent Events (SSE)**.

- **Real-Time Ticker**: Live price updates without page reloads.
- **Active Trade Management**: visual stop-loss/take-profit tracking.
- **System Health**: Monitor AI inference latency and bridge connection status.

### 3. Intelligent Engine

- **Hybrid Signal Generation**: Combines classic ML (TensorFlow/Scikit-Learn) with "Intelligent Indicators".
- **Safety First**: "Live Guard" prevents execution if MT5 connection is unstable.
- **Auto-Risk**: Dynamic position sizing based on account equity and volatility (ATR).

---

## 🛠️ Architecture

```mermaid
graph TD
    A[MT5/Binance] -->|Live Data| B(Real-time Service)
    B --> C{ML Engine}
    C -->|Raw Signal| D[RAG Evaluator]
    D <-->|Query/Context| E[(ChromaDB Memory)]
    D <-->|Inference| F[Ollama AI]
    D -->|Validated Signal| G[Execution Engine]
    G --> A
    B --> H[Web Dashboard (Flask)]
    G --> H
```

## 📦 Installation

1.  **Clone & Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Credentials**:
    - Copy `config.example.json` to `config.json`.
    - Enter your MT5 and Telegram credentials. (See `SETUP_GUIDE.md` for details).

3.  **Run the System**:
    ```bash
    # Starts the Dashboard & Trading Engine
    py run.py
    ```
    Access the UI at: `http://127.0.0.1:5000`

## 🧠 Training & Offline Mode

The system handles offline model training via the `scripts/` module.

- `python -m scripts.train -c config.json`

## 🤝 Contributing

- **Frontend**: `app/templates` (HTML/Tailwind)
- **AI Logic**: `service/ai_agent.py`
- **Trading Core**: `service/server.py`
