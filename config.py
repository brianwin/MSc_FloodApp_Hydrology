import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Defaults for all environments
    SECRET_KEY = 'local_secret_key_will_be_overridden'
    SQLALCHEMY_DATABASE_URI = 'local_db_credentials_will_be_overridden'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 128,          # Default is 5
        "max_overflow": 32,        # Allow up to 10 + 20 = 30 connections
        "pool_timeout": 30,        # Wait time before raising TimeoutError
        "pool_recycle": 1800,      # Avoid stale connections (optional)
    }

class DevelopmentConfig(Config):
    DEBUG = True
    #DEBUG = False


class ProductionConfig(Config):
    SECRET_KEY = os.environ.get('SECRET_KEY')  # fallback not safe in prod
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
