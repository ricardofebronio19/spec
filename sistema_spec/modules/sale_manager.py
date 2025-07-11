# modules/sale_manager.py

import sys
import os
from datetime import datetime

from models.sale_model import Sale, SaleItem
from models.part_model import Part
from models.base_model import get_db_connection
from models.financial_transaction_model import FinancialTransaction
import sqlite3

class SaleManager:
    def __init__(self, stock_manager):
        self.stock_manager = stock_manager
        Sale._create_table()
        SaleItem._create_table()
        FinancialTransaction._create_table()

    def add_sale(self, sale_date, customer_id, total_amount, discount_applied, payment_method, user_id, items, is_quote=False):
        """
        Adds a new sale or quote.
        If is_quote is True, it saves as a quote without affecting stock.
        If is_quote is False, it saves as a sale and deducts stock.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            status = "ORÇAMENTO" if is_quote else "PENDENTE PAGAMENTO"
            
            sale = Sale(
                sale_date=sale_date,
                customer_id=customer_id,
                total_amount=total_amount,
                discount_applied=discount_applied,
                payment_method=payment_method,
                user_id=user_id,
                status=status,
                is_quote=is_quote
            )
            sale.save(cursor=cursor)
            sale_id = sale.id

            for item_data in items:
                part_id = item_data['part_id']
                quantity = item_data['quantity']

                # If it's a sale (not a quote), deduct stock
                if not is_quote:
                    part = self.stock_manager.get_part_by_id(part_id)
                    if not part or part.stock < quantity:
                        raise ValueError(f"Estoque insuficiente para a peça ID {part_id}.")
                    self.stock_manager.remove_stock(part_id, quantity, user_id, cursor=cursor)

                sale_item = SaleItem(
                    sale_id=sale_id,
                    part_id=part_id,
                    quantity=quantity,
                    unit_price=item_data['unit_price'],
                    subtotal=item_data['subtotal']
                )
                sale_item.save(cursor=cursor)
            
            conn.commit()
            message = "Orçamento salvo com sucesso!" if is_quote else "Venda adicionada com sucesso!"
            return True, message, sale_id
        except ValueError as ve:
            conn.rollback()
            return False, f"Erro: {ve}", None
        except Exception as e:
            conn.rollback()
            return False, f"Erro inesperado ao adicionar venda: {e}", None
        finally:
            conn.close()

    def update_sale(self, sale_id, sale_date, customer_id, total_amount, discount_applied, payment_method, user_id, items, is_quote=False):
        """
        Updates an existing sale or quote.
        Handles stock adjustments based on changes in items and quote status.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            sale = Sale.get_by_id(sale_id)
            if not sale:
                return False, "Venda/Orçamento não encontrado.", None

            # Reverte o estoque dos itens antigos da venda (se não era um orçamento)
            old_items = self.get_sale_items(sale_id, cursor)
            if not sale.is_quote: # Se a venda original não era um orçamento, devolve o estoque
                for old_item in old_items:
                    self.stock_manager.add_stock(old_item.part_id, old_item.quantity, user_id, cursor=cursor)
            
            # Deleta todos os itens antigos para substituí-los pelos novos
            cursor.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))

            # Atualiza os dados principais da venda
            sale.sale_date = sale_date
            sale.customer_id = customer_id
            sale.total_amount = total_amount
            sale.discount_applied = discount_applied
            sale.payment_method = payment_method
            sale.user_id = user_id # O usuário que está editando
            sale.is_quote = is_quote
            
            # Ajusta o status se for uma conversão de orçamento para venda
            if not is_quote and sale.is_quote: # Se era orçamento e agora é venda
                sale.status = "PENDENTE PAGAMENTO"
            elif is_quote and not sale.is_quote: # Se era venda e agora é orçamento (raro, mas possível)
                sale.status = "ORÇAMENTO"

            sale.save(cursor=cursor)

            # Adiciona os novos itens e deduz o estoque se for uma venda
            for item_data in items:
                part_id = item_data['part_id']
                quantity = item_data['quantity']

                if not is_quote: # Se for uma venda (não orçamento), deduz o estoque
                    part = self.stock_manager.get_part_by_id(part_id)
                    if not part or part.stock < quantity:
                        raise ValueError(f"Estoque insuficiente para a peça ID {part_id}.")
                    self.stock_manager.remove_stock(part_id, quantity, user_id, cursor=cursor)

                sale_item = SaleItem(
                    sale_id=sale_id,
                    part_id=part_id,
                    quantity=quantity,
                    unit_price=item_data['unit_price'],
                    subtotal=item_data['subtotal']
                )
                sale_item.save(cursor=cursor)
            
            conn.commit()
            message = "Orçamento atualizado com sucesso!" if is_quote else "Venda atualizada com sucesso!"
            return True, message, sale_id
        except ValueError as ve:
            conn.rollback()
            return False, f"Erro: {ve}", None
        except Exception as e:
            conn.rollback()
            return False, f"Erro inesperado ao atualizar venda: {e}", None
        finally:
            conn.close()

    def delete_sale(self, sale_id, user_id=None):
        """Deletes a sale or quote and returns parts to stock if it was a sale."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            sale = Sale.get_by_id(sale_id)
            if not sale:
                return False, "Venda/Orçamento não encontrado.", None

            # Se era uma venda (não orçamento), devolve as peças ao estoque
            if not sale.is_quote:
                items_to_return_to_stock = self.get_sale_items(sale_id, cursor)
                for item in items_to_return_to_stock:
                    self.stock_manager.add_stock(item.part_id, item.quantity, user_id, cursor=cursor)
            
            # Deleta a venda (ON DELETE CASCADE no SaleItem cuidará dos itens)
            Sale.delete(sale_id, cursor=cursor)

            conn.commit()
            return True, "Venda/Orçamento removido com sucesso e estoque atualizado (se aplicável)!"
        except Exception as e:
            conn.rollback()
            return False, f"Erro ao remover venda/orçamento: {e}"
        finally:
            conn.close()
            
    def get_all_sales_for_display(self, query=None, start_date=None, end_date=None, status_filter=None, is_quote_filter=None):
        """
        Fetches all sales/quotes for display in the UI, with customer and user names.
        Can be filtered by a search query, date range, and status.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    s.id, 
                    s.sale_date, 
                    COALESCE(c.name, 'CLIENTE REMOVIDO') as customer_name, 
                    s.total_amount, 
                    s.status,
                    s.is_quote,
                    s.payment_method,
                    COALESCE(u.username, 'N/A') as registered_by
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                LEFT JOIN users u ON s.user_id = u.id
            """
            params = []
            where_clauses = []

            if query:
                search_term = f"%{query}%"
                where_clauses.append(f"""
                    (LOWER(c.name) LIKE ? OR 
                    LOWER(s.status) LIKE ? OR 
                    LOWER(s.payment_method) LIKE ? OR 
                    CAST(s.id AS TEXT) LIKE ?)
                """)
                params.extend([search_term, search_term, search_term, search_term])
            
            if start_date:
                where_clauses.append("s.sale_date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("s.sale_date <= ?")
                params.append(end_date)
            if status_filter:
                where_clauses.append("s.status = ?")
                params.append(status_filter)
            if is_quote_filter is not None:
                where_clauses.append("s.is_quote = ?")
                params.append(1 if is_quote_filter else 0) # SQLite stores booleans as 0 or 1

            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            
            sql += " ORDER BY s.id DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error fetching sales for display: {e}")
            return []
        finally:
            conn.close()

    def convert_quote_to_sale(self, sale_id, user_id):
        quote = Sale.get_by_id(sale_id)
        if not quote or not quote.is_quote:
            return False, "Orçamento não encontrado ou já é uma venda."

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")
            
            items = self.get_sale_items(sale_id, cursor)
            for item in items:
                part = self.stock_manager.get_part_by_id(item.part_id)
                if not part or part.stock < item.quantity:
                    raise ValueError(f"Estoque insuficiente para a peça {part.name} para converter o orçamento.")
                self.stock_manager.remove_stock(item.part_id, item.quantity, user_id, cursor=cursor)

            quote.is_quote = False
            quote.status = "PENDENTE PAGAMENTO"
            quote.save(cursor=cursor)

            conn.commit()
            return True, "Orçamento convertido em venda com sucesso!"
        except ValueError as ve:
            conn.rollback()
            return False, f"Erro ao converter orçamento: {ve}"
        except Exception as e:
            conn.rollback()
            return False, f"Erro inesperado: {e}"
        finally:
            conn.close()

    def mark_sale_as_paid(self, sale_id, closed_by_user_id):
        sale = Sale.get_by_id(sale_id)
        if not sale or sale.is_quote:
            return False, "Apenas vendas podem ser marcadas como pagas."
        if sale.status == "PAGA":
            return False, "Esta venda já foi paga."

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")
            sale.status = "PAGA"
            sale.closed_by_user_id = closed_by_user_id
            sale.save(cursor=cursor)

            transaction = FinancialTransaction(
                transaction_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Full timestamp
                amount=sale.total_amount,
                type="Receita",
                category="Venda",
                description=f"Receita da Venda ID {sale.id}",
                related_entity_id=sale.id,
                related_entity_type="sale"
            )
            transaction.save(cursor=cursor)

            conn.commit()
            return True, f"Venda ID {sale_id} marcada como paga e receita registrada."
        except Exception as e:
            conn.rollback()
            return False, f"Erro ao marcar venda como paga: {e}"
        finally:
            conn.close()

    def get_sale_items(self, sale_id, cursor=None):
        if cursor:
            conn = cursor.connection; local_cursor = cursor; close_conn = False
        else:
            conn = get_db_connection(); local_cursor = conn.cursor(); close_conn = True
        
        try:
            local_cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
            rows = local_cursor.fetchall()
            return [SaleItem(**dict(row)) for row in rows]
        finally:
            if close_conn:
                conn.close()
    
    def get_sale_details_for_email(self, sale_id):
        sale = Sale.get_by_id(sale_id)
        if not sale: return None
        items = self.get_sale_items(sale_id)
        
        details = f"Detalhes do {'Orçamento' if sale.is_quote else 'Venda'} ID: {sale.id}\n"
        details += f"Data: {sale.sale_date.split('T')[0]}\n" # Apenas a data
        details += f"Total: R$ {sale.total_amount:.2f}\n"
        details += f"Status: {sale.status}\n\n"
        details += "Itens:\n"
        details += "--------------------------------\n"
        for item in items:
            part = Part.get_by_id(item.part_id)
            part_name = part.name if part else "Peça Removida"
            details += f"- {part_name}: {item.quantity} x R$ {item.unit_price:.2f} = R$ {item.subtotal:.2f}\n"
        details += "--------------------------------\n"
        return details

