# models/supplier_model.py
import sqlite3
import uuid

from models.base_model import BaseModel, get_db_connection

class Supplier(BaseModel):
    _table_name = "suppliers"
    _fields = [
        "name", "cnpj", "contact_person", "phone", "email", "address"
    ]

    def __init__(self, name, cnpj, contact_person, phone, email, address, id=None):
        super().__init__(id)
        self.name = name.upper() if name else None
        self.cnpj = cnpj.upper() if cnpj else None
        self.contact_person = contact_person.upper() if contact_person else None
        self.phone = phone
        self.email = email
        self.address = address.upper() if address else None

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cnpj TEXT UNIQUE NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_suppliers_name ON {cls._table_name} (name COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_suppliers_cnpj ON {cls._table_name} (cnpj COLLATE NOCASE)")
        conn.commit()
        conn.close()

    @classmethod
    def search(cls, query):
        conn = get_db_connection()
        cursor = conn.cursor()
        search_query = f"%{query.upper()}%"
        cursor.execute(f"""
            SELECT id, name, cnpj, contact_person, phone, email, address
            FROM {cls._table_name}
            WHERE UPPER(name) LIKE ? OR UPPER(cnpj) LIKE ? OR UPPER(contact_person) LIKE ? OR UPPER(address) LIKE ?
        """, (search_query, search_query, search_query, search_query))
        rows = cursor.fetchall()
        conn.close()
        
        return [cls(id=row['id'], **{k: row[k] for k in cls._fields}) for row in rows]

