# models/user_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3
import bcrypt

class User(BaseModel):
    _table_name = "users"
    _fields = ["username", "password_hash", "role", "is_active"]

    def __init__(self, id=None, username=None, password_hash=None, role=None, is_active=1):
        super().__init__(id)
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active # 0 for inactive, 1 for active

    @classmethod
    def _create_table(cls):
        """Cria a tabela de usuários se ela não existir."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL, -- e.g., 'Administrador', 'Funcionário', 'Gerente'
                is_active INTEGER DEFAULT 1 -- 'is_active' column
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_users_username ON {cls._table_name} (username COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_users_role ON {cls._table_name} (role COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_users_is_active ON {cls._table_name} (is_active)")
        conn.commit()
        conn.close()

    def set_password(self, password):
        """Define a senha do usuário, armazenando o hash."""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        """Verifica se a senha fornecida corresponde ao hash armazenado."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @classmethod
    def get_by_username(cls, username):
        """Retorna um usuário pelo nome de usuário."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls._table_name} WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return cls(id=row['id'], **{k: row[k] for k in cls._fields})
            # CORREÇÃO AQUI: O finally garantirá que a conexão seja fechada.
            # O 'return None' está fora do try, mas é o comportamento desejado.
            return None
        finally: # Garante que a conexão é sempre fechada
            conn.close()

    @classmethod
    def search(cls, query_text):
        """
        Busca usuários por nome de usuário.
        Retorna uma lista de objetos User.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            search_term = f'%{query_text.lower()}%'
            
            sql_query = f"""
                SELECT id, username, password_hash, role, is_active
                FROM {cls._table_name}
                WHERE LOWER(username) LIKE ?
                ORDER BY username
            """
            params = [search_term]
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            return [cls(id=row['id'], **{k: row[k] for k in cls._fields}) for row in rows]
        finally:
            conn.close()

