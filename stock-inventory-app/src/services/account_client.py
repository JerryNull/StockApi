from configparser import ConfigParser
import requests

class AccountClient:
    def __init__(self, config_path):
        self.config = ConfigParser()
        self.config.read(config_path)
        self.base_url = self.config.get('API', 'base_url')
        self.api_key = self.config.get('API', 'api_key')

    def get_inventory_details(self):
        url = f"{self.base_url}/account/inventory"
        headers = {
            'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def get_account_balance(self):
        url = f"{self.base_url}/account/balance"
        headers = {
            'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()