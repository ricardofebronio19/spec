from PySide6.QtWidgets import QMessageBox
from config.user_roles import UserRole

def login_required(func):
    """
    Decorator para exigir que o usuário esteja logado.
    Espera que a instância da classe tenha um atributo 'current_user'.
    """
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'current_user') or self.current_user is None:
            QMessageBox.warning(self, "Acesso Negado", "Você precisa estar logado para acessar esta funcionalidade.")
            return
        return func(self, *args, **kwargs)
    return wrapper

def role_required(required_roles):
    """
    Decorator para exigir um papel de usuário específico.
    `required_roles` pode ser uma única UserRole ou uma lista de UserRoles.
    Espera que a instância da classe tenha um atributo 'current_user' com o campo 'role'.
    """
    if not isinstance(required_roles, list):
        required_roles = [required_roles]

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'current_user') or self.current_user is None:
                QMessageBox.warning(self, "Acesso Negado", "Você precisa estar logado para acessar esta funcionalidade.")
                return

            try:
                user_role_enum = UserRole(self.current_user.role) # Converte a string do papel para o Enum
            except ValueError:
                QMessageBox.warning(self, "Erro de Permissão", "Papel de usuário inválido configurado.")
                return

            if user_role_enum not in required_roles:
                role_names = ", ".join([role.value for role in required_roles])
                QMessageBox.warning(self, "Permissão Negada", f"Seu papel de usuário ({self.current_user.role}) não tem permissão para acessar esta funcionalidade. Papéis necessários: {role_names}.")
                return
            return func(self, *args, **kwargs)
        return wrapper
    return decorator