# models/notification_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3

class Notification(BaseModel):
    _table_name = "notifications"
    _fields = ["timestamp", "type", "message", "is_read", "entity_id", "entity_type"]

    def __init__(self, id=None, timestamp=None, type=None, message=None,
                 is_read=0, entity_id=None, entity_type=None):
        super().__init__(id)
        self.timestamp = timestamp # Ex: "YYYY-MM-DD HH:MM:SS"
        self.type = type # e.g., 'Estoque Baixo', 'Nova Venda', 'Ordem Serviço Vencida'
        self.message = message
        self.is_read = is_read # 0 for false, 1 for true
        self.entity_id = entity_id # ID da entidade relacionada (peça, venda, etc.)
        self.entity_type = entity_type # Tipo da entidade ('part', 'sale', 'service_order', etc.)

    @classmethod
    def _create_table(cls):
        """Cria a tabela de notificações se ela não existir."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                entity_id INTEGER,
                entity_type TEXT
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON {cls._table_name} (timestamp DESC)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON {cls._table_name} (is_read)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_notifications_entity ON {cls._table_name} (entity_type, entity_id)")
        conn.commit()
        conn.close()

    @classmethod
    def get_unread_notifications(cls):
        """Retorna todas as notificações não lidas."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {cls._table_name} WHERE is_read = 0 ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        
        result_notifications = []
        for row in rows:
            row_dict = dict(row)
            notification_id = row_dict.pop('id')
            result_notifications.append(cls(id=notification_id, **row_dict))
        return result_notifications

    def mark_as_read(self):
        """Marca a notificação como lida."""
        self.is_read = 1
        return self.save()

