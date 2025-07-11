# models/sale_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3

class Sale(BaseModel):
    _table_name = "sales"
    _fields = [
        "sale_date", "customer_id", "total_amount", "discount_applied",
        "payment_method", "user_id", "status", "closed_by_user_id", "is_quote"
    ]

    def __init__(self, id=None, sale_date=None, customer_id=None, total_amount=0.0,
                 discount_applied=0.0, payment_method=None, user_id=None,
                 status="PENDENTE", closed_by_user_id=None, is_quote=False):
        super().__init__(id)
        self.sale_date = sale_date
        self.customer_id = customer_id
        self.total_amount = total_amount
        self.discount_applied = discount_applied
        self.payment_method = payment_method
        self.user_id = user_id
        self.status = status # e.g., 'ORÇAMENTO', 'PENDENTE PAGAMENTO', 'PAGA', 'CANCELADA'
        self.closed_by_user_id = closed_by_user_id
        self.is_quote = is_quote # True if it's a quote, False if it's a sale

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                discount_applied REAL DEFAULT 0.0,
                payment_method TEXT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'PENDENTE',
                closed_by_user_id INTEGER,
                is_quote BOOLEAN DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (closed_by_user_id) REFERENCES users(id)
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON {cls._table_name} (customer_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_user_id ON {cls._table_name} (user_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_date ON {cls._table_name} (sale_date DESC)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_status ON {cls._table_name} (status COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sales_is_quote ON {cls._table_name} (is_quote)")
        conn.commit()
        conn.close()

class SaleItem(BaseModel):
    _table_name = "sale_items"
    _fields = ["sale_id", "part_id", "quantity", "unit_price", "subtotal"]

    def __init__(self, id=None, sale_id=None, part_id=None, quantity=0, unit_price=0.0, subtotal=0.0):
        super().__init__(id)
        self.sale_id = sale_id
        self.part_id = part_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.subtotal = subtotal

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                part_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON {cls._table_name} (sale_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_sale_items_part_id ON {cls._table_name} (part_id)")
        conn.commit()
        conn.close()

