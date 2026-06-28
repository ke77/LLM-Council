import os
from flask import Flask
from dotenv import load_dotenv

from config import config_by_name

def create_app():
     load_dotenv()

     app = Flask(__name__)
     
     env_name = os.environ.get("FLASK_ENV", "development")
     app.config.from_object(config_by_name[env_name])

     from app.routes.pages import pages_bp
     from app.routes.council import council_bp

     app.register_blueprint(pages_bp)
     app.register_blueprint(council_bp)

     return app