# modules/notification_manager.py
from models.notification_model import Notification
from models.base_model import get_db_connection
from datetime import datetime
import json


class NotificationManager:
    def __init__(self):
        Notification._create_table()

    def add_notification(self, type, message, entity_id=None, entity_type=None): # Argumentos são 'entity_id', 'entity_type'
        """Adiciona uma nova notificação ao sistema."""
        timestamp = datetime.now().isoformat()
        notification = Notification(
            timestamp=timestamp,
            type=type,
            message=message,
            is_read=0,  # Nova notificação é sempre não lida
            entity_id=entity_id,   # Passa como 'entity_id'
            entity_type=entity_type # Passa como 'entity_type'
        )
        notification.save()
        return True, "Notificação adicionada com sucesso!"

    def get_all_notifications(self, unread_only=False):
        """
        Retorna todas as notificações, opcionalmente filtrando por não lidas.
        As notificações são retornadas em ordem cronológica inversa (mais recentes primeiro).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_query = "SELECT * FROM notifications"
        params = []
        if unread_only:
            sql_query += " WHERE is_read = 0"
        
        sql_query += " ORDER BY timestamp DESC, id DESC"

        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()
        
        result_notifications = []
        for row in rows:
            row_dict = dict(row)
            notification_id = row_dict.pop('id')
            # Aqui, os nomes das chaves em row_dict DEVEM ser 'entity_id' e 'entity_type'
            # se a migração ou criação da tabela foi bem-sucedida.
            result_notifications.append(Notification(id=notification_id, **row_dict))
        return result_notifications


    def get_notification_by_id(self, notification_id):
        """Retorna uma notificação pelo ID."""
        return Notification.get_by_id(notification_id)

    def mark_notification_as_read(self, notification_id):
        """Marca uma notificação específica como lida."""
        notification = self.get_notification_by_id(notification_id)
        if notification:
            notification.is_read = 1
            notification.save()
            return True, "Notificação marcada como lida."
        return False, "Notificação não encontrada."

    def mark_all_notifications_as_read(self):
        """Marca todas as notificações como lidas."""
        notifications = self.get_all_notifications(unread_only=True)
        for notification in notifications:
            notification.is_read = 1
            notification.save()
        return True, "Todas as notificações marcadas como lidas."

    def delete_notification(self, notification_id):
        """Deleta uma notificação pelo ID."""
        Notification.delete(notification_id)
        return True, "Notificação removida com sucesso!"

    def get_unread_notifications_count(self):
        """Retorna o número de notificações não lidas."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def check_low_stock(self, part_id, current_stock, min_stock):
        """
        Verifica se uma peça está abaixo do estoque mínimo e adiciona uma notificação.
        Evita duplicidade de notificações para a mesma peça com o mesmo problema.
        """
        if current_stock <= min_stock:
            existing_notifications = self.get_all_notifications(unread_only=True)
            for notif in existing_notifications:
                # Compara usando os nomes corretos do modelo: entity_id, entity_type
                if notif.type == 'Estoque Baixo' and notif.entity_type == 'part' and notif.entity_id == part_id:
                    return False, "Já existe notificação de estoque baixo para esta peça."
            
            message = f"A peça ID {part_id} está com estoque baixo: {current_stock} (Mínimo: {min_stock})."
            self.add_notification(
                type="Estoque Baixo",
                message=message,
                entity_id=part_id,   # Passa como 'entity_id'
                entity_type="part"    # Passa como 'entity_type'
            )
            return True, "Notificação de estoque baixo gerada."
        return False, "Estoque acima do mínimo."

    def notify_new_sale(self, sale_id, customer_name, total_amount):
        """Adiciona uma notificação para uma nova venda."""
        message = f"Nova Venda! ID: {sale_id}, Cliente: {customer_name}, Total: R$ {total_amount:.2f}."
        self.add_notification(
            type="Nova Venda",
            message=message,
            entity_id=sale_id,   # Passa como 'entity_id'
            entity_type="sale"    # Passa como 'entity_type'
        )
        return True, "Notificação de nova venda gerada."

    def notify_new_service_order(self, os_id, customer_name, vehicle_plate):
        """Adiciona uma notificação para uma nova ordem de serviço."""
        message = f"Nova OS! ID: {os_id}, Cliente: {customer_name}, Veículo: {vehicle_plate}."
        self.add_notification(
            type="Nova Ordem de Serviço",
            message=message,
            entity_id=os_id,       # Passa como 'entity_id'
            entity_type="service_order" # Passa como 'entity_type'
        )
        return True, "Notificação de nova OS gerada."

