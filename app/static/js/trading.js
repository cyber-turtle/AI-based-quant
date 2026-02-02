// Trading Dashboard Controller
document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const balanceEl = document.getElementById('balance');
    const equityEl = document.getElementById('equity');
    const dailyPnlEl = document.getElementById('daily-pnl');
    const winRateEl = document.getElementById('win-rate');
    const botStatusEl = document.getElementById('bot-status');
    const currentPriceEl = document.getElementById('current-price');
    const priceChangeEl = document.getElementById('price-change');
    const positionsListEl = document.getElementById('positions-list');
    const brainLogEl = document.getElementById('brain-log');
    
    // Signal elements
    const sigDirectionEl = document.getElementById('sig-direction');
    const sigConfidenceEl = document.getElementById('sig-confidence');
    const sigEntryEl = document.getElementById('sig-entry');
    const sigRREl = document.getElementById('sig-rr');
    const sigReasoningEl = document.getElementById('sig-reasoning');
    
    // State
    let currentSymbol = 'EURUSD';
    let lastPrice = null;
    
    // Utility: Format currency
    const formatCurrency = (val) => {
        const num = parseFloat(val);
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num);
    };
    
    // Utility: Format price based on symbol
    const formatPrice = (price, symbol) => {
        const decimals = ['XAUUSD', 'BTCUSD'].includes(symbol) ? 2 : 5;
        return parseFloat(price).toFixed(decimals);
    };
    
    // Add log message
    const addLog = (source, message, type = 'info') => {
        const colors = {
            info: 'text-blue-400',
            success: 'text-green-400',
            warning: 'text-yellow-400',
            error: 'text-red-400',
            brain: 'text-purple-400'
        };
        
        const div = document.createElement('div');
        div.className = 'bg-slate-700/50 p-2 rounded';
        div.innerHTML = `
            <span class="${colors[type]} font-semibold">${source}</span>
            <span class="text-slate-400 ml-2">${message}</span>
        `;
        brainLogEl.insertBefore(div, brainLogEl.firstChild);
        
        while (brainLogEl.children.length > 20) {
            brainLogEl.removeChild(brainLogEl.lastChild);
        }
    };
    
    // Fetch account data
    const fetchAccount = async () => {
        try {
            const res = await fetch('/api/account');
            const data = await res.json();
            
            balanceEl.textContent = formatCurrency(data.balance);
            equityEl.textContent = formatCurrency(data.equity);
            
            const pnl = data.equity - data.balance;
            dailyPnlEl.textContent = (pnl >= 0 ? '+' : '') + formatCurrency(pnl);
            dailyPnlEl.className = `text-2xl font-bold mt-1 ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`;
        } catch (e) {
            console.error('Account fetch error:', e);
        }
    };
    
    // Fetch current tick
    const fetchTick = async () => {
        try {
            const res = await fetch(`/api/tick/${currentSymbol}`);
            const data = await res.json();
            
            // Use bid price if last is 0 (common in forex)
            const displayPrice = data.last > 0 ? data.last : data.bid;
            
            if (displayPrice) {
                const price = formatPrice(displayPrice, currentSymbol);
                currentPriceEl.textContent = price;
                
                if (lastPrice !== null && lastPrice > 0) {
                    const change = displayPrice - lastPrice;
                    const changePercent = (change / lastPrice * 100).toFixed(3);
                    priceChangeEl.textContent = `${change >= 0 ? '+' : ''}${changePercent}%`;
                    priceChangeEl.className = `text-sm ${change >= 0 ? 'text-green-400' : 'text-red-400'}`;
                }
                lastPrice = displayPrice;
            }
        } catch (e) {
            console.error('Tick fetch error:', e);
        }
    };
    
    // Fetch positions
    const fetchPositions = async () => {
        try {
            const res = await fetch('/api/positions');
            const data = await res.json();
            
            if (data.positions.length === 0) {
                positionsListEl.innerHTML = '<p class="text-slate-500 text-sm">No open positions</p>';
            } else {
                positionsListEl.innerHTML = data.positions.map(p => `
                    <div class="bg-slate-700/50 p-2 rounded flex justify-between items-center">
                        <div>
                            <span class="font-semibold text-white">${p.symbol}</span>
                            <span class="ml-2 ${p.side === 'BUY' ? 'text-green-400' : 'text-red-400'}">${p.side}</span>
                        </div>
                        <div class="${p.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${p.unrealized_pnl >= 0 ? '+' : ''}${p.unrealized_pnl.toFixed(2)}
                        </div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('Positions fetch error:', e);
        }
    };
    
    // Fetch signal
    const fetchSignal = async () => {
        try {
            const res = await fetch(`/api/signal/${currentSymbol}`);
            const data = await res.json();
            
            sigDirectionEl.textContent = data.direction || 'NEUTRAL';
            sigDirectionEl.className = `text-lg font-bold ${
                data.direction === 'BUY' ? 'text-green-400' : 
                data.direction === 'SELL' ? 'text-red-400' : 'text-slate-400'
            }`;
            
            if (data.confidence) {
                sigConfidenceEl.textContent = `${data.confidence}%`;
                sigEntryEl.textContent = formatPrice(data.entry, currentSymbol);
                sigRREl.textContent = `1:${data.risk_reward}`;
                
                sigReasoningEl.innerHTML = data.reasoning ? 
                    data.reasoning.map(r => `<p>• ${r}</p>`).join('') : '';
            } else {
                sigConfidenceEl.textContent = '--';
                sigEntryEl.textContent = '--';
                sigRREl.textContent = '--';
                sigReasoningEl.innerHTML = '<p class="text-slate-500">No active signal</p>';
            }
        } catch (e) {
            console.error('Signal fetch error:', e);
        }
    };
    
    // Bot control
    document.getElementById('btn-start').addEventListener('click', async () => {
        const res = await fetch('/api/bot/start', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started') {
            botStatusEl.textContent = 'RUNNING';
            botStatusEl.className = 'text-xl font-bold text-green-400 mt-1';
            addLog('SYSTEM', 'Trading bot started', 'success');
        }
    });
    
    document.getElementById('btn-stop').addEventListener('click', async () => {
        const res = await fetch('/api/bot/stop', { method: 'POST' });
        botStatusEl.textContent = 'STOPPED';
        botStatusEl.className = 'text-xl font-bold text-red-400 mt-1';
        addLog('SYSTEM', 'Trading bot stopped', 'warning');
    });
    
    // Scan button
    document.getElementById('btn-scan').addEventListener('click', async () => {
        addLog('BRAIN', 'Scanning all markets...', 'brain');
        await fetchSignal();
        addLog('BRAIN', `Signal analysis complete for ${currentSymbol}`, 'success');
    });
    
    // Quick trade buttons
    document.getElementById('btn-buy').addEventListener('click', async () => {
        const symbol = document.getElementById('trade-symbol').value;
        const size = parseFloat(document.getElementById('trade-size').value);
        
        addLog('TRADE', `Placing BUY order for ${symbol}...`, 'info');
        
        try {
            const tickRes = await fetch(`/api/tick/${symbol}`);
            const tick = await tickRes.json();
            
            const res = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    side: 'BUY',
                    quantity: size,
                    price: tick.ask,
                    stop_loss: tick.ask * 0.99,
                    take_profit: tick.ask * 1.02
                })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                addLog('TRADE', `BUY order filled @ ${formatPrice(data.order.filled_price, symbol)}`, 'success');
                fetchPositions();
            }
        } catch (e) {
            addLog('TRADE', `Order failed: ${e.message}`, 'error');
        }
    });
    
    document.getElementById('btn-sell').addEventListener('click', async () => {
        const symbol = document.getElementById('trade-symbol').value;
        const size = parseFloat(document.getElementById('trade-size').value);
        
        addLog('TRADE', `Placing SELL order for ${symbol}...`, 'info');
        
        try {
            const tickRes = await fetch(`/api/tick/${symbol}`);
            const tick = await tickRes.json();
            
            const res = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    side: 'SELL',
                    quantity: size,
                    price: tick.bid,
                    stop_loss: tick.bid * 1.01,
                    take_profit: tick.bid * 0.98
                })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                addLog('TRADE', `SELL order filled @ ${formatPrice(data.order.filled_price, symbol)}`, 'success');
                fetchPositions();
            }
        } catch (e) {
            addLog('TRADE', `Order failed: ${e.message}`, 'error');
        }
    });
    
    // Symbol change handler
    const symbolSelect = document.getElementById('symbol-select');
    if (symbolSelect) {
        symbolSelect.addEventListener('change', (e) => {
            currentSymbol = e.target.value;
            lastPrice = null;
            fetchTick();
            fetchSignal();
        });
    }
    
    // Initial fetch
    fetchAccount();
    fetchTick();
    fetchPositions();
    fetchSignal();
    
    // Polling intervals
    setInterval(fetchTick, 1000);      // Every 1 second
    setInterval(fetchAccount, 5000);   // Every 5 seconds
    setInterval(fetchPositions, 5000); // Every 5 seconds
    
    // Bot status polling
    setInterval(async () => {
        try {
            const res = await fetch('/api/bot/status');
            const data = await res.json();
            if (data.running) {
                botStatusEl.textContent = 'RUNNING';
                botStatusEl.className = 'text-xl font-bold text-green-400 mt-1';
            }
        } catch (e) {}
    }, 5000);
});
