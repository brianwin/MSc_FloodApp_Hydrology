import os
from app import create_app
from config import DevelopmentConfig, ProductionConfig

env = os.getenv('FLASK_ENV', 'development')

config_name = os.getenv('FLASK_ENV', 'development')
config_map = {
    'development': 'config.DevelopmentConfig',
    'production':  'config.ProductionConfig',
    'testing':     'config.TestingConfig',
}
app = create_app(config_map[config_name])

if __name__ == '__main__':
    app.run(debug=True)