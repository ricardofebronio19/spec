# config/settings.py
import os

# Get the directory where settings.py is located
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the project root (assuming settings.py is in 'config/' within the root)
PROJECT_ROOT = os.path.join(CURRENT_DIR, '..')

# --- Configurações de Diretório ---
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# Garante que os diretórios existam
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# --- Configurações do Banco de Dados ---
DB_NAME = os.path.join(DATA_DIR, 'database.db')

# --- Configurações de API ---
# URL da API de consulta de veículos (substitua pela URL real da API que você usa)
API_VEICULOS_URL = "https://example.com/api/veiculos/placa" # URL de exemplo, substitua pela real

# Tokens para API de consulta de veículos
VEICULOS_API_BEARER_TOKEN = "SEU_BEARER_TOKEN_DA_API_VEICULOS_AQUI" # Token de autorização
VEICULOS_API_DEVICE_TOKEN = "SEU_DEVICE_TOKEN_DA_API_VEICULOS_AQUI" # Token de dispositivo (se a API usar)


# Configurações para a API de consulta de CNPJ
# CORREÇÃO: Utilizando o domínio 'open.cnpja.com' e mantendo o endpoint '/office/'
# pois o CNPJ será anexado a esta URL para requisições GET.
API_CNPJ_URL = "https://open.cnpja.com/office/" # << CORRIGIDO PARA OPEN.CNPJA.COM >>
CNPJA_API_TOKEN = "6e18262b-bf58-454e-92fd-1a1d4cd87be5-80a7e607-eb43-4573-b672-25794946c31a" # SEU NOVO TOKEN

# Configuração de Estoque
MIN_STOCK_THRESHOLD = 5 # Limiar para notificação de estoque baixo
