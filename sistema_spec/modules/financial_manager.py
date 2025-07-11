# modules/financial_manager.py
from models.financial_transaction_model import FinancialTransaction
from models.base_model import get_db_connection
import sqlite3

class FinancialManager:
    def __init__(self):
        FinancialTransaction._create_table()

    def add_transaction(self, transaction_date, amount, type, category=None, description=None, related_entity_id=None, related_entity_type=None):
        """Adiciona uma nova transação financeira (receita ou despesa)."""
        try:
            transaction = FinancialTransaction(
                transaction_date=transaction_date,
                amount=amount,
                type=type,
                category=category,
                description=description,
                related_entity_id=related_entity_id,
                related_entity_type=related_entity_type
            )
            transaction.save()
            return True, "Transação adicionada com sucesso!"
        except Exception as e:
            return False, f"Erro ao adicionar transação: {e}"

    def update_transaction(self, transaction_id, transaction_date, amount, type, category=None, description=None, related_entity_id=None, related_entity_type=None):
        """Atualiza os dados de uma transação existente."""
        transaction = FinancialTransaction.get_by_id(transaction_id)
        if transaction:
            transaction.transaction_date = transaction_date
            transaction.amount = amount
            transaction.type = type
            transaction.category = category
            transaction.description = description
            transaction.related_entity_id = related_entity_id
            transaction.related_entity_type = related_entity_type
            transaction.save()
            return True, "Transação atualizada com sucesso!"
        return False, "Transação não encontrada."

    def delete_transaction(self, transaction_id):
        """Deleta uma transação."""
        FinancialTransaction.delete(transaction_id)
        return True, "Transação removida com sucesso!"

    def get_all_transactions(self, transaction_type_filter=None, start_date=None, end_date=None):
        """
        Retorna todas as transações financeiras, opcionalmente filtradas por data e tipo.
        As datas devem estar no formato TEXT (YYYY-MM-DD HH:MM:SS).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_query = f"SELECT id, transaction_date, amount, type, category, description, related_entity_id, related_entity_type FROM {FinancialTransaction._table_name}"
        params = []
        where_clauses = []

        if transaction_type_filter:
            where_clauses.append("type = ?")
            params.append(transaction_type_filter)
        if start_date:
            where_clauses.append("transaction_date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("transaction_date <= ?")
            params.append(end_date)
        
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        
        sql_query += " ORDER BY transaction_date DESC, id DESC"

        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()

        return [FinancialTransaction(id=row['id'], **{k: row[k] for k in FinancialTransaction._fields}) for row in rows]


    def get_transaction_by_id(self, transaction_id):
        """Retorna uma transação pelo ID."""
        return FinancialTransaction.get_by_id(transaction_id)

    def search_transactions(self, query_text, transaction_type_filter=None, start_date=None, end_date=None):
        """
        Busca transações financeiras por categoria ou descrição, com filtros adicionais.
        Retorna uma lista de objetos FinancialTransaction.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        search_term = f'%{query_text.lower()}%'
        
        sql_query = f"""
            SELECT id, transaction_date, amount, type, category, description, related_entity_id, related_entity_type
            FROM {FinancialTransaction._table_name}
            WHERE (LOWER(category) LIKE ? OR
                  LOWER(description) LIKE ?)
        """
        params = [search_term, search_term]
        
        if transaction_type_filter:
            sql_query += " AND type = ?"
            params.append(transaction_type_filter)
        if start_date:
            sql_query += " AND transaction_date >= ?"
            params.append(start_date)
        if end_date:
            sql_query += " AND transaction_date <= ?"
            params.append(end_date)

        sql_query += " ORDER BY transaction_date DESC, id DESC"
        
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Note: 'cls' is not defined here, assuming it's meant to be FinancialTransaction
        return [FinancialTransaction(id=row['id'], **{k: row[k] for k in FinancialTransaction._fields}) for row in rows]


    def get_balance(self, start_date=None, end_date=None):
        """
        Calcula o balanço total (Receitas - Despesas), opcionalmente filtrado por período.
        As datas devem estar no formato TEXT (YYYY-MM-DD HH:MM:SS).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query para receitas
        revenue_query = "SELECT SUM(amount) FROM financial_transactions WHERE type = 'Receita'"
        revenue_params = []
        # Query para despesas
        expense_query = "SELECT SUM(amount) FROM financial_transactions WHERE type = 'Despesa'"
        expense_params = []

        where_clauses = []
        if start_date:
            where_clauses.append("transaction_date >= ?")
            revenue_params.append(start_date)
            expense_params.append(start_date)
        if end_date:
            where_clauses.append("transaction_date <= ?")
            revenue_params.append(end_date)
            expense_params.append(end_date)

        if where_clauses:
            where_str = " AND ".join(where_clauses)
            revenue_query += f" AND {where_str}"
            expense_query += f" AND {where_str}"

        cursor.execute(revenue_query, revenue_params)
        total_revenue = cursor.fetchone()[0] or 0.0

        cursor.execute(expense_query, expense_params)
        total_expense = cursor.fetchone()[0] or 0.0

        conn.close()
        
        return total_revenue - total_expense

