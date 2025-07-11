# models/base_model.py
import sqlite3
from config.settings import DB_NAME

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn

class BaseModel:
    _table_name = None  # Deve ser definido nas subclasses
    _fields = []        # Deve ser definido nas subclasses, excluindo 'id'

    def __init__(self, id=None):
        self.id = id

    def save(self, cursor=None):
        """
        Salva (insere ou atualiza) a instância no banco de dados.
        Se 'cursor' for fornecido, ele é usado e a conexão não é fechada/comitada.
        Caso contrário, uma nova conexão é criada, usada, comitada e fechada.
        """
        if not self._table_name or not self._fields:
            raise NotImplementedError("As subclasses devem definir _table_name e _fields.")

        internal_conn_management = False
        if cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()
            internal_conn_management = True
        else:
            conn = cursor.connection # Obtém a conexão do cursor fornecido (para transações)

        field_names = ", ".join(self._fields)
        placeholders = ", ".join(["?" for _ in self._fields])
        field_values = [getattr(self, field) for field in self._fields]

        try:
            if self.id is None:
                # Inserir novo registro
                sql = f"INSERT INTO {self._table_name} ({field_names}) VALUES ({placeholders})"
                cursor.execute(sql, field_values)
                self.id = cursor.lastrowid
            else:
                # Atualizar registro existente
                set_clause = ", ".join([f"{field} = ?" for field in self._fields])
                sql = f"UPDATE {self._table_name} SET {set_clause} WHERE id = ?"
                cursor.execute(sql, field_values + [self.id])

            if internal_conn_management:
                conn.commit()
                return True # Retorna True para indicar sucesso
            return True # Sucesso, mas commit será feito externamente
        except sqlite3.Error as e:
            print(f"Erro ao salvar {self._table_name}: {e}")
            if internal_conn_management:
                conn.rollback()
            return False # Retorna False para indicar falha
        finally:
            if internal_conn_management:
                conn.close()

    @classmethod
    def get_by_id(cls, id):
        """Retorna uma instância da classe pelo ID."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls._table_name} WHERE id = ?", (id,))
            row = cursor.fetchone()
            if row:
                return cls(id=row['id'], **{k: row[k] for k in cls._fields}) # Desempacota campos
            return None
        finally:
            conn.close()

    @classmethod
    def get_all(cls):
        """Retorna uma lista de todas as instâncias da classe."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {cls._table_name}")
            rows = cursor.fetchall()
            return [cls(id=row['id'], **{k: row[k] for k in cls._fields}) for row in rows]
        finally:
            conn.close()

    @classmethod
    def delete(cls, id):
        """Deleta um registro pelo ID."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {cls._table_name} WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0 # Retorna True se algum registro foi deletado
        except sqlite3.Error as e:
            print(f"Erro ao deletar de {cls._table_name}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @classmethod
    def search(cls, query, column_name=None):
        """
        Busca instâncias da classe por um termo em uma coluna específica.
        Retorna uma lista de objetos do tipo da classe.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if column_name:
                sql_query = f"SELECT * FROM {cls._table_name} WHERE LOWER({column_name}) LIKE LOWER(?)"
                params = (f'%{query}%',)
            else:
                # Se column_name não for fornecido, este método genérico não sabe em qual coluna buscar.
                # As subclasses devem sobrescrever este método para implementar busca em múltiplos campos.
                raise NotImplementedError("A busca sem 'column_name' deve ser implementada na subclasse.")
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            return [cls(id=row['id'], **{k: row[k] for k in cls._fields}) for row in rows]
        finally:
            conn.close()

    @classmethod
    def _create_table(cls):
        """
        Cria a tabela no banco de dados.
        Esta é uma função de esqueleto e deve ser implementada nas subclasses.
        É chamada pelos Managers para garantir que as tabelas existam.
        """
        raise NotImplementedError("O método _create_table deve ser implementado na subclasse.")

