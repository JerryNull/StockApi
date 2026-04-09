from tkinter import Frame, Label, Treeview, Scrollbar, ttk
from services.account_client import AccountClient
from models.inventory import Inventory

class InventoryView(Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        self.account_client = AccountClient()
        self.load_inventory()

    def create_widgets(self):
        self.label = Label(self, text="Stock Inventory", font=("Arial", 16))
        self.label.pack(pady=10)

        self.tree = Treeview(self, columns=('Symbol', 'Quantity', 'Average Cost'), show='headings')
        self.tree.heading('Symbol', text='Stock Symbol')
        self.tree.heading('Quantity', text='Quantity')
        self.tree.heading('Average Cost', text='Average Cost')

        self.scrollbar = Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

    def load_inventory(self):
        inventory_data = self.account_client.get_inventory()
        for item in inventory_data:
            inventory_item = Inventory(**item)
            self.tree.insert('', 'end', values=(inventory_item.symbol, inventory_item.quantity, inventory_item.average_cost))