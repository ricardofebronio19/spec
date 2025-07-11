# models/service_order_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3
from datetime import datetime

class ServiceOrder(BaseModel):
    _table_name = "service_orders"
    _fields = [
        "order_date", "customer_id", "vehicle_make", "vehicle_model",
        "vehicle_year", "vehicle_plate", "description", "status",
        "total_amount", "labor_cost", "parts_cost", "assigned_user_id",
        "start_date", "end_date", "payment_status"
    ]

    def __init__(self, id=None, order_date=None, customer_id=None,\
                 vehicle_make=None, vehicle_model=None, vehicle_year=None,\
                 vehicle_plate=None, description=None, status="Pendente",\
                 total_amount=0.0, labor_cost=0.0, parts_cost=0.0, assigned_user_id=None,\
                 start_date=None, end_date=None, payment_status="Pendente"):
        super().__init__(id)
        self.order_date = order_date if order_date else datetime.now().isoformat()
        self.customer_id = customer_id
        self.vehicle_make = vehicle_make
        self.vehicle_model = vehicle_model
        self.vehicle_year = vehicle_year
        self.vehicle_plate = vehicle_plate
        self.description = description
        self.status = status
        self.total_amount = total_amount
        self.labor_cost = labor_cost
        self.parts_cost = parts_cost
        self.assigned_user_id = assigned_user_id
        self.start_date = start_date
        self.end_date = end_date
        self.payment_status = payment_status

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_date TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                vehicle_make TEXT,
                vehicle_model TEXT,
                vehicle_year TEXT,
                vehicle_plate TEXT,
                description TEXT,
                status TEXT NOT NULL,
                total_amount REAL NOT NULL,
                labor_cost REAL DEFAULT 0.0,
                parts_cost REAL DEFAULT 0.0,
                assigned_user_id INTEGER,
                start_date TEXT,
                end_date TEXT,
                payment_status TEXT DEFAULT 'Pendente',
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (assigned_user_id) REFERENCES users(id)
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_customer_id ON {cls._table_name} (customer_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_assigned_user_id ON {cls._table_name} (assigned_user_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_date ON {cls._table_name} (order_date DESC)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_status ON {cls._table_name} (status COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_payment_status ON {cls._table_name} (payment_status COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_orders_vehicle_plate ON {cls._table_name} (vehicle_plate COLLATE NOCASE)")
        conn.commit()
        conn.close()

class ServiceOrderItem(BaseModel):
    _table_name = "service_order_items"
    _fields = ["service_order_id", "part_id", "quantity", "unit_price", "subtotal", "is_service", "description"]

    def __init__(self, id=None, service_order_id=None, part_id=None, quantity=0, unit_price=0.0, subtotal=0.0, is_service=0, description=None):
        super().__init__(id)
        self.service_order_id = service_order_id
        self.part_id = part_id # Será NULL se for um serviço
        self.quantity = quantity
        self.unit_price = unit_price
        self.subtotal = subtotal
        self.is_service = is_service # 0 para peça, 1 para serviço
        self.description = description # Usado para descrição do serviço ou da peça, se necessário

    @classmethod
    def _create_table(cls):
        """Cria a tabela de itens de ordem de serviço se ela não existir."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_order_id INTEGER NOT NULL,
                part_id INTEGER, -- Pode ser NULL se for um serviço
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                is_service BOOLEAN DEFAULT 0,
                description TEXT,
                FOREIGN KEY (service_order_id) REFERENCES service_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_order_items_so_id ON {cls._table_name} (service_order_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_service_order_items_part_id ON {cls._table_name} (part_id)")
        conn.commit()
        conn.close()

