# models/settings_model.py
import sqlite3
from models.base_model import get_db_connection

class Setting:
    """
    Represents a key-value setting in the database.
    This model doesn't use the standard BaseModel to allow for a simple key-value store.
    """
    _table_name = "settings"

    @classmethod
    def _create_table(cls):
        """Creates the settings table if it doesn't exist."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        conn.close()

    @classmethod
    def set(cls, key, value):
        """Saves or updates a setting in the database."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT OR REPLACE INTO {cls._table_name} (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error in Setting.set: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @classmethod
    def get(cls, key, default=None):
        """Retrieves a setting from the database by its key."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT value FROM {cls._table_name} WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        except sqlite3.Error as e:
            print(f"Database error in Setting.get: {e}")
            return default
        finally:
            conn.close()

