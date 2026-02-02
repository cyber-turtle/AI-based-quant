from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from .config import Config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.routes.main import main
    from app.routes.auth import auth
    from app.routes.settings import settings
    from app.routes.api import api
    from app.routes.stream import stream_bp
    
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(settings, url_prefix='/settings')
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(stream_bp)

    return app
