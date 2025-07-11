# config/user_roles.py

from enum import Enum

class UserRole(Enum):
    ADMIN = "Administrador"
    MANAGER = "Gerente"
    EMPLOYEE = "Funcionário"
    FINANCIAL = "Financeiro"
    MARKETING = "Marketing"
    CAIXA = "Caixa" # Papel para responsável pelo caixa/recebimento