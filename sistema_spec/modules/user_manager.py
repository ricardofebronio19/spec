# modules/user_manager.py
from models.user_model import User
import bcrypt # Para hash de senhas

class UserManager:
    def __init__(self):
        # Garante que a tabela de usuários é criada quando o manager é inicializado
        User._create_table()

    def add_user(self, username, password, role, is_active=True): # is_active default True
        """Adiciona um novo usuário."""
        if User.get_by_username(username):
            return False, "Nome de usuário já existe."

        user = User(username=username, role=role, is_active=is_active)
        user.set_password(password) # Usa o método set_password para fazer o hash
        user.save()
        return True, "Usuário adicionado com sucesso."

    def update_user(self, user_id, username, role, is_active, new_password=None):
        """Atualiza os dados de um usuário existente."""
        user = User.get_by_id(user_id)
        if not user:
            return False, "Usuário não encontrado."

        # Verifica se o nome de usuário está sendo alterado para um que já existe (excluindo o próprio usuário)
        existing_user_with_new_username = User.get_by_username(username)
        if existing_user_with_new_username and existing_user_with_new_username.id != user_id:
            return False, "Nome de usuário já está em uso por outro usuário."

        user.username = username
        user.role = role
        user.is_active = is_active # Atualiza o status de atividade
        if new_password:
            user.set_password(new_password) # Atualiza a senha se uma nova for fornecida
        
        user.save()
        return True, "Usuário atualizado com sucesso."

    def delete_user(self, user_id):
        """Deleta um usuário."""
        user = User.get_by_id(user_id)
        if not user:
            return False, "Usuário não encontrado."
        
        # TODO: Adicionar lógica para lidar com a exclusão de usuário que criou vendas/OS etc.
        # Por exemplo, definir 'user_id' para NULL em registros dependentes, ou impedir exclusão.
        # Por enquanto, apenas deleta.
        User.delete(user_id)
        return True, "Usuário deletado com sucesso."

    def get_all_users(self):
        """Retorna todos os usuários."""
        return User.get_all()

    def get_user_by_id(self, user_id):
        """Retorna um usuário pelo ID."""
        return User.get_by_id(user_id)

    def authenticate_user(self, username, password):
        """Autentica um usuário com nome de usuário e senha."""
        user = User.get_by_username(username)
        if user and user.is_active: # Verifica se o usuário existe e está ativo
            if user.check_password(password): # Usa o método check_password para verificar a senha
                return user
        return None # Retorna None se o usuário não for encontrado, estiver inativo ou a senha estiver incorreta

    def change_password(self, user_id, old_password, new_password):
        """Altera a senha de um usuário."""
        user = User.get_by_id(user_id)
        if not user or not user.check_password(old_password): # Verifica a senha antiga
            return False, "Senha antiga incorreta ou usuário não encontrado."

        user.set_password(new_password) # Define a nova senha
        user.save()
        return True, "Senha alterada com sucesso."

    def search_users(self, query):
        """
        Busca usuários por nome de usuário.
        Utiliza o método search do UserModel.
        """
        return User.search(query)