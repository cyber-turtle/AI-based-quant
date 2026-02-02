// Dashboard Controls and Bot Interaction
document.addEventListener('DOMContentLoaded', () => {
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const botStatus = document.getElementById('bot-status');
    const brainLog = document.getElementById('brain-log');

    function addLogMessage(source, message, type = 'info') {
        const colors = {
            'info': 'text-blue-300',
            'success': 'text-green-300',
            'warning': 'text-yellow-300',
            'error': 'text-red-300',
            'brain': 'text-purple-300'
        };
        
        const div = document.createElement('div');
        div.className = 'bg-slate-700/50 p-4 rounded-lg border border-slate-600';
        div.innerHTML = `
            <div class="flex justify-between items-start mb-2">
                <span class="text-xs font-bold ${colors[type] || colors.info}">${source}</span>
                <span class="text-xs text-slate-500">${new Date().toLocaleTimeString()}</span>
            </div>
            <p class="text-sm text-slate-300">${message}</p>
        `;
        brainLog.insertBefore(div, brainLog.firstChild);
        
        // Keep only last 10 messages
        while (brainLog.children.length > 10) {
            brainLog.removeChild(brainLog.lastChild);
        }
    }

    // Start Bot
    if (btnStart) {
        btnStart.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/bot/start', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'started') {
                    botStatus.textContent = 'RUNNING';
                    botStatus.className = 'text-3xl font-bold text-green-400 mt-2';
                    addLogMessage('SYSTEM', 'Bot started. Scanning for opportunities...', 'success');
                } else if (data.status === 'already_running') {
                    addLogMessage('SYSTEM', 'Bot is already running.', 'warning');
                }
            } catch (e) {
                addLogMessage('SYSTEM', 'Failed to start bot: ' + e.message, 'error');
            }
        });
    }

    // Stop Bot
    if (btnStop) {
        btnStop.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/bot/stop', { method: 'POST' });
                const data = await res.json();
                botStatus.textContent = 'STOPPED';
                botStatus.className = 'text-3xl font-bold text-red-400 mt-2';
                addLogMessage('SYSTEM', 'Bot stopped.', 'warning');
            } catch (e) {
                addLogMessage('SYSTEM', 'Failed to stop bot: ' + e.message, 'error');
            }
        });
    }

    // Manual Scan (triggered by clicking the signal card)
    const signalCard = document.querySelector('.group');
    if (signalCard) {
        signalCard.addEventListener('click', async () => {
            addLogMessage('BRAIN', 'Running manual scan...', 'brain');
            try {
                const res = await fetch('/api/brain/scan', { method: 'POST' });
                const data = await res.json();
                
                const signalAction = document.getElementById('signal-action');
                const signalConfidence = document.getElementById('signal-confidence');
                
                if (data.status === 'found') {
                    signalAction.textContent = data.setup.action;
                    signalAction.className = data.setup.action === 'BUY' 
                        ? 'text-3xl font-bold text-green-400 mt-2'
                        : 'text-3xl font-bold text-red-400 mt-2';
                    signalConfidence.textContent = data.setup.reason;
                    signalConfidence.className = 'text-green-400 text-sm mt-1';
                    addLogMessage('BRAIN', `Signal: ${data.setup.action} ${data.setup.symbol} - ${data.setup.reason}`, 'success');
                } else {
                    signalAction.textContent = 'WAITING';
                    signalAction.className = 'text-3xl font-bold text-yellow-400 mt-2';
                    signalConfidence.textContent = data.message || 'No valid setup';
                    addLogMessage('BRAIN', data.message || 'No setups found.', 'info');
                }
            } catch (e) {
                addLogMessage('BRAIN', 'Scan error: ' + e.message, 'error');
            }
        });
    }

    // Poll bot status every 10 seconds
    setInterval(async () => {
        try {
            const res = await fetch('/api/bot/status');
            const data = await res.json();
            if (data.running) {
                botStatus.textContent = 'RUNNING';
                botStatus.className = 'text-3xl font-bold text-green-400 mt-2';
            } else {
                botStatus.textContent = 'IDLE';
                botStatus.className = 'text-3xl font-bold text-yellow-400 mt-2';
            }
        } catch (e) {}
    }, 10000);
});
