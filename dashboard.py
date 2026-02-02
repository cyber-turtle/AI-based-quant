import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import os
from pathlib import Path
from datetime import datetime

# Import local modules
# (We need to add the current dir to path or run as module)
import sys
sys.path.append(os.getcwd())

from service.App import load_config, App
from service.ai_agent import AIAgent
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

# === CONFIGURATION ===
st.set_page_config(page_title="Intelligent Trading Bot", page_icon="📈", layout="wide")

# Load Config
CONFIG_PATH = "config.json"
if "config" not in st.session_state:
    load_config(CONFIG_PATH)
    st.session_state["config"] = App.config

config = st.session_state["config"]
symbol = config.get("symbol", "EURUSD")
data_path = Path(config.get("data_folder")) / symbol
signals_file = data_path / "signals.csv"

# Initialize AI Agent
if "agent" not in st.session_state:
    st.session_state["agent"] = AIAgent(config)

agent = st.session_state["agent"]

# === SIDEBAR ===
st.sidebar.title("🤖 Hybrid Brain")
st.sidebar.markdown(f"**Symbol:** {symbol}")
st.sidebar.markdown(f"**Model:** {os.getenv('OLLAMA_MODEL', 'llama3.1:8b')}")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# === TABS ===
tab1, tab2, tab3 = st.tabs(["📈 Live Market", "💰 Performance", "🧠 The Lab"])

# --- TAB 1: LIVE MARKET ---
with tab1:
    st.subheader("Live Market Analysis")
    
    if signals_file.exists():
        # Load Data
        df = pd.read_csv(signals_file)
        df['time'] = pd.to_datetime(df[config.get("time_column", "timestamp")])
        df = df.sort_values('time')
        
        # Filter last N candles for performance
        lookback = st.slider("Lookback Candles", min_value=50, max_value=5000, value=200)
        subset = df.tail(lookback).reset_index(drop=True)
        
        # Main Chart
        fig = go.Figure()
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=subset['time'],
            open=subset['open'],
            high=subset['high'],
            low=subset['low'],
            close=subset['close'],
            name='OHLC'
        ))
        
        # EMA Overlays (if they exist)
        if 'close_EMA_12' in subset.columns:
            fig.add_trace(go.Scatter(x=subset['time'], y=subset['close_EMA_12'], line=dict(color='orange', width=1), name='EMA 12'))
        if 'close_EMA_26' in subset.columns:
            fig.add_trace(go.Scatter(x=subset['time'], y=subset['close_EMA_26'], line=dict(color='blue', width=1), name='EMA 26'))
            
        # Buy/Sell Markers from AI
        buys = subset[subset['ai_action'] == 'BUY']
        sells = subset[subset['ai_action'] == 'SELL']
        
        fig.add_trace(go.Scatter(
            x=buys['time'], y=buys['low']*0.9995,
            mode='markers', marker=dict(symbol='triangle-up', size=10, color='green'),
            name='AI BUY'
        ))
        
        fig.add_trace(go.Scatter(
            x=sells['time'], y=sells['high']*1.0005,
            mode='markers', marker=dict(symbol='triangle-down', size=10, color='red'),
            name='AI SELL'
        ))
        
        fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
        # Latest Signal Panel
        latest = subset.iloc[-1]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Latest Close", f"{latest['close']:.5f}")
        with c2:
            signal_color = "green" if latest['ai_action'] == "BUY" else "red" if latest['ai_action'] == "SELL" else "gray"
            st.markdown(f"### AI Signal: :{signal_color}[{latest['ai_action']}]")
        with c3:
            st.metric("ML Score", f"{latest.get('trade_score', 0.0):.4f}")
            
        st.info(f"**AI Reasoning:** {latest.get('ai_reasoning', 'No reasoning available.')}")
        
    else:
        st.error(f"Signals file not found at: {signals_file}. Run 'py -m scripts.signals' first.")

# --- TAB 2: PERFORMANCE ---
with tab2:
    st.subheader("Account Performance (MT5)")
    
    if mt5 and config.get("mt5_account_id"):
        try:
            # Init MT5
            if not mt5.initialize():
                 st.error(f"MT5 Init failed: {mt5.last_error()}")
            else:
                authorized = mt5.login(
                    login=int(config["mt5_account_id"]), 
                    password=config["mt5_password"], 
                    server=config["mt5_server"]
                )
                if authorized:
                    account_info = mt5.account_info()
                    if account_info:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Balance", f"{account_info.balance} {account_info.currency}")
                        col2.metric("Equity", f"{account_info.equity} {account_info.currency}")
                        col3.metric("Profit", f"{account_info.profit} {account_info.currency}")
                        
                        st.write("---")
                        st.write("### Recent Deals")
                        
                        # Get history
                        from_date = datetime(2020, 1, 1)
                        deals = mt5.history_deals_get(from_date, datetime.now())
                        if deals:
                            deals_df = pd.DataFrame(list(deals))
                            st.dataframe(deals_df.tail(10))
                        else:
                            st.warning("No deals found.")
                    else:
                        st.error("Failed to get account info.")
                else:
                    st.error(f"MT5 Login failed: {mt5.last_error()}")
        except Exception as e:
            st.error(f"MT5 Connection Error: {e}")
    else:
        st.warning("MT5 configuration missing or module not installed.")

# --- TAB 3: THE LAB ---
with tab3:
    st.subheader("🧠 Cortex Lab")
    st.write("Chat directly with your AI Agent. It has access to your trading 'playbooks'.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about the market or strategy..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # Simple wrapper to use Ollama directly for chat, potentially using RAG later
            import ollama
            
            # Retrieve RAG context if applicable (naive implementation for now)
            # We reuse the agent's collection
            results = agent.collection.query(query_texts=[prompt], n_results=1)
            context = results['documents'][0][0] if results['documents'] else "No specific memory."
            
            full_prompt = f"User Question: {prompt}\n\nRelevant Memory: {context}\n\nAnswer as a Trading Assistant:"
            
            stream = ollama.chat(
                model=agent.model_name,
                messages=[{'role': 'user', 'content': full_prompt}],
                stream=True,
            )
            response = st.write_stream(chunk['message']['content'] for chunk in stream)
            
        st.session_state.messages.append({"role": "assistant", "content": response})
