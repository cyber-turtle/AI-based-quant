import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-prod'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///brain.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Intelligent Trading Bot Config
    MT5_ACCOUNT = os.environ.get('MT5_ACCOUNT')
    MT5_PASSWORD = os.environ.get('MT5_PASSWORD')
    MT5_SERVER = os.environ.get('MT5_SERVER')
    
    # Feature Flags
    PAPER_TRADING = True
