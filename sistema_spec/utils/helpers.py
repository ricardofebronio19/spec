import uuid
import re
from datetime import datetime

def generate_unique_id():
    """Gera um ID único universal (UUID)."""
    return str(uuid.uuid4())

def is_valid_email(email):
    """Verifica se o formato do email é válido usando uma regex simples."""
    # Regex básica para validação de email
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email) is not None

def format_currency_brl(amount):
    """Formata um valor numérico para a moeda brasileira (BRL)."""
    # Formato R$ X.XXX,XX
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def is_valid_phone(phone):
    """Verifica se o telefone é válido (apenas dígitos, mínimo 8, máximo 15)."""
    # Remove caracteres não numéricos antes de validar
    cleaned_phone = re.sub(r'\D', '', phone)
    return re.match(r"^\d{8,15}$", cleaned_phone) is not None

def get_current_timestamp():
    """Retorna o timestamp atual no formato ISO 8601 para armazenamento no BD."""
    return datetime.now().isoformat()