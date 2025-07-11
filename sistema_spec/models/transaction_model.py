# models/transaction_model.py
import sqlite3
import uuid
from datetime import datetime

from models.base_model import BaseModel, get_db_connection

class Transaction(BaseModel):
    _table_name = "transactions"
    _columns = [
        "transaction_date", "customer_id", "total_amount", "discount_applied",
        "payment_method", "type", "status", "registered_by_user_id"
    ]

    def __init__(self, id, transaction_date, customer_id, total_amount, discount_applied,
                 payment_method, type, status, registered_by_user_id):
        super().__init__(id)
        self.transaction_date = transaction_date # Data no formato YYYY-MM-DD
        self.customer_id = customer_id
        self.total_amount = total_amount
        self.discount_applied = discount_applied
        self.payment_method = payment_method.upper() if payment_method else None
        self.type = type.upper() # 'VENDA' ou 'ORCAMENTO'
        self.status = status.upper() # Ex: 'PENDENTE', 'CONCLUIDA', 'CANCELADA', 'APROVADO', 'REPROVADO'
        self.registered_by_user_id = registered_by_user_id
        self.items = [] # Para armazenar objetos TransactionItem relacionados

    @classmethod
    def _create_table(cls):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id TEXT PRIMARY KEY,
                transaction_date TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                total_amount REAL NOT NULL,
                discount_applied REAL DEFAULT 0.0,
                payment_method TEXT,
                type TEXT NOT NULL, -- 'VENDA' ou 'ORCAMENTO'
                status TEXT NOT NULL, -- Status específico para cada tipo (e.g., 'CONCLUIDA', 'PENDENTE', 'APROVADO')
                registered_by_user_id TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (registered_by_user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
        conn.close()

    @classmethod
    def get_all(cls, transaction_type=None, status=None, start_date=None, end_date=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        sql_query = f"""
            SELECT t.*, c.name AS customer_name, u.username AS registered_by_username
            FROM {cls._table_name} t
            JOIN customers c ON t.customer_id = c.id
            LEFT JOIN users u ON t.registered_by_user_id = u.id
            WHERE 1=1
        """
        params = []

        if transaction_type:
            sql_query += " AND t.type = ?"
            params.append(transaction_type.upper())
        if status:
            sql_query += " AND t.status = ?"
            params.append(status.upper())
        if start_date:
            sql_query += " AND t.transaction_date >= ?"
            params.append(start_date)
        if end_date:
            sql_query += " AND t.transaction_date <= ?"
            params.append(end_date)
        
        sql_query += " ORDER BY t.transaction_date DESC, t.id DESC"

        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            row_dict = dict(row)
            # Instanciar o objeto Transaction
            transaction_id = row_dict.pop('id')
            transaction_instance = cls(id=transaction_id, **row_dict)
            
            # Adicionar nomes de customer e user para exibição, sem serem atributos diretos do modelo Transaction
            transaction_instance.customer_name = row_dict.get('customer_name')
            transaction_instance.registered_by_username = row_dict.get('registered_by_username')
            results.append(transaction_instance)
        return results

    @classmethod
    def search(cls, query_text, transaction_type=None, status=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        search_query_param = f"%{query_text.upper()}%"
        sql_query = f"""
            SELECT t.*, c.name AS customer_name, u.username AS registered_by_username
            FROM {cls._table_name} t
            JOIN customers c ON t.customer_id = c.id
            LEFT JOIN users u ON t.registered_by_user_id = u.id
            WHERE (UPPER(c.name) LIKE ? OR UPPER(t.payment_method) LIKE ? OR UPPER(t.status) LIKE ? OR t.id LIKE ?)
        """
        params = [search_query_param, search_query_param, search_query_param, search_query_param]

        if transaction_type:
            sql_query += " AND t.type = ?"
            params.append(transaction_type.upper())
        if status:
            sql_query += " AND t.status = ?"
            params.append(status.upper())
        
        sql_query += " ORDER BY t.transaction_date DESC, t.id DESC"

        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            row_dict = dict(row)
            transaction_id = row_dict.pop('id')
            transaction_instance = cls(id=transaction_id, **row_dict)
            transaction_instance.customer_name = row_dict.get('customer_name')
            transaction_instance.registered_by_username = row_dict.get('registered_by_username')
            results.append(transaction_instance)
        return results

