import os

class Config: 
     """Base configuration shared by every environment."""

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-for-production")

DEBUG = False


class DevelopmentConfig(Config):
    """Used when you run this locally while building."""
    DEBUG = True
 
 
class ProductionConfig(Config):
    """Used when this is deployed for real (Render, Railway, etc.)."""
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}