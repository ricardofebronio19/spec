# models/report_model.py
from models.base_model import BaseModel, get_db_connection
import sqlite3

class Report(BaseModel):
    _table_name = "reports"
    _fields = ["report_type", "generation_date", "generated_by_user_id", "file_path", "filters_json"]

    def __init__(self, id=None, report_type=None, generation_date=None,\
                 generated_by_user_id=None, file_path=None, filters_json=None):
        super().__init__(id)
        self.report_type = report_type
        self.generation_date = generation_date
        self.generated_by_user_id = generated_by_user_id
        self.file_path = file_path
        self.filters_json = filters_json # Armazena filtros usados em formato JSON (string)

    @classmethod
    def _create_table(cls):
        """Cria a tabela de relatórios se ela não existir."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls._table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                generation_date TEXT NOT NULL,
                generated_by_user_id INTEGER,
                file_path TEXT NOT NULL UNIQUE, -- Caminho do arquivo do relatório gerado
                filters_json TEXT, -- Para armazenar filtros como string JSON (opcional)
                FOREIGN KEY (generated_by_user_id) REFERENCES users(id)
            )
        """)
        # Adicionando índices
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_reports_type ON {cls._table_name} (report_type COLLATE NOCASE)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_reports_date ON {cls._table_name} (generation_date DESC)")
        conn.commit()
        conn.close()

