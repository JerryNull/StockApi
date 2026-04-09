# Stock Inventory App

## Overview
The Stock Inventory App is a Python application designed to manage and display stock inventory details. It interacts with market data and account APIs to provide real-time information about stock holdings and prices.

## Project Structure
```
stock-inventory-app
├── src
│   ├── app.py                # Main entry point of the application
│   ├── ui
│   │   ├── main_window.py    # Implementation of the main application window
│   │   └── inventory_view.py  # Displays inventory details
│   ├── services
│   │   ├── marketdata_client.py # Handles interactions with the market data API
│   │   └── account_client.py  # Manages account-related operations
│   ├── models
│   │   └── inventory.py       # Defines the inventory model
│   ├── utils
│   │   └── logging.py         # Provides logging utilities
│   └── config
│       └── settings.py        # Configuration settings for the application
├── config.simulation.ini      # Configuration file for simulation settings
├── requirements.txt           # Lists dependencies required for the project
└── README.md                  # Documentation for the project
```

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd stock-inventory-app
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the application by editing the `config.simulation.ini` file as needed.

## Usage
To run the application, execute the following command:
```
python src/app.py
```

## Features
- Real-time stock price updates
- Inventory management for stock holdings
- User-friendly interface for viewing inventory details

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.