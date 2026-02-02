"""
BACKTESTING ENGINE
- Historical data replay
- Strategy performance metrics
- Sharpe Ratio, Sortino Ratio, Max Drawdown
- Trade-by-trade analysis
- Monte Carlo simulation
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    direction: TradeDirection
    entry_price: float
    exit_price: Optional[float]
    size: float
    stop_loss: float
    take_profit: float
    pnl: float = 0.0
    pnl_pips: float = 0.0
    status: str = "OPEN"
    
@dataclass
class BacktestResult:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

class BacktestEngine:
    """
    Professional backtesting engine for strategy validation.
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.current_position: Optional[Trade] = None
    
    def reset(self):
        """Reset backtester state"""
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = [self.initial_capital]
        self.current_position = None
    
    def run_backtest(self, df: pd.DataFrame, strategy_func, risk_per_trade: float = 0.02) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            df: DataFrame with OHLC data
            strategy_func: Function that takes df and returns (direction, entry, sl, tp) or None
            risk_per_trade: Risk per trade as decimal (0.02 = 2%)
        """
        self.reset()
        
        for i in range(100, len(df)):
            current_bar = df.iloc[i]
            historical_df = df.iloc[:i+1]
            
            # Check if we have an open position
            if self.current_position:
                self._check_exit(current_bar)
            else:
                # Check for new signal
                signal = strategy_func(historical_df)
                if signal:
                    direction, entry, sl, tp = signal
                    self._open_trade(
                        current_bar['time'] if 'time' in current_bar else datetime.now(),
                        direction,
                        entry,
                        sl,
                        tp,
                        risk_per_trade
                    )
            
            # Update equity curve
            current_equity = self.capital
            if self.current_position:
                unrealized = self._calculate_unrealized_pnl(current_bar['close'])
                current_equity += unrealized
            self.equity_curve.append(current_equity)
        
        # Close any remaining position
        if self.current_position:
            self.current_position.exit_price = df.iloc[-1]['close']
            self.current_position.exit_time = df.iloc[-1]['time'] if 'time' in df.iloc[-1] else datetime.now()
            self._close_position()
        
        return self._calculate_results()
    
    def _open_trade(self, time, direction: str, entry: float, sl: float, tp: float, risk_pct: float):
        """Open a new trade"""
        risk_amount = self.capital * risk_pct
        risk_per_unit = abs(entry - sl)
        
        if risk_per_unit == 0:
            return
        
        size = risk_amount / risk_per_unit
        
        self.current_position = Trade(
            entry_time=time if isinstance(time, datetime) else datetime.fromtimestamp(time),
            exit_time=None,
            direction=TradeDirection.LONG if direction == "BUY" else TradeDirection.SHORT,
            entry_price=entry,
            exit_price=None,
            size=size,
            stop_loss=sl,
            take_profit=tp,
            status="OPEN"
        )
    
    def _check_exit(self, bar):
        """Check if position should be closed"""
        if not self.current_position:
            return
        
        pos = self.current_position
        
        if pos.direction == TradeDirection.LONG:
            # Check stop loss
            if bar['low'] <= pos.stop_loss:
                pos.exit_price = pos.stop_loss
                self._close_position(bar)
                return
            # Check take profit
            if bar['high'] >= pos.take_profit:
                pos.exit_price = pos.take_profit
                self._close_position(bar)
                return
        else:  # SHORT
            # Check stop loss
            if bar['high'] >= pos.stop_loss:
                pos.exit_price = pos.stop_loss
                self._close_position(bar)
                return
            # Check take profit
            if bar['low'] <= pos.take_profit:
                pos.exit_price = pos.take_profit
                self._close_position(bar)
                return
    
    def _close_position(self, bar=None):
        """Close current position"""
        if not self.current_position:
            return
        
        pos = self.current_position
        
        if bar:
            pos.exit_time = bar['time'] if 'time' in bar else datetime.now()
        
        # Calculate PnL
        if pos.direction == TradeDirection.LONG:
            pos.pnl = (pos.exit_price - pos.entry_price) * pos.size
        else:
            pos.pnl = (pos.entry_price - pos.exit_price) * pos.size
        
        pos.pnl_pips = abs(pos.exit_price - pos.entry_price) * 10000  # For forex
        pos.status = "CLOSED"
        
        self.capital += pos.pnl
        self.trades.append(pos)
        self.current_position = None
    
    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL"""
        if not self.current_position:
            return 0.0
        
        pos = self.current_position
        if pos.direction == TradeDirection.LONG:
            return (current_price - pos.entry_price) * pos.size
        else:
            return (pos.entry_price - current_price) * pos.size
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate comprehensive backtest results"""
        if not self.trades:
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, total_pnl=0, max_drawdown=0, max_drawdown_percent=0,
                sharpe_ratio=0, sortino_ratio=0, profit_factor=0,
                avg_win=0, avg_loss=0, largest_win=0, largest_loss=0,
                avg_trade_duration=0, trades=[], equity_curve=self.equity_curve
            )
        
        pnls = [t.pnl for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        # Max Drawdown
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        max_dd_pct = np.max(drawdowns) * 100
        max_dd = np.max(running_max - equity)
        
        # Returns for Sharpe/Sortino
        returns = np.diff(equity) / equity[:-1]
        
        # Sharpe Ratio (annualized, assuming daily)
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Sortino Ratio
        downside_returns = returns[returns < 0]
        sortino = np.mean(returns) / np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 and np.std(downside_returns) > 0 else 0
        
        # Profit Factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return BacktestResult(
            total_trades=len(self.trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / len(self.trades) * 100 if self.trades else 0,
            total_pnl=sum(pnls),
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            profit_factor=profit_factor,
            avg_win=np.mean(wins) if wins else 0,
            avg_loss=np.mean(losses) if losses else 0,
            largest_win=max(wins) if wins else 0,
            largest_loss=min(losses) if losses else 0,
            avg_trade_duration=0,  # TODO: Calculate from exit_time - entry_time
            trades=self.trades,
            equity_curve=self.equity_curve
        )

# Singleton
backtest_engine = BacktestEngine()
