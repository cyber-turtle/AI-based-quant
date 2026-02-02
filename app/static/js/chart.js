// Lightweight Charts Implementation with Symbol/Timeframe Switching
document.addEventListener('DOMContentLoaded', () => {
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer) {
        console.error('Chart container not found');
        return;
    }

    // State
    let currentSymbol = 'EURUSD';
    let currentTimeframe = 'M5';

    // Get dimensions - use fallbacks if container isn't sized yet
    const getChartDimensions = () => {
        const rect = chartContainer.getBoundingClientRect();
        return {
            width: rect.width > 0 ? rect.width : 800,
            height: rect.height > 0 ? rect.height : 400
        };
    };

    const dims = getChartDimensions();
    console.log('Creating chart with dimensions:', dims);

    // Create Chart immediately
    const chart = LightweightCharts.createChart(chartContainer, {
        width: dims.width,
        height: dims.height,
        layout: {
            background: { type: 'solid', color: '#0f172a' },
            textColor: '#94a3b8',
        },
        grid: {
            vertLines: { color: '#1e293b' },
            horzLines: { color: '#1e293b' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: true,
            secondsVisible: false,
        },
        rightPriceScale: {
            borderColor: '#334155',
        },
    });

    // Use v5 API: addSeries with CandlestickSeries type
    const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
    });

    console.log('Chart and candleSeries created');

    // Resize Handler
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartContainer) { return; }
        const newRect = entries[0].contentRect;
        if (newRect.width > 0 && newRect.height > 0) {
            chart.applyOptions({ height: newRect.height, width: newRect.width });
        }
    }).observe(chartContainer);

    // Fetch and Display Data
    function loadChartData(symbol, timeframe) {
        console.log('Loading chart data for', symbol, timeframe);
        fetch(`/api/history/${symbol}/${timeframe}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                console.log('Received data:', data.length, 'candles');
                if (data.error) {
                    console.error('API Error:', data.error);
                    return;
                }
                if (Array.isArray(data) && data.length > 0) {
                    candleSeries.setData(data);
                    chart.timeScale().fitContent();
                    console.log('Chart data set successfully');
                } else {
                    console.warn('No data received or empty array');
                }
            })
            .catch(err => console.error('Fetch error:', err));
    }

    // Initial Load
    loadChartData(currentSymbol, currentTimeframe);

    // Symbol Selector
    const symbolSelect = document.getElementById('symbol-select');
    if (symbolSelect) {
        symbolSelect.addEventListener('change', (e) => {
            currentSymbol = e.target.value;
            loadChartData(currentSymbol, currentTimeframe);
        });
    }

    // Timeframe Buttons
    const tfButtons = document.querySelectorAll('.tf-btn');
    tfButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            tfButtons.forEach(b => b.classList.remove('bg-green-900/40', 'text-green-400', 'border-green-800'));
            tfButtons.forEach(b => b.classList.add('bg-slate-700', 'text-slate-300'));
            btn.classList.remove('bg-slate-700', 'text-slate-300');
            btn.classList.add('bg-green-900/40', 'text-green-400', 'border-green-800');

            currentTimeframe = btn.dataset.tf;
            loadChartData(currentSymbol, currentTimeframe);
        });
    });

    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadChartData(currentSymbol, currentTimeframe);
    }, 30000);
});
