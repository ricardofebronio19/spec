# utils/logger_config.py
import logging
import os
from datetime import datetime

# Define o diretório de logs no diretório 'data' do projeto
# Isso pressupõe que DATA_DIR está acessível ou que você define o caminho
# de forma independente para o logger. Aqui, vamos usar um caminho relativo seguro.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILENAME = datetime.now().strftime('app_%Y-%m-%d.log')
LOG_FILEPATH = os.path.join(LOG_DIR, LOG_FILENAME)

def setup_logging():
    """
    Configura o logger principal da aplicação.
    - Saída para console (INFO e superior)
    - Saída para arquivo (DEBUG e superior)
    """
    logger = logging.getLogger('sistema_spec_logger')
    logger.setLevel(logging.DEBUG) # Nível mínimo para o logger principal

    # Evita adicionar múltiplos handlers se a função for chamada mais de uma vez
    if not logger.handlers:
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO) # Apenas INFO ou superior no console
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # Handler para arquivo
        file_handler = logging.FileHandler(LOG_FILEPATH, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG) # DEBUG ou superior no arquivo (mais detalhes)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

# Inicializa o logger na primeira importação
logger = setup_logging()

