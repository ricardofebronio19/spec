# modules/supplier_manager.py
from models.supplier_model import Supplier
import sqlite3

class SupplierManager:
    def __init__(self):
        # Garante que a tabela de fornecedores é criada quando o manager é inicializado
        Supplier._create_table()

    def add_supplier(self, name, cnpj, contact_person, phone, email, address):
        """Adiciona um novo fornecedor."""
        try:
            # Verifica unicidade do nome
            existing_name = Supplier.search(name) # search agora busca em múltiplos campos
            if existing_name and any(s.name == name for s in existing_name):
                return False, f"Fornecedor com nome '{name}' já existe."
            
            # Verifica unicidade do CNPJ (se fornecido)
            if cnpj:
                existing_cnpj = Supplier.search(cnpj) # search agora busca em múltiplos campos
                if existing_cnpj and any(s.cnpj == cnpj for s in existing_cnpj):
                    return False, f"Fornecedor com CNPJ '{cnpj}' já existe."

            supplier = Supplier(
                name=name,
                cnpj=cnpj,
                contact_person=contact_person,
                phone=phone,
                email=email,
                address=address
            )
            supplier.save()
            return True, "Fornecedor adicionado com sucesso!"
        except Exception as e:
            return False, f"Erro ao adicionar fornecedor: {e}"

    def update_supplier(self, supplier_id, name, cnpj, contact_person, phone, email, address):
        """Atualiza os dados de um fornecedor existente."""
        supplier = Supplier.get_by_id(supplier_id)
        if not supplier:
            return False, "Fornecedor não encontrado."

        try:
            # Verifica se o nome está sendo alterado para um que já existe (excluindo o próprio fornecedor)
            if supplier.name != name: # Só verifica se o nome foi modificado
                existing_name = Supplier.search(name)
                if existing_name and any(s.id != supplier_id and s.name == name for s in existing_name):
                    return False, f"Fornecedor com nome '{name}' já existe."
            
            # Verifica se o CNPJ está sendo alterado para um que já existe (excluindo o próprio fornecedor)
            if cnpj and supplier.cnpj != cnpj: # Só verifica se o CNPJ foi modificado
                existing_cnpj = Supplier.search(cnpj)
                if existing_cnpj and any(s.id != supplier_id and s.cnpj == cnpj for s in existing_cnpj):
                    return False, f"Fornecedor com CNPJ '{cnpj}' já existe."

            supplier.name = name
            supplier.cnpj = cnpj
            supplier.contact_person = contact_person
            supplier.phone = phone
            supplier.email = email
            supplier.address = address
            supplier.save()
            return True, "Fornecedor atualizado com sucesso!"
        except Exception as e:
            return False, f"Erro ao atualizar fornecedor: {e}"

    def delete_supplier(self, supplier_id):
        """Deleta um fornecedor."""
        # TODO: Adicionar verificação de dependências (peças) antes de deletar
        # Se um fornecedor tiver peças associadas, a exclusão pode gerar inconsistências.
        # Por enquanto, apenas deleta.
        Supplier.delete(supplier_id)
        return True, "Fornecedor removido com sucesso!"

    def get_all_suppliers(self):
        """Retorna todos os fornecedores."""
        return Supplier.get_all()

    def get_supplier_by_id(self, supplier_id):
        """Retorna um fornecedor pelo ID."""
        return Supplier.get_by_id(supplier_id)

    def search_suppliers(self, query):
        """
        Busca fornecedores por nome, CNPJ ou pessoa de contato.
        Utiliza o método search do SupplierModel, que já busca em múltiplos campos.
        """
        return Supplier.search(query)