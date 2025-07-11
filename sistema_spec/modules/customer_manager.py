# modules/customer_manager.py
from models.customer_model import Customer

class CustomerManager:
    def __init__(self):
        # Garante que a tabela de clientes existe
        Customer._create_table()

    def add_customer(self, name, cpf_cnpj, phone, email, street=None, number=None, neighborhood=None, city=None, zip_code=None):
        """Adiciona um novo cliente."""
        try:
            # Verifica se CPF/CNPJ já existe (se fornecido)
            if cpf_cnpj:
                # Corrigido: Certifique-se de que a chamada ao search seja consistente.
                # Como Customer.search agora busca em múltiplas colunas, a chamada simples com query_text é adequada para a busca geral.
                # Para uma verificação de unicidade por CPF/CNPJ específico, o search precisa usar o `column` parametro.
                existing_customer = Customer.search(cpf_cnpj, 'cpf_cnpj') 
                if existing_customer and any(c.cpf_cnpj == cpf_cnpj for c in existing_customer):
                    return False, f"Cliente com CPF/CNPJ '{cpf_cnpj}' já existe."

            customer = Customer(
                name=name,
                cpf_cnpj=cpf_cnpj,
                phone=phone,
                email=email,
                street=street,
                number=number,
                neighborhood=neighborhood,
                city=city,
                zip_code=zip_code
            )
            customer.save()
            return True, "Cliente adicionado com sucesso!"
        except Exception as e:
            return False, f"Erro ao adicionar cliente: {e}"

    def update_customer(self, customer_id, name, cpf_cnpj, phone, email, street=None, number=None, neighborhood=None, city=None, zip_code=None):
        """Atualiza os dados de um cliente existente."""
        customer = Customer.get_by_id(customer_id)
        if not customer:
            return False, "Cliente não encontrado."

        # Verifica se CPF/CNPJ já existe para outro cliente (se fornecido)
        if cpf_cnpj:
            existing_customer = Customer.search(cpf_cnpj, 'cpf_cnpj')
            if existing_customer and any(c.id != customer_id and c.cpf_cnpj == cpf_cnpj for c in existing_customer):
                return False, f"Cliente com CPF/CNPJ '{cpf_cnpj}' já existe para outro registro."

        customer.name = name
        customer.cpf_cnpj = cpf_cnpj
        customer.phone = phone
        customer.email = email
        customer.street = street
        customer.number = number
        customer.neighborhood = neighborhood
        customer.city = city
        customer.zip_code = zip_code
        customer.save()
        return True, "Cliente atualizado com sucesso!"

    def delete_customer(self, customer_id):
        """Deleta um cliente."""
        # TODO: Adicionar verificação de dependências (vendas, OS) antes de deletar
        Customer.delete(customer_id)
        return True, "Cliente removido com sucesso!"

    def get_all_customers(self):
        """Retorna todos os clientes."""
        return Customer.get_all()

    def get_customer_by_id(self, customer_id):
        """Retorna um cliente pelo ID."""
        return Customer.get_by_id(customer_id)

    def search_customers(self, query):
        """
        Busca clientes por nome, CPF/CNPJ, email, telefone, rua, número, bairro, cidade, CEP.
        Este método usará a busca multi-coluna de Customer.search.
        """
        return Customer.search(query) # O `column='name'` é o padrão no modelo, então 1 argumento aqui está correto.

