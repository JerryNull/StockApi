from flask import Flask, render_template
from services.account_client import AccountClient

app = Flask(__name__)
account_client = AccountClient()

@app.route('/')
def index():
    inventory_details = account_client.get_inventory_details()
    return render_template('inventory_view.html', inventory=inventory_details)

if __name__ == '__main__':
    app.run(debug=True)