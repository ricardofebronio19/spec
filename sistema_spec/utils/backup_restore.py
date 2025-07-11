import os
import shutil
from datetime import datetime
from config.settings import DATA_DIR, BACKUP_DIR, DB_NAME

def create_backup():
    """Cria um backup do banco de dados."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    db_path = os.path.join(DATA_DIR, DB_NAME)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"autopeças_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        shutil.copyfile(db_path, backup_path)
        return True, f"Backup criado com sucesso: {backup_filename}"
    except FileNotFoundError:
        return False, "Erro: Banco de dados não encontrado para backup."
    except Exception as e:
        return False, f"Erro ao criar backup: {e}"

def restore_backup(backup_file_path):
    """Restaura o banco de dados a partir de um arquivo de backup."""
    db_path = os.path.join(DATA_DIR, DB_NAME)
    
    try:
        # Opcional: Criar um backup temporário do BD atual antes de restaurar
        # Isso pode ser útil para reverter se a restauração der errado.
        current_db_temp_backup_name = f"autopeças_pre_restore_temp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copyfile(db_path, os.path.join(BACKUP_DIR, current_db_temp_backup_name))
        
        shutil.copyfile(backup_file_path, db_path)
        return True, "Restauração concluída com sucesso."
    except FileNotFoundError:
        return False, "Erro: Arquivo de backup ou banco de dados principal não encontrado."
    except Exception as e:
        return False, f"Erro ao restaurar backup: {e}"

def get_available_backups():
    """Retorna uma lista de caminhos completos para os arquivos de backup disponíveis."""
    if not os.path.exists(BACKUP_DIR):
        return []
    
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db') and f.startswith('autopeças_backup_')]
    backups.sort(reverse=True) # Mais recente primeiro
    return [os.path.join(BACKUP_DIR, b) for b in backups]