# modules/service_order_manager.py
from models.service_order_model import ServiceOrder, ServiceOrderItem
from models.part_model import Part
from models.base_model import get_db_connection
from modules.user_manager import UserManager
import sqlite3
from datetime import datetime

class ServiceOrderManager:
    def __init__(self, stock_manager, user_manager):
        self.stock_manager = stock_manager
        self.user_manager = user_manager
        ServiceOrder._create_table()
        ServiceOrderItem._create_table()

    def add_service_order(self, order_date, customer_id, vehicle_make, vehicle_model, vehicle_year, vehicle_plate,
                          description, status, total_amount, labor_cost, parts_cost, assigned_user_id, items,
                          start_date, end_date, payment_status):
        """Adiciona uma nova ordem de serviço com itens e serviços."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            so = ServiceOrder(
                order_date=order_date,
                customer_id=customer_id,
                vehicle_make=vehicle_make,
                vehicle_model=vehicle_model,
                vehicle_year=vehicle_year,
                vehicle_plate=vehicle_plate,
                description=description,
                status=status,
                total_amount=total_amount,
                labor_cost=labor_cost,
                parts_cost=parts_cost,
                assigned_user_id=assigned_user_id,
                start_date=start_date,
                end_date=end_date,
                payment_status=payment_status
            )
            so.save(cursor=cursor)

            so_id = so.id

            for item_data in items:
                part_id = item_data.get('part_id')
                quantity = item_data['quantity']
                unit_price = item_data['unit_price']
                subtotal = item_data['subtotal']
                is_service = item_data.get('is_service', 0)
                item_description = item_data.get('description')

                so_item = ServiceOrderItem(
                    service_order_id=so_id,
                    part_id=part_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                    is_service=is_service,
                    description=item_description
                )
                so_item.save(cursor=cursor)

                # Se for uma peça, remove do estoque
                if not is_service and part_id:
                    part = self.stock_manager.get_part_by_id(part_id)
                    if part and part.stock >= quantity:
                        self.stock_manager.remove_stock(part_id, quantity, user_id=so.assigned_user_id, cursor=cursor)
                    else:
                        raise ValueError(f"Estoque insuficiente para a peça ID {part_id}.")

            conn.commit()
            return True, "Ordem de Serviço adicionada com sucesso!", so_id
        except ValueError as ve:
            conn.rollback()
            return False, f"Erro: {ve}", None
        except Exception as e:
            conn.rollback()
            return False, f"Erro inesperado ao adicionar Ordem de Serviço: {e}", None
        finally:
            conn.close()

    def update_service_order(self, so_id, order_date, customer_id, vehicle_make, vehicle_model, vehicle_year, vehicle_plate,
                             description, status, total_amount, labor_cost, parts_cost, assigned_user_id, items,
                             start_date, end_date, payment_status):
        """Atualiza os dados de uma ordem de serviço existente e seus itens."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            so = ServiceOrder.get_by_id(so_id)
            if not so:
                return False, "Ordem de Serviço não encontrada.", None

            # Reverte o estoque das peças antigas antes de atualizar
            old_items = self.get_service_order_items(so_id)
            for old_item in old_items:
                if not old_item.is_service and old_item.part_id:
                    self.stock_manager.add_stock(old_item.part_id, old_item.quantity, user_id=assigned_user_id, cursor=cursor)

            # Deleta os itens antigos da OS
            cursor.execute("DELETE FROM service_order_items WHERE service_order_id = ?", (so_id,))

            so.order_date = order_date
            so.customer_id = customer_id
            so.vehicle_make = vehicle_make
            so.vehicle_model = vehicle_model
            so.vehicle_year = vehicle_year
            so.vehicle_plate = vehicle_plate
            so.description = description
            so.status = status
            so.total_amount = total_amount
            so.labor_cost = labor_cost
            so.parts_cost = parts_cost
            so.assigned_user_id = assigned_user_id
            so.start_date = start_date
            so.end_date = end_date
            so.payment_status = payment_status
            so.save(cursor=cursor)

            # Adiciona os novos itens e remove do estoque
            for item_data in items:
                part_id = item_data.get('part_id')
                quantity = item_data['quantity']
                unit_price = item_data['unit_price']
                subtotal = item_data['subtotal']
                is_service = item_data.get('is_service', 0)
                item_description = item_data.get('description')

                so_item = ServiceOrderItem(
                    service_order_id=so_id,
                    part_id=part_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                    is_service=is_service,
                    description=item_description
                )
                so_item.save(cursor=cursor)

                if not is_service and part_id:
                    part = self.stock_manager.get_part_by_id(part_id)
                    if part and part.stock >= quantity:
                        self.stock_manager.remove_stock(part_id, quantity, user_id=assigned_user_id, cursor=cursor)
                    else:
                        raise ValueError(f"Estoque insuficiente para a peça ID {part_id}")

            conn.commit()
            return True, "Ordem de Serviço atualizada com sucesso!", so_id
        except Exception as e:
            conn.rollback()
            return False, f"Erro ao atualizar Ordem de Serviço: {e}", None
        finally:
            conn.close()

    def delete_service_order(self, so_id, user_id=None):
        """Deleta uma ordem de serviço e devolve as peças ao estoque."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION;")

            # Obtém os itens da OS antes de deletar
            items_to_return_to_stock = self.get_service_order_items(so_id)

            # Deleta a Ordem de Serviço (o ON DELETE CASCADE cuidará dos ServiceOrderItems)
            ServiceOrder.delete(so_id, cursor=cursor)

            # Devolve as peças ao estoque
            for item in items_to_return_to_stock:
                if not item.is_service and item.part_id:
                    self.stock_manager.add_stock(item.part_id, item.quantity, user_id=user_id, cursor=cursor)

            conn.commit()
            return True, "Ordem de Serviço removida com sucesso e estoque atualizado!"
        except Exception as e:
            conn.rollback()
            return False, f"Erro ao remover Ordem de Serviço: {e}"
        finally:
            conn.close()

    def update_service_order_status(self, so_id, new_status):
        """Atualiza apenas o status de uma ordem de serviço."""
        so = ServiceOrder.get_by_id(so_id)
        if so:
            so.status = new_status
            if new_status == "Concluída":
                so.end_date = datetime.now().isoformat() # Define a data de fim ao concluir
            so.save()
            return True, f"Status da OS {so_id} atualizado para '{new_status}'."
        return False, "Ordem de Serviço não encontrada."
    
    def update_service_order_payment_status(self, so_id, new_payment_status):
        """Atualiza o status de pagamento de uma ordem de serviço."""
        so = ServiceOrder.get_by_id(so_id)
        if so:
            so.payment_status = new_payment_status
            so.save()
            return True, f"Status de pagamento da OS {so_id} atualizado para '{new_payment_status}'."
        return False, "Ordem de Serviço não encontrada."


    def get_all_service_orders(self, query_text=None, status_filter=None, start_date=None, end_date=None, assigned_user_id=None):
        """
        Retorna todas as ordens de serviço, opcionalmente filtradas por query_text (nome do cliente, placa, modelo, descrição),
        status, data e usuário atribuído, com nomes de cliente e usuário.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT
                    so.id AS so_id,
                    so.order_date,
                    c.name AS customer_name,
                    so.vehicle_make,
                    so.vehicle_model,
                    so.vehicle_year,
                    so.vehicle_plate,
                    so.description AS so_description,
                    so.status,
                    so.total_amount,
                    so.labor_cost,
                    so.parts_cost,
                    u.username AS assigned_user_name,
                    so.start_date,
                    so.end_date,
                    so.payment_status
                FROM
                    service_orders so
                JOIN
                    customers c ON so.customer_id = c.id
                LEFT JOIN
                    users u ON so.assigned_user_id = u.id
            """
            params = []
            where_clauses = []

            if query_text:
                search_term = f"%{query_text.lower()}%"
                where_clauses.append(f"""
                    (LOWER(c.name) LIKE ? OR
                    LOWER(so.vehicle_plate) LIKE ? OR
                    LOWER(so.vehicle_model) LIKE ? OR
                    LOWER(so.description) LIKE ?)
                """)
                params.extend([search_term, search_term, search_term, search_term])

            if status_filter:
                where_clauses.append("so.status = ?")
                params.append(status_filter)
            if start_date:
                where_clauses.append("so.order_date >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("so.order_date <= ?")
                params.append(end_date)
            if assigned_user_id:
                where_clauses.append("so.assigned_user_id = ?")
                params.append(assigned_user_id)
            
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            
            sql += " ORDER BY so.order_date DESC, so.id DESC"

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_service_order_by_id(self, so_id):
        """Retorna uma ordem de serviço pelo ID."""
        return ServiceOrder.get_by_id(so_id)

    def get_service_order_items(self, so_id):
        """Retorna todos os itens (peças e serviços) para uma ordem de serviço específica."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM service_order_items WHERE service_order_id = ?
            """, (so_id,))
            rows = cursor.fetchall()
            result_items = []
            for row in rows:
                row_dict = dict(row) 
                item_id = row_dict.pop('id') 
                result_items.append(ServiceOrderItem(id=item_id, **row_dict))
            return result_items
        finally:
            conn.close()

