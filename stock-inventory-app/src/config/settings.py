from configparser import ConfigParser
import os

config = ConfigParser()

# Load configuration from the simulation ini file
config_path = os.path.join(os.path.dirname(__file__), 'config.simulation.ini')
config.read(config_path)

# Application settings
API_KEY = config.get('API', 'key', fallback='your_api_key_here')
API_SECRET = config.get('API', 'secret', fallback='your_api_secret_here')
API_ENDPOINT = config.get('API', 'endpoint', fallback='https://api.example.com')

# Inventory settings
INVENTORY_LIMIT = config.getint('Inventory', 'limit', fallback=100)
CURRENCY = config.get('Inventory', 'currency', fallback='USD')

# Logging settings
LOG_LEVEL = config.get('Logging', 'level', fallback='INFO')
LOG_FILE = config.get('Logging', 'file', fallback='app.log')