from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Preferences
    preferences = db.Column(db.Text, nullable=True) 

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class RiskSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_drawdown_percent = db.Column(db.Float, default=10.0)
    position_size_percent = db.Column(db.Float, default=5.0)
    max_leverage = db.Column(db.Float, default=10.0)
    daily_loss_limit_percent = db.Column(db.Float, default=5.0)
    require_stop_loss = db.Column(db.Boolean, default=True)
    max_open_positions = db.Column(db.Integer, default=3)

class AccountSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    equity = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)
    daily_pnl = db.Column(db.Float, default=0.0)
    drawdown_percent = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trading_enabled = db.Column(db.Boolean, default=True)
    pause_reason = db.Column(db.String(255))
    mt5_account = db.Column(db.String(50))
    mt5_password = db.Column(db.String(100))
    mt5_server = db.Column(db.String(50))
    telegram_chat_id = db.Column(db.String(50))
    telegram_enabled = db.Column(db.Boolean, default=True)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    event_data = db.Column(db.Text) # JSON
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Strategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    parameters = db.Column(db.Text, nullable=False) # JSON
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('strategies', lazy=True))
