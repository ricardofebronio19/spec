# models/customer_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3

class Customer(BaseModel):
    _table_name = "customers"
    _fields = [
        "name", "cpf_cnpj", "phone", "email", "street", "number", 
        "neighborhood", "city", "zip_code"
    ]

    def __init__(self, id=None, name=None, cpf_cnpj=None, phone=None, email=None,\
                 street=None, number=None, neighborhood=None, city=None, zip_code=None):
        super().__init__(id)
        self.name = name
        self.cpf_cnpj = cpf_cnpj
        self.phone = phone
        self.email = email
        self.street = street
        self.number = number
        self.neighborhood = neighborhood
        self.city = city
        self.zip_code = zip_code

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cpf_cnpj TEXT,
                phone TEXT,
                email TEXT,
                street TEXT,
                number TEXT,
                neighborhood TEXT,
                city TEXT,
                zip_code TEXT
            )
        """)
        # Adicionando índices para colunas de busca frequente
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_customers_name ON {cls._table_name} (name COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_customers_cpf_cnpj ON {cls._table_name} (cpf_cnpj COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_customers_email ON {cls._table_name} (email COLLATE NOCASE)")
        conn.commit()
        conn.close()

    @classmethod
    def search(cls, query_text, column=None): 
        conn = get_db_connection()
        cursor = conn.cursor()
        search_columns = ['name', 'cpf_cnpj', 'phone', 'email', 'street', 'number', 'neighborhood', 'city', 'zip_code']
        
        where_clauses = [f"LOWER({col}) LIKE ?" for col in search_columns]
        sql_query = f"""
            SELECT id, name, cpf_cnpj, phone, email, street, number, neighborhood, city, zip_code 
            FROM {cls._table_name}
            WHERE {' OR '.join(where_clauses)}
            ORDER BY name
        """
        search_term = f'%{query_text.lower()}%'
        params = [search_term] * len(search_columns)
        
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()
        
        customers = []
        for row in rows:
            row_dict = dict(row)
            customer_id = row_dict.pop('id')
            customers.append(cls(id=customer_id, **row_dict))
        return customers
    
