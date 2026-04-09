from tkinter import Tk, Frame, Label, Button, ttk
from services.account_client import AccountClient

class MainWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("Stock Inventory Management")
        self.master.geometry("800x600")

        self.frame = Frame(self.master)
        self.frame.pack(pady=10)

        self.label = Label(self.frame, text="Stock Inventory", font=("Arial", 16))
        self.label.pack()

        self.tree = ttk.Treeview(self.master, columns=('Symbol', 'Quantity', 'Average Cost'), show='headings')
        self.tree.heading('Symbol', text='Stock Symbol')
        self.tree.heading('Quantity', text='Quantity')
        self.tree.heading('Average Cost', text='Average Cost')

        self.tree.pack(fill='both', expand=True, padx=10, pady=10)

        self.refresh_button = Button(self.frame, text="Refresh Inventory", command=self.refresh_inventory)
        self.refresh_button.pack(pady=5)

        self.account_client = AccountClient()

    def refresh_inventory(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        inventory_data = self.account_client.get_inventory()
        for stock in inventory_data:
            self.tree.insert('', 'end', values=(stock.symbol, stock.quantity, stock.average_cost))

if __name__ == "__main__":
    root = Tk()
    app = MainWindow(root)
    root.mainloop()