from configparser import ConfigParser
import requests

class MarketDataClient:
    def __init__(self, config_path):
        self.config = ConfigParser()
        self.config.read(config_path)
        self.base_url = self.config.get('API', 'base_url')
        self.api_key = self.config.get('API', 'api_key')

    def fetch_stock_price(self, symbol):
        url = f"{self.base_url}/stock/{symbol}/quote"
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def fetch_market_data(self, symbols):
        prices = {}
        for symbol in symbols:
            try:
                prices[symbol] = self.fetch_stock_price(symbol)
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
        return prices

    def fetch_historical_data(self, symbol, start_date, end_date):
        url = f"{self.base_url}/stock/{symbol}/chart"
        params = {
            'start': start_date,
            'end': end_date
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()