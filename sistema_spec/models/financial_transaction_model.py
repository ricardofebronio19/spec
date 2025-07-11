# models/financial_transaction_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3

class FinancialTransaction(BaseModel):
    _table_name = "financial_transactions"
    _fields = [
        "transaction_date", "amount", "type", "category",
        "description", "related_entity_id", "related_entity_type"
    ]

    def __init__(self, id=None, transaction_date=None, amount=0.0, type=None,\
                 category=None, description=None, related_entity_id=None,\
                 related_entity_type=None):
        super().__init__(id)
        self.transaction_date = transaction_date
        self.amount = amount
        self.type = type # 'Receita' ou 'Despesa'
        self.category = category
        self.description = description
        self.related_entity_id = related_entity_id # ID da venda/OS etc. se houver
        self.related_entity_type = related_entity_type # 'sale', 'service_order' etc.

    @classmethod
    def _create_table(cls):
        """Cria a tabela de transações financeiras se ela não existir."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL, -- 'Receita' ou 'Despesa'
                category TEXT,
                description TEXT,
                related_entity_id INTEGER,
                related_entity_type TEXT
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_financial_transactions_date ON {cls._table_name} (transaction_date)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_financial_transactions_type ON {cls._table_name} (type COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_financial_transactions_category ON {cls._table_name} (category COLLATE NOCASE)")
        conn.commit()
        conn.close()

    @classmethod
    def search(cls, query_text):
        """
        Busca transações financeiras por categoria ou descrição.
        Retorna uma lista de objetos FinancialTransaction.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        search_term = f'%{query_text.lower()}%'
        
        sql_query = f"""
            SELECT id, transaction_date, amount, type, category, description, related_entity_id, related_entity_type
            FROM {cls._table_name}
            WHERE LOWER(category) LIKE ? OR
                  LOWER(description) LIKE ?
            ORDER BY transaction_date DESC, id DESC
        """
        params = [search_term, search_term]
        
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [cls(id=row['id'], **{k: row[k] for k in cls._fields}) for row in rows]

