from dataclasses import dataclass

@dataclass
class InventoryItem:
    symbol: str
    quantity: int
    average_cost: float

class Inventory:
    def __init__(self):
        self.items = {}

    def add_item(self, symbol: str, quantity: int, average_cost: float):
        if symbol in self.items:
            existing_item = self.items[symbol]
            existing_item.quantity += quantity
            existing_item.average_cost = (existing_item.average_cost + average_cost) / 2
        else:
            self.items[symbol] = InventoryItem(symbol, quantity, average_cost)

    def remove_item(self, symbol: str, quantity: int):
        if symbol in self.items:
            existing_item = self.items[symbol]
            if existing_item.quantity >= quantity:
                existing_item.quantity -= quantity
                if existing_item.quantity == 0:
                    del self.items[symbol]
            else:
                raise ValueError("Not enough quantity to remove")

    def get_inventory(self):
        return {symbol: item for symbol, item in self.items.items()}

    def clear_inventory(self):
        self.items.clear()