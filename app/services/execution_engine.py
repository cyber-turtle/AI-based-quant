"""
EXECUTION ENGINE
- Order management
- Position tracking  
- Paper trading simulation
- Real MT5 order execution
"""
import MetaTrader5 as mt5
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET_BUY = "MARKET_BUY"
    MARKET_SELL = "MARKET_SELL"
    LIMIT_BUY = "LIMIT_BUY"
    LIMIT_SELL = "LIMIT_SELL"
    STOP_BUY = "STOP_BUY"
    STOP_SELL = "STOP_SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Order:
    id: str
    symbol: str
    order_type: OrderType
    side: str  # BUY or SELL
    quantity: float
    price: float
    stop_loss: float
    take_profit: float
    status: OrderStatus
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    created_at: datetime = None
    filled_at: Optional[datetime] = None
    pnl: float = 0.0
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'order_type': self.order_type.value,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'status': self.status.value,
            'filled_price': self.filled_price,
            'pnl': self.pnl,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    realized_pnl: float
    opened_at: datetime
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl
        }

class ExecutionEngine:
    """
    Handles order execution and position management.
    Supports both paper trading and live MT5 execution.
    """
    
    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Order] = []
        self.order_counter = 0
        
        # Paper trading account
        self.paper_balance = 10000.0
        self.paper_equity = 10000.0
        
        # MT5 connection
        self.mt5_connected = False
        if not paper_trading:
            self._init_mt5()
    
    def _init_mt5(self):
        """Initialize MT5 for live trading"""
        try:
            if mt5.initialize():
                self.mt5_connected = True
                logger.info("MT5 connected for live trading")
        except Exception as e:
            logger.warning(f"MT5 init failed: {e}")
            self.mt5_connected = False
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self.order_counter += 1
        return f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.order_counter}"
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        order_type: OrderType = OrderType.MARKET_BUY
    ) -> Order:
        """
        Place a new order.
        Returns the created order object.
        """
        order_id = self._generate_order_id()
        
        order = Order(
            id=order_id,
            symbol=symbol,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=OrderStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.orders[order_id] = order
        
        if self.paper_trading:
            self._execute_paper_order(order)
        else:
            self._execute_mt5_order(order)
        
        return order
    
    def _execute_paper_order(self, order: Order):
        """Execute order in paper trading mode"""
        # Simulate fill with slight slippage
        slippage = order.price * 0.0001 * np.random.choice([-1, 1])
        fill_price = order.price + slippage
        
        order.status = OrderStatus.FILLED
        order.filled_price = fill_price
        order.filled_quantity = order.quantity
        order.filled_at = datetime.now()
        
        # Create or update position
        if order.symbol in self.positions:
            # Add to existing position
            pos = self.positions[order.symbol]
            pos.quantity += order.quantity
            pos.entry_price = (pos.entry_price + fill_price) / 2  # Average
        else:
            # New position
            self.positions[order.symbol] = Position(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                entry_price=fill_price,
                current_price=fill_price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                opened_at=datetime.now()
            )
        
        self.trade_history.append(order)
        logger.info(f"Paper order filled: {order.id} @ {fill_price}")
    
    def _execute_mt5_order(self, order: Order):
        """Execute order on MT5"""
        if not self.mt5_connected:
            order.status = OrderStatus.REJECTED
            logger.error("MT5 not connected")
            return
        
        try:
            # Build MT5 order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": order.symbol,
                "volume": order.quantity,
                "type": mt5.ORDER_TYPE_BUY if order.side == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": order.price,
                "sl": order.stop_loss,
                "tp": order.take_profit,
                "deviation": 20,
                "magic": 234000,
                "comment": "Cortex Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                order.status = OrderStatus.FILLED
                order.filled_price = result.price
                order.filled_quantity = order.quantity
                order.filled_at = datetime.now()
                logger.info(f"MT5 order filled: {order.id}")
            else:
                order.status = OrderStatus.REJECTED
                logger.error(f"MT5 order rejected: {result.comment}")
                
        except Exception as e:
            order.status = OrderStatus.REJECTED
            logger.error(f"MT5 order error: {e}")
    
    def close_position(self, symbol: str, current_price: float) -> Optional[float]:
        """Close a position and return realized PnL"""
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        
        # Calculate PnL
        if pos.side == "BUY":
            pnl = (current_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - current_price) * pos.quantity
        
        # Update paper balance
        if self.paper_trading:
            self.paper_balance += pnl
            self.paper_equity = self.paper_balance
        
        # Remove position
        del self.positions[symbol]
        
        logger.info(f"Position closed: {symbol}, PnL: {pnl:.2f}")
        return pnl
    
    def update_positions(self, prices: Dict[str, float]):
        """Update all positions with current prices"""
        total_unrealized = 0.0
        
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]
                
                if pos.side == "BUY":
                    pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.quantity
                
                total_unrealized += pos.unrealized_pnl
                
                # Check stop loss / take profit
                if pos.side == "BUY":
                    if pos.current_price <= pos.stop_loss or pos.current_price >= pos.take_profit:
                        self.close_position(symbol, pos.current_price)
                else:
                    if pos.current_price >= pos.stop_loss or pos.current_price <= pos.take_profit:
                        self.close_position(symbol, pos.current_price)
        
        self.paper_equity = self.paper_balance + total_unrealized
    
    def get_account_summary(self) -> Dict:
        """Get account summary"""
        return {
            'balance': round(self.paper_balance, 2),
            'equity': round(self.paper_equity, 2),
            'unrealized_pnl': round(self.paper_equity - self.paper_balance, 2),
            'open_positions': len(self.positions),
            'total_trades': len(self.trade_history),
            'mode': 'PAPER' if self.paper_trading else 'LIVE'
        }
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        return [order.to_dict() for order in self.trade_history[-50:]]

# Singleton
execution_engine = ExecutionEngine(paper_trading=True)
