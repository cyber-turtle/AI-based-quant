from app import create_app, db
from app.models import Strategy, User

app = create_app()

def seed_strategies():
    with app.app_context():
        # Get default user or create one
        user_id = 1 # Assuming admin is ID 1
        
        # Strategies to Seed (Ported from Legacy)
        strategies = [
            {
                "name": "EMA_CROSS",
                "type": "TREND",
                "parameters": '{"fast": 20, "slow": 50}',
                "user_id": user_id
            },
            {
                "name": "RSI_REVERSAL",
                "type": "REVERSAL",
                "parameters": '{"period": 14, "overbought": 70, "oversold": 30}',
                "user_id": user_id
            },
            {
                "name": "BREAKOUT_ATR",
                "type": "BREAKOUT",
                "parameters": '{"atr_period": 14, "multiplier": 1.5}',
                "user_id": user_id
            },
            {
                "name": "MACD_DIV",
                "type": "REVERSAL",
                "parameters": '{"fast": 12, "slow": 26, "signal": 9}',
                "user_id": user_id
            },
            {
                "name": "BOL_BAND_SQUEEZE",
                "type": "VOLATILITY",
                "parameters": '{"period": 20, "dev": 2}',
                "user_id": user_id
            },
             {
                "name": "VWAP_MEAN_REVERT",
                "type": "REVERSAL",
                "parameters": '{"deviation": 2.0}',
                "user_id": user_id
            }
        ]
        
        for data in strategies:
            exists = Strategy.query.filter_by(name=data['name']).first()
            if not exists:
                strat = Strategy(**data)
                db.session.add(strat)
                print(f"Seeded {data['name']}")
            else:
                print(f"{data['name']} already exists")
                
        db.session.commit()
        print("Seeding Complete!")

if __name__ == '__main__':
    seed_strategies()
