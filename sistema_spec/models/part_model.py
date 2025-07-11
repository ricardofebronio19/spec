# models/part_model.py
import sqlite3
from models.base_model import BaseModel, get_db_connection

class Part(BaseModel):
    _table_name = "parts"
    _fields = [
        "name", "description", "part_number", "manufacturer", "price", "cost",
        "stock", "min_stock", "location", "supplier_id", "category",
        "original_code", "similar_code_01", "similar_code_02", "barcode"
    ]

    def __init__(self, id=None, name=None, description=None, part_number=None,
                 manufacturer=None, price=0.0, cost=0.0, stock=0,
                 min_stock=0, location=None, supplier_id=None, category=None,
                 original_code=None, similar_code_01=None, similar_code_02=None,
                 barcode=None):
        """Initializes a Part instance. ID is handled by the database."""
        super().__init__(id)
        self.name = name
        self.description = description
        self.part_number = part_number
        self.manufacturer = manufacturer
        self.price = price
        self.cost = cost
        self.stock = stock
        self.min_stock = min_stock
        self.location = location
        self.supplier_id = supplier_id
        self.category = category
        self.original_code = original_code
        self.similar_code_01 = similar_code_01
        self.similar_code_02 = similar_code_02
        self.barcode = barcode

    @classmethod
    def _create_table(cls):
        """Creates the parts table with an auto-incrementing integer ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                part_number TEXT NOT NULL UNIQUE,
                manufacturer TEXT,
                price REAL NOT NULL,
                cost REAL NOT NULL,
                stock INTEGER NOT NULL,
                min_stock INTEGER NOT NULL,
                location TEXT,
                supplier_id INTEGER,
                category TEXT,
                original_code TEXT UNIQUE,
                similar_code_01 TEXT UNIQUE,
                similar_code_02 TEXT UNIQUE,
                barcode TEXT UNIQUE,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_name ON {cls._table_name} (name COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_part_number ON {cls._table_name} (part_number COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_manufacturer ON {cls._table_name} (manufacturer COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_original_code ON {cls._table_name} (original_code COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_barcode ON {cls._table_name} (barcode COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_supplier_id ON {cls._table_name} (supplier_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_parts_category ON {cls._table_name} (category COLLATE NOCASE)")
        conn.commit()
        conn.close()

    @classmethod
    def search(cls, query, column_name=None):
        """
        Searches for parts. If 'column_name' is provided, performs a case-insensitive search
        on that specific column. Otherwise, performs a broad search across multiple relevant columns.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if column_name:
            sql = f"SELECT * FROM {cls._table_name} WHERE LOWER({column_name}) LIKE LOWER(?)"
            params = (query,)
        else:
            search_query = f"%{query.lower()}%"
            sql = f"""
                SELECT * FROM {cls._table_name}
                WHERE LOWER(name) LIKE ? OR LOWER(part_number) LIKE ? OR LOWER(manufacturer) LIKE ? OR LOWER(description) LIKE ?
                   OR LOWER(original_code) LIKE ? OR LOWER(similar_code_01) LIKE ? OR LOWER(similar_code_02) LIKE ? OR LOWER(barcode) LIKE ?
                   OR CAST(id AS TEXT) LIKE ? -- Adicionado busca por ID
            """
            params = (search_query,) * 8 + (f'%{query}%',) # Aplica o termo de busca a todas as 8 colunas + ID
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [cls(**dict(row)) for row in rows]

