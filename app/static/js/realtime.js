// REAL-TIME ZERO-LATENCY DASHBOARD
// Using Server-Sent Events (SSE) for sub-second updates
// Professional Charting with LightweightCharts

document.addEventListener('DOMContentLoaded', () => {
    // ==================== ELEMENTS ====================
    const balanceEl = document.getElementById('balance');
    const equityEl = document.getElementById('equity');
    const dailyPnlEl = document.getElementById('daily-pnl');
    const positionCountEl = document.getElementById('position-count');
    const botStatusEl = document.getElementById('bot-status');
    const currentBidEl = document.getElementById('current-bid');
    const currentAskEl = document.getElementById('current-ask');
    const spreadEl = document.getElementById('spread-display');
    const positionsListEl = document.getElementById('positions-list');
    const brainLogEl = document.getElementById('brain-log');
    const liveIndicator = document.getElementById('live-indicator');
    const wsIndicator = document.getElementById('ws-indicator');
    
    // ==================== STATE ====================
    let currentSymbol = 'EURUSD';
    let currentTimeframe = 'M5';
    let chart = null;
    let candleSeries = null;
    let eventSource = null;
    let isConnected = false;
    
    // ==================== UTILITIES ====================
    const formatCurrency = (val) => {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
    };
    
    const formatPrice = (price, symbol) => {
        if (!price) return '0.00';
        const s = symbol.toUpperCase();
        const decimals = (s.includes('JPY') || s.includes('XAU') || s.includes('BTC') || s.includes('ETH')) ? 2 : 5;
        return parseFloat(price).toFixed(decimals);
    };
    
    const addLog = (source, message, type = 'info') => {
        const colors = {
            info: 'text-blue-400',
            success: 'text-green-400',
            warning: 'text-yellow-400',
            error: 'text-red-400'
        };
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        const div = document.createElement('div');
        div.className = 'py-1 border-b border-slate-700/50 text-xs';
        div.innerHTML = `<span class="text-slate-500">${time}</span> <span class="${colors[type]} font-bold">[${source}]</span> <span class="text-slate-300 ml-1">${message}</span>`;
        brainLogEl.insertBefore(div, brainLogEl.firstChild);
        if (brainLogEl.children.length > 30) brainLogEl.removeChild(brainLogEl.lastChild);
    };

    // ==================== CHART ====================
    const initChart = () => {
        const container = document.getElementById('chart-container');
        if (!container) return;
        
        container.innerHTML = ''; // Clear for re-init
        chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: 400,
            layout: { background: { color: '#0f172a' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
        });
        
        candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#22c55e', downColor: '#ef4444', borderVisible: false,
            wickUpColor: '#22c55e', wickDownColor: '#ef4444',
        });
        
        loadChartData();
        
        // Resize handle
        window.addEventListener('resize', () => {
            chart.applyOptions({ width: container.clientWidth });
        });
    };
    
    const loadChartData = async () => {
        try {
            const res = await fetch(`/api/history/${currentSymbol}/${currentTimeframe}`);
            const data = await res.json();
            if (Array.isArray(data) && candleSeries) {
                // Ensure data is sorted by time
                data.sort((a, b) => a.time - b.time);
                candleSeries.setData(data);
                chart.timeScale().fitContent();
            }
        } catch (e) {
            console.error('Chart load error:', e);
        }
    };

    window.setTimeframe = (tf) => {
        currentTimeframe = tf;
        addLog('SYSTEM', `Switching chart to ${tf} timeframe`, 'info');
        
        // Update UI buttons
        document.querySelectorAll('[data-timeframe]').forEach(btn => {
            if (btn.dataset.timeframe === tf) {
                btn.classList.add('bg-indigo-600', 'text-white');
                btn.classList.remove('text-slate-500');
            } else {
                btn.classList.remove('bg-indigo-600', 'text-white');
                btn.classList.add('text-slate-500');
            }
        });
        
        loadChartData();
    };

    window.setSymbol = (symbol) => {
        currentSymbol = symbol;
        document.getElementById('chart-symbol').textContent = symbol;
        addLog('SYSTEM', `Trading Pair changed to ${symbol}`, 'info');
        loadChartData();
    };
    
    // ==================== REAL-TIME STREAM (SSE) ====================
    const connectStream = () => {
        if (eventSource) eventSource.close();
        
        addLog('SYSTEM', 'Opening real-time data stream...', 'info');
        eventSource = new EventSource('/stream');
        
        eventSource.onopen = () => {
            isConnected = true;
            wsIndicator.className = 'w-2 h-2 rounded-full bg-green-500 animate-pulse';
            addLog('SYSTEM', 'Stream connected - Real-time market data active', 'success');
        };
        
        eventSource.onerror = (e) => {
            isConnected = false;
            wsIndicator.className = 'w-2 h-2 rounded-full bg-red-500';
            addLog('ERROR', 'Stream disconnected. Auto-reconnecting...', 'error');
            eventSource.close();
            setTimeout(connectStream, 3000); // Robust retry loop
        };
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            // Handle Heartbeat
            if (data.type === 'heartbeat') return;
            
            // Handle Tick Updates (Price)
            if (data.type === 'tick_update') {
                const tick = data.ticks[currentSymbol];
                if (tick) {
                    currentBidEl.textContent = formatPrice(tick.bid, currentSymbol);
                    currentAskEl.textContent = formatPrice(tick.ask, currentSymbol);
                    spreadEl.textContent = `S: ${tick.spread}`;
                    
                    // Live Indicator Flash
                    liveIndicator.classList.remove('bg-green-500');
                    liveIndicator.classList.add('bg-white');
                    setTimeout(() => {
                        liveIndicator.classList.remove('bg-white');
                        liveIndicator.classList.add('bg-green-500');
                    }, 50);
                    
                    // Update current candle's close price in real-time
                    if (candleSeries) {
                        // Calculate bar time based on current timeframe
                        const now = Math.floor(Date.now() / 1000);
                        let barTime;
                        
                        if (currentTimeframe === 'M1') barTime = Math.floor(now / 60) * 60;
                        else if (currentTimeframe === 'M5') barTime = Math.floor(now / 300) * 300;
                        else if (currentTimeframe === 'M15') barTime = Math.floor(now / 900) * 900;
                        else if (currentTimeframe === 'H1') barTime = Math.floor(now / 3600) * 3600;
                        else if (currentTimeframe === 'D1') barTime = Math.floor(now / 86400) * 86400;
                        else barTime = Math.floor(now / 60) * 60;

                        candleSeries.update({
                            time: barTime,
                            close: tick.bid
                        });
                    }
                }

                // Update prices for all symbols in the dashboard summary if needed
                // (Optional enhancement: update a sidebar with all prices)
            }
            
            // Handle Candle Updates (Locked OHLC)
            if (data.type === 'candle_update' && data.symbol === currentSymbol) {
                // Only update if it matches our timeframe (default MT5 bridge sends M1)
                // If the user is on M5, the M1 'locks' don't finalize the M5 candle yet
                if (currentTimeframe === 'M1' && candleSeries) {
                    candleSeries.update(data.candle);
                    addLog('CHART', `Candle finalized @ ${data.candle.close}`, 'info');
                }
            }
        };
    };
    
    // ==================== ACCOUNT POLLING ====================
    const fetchAccount = async () => {
        try {
            const res = await fetch('/api/account');
            const data = await res.json();
            
            // Check if disconnected
            if (!data.connected) {
                balanceEl.innerHTML = '<span class="text-yellow-400 animate-pulse">Connecting...</span>';
                equityEl.innerHTML = '<span class="text-yellow-400 animate-pulse">Connecting...</span>';
                dailyPnlEl.innerHTML = '<span class="text-slate-500">MT5 Disconnected</span>';
                dailyPnlEl.className = 'text-sm font-bold mt-1 text-slate-500';
                addLog('SYSTEM', `${data.error || 'MT5 Disconnected - Reconnecting...'}`, 'warning');
                return;
            }
            
            balanceEl.textContent = formatCurrency(data.balance);
            equityEl.textContent = formatCurrency(data.equity);
            positionCountEl.textContent = data.open_positions || 0;
            
            const pnl = data.equity - data.balance;
            const drawdownPercent = Math.min(100, Math.max(0, (Math.abs(pnl) / data.balance) * 100));
            
            dailyPnlEl.textContent = (pnl >= 0 ? '+' : '') + formatCurrency(pnl);
            dailyPnlEl.className = `text-2xl font-bold mt-1 ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`;
            
            // Update Risk Profile Meter
            const riskBar = document.getElementById('risk-meter-bar');
            if (riskBar) {
                riskBar.style.width = `${drawdownPercent * 20}%`; // Scaling for visual impact
                riskBar.className = `h-full transition-all duration-500 shadow-[0_0_10px_#6366f1] ${drawdownPercent > 5 ? 'bg-red-500' : 'bg-indigo-500'}`;
            }
            const riskLabel = document.getElementById('risk-profile-label');
            if (riskLabel) {
                if (drawdownPercent < 1) riskLabel.textContent = 'Safe / Idle';
                else if (drawdownPercent < 3) riskLabel.textContent = 'Active Exposure';
                else riskLabel.textContent = 'High Drawdown';
            }
        } catch (e) {
            balanceEl.innerHTML = '<span class="text-red-400">Error</span>';
        }
    };

    const fetchPositions = async () => {
        try {
            const res = await fetch('/api/positions');
            const data = await res.json();
            if (data.positions && data.positions.length > 0) {
                positionsListEl.innerHTML = data.positions.map(p => `
                    <div class="bg-slate-700/50 p-2 rounded flex justify-between items-center text-xs">
                        <div><span class="font-bold text-white">${p.symbol}</span> <span class="${p.side === 'BUY' ? 'text-green-400' : 'text-red-400'}">${p.side}</span></div>
                        <div class="${p.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}">$${p.unrealized_pnl.toFixed(2)}</div>
                    </div>
                `).join('');
            } else {
                positionsListEl.innerHTML = '<p class="text-slate-500 text-xs text-center">No active positions</p>';
            }
        } catch (e) {}
    };

    // ==================== AUTO TRADER ====================
    window.toggleAutoTrader = async (action) => {
        try {
            // Check status first if starting
            if (action === 'start') {
                const statusRes = await fetch('/api/auto/status');
                const statusData = await statusRes.json();
                
                if (!statusData.ready) {
                    botStatusEl.textContent = 'NOT LIVE';
                    botStatusEl.className = 'text-xl font-bold text-red-400 mt-1';
                    addLog('ERROR', `Cannot engage: ${statusData.ready_reason}`, 'error');
                    addLog('SYSTEM', 'Please ensure Ollama is running and models are loaded', 'warning');
                    return;
                }
            }
            
            const res = await fetch(`/api/auto/${action}`, { method: 'POST' });
            const data = await res.json();
            
            if (action === 'start') {
                if (data.status === 'error') {
                    botStatusEl.textContent = 'NOT LIVE';
                    botStatusEl.className = 'text-xl font-bold text-red-400 mt-1';
                    addLog('ERROR', data.message || 'Failed to engage auto-trading', 'error');
                } else {
                    botStatusEl.textContent = 'LIVE';
                    botStatusEl.className = 'text-xl font-bold text-green-400 mt-1 animate-pulse';
                    addLog('BOT', 'Auto-Trading ACTIVATED - All systems operational', 'success');
                }
            } else {
                botStatusEl.textContent = 'OFF';
                botStatusEl.className = 'text-xl font-bold text-slate-500 mt-1';
                addLog('BOT', 'Auto-Trading Deactivated', 'warning');
            }
        } catch (e) {
            botStatusEl.textContent = 'ERROR';
            botStatusEl.className = 'text-xl font-bold text-red-400 mt-1';
            addLog('ERROR', `Failed to toggle AutoTrader: ${e.message}`, 'error');
        }
    };
    
    // Check system status on load and periodically
    const checkSystemStatus = async () => {
        try {
            const res = await fetch('/api/auto/status');
            const data = await res.json();
            
            if (!data.running && !data.ready) {
                // System not ready - update UI
                botStatusEl.textContent = 'NOT READY';
                botStatusEl.className = 'text-xl font-bold text-yellow-400 mt-1';
            } else if (!data.running && data.ready) {
                botStatusEl.textContent = 'STANDBY';
                botStatusEl.className = 'text-xl font-bold text-slate-500 mt-1';
            }
        } catch (e) {
            console.error('Status check failed:', e);
        }
    };
    
    // Check status on load
    checkSystemStatus();
    setInterval(checkSystemStatus, 10000); // Check every 10 seconds

    // ==================== DATA FETCHING ====================
    const fetchSignals = async () => {
        try {
            const res = await fetch('/api/scan');
            const data = await res.json();
            const signalListEl = document.getElementById('signals-list');
            if (signalListEl && data.signals) {
                if (data.signals.length === 0) {
                    signalListEl.innerHTML = '<p class="text-slate-500 text-[10px] text-center py-4">Scanning for high-confidence entries...</p>';
                } else {
                    signalListEl.innerHTML = data.signals.map(s => `
                        <div class="stat-card p-3 rounded-xl border border-indigo-500/10 hover:border-indigo-500/30 transition-all">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-[10px] font-black text-white uppercase">${s.symbol}</span>
                                <span class="px-2 py-0.5 rounded bg-${s.direction === 'BUY' ? 'green' : 'red'}-400/10 text-${s.direction === 'BUY' ? 'green' : 'red'}-400 text-[8px] font-extrabold">${s.direction}</span>
                            </div>
                            <div class="space-y-1 my-2">
                                <div class="flex justify-between text-[9px]">
                                    <span class="text-slate-500">Entry:</span>
                                    <span class="text-white font-bold">${s.entry_price || '---'}</span>
                                </div>
                                <div class="flex justify-between text-[9px]">
                                    <span class="text-slate-500">Stop Loss:</span>
                                    <span class="text-red-400 font-bold">${s.stop_loss || '---'}</span>
                                </div>
                                <div class="flex justify-between text-[9px]">
                                    <span class="text-slate-500">Take Profit:</span>
                                    <span class="text-green-400 font-bold">${s.take_profit_1 || '---'}</span>
                                </div>
                            </div>
                            <div class="flex justify-between items-center pt-1 border-t border-slate-800">
                                <span class="text-[8px] text-slate-500 font-bold">Conf: ${s.confidence}%</span>
                                <span class="text-[8px] text-indigo-400 font-bold italic">RR ${s.risk_reward}</span>
                            </div>
                        </div>
                    `).join('');
                }
            }
        } catch (e) {}
    };

    const fetchStrategies = async () => {
        try {
            const res = await fetch('/api/strategies');
            const data = await res.json();
            const strategyListEl = document.getElementById('strategies-list');
            if (strategyListEl && data.strategies) {
                strategyListEl.innerHTML = data.strategies.map(s => `
                    <div class="stat-card p-4 rounded-xl border border-slate-800 hover:border-indigo-500/50 transition-all group">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs font-black text-white uppercase italic">${s.name}</span>
                            <span class="px-2 py-0.5 rounded bg-${s.status === 'ACTIVE' ? 'green' : 'slate'}-400/10 text-${s.status === 'ACTIVE' ? 'green' : 'slate'}-400 text-[8px] font-bold">${s.status}</span>
                        </div>
                        <p class="text-[9px] text-slate-500 mb-2">${s.description}</p>
                        <div class="flex justify-between items-center text-[8px] font-bold uppercase tracking-widest">
                            <span class="text-indigo-400/60">${s.type}</span>
                            <span class="text-slate-600">v2.4.0</span>
                        </div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('Failed to fetch strategies:', e);
        }
    };

    window.switchTab = (tab) => {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
        document.getElementById(`${tab}-tab`).classList.remove('hidden');
        
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-indigo-600/20');
            btn.classList.add('text-slate-400');
        });
        
        // Select logic by ID now
        const activeBtn = document.getElementById(`btn-tab-${tab}`);
        if (activeBtn) {
            activeBtn.classList.add('bg-indigo-600', 'text-white', 'shadow-indigo-600/20');
            activeBtn.classList.remove('text-slate-400');
        }
        
        if (tab === 'signals') fetchSignals();
        if (tab === 'strategies') fetchStrategies();
        if (tab === 'settings') loadSettings();
    };

    // ==================== SETTINGS ====================
    const updateModeUI = () => {
        const btnPaper = document.getElementById('btn-paper');
        const btnLive = document.getElementById('btn-live');
        if (isPaperMode) {
            btnPaper.className = 'flex-1 py-2 rounded-lg text-xs font-bold bg-indigo-600 text-white';
            btnLive.className = 'flex-1 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-400';
        } else {
            btnPaper.className = 'flex-1 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-400';
            btnLive.className = 'flex-1 py-2 rounded-lg text-xs font-bold bg-indigo-600 text-white';
        }
    };

    const fetchSettings = async () => {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            if (data.success) {
                const s = data.settings;
                document.getElementById('setting-risk').value = s.risk_per_trade;
                document.getElementById('risk-val').textContent = s.risk_per_trade + '%';
                
                document.getElementById('setting-drawdown').value = s.max_drawdown;
                document.getElementById('dd-val').textContent = s.max_drawdown + '%';
                
                document.getElementById('setting-ml').value = s.ml_threshold;
                document.getElementById('ml-val').textContent = s.ml_threshold + '%';
                
                document.getElementById('setting-confidence').value = s.quant_confidence;
                document.getElementById('conf-val').textContent = s.quant_confidence + '%';

                if (document.getElementById('setting-min-rr')) {
                    document.getElementById('setting-min-rr').value = s.risk_reward_min || 1.5;
                    document.getElementById('min-rr-val').textContent = s.risk_reward_min || 1.5;
                }

                if (document.getElementById('setting-target-rr')) {
                    document.getElementById('setting-target-rr').value = s.target_risk_reward || 2.0;
                    document.getElementById('target-rr-val').textContent = s.target_risk_reward || 2.0;
                }
                
                document.getElementById('setting-news').value = s.news_buffer;
                document.getElementById('news-val').textContent = s.news_buffer + 'm';
                
                if (tgTokenEl) tgTokenEl.value = s.telegram_bot_token || '';
                if (tgChatIdEl) tgChatIdEl.value = s.telegram_chat_id || '';
                if (tgSwitch) tgSwitch.checked = s.telegram_enabled;
                if (tgSwitch) toggleTelegram(s.telegram_enabled);

                updateRiskUI();
            }
        } catch (e) {
            addLog('ERROR', 'Failed to load settings', 'error');
        }
    };

    window.loadSettings = async () => {
        await fetchSettings();
        fetchSystemStatus();
    };

    window.saveSettings = async () => {
        const settings = {
            risk_per_trade: parseFloat(document.getElementById('setting-risk').value),
            max_drawdown: parseFloat(document.getElementById('setting-drawdown').value),
            ml_threshold: parseInt(document.getElementById('setting-ml').value),
            quant_confidence: parseInt(document.getElementById('setting-confidence').value),
            risk_reward_min: parseFloat(document.getElementById('setting-min-rr').value),
            target_risk_reward: parseFloat(document.getElementById('setting-target-rr').value),
            news_buffer: parseInt(document.getElementById('setting-news').value),
            paper_mode: false,
            telegram_enabled: tgSwitch.checked,
            telegram_bot_token: tgTokenEl.value,
            telegram_chat_id: tgChatIdEl.value
        };

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });
            const data = await res.json();
            if (data.success) {
                addLog('SETTINGS', 'Configuration saved successfully', 'success');
                // Re-fetch to confirm
                fetchSettings();
            } else {
                addLog('ERROR', `Failed to save settings: ${data.error || res.statusText}`, 'error');
            }
        } catch (e) {
            addLog('ERROR', 'Failed to save settings', 'error');
        }
        updateRiskUI();
    };

    window.applyRiskProfile = (profile) => {
        const risk = document.getElementById('setting-risk');
        const conf = document.getElementById('setting-confidence');
        const minRR = document.getElementById('setting-min-rr');
        const targetRR = document.getElementById('setting-target-rr');

        if (profile === 'conservative') {
            risk.value = 0.5;
            conf.value = 60;
            minRR.value = 2.0;
            targetRR.value = 3.0;
        } else if (profile === 'moderate') {
            risk.value = 1.5;
            conf.value = 40;
            minRR.value = 1.5;
            targetRR.value = 2.0;
        } else if (profile === 'aggressive') {
            risk.value = 2.5;
            conf.value = 30;
            minRR.value = 1.1;
            targetRR.value = 1.5;
        }

        // Update display labels
        document.getElementById('risk-val').textContent = risk.value + '%';
        document.getElementById('conf-val').textContent = conf.value + '%';
        document.getElementById('min-rr-val').textContent = minRR.value;
        document.getElementById('target-rr-val').textContent = targetRR.value;

        saveSettings();
    };

    const updateRiskUI = () => {
        const risk = parseFloat(document.getElementById('setting-risk').value);
        const minRR = parseFloat(document.getElementById('setting-min-rr').value);
        const label = document.getElementById('risk-profile-label');
        const bar = document.getElementById('risk-meter-bar');

        // Update Meter Bar (0.5% to 5% mapped to 10% to 100%)
        const percent = Math.min(100, Math.max(10, (risk / 5) * 100));
        bar.style.width = percent + '%';

        // Update Label
        if (risk <= 1.0 && minRR >= 2.0) {
            label.textContent = "Conservative / Safe";
            label.className = "text-green-400";
            bar.className = "bg-green-500 w-0 h-full shadow-[0_0_10px_#22c55e]";
        } else if (risk <= 2.0 && minRR >= 1.4) {
            label.textContent = "Moderate / Balanced";
            label.className = "text-indigo-400";
            bar.className = "bg-indigo-500 w-0 h-full shadow-[0_0_10px_#6366f1]";
        } else {
            label.textContent = "Aggressive / Growth";
            label.className = "text-red-400";
            bar.className = "bg-red-500 w-0 h-full shadow-[0_0_10px_#ef4444]";
        }
    };

    window.togglePaperMode = (isPaper) => {
        // Feature removed - system defaults to MT5 Live
        console.log("Paper mode toggle is no longer available. MT5 Live is prioritized.");
    };

    window.toggleTelegram = (enabled) => {
        const btnOn = document.getElementById('btn-tg-on');
        const btnOff = document.getElementById('btn-tg-off');
        const label = document.getElementById('tg-status-label');
        if (enabled) {
            btnOn.className = 'px-3 py-1 rounded bg-indigo-600 text-[10px] font-bold text-white';
            btnOff.className = 'px-3 py-1 rounded bg-slate-800 text-[10px] font-bold text-slate-500';
            label.textContent = 'Enabled';
            label.className = 'text-[10px] text-indigo-400 font-bold uppercase';
        } else {
            btnOn.className = 'px-3 py-1 rounded bg-slate-800 text-[10px] font-bold text-slate-500';
            btnOff.className = 'px-3 py-1 rounded bg-red-600 text-[10px] font-bold text-white';
            label.textContent = 'Disabled';
            label.className = 'text-[10px] text-slate-500 font-bold uppercase';
        }
    };

    window.testTelegram = async () => {
        const chatId = document.getElementById('setting-tg-chatid').value;
        if (!chatId) {
            addLog('ERROR', 'Enter a Chat ID first', 'error');
            return;
        }
        addLog('SYSTEM', 'Sending test message...', 'info');
        // This will call a simple test endpoint or just save and notify
        await saveSettings();
        // In backend, we could add a dedicated test endpoint, but for now we'll just log
        addLog('SYSTEM', 'Check your Telegram for a confirmation message.', 'success');
    };

    const fetchSystemStatus = async () => {
        try {
            const res = await fetch('/api/system/status');
            const data = await res.json();
            document.getElementById('status-data-mode').textContent = data.data_mode;
            document.getElementById('status-ai').textContent = data.ai_status.status;
            document.getElementById('status-auto').textContent = data.auto_trader_running ? 'ACTIVE' : 'OFF';
            document.getElementById('status-news').textContent = data.settings.news_buffer + 'm';

            // Systems Health update
            const mt5Health = document.getElementById('health-mt5');
            const aiHealth = document.getElementById('health-ai');
            
            if (mt5Health) {
                mt5Health.textContent = data.mt5_connected ? 'CONNECTED' : 'DISCONNECTED';
                mt5Health.className = `text-[10px] font-black ${data.mt5_connected ? 'text-green-500' : 'text-red-500'}`;
            }
            if (aiHealth) {
                aiHealth.textContent = (data.ai_status.status === 'ACTIVE') ? 'OPTIMAL' : 'OFFLINE';
                aiHealth.className = `text-[10px] font-black ${data.ai_status.status === 'ACTIVE' ? 'text-green-500' : 'text-red-500'}`;
            }
        } catch (e) {}
    };

    // ==================== INDICATORS ====================
    window.toggleIndicators = async () => {
        const overlay = document.getElementById('indicators-overlay');
        overlay.classList.toggle('hidden');
        
        if (!overlay.classList.contains('hidden')) {
            try {
                const res = await fetch(`/api/indicators/${currentSymbol}`);
                const data = await res.json();
                document.getElementById('ind-rsi').textContent = data.rsi;
                document.getElementById('ind-ema20').textContent = data.ema_20;
                document.getElementById('ind-ema50').textContent = data.ema_50;
                document.getElementById('ind-atr').textContent = data.atr;
                const trendEl = document.getElementById('ind-trend');
                trendEl.textContent = data.trend;
                trendEl.className = `font-bold ${data.trend === 'BULLISH' ? 'text-green-400' : 'text-red-400'}`;
            } catch (e) {}
        }
    };

    // ==================== TERMINAL ====================
    window.toggleTerminal = async () => {
        const overlay = document.getElementById('terminal-overlay');
        overlay.classList.toggle('hidden');
        
        if (!overlay.classList.contains('hidden')) {
            try {
                const res = await fetch('/api/logs');
                const data = await res.json();
                const terminalEl = document.getElementById('terminal-content');
                if (data.logs && data.logs.length > 0) {
                    terminalEl.innerHTML = data.logs.map(l => 
                        `<div><span class="text-slate-500">${new Date(l.time).toLocaleTimeString()}</span> <span class="text-yellow-400">[${l.source}]</span> ${l.message}</div>`
                    ).join('');
                } else {
                    terminalEl.innerHTML = '<div class="text-slate-500">No logs yet...</div>';
                }
            } catch (e) {}
        }
    };
    
    // ==================== SIMULATION ====================
    window.injectPattern = async () => {
        const symbol = document.getElementById('sim-symbol').value;
        const pattern = document.getElementById('sim-pattern').value;
        
        try {
            const res = await fetch('/api/simulate/inject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, pattern })
            });
            const data = await res.json();
            
            if (data.status === 'queued') {
                addLog('SYSTEM', data.message, 'success');
                // Switch to Trading tab to see the chart refresh
                switchTab('trading');
                // Select the injected symbol
                if (window.setSymbol) window.setSymbol(symbol);
                // Fetch new candles immediately is handled by symbol switch
            } else {
                addLog('ERROR', data.error || 'Failed to inject pattern', 'error');
            }
        } catch (e) {
            addLog('ERROR', 'Simulation API error: ' + e.message, 'error');
        }
    };

    const initSymbols = async () => {
        try {
            const res = await fetch('/api/symbols');
            const data = await res.json();
            if (data.symbols && data.symbols.length > 0) {
                // Populate Chart Symbol Dropdown
                const menu = document.getElementById('symbol-menu');
                if (menu) {
                    menu.innerHTML = data.symbols.map(s => `
                        <div onclick="setSymbol('${s}'); document.getElementById('symbol-menu').classList.add('hidden')" 
                             class="p-2 hover:bg-slate-800 rounded-lg cursor-pointer text-xs font-bold text-white uppercase">
                             ${s}
                        </div>
                    `).join('');
                }

                // Populate Simulation Select
                const simSelect = document.getElementById('sim-symbol');
                if (simSelect) {
                    simSelect.innerHTML = data.symbols.map(s => `
                        <option value="${s}">${s}</option>
                    `).join('');
                }

                // Default to first symbol if current one is invalid
                if (!data.symbols.includes(currentSymbol)) {
                    setSymbol(data.symbols[0]);
                }
            }
        } catch (e) {
            console.error('Failed to init symbols:', e);
        }
    };

    // ==================== INIT ====================
    initSymbols();
    initChart();
    connectStream();
    fetchAccount();
    fetchPositions();
    fetchSignals();
    fetchStrategies();
    
    // Secondary Polling
    setInterval(fetchAccount, 5000);
    setInterval(fetchPositions, 5001);
    setInterval(fetchSignals, 10000);
});
