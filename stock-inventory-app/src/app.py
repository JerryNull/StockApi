import os
from configparser import ConfigParser
from flask import Flask, render_template, jsonify
from services.account_client import AccountClient
from services.sector_service import SectorService
from esun_marketdata import EsunMarketdata

# ── 初始化玉山 SDK ──────────────────────────────────────────────
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config.simulation.ini')
config = ConfigParser()
config.read(config_path)

marketdata_sdk = EsunMarketdata(config)
marketdata_sdk.login()
rest_stock = marketdata_sdk.rest_client.stock

# ── Flask 應用 ──────────────────────────────────────────────────
app = Flask(__name__)
account_client = AccountClient()
sector_service = SectorService(rest_stock)


# ── 既有路由 ─────────────────────────────────────────────────────
@app.route('/')
def index():
    inventory_details = account_client.get_inventory_details()
    return render_template('inventory_view.html', inventory=inventory_details)


# ── 產業 Dashboard 路由 ──────────────────────────────────────────
@app.route('/sector')
def sector_dashboard():
    return render_template('sector_dashboard.html')


@app.route('/api/sector/summaries')
def sector_summaries():
    data = sector_service.get_sector_summaries()
    return jsonify(data)


@app.route('/api/sector/stocks/<industry_code>')
def sector_stocks(industry_code):
    data = sector_service.get_stocks_in_sector(industry_code)
    return jsonify(data)


if __name__ == '__main__':
    app.run(debug=True)
