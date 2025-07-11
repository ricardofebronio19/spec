# gui_app.py

import sys
import os
import shutil
from datetime import datetime, date
import re
import json
import sqlite3
import logging

# --- Path adjustment ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_for_imports = script_dir 
if project_root_for_imports not in sys.path:
    sys.path.insert(0, project_root_for_imports)

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QInputDialog, QDialog, QFormLayout, QComboBox,
    QDateEdit, QSpinBox, QStackedWidget, QCompleter, QStatusBar,
    QCheckBox, QGroupBox, QFileDialog, QColorDialog, QStyle, QListWidget, QListWidgetItem, QDoubleSpinBox, QMenu
)
from PySide6.QtCore import Qt, QSize, QDate, QStringListModel, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QBrush, QColor, QPalette, QPixmap, QAction, QShortcut # Importa QShortcut

# --- Local Imports ---
from config.settings import DATA_DIR, BACKUP_DIR, REPORTS_DIR, MIN_STOCK_THRESHOLD
from config.user_roles import UserRole
from models.user_model import User
from models.customer_model import Customer
from models.supplier_model import Supplier
from models.part_model import Part
from models.sale_model import Sale, SaleItem
from models.service_order_model import ServiceOrder, ServiceOrderItem
from models.financial_transaction_model import FinancialTransaction
from models.notification_model import Notification
from models.report_model import Report
from models.settings_model import Setting
from models.base_model import get_db_connection
from modules.user_manager import UserManager
from modules.customer_manager import CustomerManager
from modules.supplier_manager import SupplierManager
from modules.stock_manager import StockManager
from modules.sale_manager import SaleManager
from modules.service_order_manager import ServiceOrderManager
from modules.financial_manager import FinancialManager
from modules.notification_manager import NotificationManager
from modules.report_manager import ReportManager
from modules.settings_manager import SettingsManager
from utils.api_integrations import APIIntegrations
from utils.email_sender import send_email
from utils.logger_config import logger
from utils.helpers import is_valid_email, is_valid_phone
from utils.backup_restore import create_backup, restore_backup, get_available_backups

# --- CUSTOM WIDGET FOR UPPERCASE INPUT ---
class UppercaseLineEdit(QLineEdit):
    """
    Custom QLineEdit that automatically converts text to uppercase.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textChanged.connect(self.to_uppercase)

    def to_uppercase(self, text):
        self.blockSignals(True)
        self.setText(text.upper())
        self.blockSignals(False)
        self.setCursorPosition(len(text))

# --- COMMON WIDGET FOR VALIDATED INPUT ---
class ValidatedLineEdit(QLineEdit):
    """
    A QLineEdit that provides visual feedback (border color) based on a validation function.
    """
    def __init__(self, validator_func=None, parent=None, placeholder_text=""):
        super().__init__(parent)
        self.validator_func = validator_func
        self.setPlaceholderText(placeholder_text)
        self.textChanged.connect(self.validate_text)
        self.setStyleSheet("QLineEdit { border: 1px solid #5a5d5f; }")

    def validate_text(self, text):
        if self.validator_func:
            if self.validator_func(text):
                self.setStyleSheet("QLineEdit { border: 1px solid green; }")
            else:
                self.setStyleSheet("QLineEdit { border: 1px solid red; }")
        else:
            self.setStyleSheet("QLineEdit { border: 1px solid #5a5d5f; }")

    def clear_validation_style(self):
        self.setStyleSheet("QLineEdit { border: 1px solid #5a5d5f; }")


# --- DIALOGS ---

class LoginDialog(QDialog):
    """
    Dialog for user authentication.
    Emits a 'login_successful' signal with the logged-in User object.
    """
    login_successful = Signal(User)

    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("Login")
        self.setFixedSize(300, 180)

        self.username_input = QLineEdit(placeholderText="Utilizador")
        self.password_input = QLineEdit(placeholderText="Senha", echoMode=QLineEdit.Password)
        self.login_button = QPushButton("Entrar")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Utilizador:"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Senha:"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        self.login_button.clicked.connect(self.accept_login)
        self.password_input.returnPressed.connect(self.accept_login)
        self.username_input.setFocus()

    def accept_login(self):
        user = self.user_manager.authenticate_user(self.username_input.text(), self.password_input.text())
        if user and user.is_active:
            self.login_successful.emit(user)
            self.accept()
            logger.info(f"Usuário {user.username} logado com sucesso.")
        else:
            QMessageBox.warning(self, "Login Falhou", "Utilizador ou senha inválidos, ou utilizador inativo.")
            logger.warning(f"Tentativa de login falhou para o usuário: {self.username_input.text()}")

class AddEditUserDialog(QDialog):
    """
    Diálogo para adicionar ou editar um usuário.
    Permite definir username, password, role e status de atividade.
    """
    def __init__(self, user=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Editar Utilizador" if user else "Adicionar Utilizador")
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        layout.addLayout(self.form_layout)

        self.username_input = UppercaseLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Deixar em branco para não alterar")
        
        self.role_combo = QComboBox()
        self.role_combo.addItems([role.value for role in UserRole])
        
        self.is_active_checkbox = QCheckBox("Ativo")

        self.form_layout.addRow("Utilizador:", self.username_input)
        self.form_layout.addRow("Senha:", self.password_input)
        self.form_layout.addRow("Função:", self.role_combo)
        self.form_layout.addRow("Status:", self.is_active_checkbox)

        if user:
            self.username_input.setText(user.username)
            self.role_combo.setCurrentText(user.role)
            self.is_active_checkbox.setChecked(bool(user.is_active))
        else:
            self.is_active_checkbox.setChecked(True)

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_user_data(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Dados Inválidos", "O nome de utilizador não pode estar vazio.")
            logger.warning("Tentativa de salvar usuário com nome de usuário vazio.")
            self.username_input.setFocus()
            return None
        
        password = self.password_input.text()
        if not self.user and not password:
            QMessageBox.warning(self, "Dados Inválidos", "A senha é obrigatória para novos utilizadores.")
            logger.warning("Tentativa de salvar novo usuário sem senha.")
            self.password_input.setFocus()
            return None
        
        return {
            "username": username,
            "password": password or None,
            "role": self.role_combo.currentText(),
            "is_active": self.is_active_checkbox.isChecked()
        }

class AddEditCustomerDialog(QDialog):
    """
    Diálogo para adicionar ou editar um cliente.
    Inclui campos para dados pessoais e endereço, com integração de API para CNPJ e CEP.
    Apresenta validação em tempo real para e-mail, telefone e CPF/CNPJ.
    """
    def __init__(self, customer=None, api_integrations=None, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.api_integrations = api_integrations
        self.setWindowTitle("Editar Cliente" if customer else "Adicionar Cliente")
        self.setModal(True)
        self.setMinimumWidth(500)

        self.form_layout = QFormLayout()
        
        self.name_input = UppercaseLineEdit(placeholderText="Nome completo ou Razão Social")
        self.form_layout.addRow("Nome/Razão Social*:", self.name_input)
        
        # Validação de CPF/CNPJ
        self.cpf_cnpj_input = ValidatedLineEdit(
            validator_func=lambda text: len(re.sub(r'\D', '', text)) in [11, 14] if text else True,
            placeholder_text="CPF ou CNPJ (apenas números)"
        )
        self.check_cnpj_button = QPushButton("Consultar CNPJ")
        self.check_cnpj_button.clicked.connect(self.consult_cnpj)
        
        cpf_cnpj_layout = QHBoxLayout()
        cpf_cnpj_layout.addWidget(self.cpf_cnpj_input)
        cpf_cnpj_layout.addWidget(self.check_cnpj_button)
        self.form_layout.addRow("CPF/CNPJ:", cpf_cnpj_layout)
        
        # Validação de Telefone
        self.phone_input = ValidatedLineEdit(is_valid_phone, placeholder_text="(99) 99999-9999")
        self.form_layout.addRow("Telefone:", self.phone_input)

        # Validação de Email
        self.email_input = ValidatedLineEdit(is_valid_email, placeholder_text="exemplo@dominio.com")
        self.form_layout.addRow("Email:", self.email_input)
        
        cep_layout = QHBoxLayout()
        self.zip_code_input = QLineEdit(placeholderText="99999-999")
        cep_layout.addWidget(self.zip_code_input)
        self.search_cep_button = QPushButton("Buscar CEP")
        self.search_cep_button.clicked.connect(self._buscar_cep_e_preencher_campos)
        cep_layout.addWidget(self.search_cep_button)
        self.form_layout.addRow("CEP:", cep_layout)
        
        self.street_input = UppercaseLineEdit()
        self.form_layout.addRow("Rua:", self.street_input)
        self.number_input = QLineEdit()
        self.form_layout.addRow("Número:", self.number_input)
        self.neighborhood_input = UppercaseLineEdit()
        self.form_layout.addRow("Bairro:", self.neighborhood_input)
        self.city_input = UppercaseLineEdit()
        self.form_layout.addRow("Cidade:", self.city_input)

        if self.customer:
            self.name_input.setText(self.customer.name)
            self.cpf_cnpj_input.setText(self.customer.cpf_cnpj)
            self.phone_input.setText(self.customer.phone)
            self.email_input.setText(self.customer.email)
            self.street_input.setText(self.customer.street)
            self.number_input.setText(self.customer.number)
            self.neighborhood_input.setText(self.customer.neighborhood)
            self.city_input.setText(self.customer.city)
            self.zip_code_input.setText(self.customer.zip_code)
            self.check_cnpj_button.hide()
            # Aciona a validação manualmente ao carregar dados existentes
            self.cpf_cnpj_input.validate_text(self.customer.cpf_cnpj)
            self.phone_input.validate_text(self.customer.phone)
            self.email_input.validate_text(self.customer.email)
        
        self.buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        self.buttons_layout.addWidget(self.save_button)
        self.buttons_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(self.form_layout)
        main_layout.addLayout(self.buttons_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def consult_cnpj(self):
        cnpj = self.cpf_cnpj_input.text().strip().replace('.', '').replace('/', '').replace('-', '')
        if not cnpj or len(cnpj) != 14:
            QMessageBox.warning(self, "Consulta CNPJ", "Por favor, insira um CNPJ válido (14 dígitos).")
            logger.warning(f"Tentativa de consulta CNPJ inválido: {cnpj}")
            self.cpf_cnpj_input.setFocus()
            return
        
        if self.api_integrations:
            self.check_cnpj_button.setEnabled(False)
            self.check_cnpj_button.setText("Consultando...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                logger.info(f"Consultando CNPJ: {cnpj}")
                cnpj_data = self.api_integrations.get_cnpj_data(cnpj)
                if cnpj_data and "error" not in cnpj_data:
                    QMessageBox.information(self, "Consulta CNPJ", "Dados do CNPJ obtidos com sucesso!")
                    self.name_input.setText(cnpj_data.get('razao_social', ''))
                    self.street_input.setText(cnpj_data.get('logradouro', ''))
                    self.number_input.setText(cnpj_data.get('numero', ''))
                    self.neighborhood_input.setText(cnpj_data.get('bairro', ''))
                    self.city_input.setText(cnpj_data.get('municipio', ''))
                    self.zip_code_input.setText(''.join(filter(str.isdigit, cnpj_data.get('cep', ''))))
                    self.phone_input.setText(cnpj_data.get('ddd_telefone_1', ''))
                    self.email_input.setText(cnpj_data.get('email', ''))
                    logger.info(f"Dados do CNPJ {cnpj} obtidos e preenchidos com sucesso.")
                else:
                    error_msg = cnpj_data.get("error") if cnpj_data else "Não foi possível obter dados para o CNPJ informado."
                    QMessageBox.warning(self, "Consulta CNPJ", error_msg)
                    logger.warning(f"Falha ao consultar CNPJ {cnpj}: {error_msg}")
            except Exception as e:
                logger.error(f"Erro inesperado durante consulta de CNPJ {cnpj}: {e}", exc_info=True)
                QMessageBox.critical(self, "Erro na Consulta", f"Ocorreu um erro inesperado: {e}")
            finally:
                QApplication.restoreOverrideCursor()
                self.check_cnpj_button.setEnabled(True)
                self.check_cnpj_button.setText("Consultar CNPJ")
        else:
            QMessageBox.warning(self, "API Não Configurada", "Integração da API de CNPJ não disponível.")
            logger.warning("Tentativa de consultar CNPJ com API não configurada.")
    
    def _buscar_cep_e_preencher_campos(self):
        cep = self.zip_code_input.text().strip().replace('-', '')
        if not cep:
            QMessageBox.warning(self, "Buscar CEP", "Por favor, insira um CEP para buscar.")
            self.zip_code_input.setFocus()
            return
        
        if self.api_integrations:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                endereco_data = self.api_integrations.buscar_endereco_por_cep(cep)
                if endereco_data:
                    self.street_input.setText(endereco_data.get('street', ''))
                    self.neighborhood_input.setText(endereco_data.get('neighborhood', ''))
                    self.city_input.setText(endereco_data.get('city', ''))
                    self.zip_code_input.setText(endereco_data.get('zip_code', ''))
                    QMessageBox.information(self, "Buscar CEP", "Endereço preenchido com sucesso!")
                else:
                    QMessageBox.warning(self, "Buscar CEP", "Não foi possível encontrar o endereço para o CEP informado.")
            except Exception as e:
                QMessageBox.critical(self, "Erro na Busca de CEP", f"Ocorreu um erro inesperado: {e}")
            finally:
                QApplication.restoreOverrideCursor()
        else:
            QMessageBox.warning(self, "API Não Configurada", "Integração da API de CEP não disponível.")


    def get_customer_data(self):
        # Realiza a validação final antes de retornar os dados
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O campo 'Nome/Razão Social' é obrigatório.")
            self.name_input.setFocus()
            return None
        if self.email_input.text().strip() and not self.email_input.validator_func(self.email_input.text()):
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um endereço de e-mail válido.")
            self.email_input.setFocus()
            return None
        if self.phone_input.text().strip() and not self.phone_input.validator_func(self.phone_input.text()):
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um número de telefone válido.")
            self.phone_input.setFocus()
            return None
        # Valida CPF/CNPJ apenas se não estiver vazio
        if self.cpf_cnpj_input.text().strip() and not self.cpf_cnpj_input.validator_func(self.cpf_cnpj_input.text()):
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um CPF/CNPJ válido (11 ou 14 dígitos).")
            self.cpf_cnpj_input.setFocus()
            return None

        return {
            "name": self.name_input.text().strip(),
            "cpf_cnpj": self.cpf_cnpj_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "street": self.street_input.text().strip(),
            "number": self.number_input.text().strip(),
            "neighborhood": self.neighborhood_input.text().strip(),
            "city": self.city_input.text().strip(),
            "zip_code": self.zip_code_input.text().strip(),
        }

class AddEditSupplierDialog(QDialog):
    """Diálogo para adicionar ou editar um fornecedor. Inclui validação em tempo real para e-mail e telefone."""
    def __init__(self, supplier=None, parent=None):
        super().__init__(parent)
        self.supplier = supplier
        self.setWindowTitle("Editar Fornecedor" if supplier else "Adicionar Fornecedor")
        self.setModal(True)
        
        self.form_layout = QFormLayout(self)
        
        self.name_input = UppercaseLineEdit()
        self.form_layout.addRow("Nome/Razão Social*:", self.name_input)
        
        self.cnpj_input = QLineEdit(placeholderText="XX.XXX.XXX/XXXX-XX")
        self.form_layout.addRow("CNPJ*:", self.cnpj_input)
        
        self.contact_person_input = UppercaseLineEdit()
        self.form_layout.addRow("Pessoa de Contato:", self.contact_person_input)
        
        # Validação de Telefone
        self.phone_input = ValidatedLineEdit(is_valid_phone, placeholder_text="(99) 99999-9999")
        self.form_layout.addRow("Telefone:", self.phone_input)
        
        # Validação de Email
        self.email_input = ValidatedLineEdit(is_valid_email, placeholder_text="exemplo@dominio.com")
        self.form_layout.addRow("Email:", self.email_input)
        
        self.address_input = UppercaseLineEdit()
        self.form_layout.addRow("Endereço:", self.address_input)
        
        if self.supplier:
            self.name_input.setText(self.supplier.name)
            self.cnpj_input.setText(self.supplier.cnpj)
            self.contact_person_input.setText(self.supplier.contact_person)
            self.phone_input.setText(self.supplier.phone)
            self.email_input.setText(self.supplier.email)
            self.address_input.setText(self.supplier.address)
            # Aciona a validação manualmente ao carregar dados existentes
            self.phone_input.validate_text(self.supplier.phone)
            self.email_input.validate_text(self.supplier.email)
        
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        self.form_layout.addRow(buttons_layout)
        
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_supplier_data(self):
        # Realiza a validação final antes de retornar os dados
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O campo 'Nome/Razão Social' é obrigatório.")
            self.name_input.setFocus()
            return None
        if not self.cnpj_input.text().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O campo 'CNPJ' é obrigatório.")
            self.cnpj_input.setFocus()
            return None
        if self.email_input.text().strip() and not self.email_input.validator_func(self.email_input.text()):
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um endereço de e-mail válido.")
            self.email_input.setFocus()
            return None
        if self.phone_input.text().strip() and not self.phone_input.validator_func(self.phone_input.text()):
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um número de telefone válido.")
            self.phone_input.setFocus()
            return None

        return {
            "name": self.name_input.text().strip(),
            "cnpj": self.cnpj_input.text().strip(),
            "contact_person": self.contact_person_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "address": self.address_input.text().strip()
        }

class AddEditPartDialog(QDialog):
    """Diálogo para adicionar ou editar uma peça de estoque."""
    def __init__(self, part=None, supplier_manager=None, parent=None):
        super().__init__(parent)
        self.part = part
        self.supplier_manager = supplier_manager
        self.setWindowTitle("Editar Peça" if part else "Adicionar Peça")
        self.setModal(True)
        self.setMinimumWidth(500)

        self.form_layout = QFormLayout(self)
        
        self.name_input = UppercaseLineEdit()
        self.form_layout.addRow("Nome da Peça*:", self.name_input)
        
        self.part_number_input = UppercaseLineEdit()
        self.form_layout.addRow("Número da Peça*:", self.part_number_input)
        
        self.description_input = UppercaseLineEdit()
        self.form_layout.addRow("Descrição:", self.description_input)
        
        self.manufacturer_input = UppercaseLineEdit()
        self.form_layout.addRow("Fabricante:", self.manufacturer_input)
        
        self.location_input = UppercaseLineEdit()
        self.form_layout.addRow("Localização:", self.location_input)
        
        self.category_input = UppercaseLineEdit()
        self.form_layout.addRow("Categoria:", self.category_input)
        
        self.original_code_input = UppercaseLineEdit()
        self.form_layout.addRow("Código Original:", self.original_code_input)
        
        self.similar_code_01_input = UppercaseLineEdit()
        self.form_layout.addRow("Código Similar 1:", self.similar_code_01_input)
        
        self.similar_code_02_input = UppercaseLineEdit()
        self.form_layout.addRow("Código Similar 2:", self.similar_code_02_input)
        
        self.barcode_input = UppercaseLineEdit()
        self.form_layout.addRow("Código de Barras:", self.barcode_input)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setPrefix("R$ "); self.price_input.setDecimals(2); self.price_input.setMaximum(999999.99)
        self.form_layout.addRow("Preço de Venda*:", self.price_input)
        
        self.cost_input = QDoubleSpinBox()
        self.cost_input.setPrefix("R$ "); self.cost_input.setDecimals(2); self.cost_input.setMaximum(999999.99)
        self.form_layout.addRow("Custo*:", self.cost_input)
        
        self.stock_input = QSpinBox()
        self.stock_input.setMaximum(999999)
        self.form_layout.addRow("Estoque Atual*:", self.stock_input)
        
        self.min_stock_input = QSpinBox()
        self.min_stock_input.setMaximum(999999)
        self.form_layout.addRow("Estoque Mínimo*:", self.min_stock_input)
        
        self.supplier_combo = QComboBox()
        self.supplier_combo.addItem("Selecione um fornecedor", userData=None)
        self._load_suppliers()
        self.form_layout.addRow("Fornecedor:", self.supplier_combo)
        
        if self.part:
            self.name_input.setText(self.part.name)
            self.part_number_input.setText(self.part.part_number)
            self.description_input.setText(self.part.description)
            self.manufacturer_input.setText(self.part.manufacturer)
            self.price_input.setValue(self.part.price)
            self.cost_input.setValue(self.part.cost)
            self.stock_input.setValue(self.part.stock)
            self.min_stock_input.setValue(self.part.min_stock)
            self.location_input.setText(self.part.location)
            self.category_input.setText(self.part.category)
            self.original_code_input.setText(self.part.original_code)
            self.similar_code_01_input.setText(self.part.similar_code_01)
            self.similar_code_02_input.setText(self.part.similar_code_02)
            self.barcode_input.setText(self.part.barcode)
            
            if self.part.supplier_id:
                index = self.supplier_combo.findData(self.part.supplier_id)
                if index != -1: self.supplier_combo.setCurrentIndex(index)
        
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        self.form_layout.addRow(buttons_layout)
        
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _load_suppliers(self):
        suppliers = self.supplier_manager.get_all_suppliers()
        for supplier in suppliers:
            self.supplier_combo.addItem(supplier.name, userData=supplier.id)

    def get_part_data(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O campo 'Nome da Peça' é obrigatório.")
            self.name_input.setFocus()
            return None
        if not self.part_number_input.text().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O campo 'Número da Peça' é obrigatório.")
            self.part_number_input.setFocus()
            return None
        if self.price_input.value() <= 0:
            QMessageBox.warning(self, "Dados Inválidos", "O 'Preço de Venda' deve ser maior que zero.")
            self.price_input.setFocus()
            return None
        if self.cost_input.value() <= 0:
            QMessageBox.warning(self, "Dados Inválidos", "O 'Custo' deve ser maior que zero.")
            self.cost_input.setFocus()
            return None
        # Estoque e Estoque Mínimo podem ser zero, mas devem ser preenchidos (já são QSpinBox)
        
        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.text().strip(),
            "part_number": self.part_number_input.text().strip(),
            "manufacturer": self.manufacturer_input.text().strip(),
            "price": self.price_input.value(),
            "cost": self.cost_input.value(),
            "stock": self.stock_input.value(),
            "min_stock": self.min_stock_input.value(),
            "location": self.location_input.text().strip(),
            "supplier_id": self.supplier_combo.currentData(),
            "category": self.category_input.text().strip(),
            "original_code": self.original_code_input.text().strip(),
            "similar_code_01": self.similar_code_01_input.text().strip(),
            "similar_code_02": self.similar_code_02_input.text().strip(),
            "barcode": self.barcode_input.text().strip()
        }

class PartSearchDialog(QDialog):
    """
    Diálogo para buscar e selecionar uma peça de estoque.
    Retorna o objeto Part selecionado.
    """
    def __init__(self, stock_manager=None, parent=None):
        super().__init__(parent)
        self.stock_manager = stock_manager
        self.selected_part = None
        self.setWindowTitle("Buscar Peça")
        self.setModal(True)
        self.setMinimumSize(600, 400)

        main_layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(placeholderText="Buscar por nome, número da peça, fabricante, código de barras...")
        self.search_input.textChanged.connect(self._load_parts) # Conecta a busca em tempo real
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(7) # Ajustado para exibir informações relevantes
        self.parts_table.setHorizontalHeaderLabels(["ID", "Nome", "Nº Peça", "Fabricante", "Estoque", "Preço", "Localização"])
        self.parts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setSelectionMode(QTableWidget.SingleSelection)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.doubleClicked.connect(self._on_part_double_clicked) # Seleciona ao dar duplo clique
        main_layout.addWidget(self.parts_table)

        buttons_layout = QHBoxLayout()
        self.select_button = QPushButton("Selecionar")
        self.select_button.clicked.connect(self._select_part)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.select_button)
        buttons_layout.addWidget(self.cancel_button)
        main_layout.addLayout(buttons_layout)

        self._load_parts() # Carrega as peças iniciais

    def _load_parts(self):
        """Carrega e exibe as peças na tabela, aplicando o filtro de busca."""
        query = self.search_input.text()
        self.parts_table.setRowCount(0)
        
        parts = self.stock_manager.search_parts(query) if query else self.stock_manager.get_all_parts()
        
        for row_idx, part in enumerate(parts):
            self.parts_table.insertRow(row_idx)
            self.parts_table.setItem(row_idx, 0, QTableWidgetItem(str(part.id)))
            self.parts_table.setItem(row_idx, 1, QTableWidgetItem(part.name))
            self.parts_table.setItem(row_idx, 2, QTableWidgetItem(part.part_number))
            self.parts_table.setItem(row_idx, 3, QTableWidgetItem(part.manufacturer))
            self.parts_table.setItem(row_idx, 4, QTableWidgetItem(str(part.stock)))
            table_item_price = QTableWidgetItem(f"R$ {part.price:.2f}")
            table_item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.parts_table.setItem(row_idx, 5, table_item_price)
            self.parts_table.setItem(row_idx, 6, QTableWidgetItem(part.location))
            
            # Opcional: Destacar peças com estoque baixo
            if part.stock <= part.min_stock:
                for col in range(self.parts_table.columnCount()):
                    item = self.parts_table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor(255, 200, 200)) # Cor de fundo para estoque baixo

    def _on_part_double_clicked(self):
        """Lida com o duplo clique na tabela para selecionar a peça."""
        self._select_part()

    def _select_part(self):
        """Define a peça selecionada e aceita o diálogo."""
        selected_rows = self.parts_table.selectionModel().selectedRows()
        if selected_rows:
            part_id = int(self.parts_table.item(selected_rows[0].row(), 0).text())
            self.selected_part = self.stock_manager.get_part_by_id(part_id)
            self.accept()
        else:
            QMessageBox.warning(self, "Nenhuma Peça Selecionada", "Por favor, selecione uma peça da lista.")


class AddEditSaleDialog(QDialog):
    """Diálogo para adicionar ou editar uma venda/orçamento."""
    def __init__(self, sale=None, customer_manager=None, stock_manager=None, parent=None): 
        super().__init__(parent)
        self.sale = sale
        self.customer_manager = customer_manager
        self.stock_manager = stock_manager
        self.setWindowTitle("Editar Venda/Orçamento" if sale else "Nova Venda/Orçamento")
        self.setModal(True)
        self.showMaximized() # Abre o diálogo maximizado
        
        self.current_items = []
        self.current_selected_part = None # Armazena o objeto Part selecionado na busca
        # Certifica-se de que sale.items é uma lista de SaleItem (objetos)
        if self.sale and hasattr(self.sale, 'items') and self.sale.items:
             self.current_items = [{"id": item.id, "part_id": item.part_id, "quantity": item.quantity, "unit_price": item.unit_price, "subtotal": item.subtotal, "part_name": self.stock_manager.get_part_by_id(item.part_id).name if item.part_id else "N/A", "part_number": self.stock_manager.get_part_by_id(item.part_id).part_number if item.part_id else "N/A"} for item in self.sale.items]

        main_layout = QVBoxLayout(self)

        # --- DADOS DO ORÇAMENTO/VENDA (TOP SECTION) ---
        top_group = QGroupBox("Dados do Orçamento / Venda")
        top_layout = QFormLayout(top_group)
        main_layout.addWidget(top_group)

        # Linha 1: Orçamento, Data Emissão, Vendedor
        row1_layout = QHBoxLayout()
        self.sale_id_label = QLabel("Orçamento: [Novo]") # Ou ID da venda existente
        row1_layout.addWidget(self.sale_id_label)
        row1_layout.addStretch() # Empurra para a direita

        top_layout.addRow(row1_layout)

        row2_layout = QHBoxLayout()
        self.emission_date_input = QDateEdit(calendarPopup=True)
        self.emission_date_input.setDate(QDate.currentDate())
        self.emission_date_input.setDisplayFormat("dd/MM/yyyy")
        row2_layout.addWidget(QLabel("Data Emissão:"))
        row2_layout.addWidget(self.emission_date_input)
        row2_layout.addStretch() # Empurra para a direita

        self.seller_label = QLabel(f"Vendedor: {parent.current_user.username if parent and parent.current_user else 'N/A'}")
        row2_layout.addWidget(self.seller_label)
        top_layout.addRow(row2_layout)

        # Linha 3: Cliente, CPF, Status
        row3_layout = QHBoxLayout()
        self.customer_code_input = QLineEdit(placeholderText="Código do Cliente") # Pode ser usado para lookup
        self.customer_name_input = QLineEdit(placeholderText="Nome do Cliente/Razão Social")
        self.customer_name_input.setReadOnly(True) # Preenchido via lookup
        self.customer_cpf_input = QLineEdit(placeholderText="CPF")
        self.customer_cpf_input.setReadOnly(True) # Preenchido via lookup

        row3_layout.addWidget(QLabel("Código do Cliente:"))
        row3_layout.addWidget(self.customer_code_input)
        row3_layout.addWidget(QLabel("Nome/Razão Social:"))
        row3_layout.addWidget(self.customer_name_input)
        row3_layout.addWidget(QLabel("CPF:"))
        row3_layout.addWidget(self.customer_cpf_input)
        top_layout.addRow(row3_layout)

        self.customer_combo = QComboBox() # Mantido para o completer e seleção de cliente
        self.customer_combo.setEditable(True)
        self.customer_combo.setPlaceholderText("Selecione ou digite o cliente")
        self.customer_completer = QCompleter()
        self.customer_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.customer_combo.setCompleter(self.customer_completer)
        self._load_customers()
        top_layout.addRow("Buscar Cliente:", self.customer_combo)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_selected)
        self.customer_combo.lineEdit().textChanged.connect(self._update_customer_completer)


        self.status_label = QLabel("Status do orçamento: PENDENTE") # Ou status da venda
        top_layout.addRow(self.status_label)

        # --- CONSULTA PREÇOS (MIDDLE SECTION) ---
        prices_group = QGroupBox("Consulta Preços")
        prices_layout = QVBoxLayout(prices_group)
        main_layout.addWidget(prices_group)

        # Campo de busca principal para peças (agora um QLineEdit simples)
        part_search_layout = QHBoxLayout()
        self.part_search_input = QLineEdit(placeholderText="Código Fabricante/Original / Cód. Barras") # Campo de busca principal
        part_search_layout.addWidget(self.part_search_input)
        self.search_part_button = QPushButton("Buscar Peça") # Botão para abrir o diálogo de busca
        self.search_part_button.clicked.connect(self._open_part_search_dialog)
        part_search_layout.addWidget(self.search_part_button)
        prices_layout.addLayout(part_search_layout)

        # Labels de detalhes da peça (preenchidos após seleção no diálogo de busca)
        part_details_layout = QFormLayout()
        self.part_description_label = QLabel("Descrição do Produto: N/A")
        self.part_stock_label = QLabel("Qtde Estoque: N/A")
        self.part_unit_price_label = QLabel("Preço Unitário: R$ 0.00")
        self.part_discount_label = QLabel("Desconto: R$ 0.00") # Desconto por item
        self.part_subtotal_label = QLabel("Sub-Total: R$ 0.00") # Subtotal do item

        part_details_layout.addRow(self.part_description_label)
        part_details_layout.addRow(self.part_stock_label)
        part_details_layout.addRow(self.part_unit_price_label)
        part_details_layout.addRow(self.part_discount_label)
        part_details_layout.addRow(self.part_subtotal_label)
        prices_layout.addLayout(part_details_layout)

        # Botões de ação para itens
        item_actions_layout = QHBoxLayout()
        self.item_quantity_input = QSpinBox(); self.item_quantity_input.setMinimum(1); self.item_quantity_input.setMaximum(9999)
        item_actions_layout.addWidget(QLabel("Qtd:"))
        item_actions_layout.addWidget(self.item_quantity_input)
        self.add_item_button = QPushButton("Adic")
        self.remove_item_button = QPushButton("Remov") # Botão de remover item da tabela
        # Botões da imagem (não implementados funcionalmente, apenas visualmente)
        item_actions_layout.addWidget(self.add_item_button)
        item_actions_layout.addWidget(self.remove_item_button)
        
        # Atribuições para os botões da imagem (placeholders ou ações básicas)
        btn_limpa = QPushButton("Limpa")
        btn_limpa.clicked.connect(self._clear_part_details)
        item_actions_layout.addWidget(btn_limpa)

        # REMOVIDOS: btn_grav, btn_aprov, btn_impr, btn_ajuda
        # btn_grav = QPushButton("Grav") 
        # btn_aprov = QPushButton("Aprov") 
        # btn_impr = QPushButton("Impr") 
        # btn_ajuda = QPushButton("Ajuda") 

        btn_novo = QPushButton("Novo")
        btn_novo.clicked.connect(self._reset_sale_form)
        item_actions_layout.addWidget(btn_novo)

        btn_sair = QPushButton("Sair")
        btn_sair.clicked.connect(self.reject) # Fecha o diálogo
        item_actions_layout.addWidget(btn_sair)

        item_actions_layout.addStretch() # Empurra para a direita
        prices_layout.addLayout(item_actions_layout)

        # --- ITENS DA VENDA (TABLE) ---
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7) # Ajustado para mais colunas
        self.items_table.setHorizontalHeaderLabels(["Código", "Descrição do Produto", "Qtd", "Preço Un.", "Descon.", "Sub-Total", "Ações"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.items_table)

        # --- DESCONTO E TOTAIS (BOTTOM SECTION) ---
        bottom_group = QGroupBox("Desconto")
        bottom_layout = QFormLayout(bottom_group)
        main_layout.addWidget(bottom_group)

        discount_type_layout = QHBoxLayout()
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItems(["$", "%"])
        self.discount_type_combo.setCurrentText("$") # Default to R$
        discount_type_layout.addWidget(QLabel("Tipo de Desconto:"))
        discount_type_layout.addWidget(self.discount_type_combo)
        discount_type_layout.addStretch()
        bottom_layout.addRow(discount_type_layout)

        discount_value_layout = QHBoxLayout()
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setPrefix("R$ ")
        self.discount_input.setDecimals(2)
        self.discount_input.setMaximum(999999.99)
        self.discount_input.valueChanged.connect(self._update_totals)
        discount_value_layout.addWidget(QLabel("Desconto:"))
        discount_value_layout.addWidget(self.discount_input)
        bottom_layout.addRow(discount_value_layout)

        self.observations_input = QLineEdit()
        bottom_layout.addRow("Observações:", self.observations_input)

        # Totais resumidos
        totals_layout = QHBoxLayout()
        self.items_total_label = QLabel("Itens: R$ 0.00")
        self.subtotal_label = QLabel("Sub-Total: R$ 0.00")
        self.discount_applied_label = QLabel("Desconto: R$ 0.00")
        self.total_amount_label = QLabel("Total do Orçamento: R$ 0.00") # Total geral

        totals_layout.addWidget(self.items_total_label)
        totals_layout.addStretch()
        totals_layout.addWidget(self.subtotal_label)
        totals_layout.addStretch()
        totals_layout.addWidget(self.discount_applied_label)
        totals_layout.addStretch()
        totals_layout.addWidget(self.total_amount_label)
        bottom_layout.addRow(totals_layout)

        # Adiciona o QComboBox para o método de pagamento ao layout
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems(["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "Pix", "Boleto"])
        bottom_layout.addRow("Método de Pagamento:", self.payment_method_combo)


        # Botões de ação final (Salvar Orçamento, Efetuar Venda, Cancelar)
        final_buttons_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar")
        self.save_quote_button = QPushButton("Salvar Orçamento")
        self.make_sale_button = QPushButton("Efetuar Venda")
        
        final_buttons_layout.addWidget(self.cancel_button)
        final_buttons_layout.addStretch()
        final_buttons_layout.addWidget(self.save_quote_button)
        final_buttons_layout.addWidget(self.make_sale_button)
        main_layout.addLayout(final_buttons_layout)

        # Conexões de sinais/slots
        self.add_item_button.clicked.connect(self.add_sale_item)
        self.remove_item_button.clicked.connect(lambda: self._remove_item_from_sale(self.items_table.currentRow()))
        self.save_quote_button.clicked.connect(self.save_as_quote)
        self.make_sale_button.clicked.connect(self.save_as_sale)
        self.cancel_button.clicked.connect(self.reject)
        self.items_table.itemChanged.connect(self._update_totals)

        # Se for uma edição de venda, preenche os campos e a tabela de itens
        if self.sale:
            self.sale_id_label.setText(f"Orçamento: {self.sale.id}" if self.sale.is_quote else f"Venda: {self.sale.id}")
            self.emission_date_input.setDate(QDate.fromString(self.sale.sale_date.split('T')[0], "yyyy-MM-dd"))
            
            customer = self.customer_manager.get_customer_by_id(self.sale.customer_id)
            if customer:
                self.customer_combo.setCurrentText(customer.name)
                self.customer_name_input.setText(customer.name)
                self.customer_cpf_input.setText(customer.cpf_cnpj)
            
            self.discount_input.setValue(self.sale.discount_applied)
            self.payment_method_combo.setCurrentText(self.sale.payment_method) # Agora payment_method_combo é um atributo
            self._populate_items_table()
            self._update_totals()
            
            if not self.sale.is_quote:
                self.save_quote_button.hide()
                self.make_sale_button.setText("Atualizar Venda")
            self.status_label.setText(f"Status do orçamento: {self.sale.status}")
        else:
            self.status_label.setText("Status do orçamento: NOVO")
        
        # Conecta o atalho F3 para abrir a busca de peças
        QShortcut(Qt.Key_F3, self, self._open_part_search_dialog)


    def _load_customers(self):
        self.customers_data = self.customer_manager.get_all_customers()
        customer_names = [c.name for c in self.customers_data]
        model = QStringListModel(customer_names)
        self.customer_completer.setModel(model)
        self.customer_combo.addItems(customer_names)

    def _on_customer_selected(self, index):
        """Preenche o nome e CPF do cliente selecionado no QComboBox."""
        customer_name = self.customer_combo.currentText()
        selected_customer = next((c for c in self.customers_data if c.name == customer_name), None)
        if selected_customer:
            self.customer_code_input.setText(str(selected_customer.id))
            self.customer_name_input.setText(selected_customer.name)
            self.customer_cpf_input.setText(selected_customer.cpf_cnpj)
        else:
            self.customer_code_input.clear()
            self.customer_name_input.clear()
            self.customer_cpf_input.clear()

    def _update_customer_completer(self, text):
        """Atualiza o completer de clientes com base no texto digitado."""
        if not text:
            filtered_customers = self.customer_manager.get_all_customers()
        else:
            filtered_customers = self.customer_manager.search_customers(text)
        
        customer_display_names = [c.name for c in filtered_customers]
        self.customer_completer.model().setStringList(customer_display_names)


    def _load_parts(self):
        """
        Carrega todas as peças. Este método não preenche o completer diretamente,
        mas sim o `self.parts_data` que será usado por `_update_part_completer`.
        """
        self.parts_data = self.stock_manager.get_all_parts()
        # O modelo do completer será inicializado na primeira chamada de _update_part_completer
        # ou se o modelo for None.

    def _open_part_search_dialog(self):
        """Abre o diálogo de busca de peças e processa a seleção."""
        dialog = PartSearchDialog(stock_manager=self.stock_manager, parent=self)
        if dialog.exec() == QDialog.Accepted:
            selected_part = dialog.selected_part
            if selected_part:
                # Preenche os labels de detalhes da peça na AddEditSaleDialog
                self.part_search_input.setText(f"ID: {selected_part.id} - {selected_part.name} (Nº Peça: {selected_part.part_number})")
                self.part_description_label.setText(f"Descrição do Produto: {selected_part.description or 'N/A'}")
                self.part_stock_label.setText(f"Qtde Estoque: {selected_part.stock}")
                self.part_unit_price_label.setText(f"Preço Unitário: R$ {selected_part.price:.2f}")
                self.part_discount_label.setText("Desconto: R$ 0.00") # Reseta ou mantém 0
                self.part_subtotal_label.setText(f"Sub-Total: R$ {selected_part.price:.2f}") # Para 1 unidade
                self.current_selected_part = selected_part # Armazena o objeto Part completo
                logger.info(f"Peça '{selected_part.name}' selecionada do diálogo de busca.")
                
                # Adiciona a peça automaticamente à venda após a seleção no pop-up
                self.add_sale_item() # Chama a função para adicionar o item
            else:
                self.current_selected_part = None
                self.part_search_input.clear()
                self.part_description_label.setText("Descrição do Produto: N/A")
                self.part_stock_label.setText("Qtde Estoque: N/A")
                self.part_unit_price_label.setText("Preço Unitário: R$ 0.00")
                self.part_discount_label.setText("Desconto: R$ 0.00")
                self.part_subtotal_label.setText("Sub-Total: R$ 0.00")
        
        # Após a seleção no pop-up, o foco volta para o campo de busca de peças
        self.part_search_input.setFocus()


    def _update_part_completer(self, text):
        """
        Atualiza o modelo do completer com base no texto digitado, usando a busca abrangente.
        Este método é chamado pelo `textChanged` do `part_search_input`.
        """
        if not hasattr(self, 'part_completer') or self.part_completer.model() is None:
            # Inicializa o completer se ainda não estiver configurado
            self.part_completer = QCompleter()
            self.part_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.part_completer.setModel(QStringListModel())
            self.part_search_input.setCompleter(self.part_completer) # Conecta o completer ao QLineEdit

        if not text:
            filtered_parts = self.stock_manager.get_all_parts()
        else:
            filtered_parts = self.stock_manager.search_parts(text)
        
        part_display_names = [
            f"ID: {p.id} - {p.name} (Nº Peça: {p.part_number}) - Fab: {p.manufacturer or 'N/A'} - "
            f"Cód. Orig: {p.original_code or 'N/A'} - Barras: {p.barcode or 'N/A'} - Est: {p.stock}"
            for p in filtered_parts
        ]
        
        self.part_completer.model().setStringList(part_display_names)

        # Tenta preencher os detalhes da peça se houver uma correspondência única
        if len(filtered_parts) == 1:
            selected_part = filtered_parts[0]
            self.part_description_label.setText(f"Descrição do Produto: {selected_part.description or 'N/A'}")
            self.part_stock_label.setText(f"Qtde Estoque: {selected_part.stock}")
            self.part_unit_price_label.setText(f"Preço Unitário: R$ {selected_part.price:.2f}")
            self.part_discount_label.setText("Desconto: R$ 0.00") 
            self.part_subtotal_label.setText(f"Sub-Total: R$ {selected_part.price:.2f}")
            self.current_selected_part = selected_part
        else:
            self.part_description_label.setText("Descrição do Produto: N/A")
            self.part_stock_label.setText("Qtde Estoque: N/A")
            self.part_unit_price_label.setText("Preço Unitário: R$ 0.00")
            self.part_discount_label.setText("Desconto: R$ 0.00")
            self.part_subtotal_label.setText("Sub-Total: R$ 0.00")
            self.current_selected_part = None


    def add_sale_item(self):
        # Usa a peça que foi selecionada ou preenchida na seção de consulta
        selected_part = self.current_selected_part
        quantity = self.item_quantity_input.value()
        
        if not selected_part:
            QMessageBox.warning(self, "Item Inválido", "Por favor, selecione uma peça válida usando a busca.")
            logger.warning("Tentativa de adicionar item de venda sem peça selecionada.")
            self.part_search_input.setFocus()
            return
        
        if any(item.get('part_id') == selected_part.id for item in self.current_items):
            QMessageBox.information(self, "Item Existente", "Esta peça já foi adicionada.")
            logger.info(f"Tentativa de adicionar peça {selected_part.name} duplicada na venda.")
            return
        
        self.current_items.append({
            "part_id": selected_part.id,
            "quantity": quantity,
            "unit_price": selected_part.price,
            "subtotal": selected_part.price * quantity,
            "part_name": selected_part.name,
            "part_number": selected_part.part_number,
            "item_discount": 0.0 # Desconto por item, se aplicável
        })
        
        self._populate_items_table()
        self._update_totals()
        
        self.part_search_input.clear() # Limpa o campo de busca após adicionar
        self.item_quantity_input.setValue(1)
        # Limpa também os detalhes da peça
        self._clear_part_details() # Chama a nova função para limpar os detalhes
        self.current_selected_part = None # Reseta a peça selecionada
        logger.info(f"Item {selected_part.name} (Qtd: {quantity}) adicionado à venda/orçamento.")

    def _clear_part_details(self):
        """Limpa os campos de detalhes da peça na seção 'Consulta Preços'."""
        self.part_search_input.clear()
        self.part_description_label.setText("Descrição do Produto: N/A")
        self.part_stock_label.setText("Qtde Estoque: N/A")
        self.part_unit_price_label.setText("Preço Unitário: R$ 0.00")
        self.part_discount_label.setText("Desconto: R$ 0.00")
        self.part_subtotal_label.setText("Sub-Total: R$ 0.00")
        self.current_selected_part = None


    def _reset_sale_form(self):
        """Reseta todos os campos do formulário de venda para uma nova venda."""
        reply = QMessageBox.question(self, "Confirmar Novo", "Tem certeza que deseja iniciar uma nova venda/orçamento? Os dados atuais serão perdidos.")
        if reply == QMessageBox.Yes:
            self.sale = None
            self.current_items = []
            self.current_selected_part = None
            
            self.sale_id_label.setText("Orçamento: [Novo]")
            self.emission_date_input.setDate(QDate.currentDate())
            self.customer_combo.setCurrentIndex(-1)
            self.customer_combo.clearEditText()
            self.customer_code_input.clear()
            self.customer_name_input.clear()
            self.customer_cpf_input.clear()
            self.status_label.setText("Status do orçamento: NOVO")
            
            self._clear_part_details()
            self.item_quantity_input.setValue(1)
            self.items_table.setRowCount(0)
            
            self.discount_input.setValue(0.0)
            self.observations_input.clear()
            self._update_totals() # Para resetar os totais
            
            self.save_quote_button.show() # Garante que os botões de salvar aparecem para nova venda
            self.make_sale_button.setText("Efetuar Venda")
            logger.info("Formulário de venda/orçamento resetado.")


    def _populate_items_table(self):
        self.items_table.setRowCount(0)
        for row_idx, item in enumerate(self.current_items):
            self.items_table.insertRow(row_idx)
            self.items_table.setItem(row_idx, 0, QTableWidgetItem(item['part_number'])) # Código
            self.items_table.setItem(row_idx, 1, QTableWidgetItem(item['part_name'])) # Descrição
            self.items_table.setItem(row_idx, 2, QTableWidgetItem(str(item['quantity']))) # Qtd
            self.items_table.setItem(row_idx, 3, QTableWidgetItem(f"R$ {item['unit_price']:.2f}")) # Preço Un.
            self.items_table.setItem(row_idx, 4, QTableWidgetItem(f"R$ {item.get('item_discount', 0.0):.2f}")) # Desconto
            self.items_table.setItem(row_idx, 5, QTableWidgetItem(f"R$ {item['subtotal']:.2f}")) # Sub-Total
            
            remove_button = QPushButton("Remover")
            remove_button.clicked.connect(lambda _, r=row_idx: self._remove_item_from_sale(r))
            self.items_table.setCellWidget(row_idx, 6, remove_button) # Ações
        
        self.items_table.resizeColumnsToContents()
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _remove_item_from_sale(self, row_index):
        if 0 <= row_index < len(self.current_items):
            removed_item_name = self.current_items[row_index].get('part_name', 'Item Desconhecido')
            del self.current_items[row_index]
            self._populate_items_table()
            self._update_totals() 
            logger.info(f"Item {removed_item_name} removido da venda/orçamento (linha {row_index}).")
    
    def _update_totals(self):
        subtotal_items = sum(item['subtotal'] for item in self.current_items)
        total_discount_items = sum(item.get('item_discount', 0.0) for item in self.current_items) # Soma descontos por item

        # Desconto geral (do campo de desconto)
        general_discount = self.discount_input.value()
        
        final_total_amount = subtotal_items - general_discount
        
        self.items_total_label.setText(f"Itens: R$ {subtotal_items:.2f}")
        self.subtotal_label.setText(f"Sub-Total: R$ {subtotal_items - total_discount_items:.2f}") # Subtotal após desconto por item
        self.discount_applied_label.setText(f"Desconto: R$ {general_discount:.2f}")
        self.total_amount_label.setText(f"Total do Orçamento: R$ {final_total_amount:.2f}")

    def get_sale_data(self):
        customer_name_input = self.customer_combo.currentText().strip()
        selected_customer = next((c for c in self.customers_data if c.name == customer_name_input), None)
        
        if not selected_customer:
            QMessageBox.warning(self, "Cliente Inválido", "Por favor, selecione um cliente válido.")
            logger.warning(f"Tentativa de salvar venda com cliente inválido: {customer_name_input}")
            self.customer_combo.setFocus()
            return None
        
        if not self.current_items:
            QMessageBox.warning(self, "Itens Vazios", "Por favor, adicione pelo menos um item à venda/orçamento.")
            logger.warning("Tentativa de salvar venda/orçamento sem itens.")
            self.part_search_input.setFocus() # Ou algum outro campo relevante para adicionar itens
            return None
        
        total_amount = float(self.total_amount_label.text().replace("Total do Orçamento: R$", "").strip().replace(",", "."))
        
        # O payment_method_combo já é um atributo da classe, então não precisa ser instanciado localmente aqui.
        # Apenas use self.payment_method_combo.currentText()
        return {
            "sale_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": selected_customer.id,
            "total_amount": total_amount,
            "discount_applied": self.discount_input.value(),
            "payment_method": self.payment_method_combo.currentText(), 
            "items": self.current_items
        }

    def save_as_quote(self):
        self.is_quote = True
        self.accept()
        logger.info("Diálogo de venda/orçamento aceito como orçamento.")

    def save_as_sale(self):
        self.is_quote = False
        self.accept()
        logger.info("Diálogo de venda/orçamento aceito como venda.")


class AddEditServiceOrderItemDialog(QDialog):
    """
    Diálogo para adicionar/editar um item (peça ou serviço) de uma Ordem de Serviço.
    """
    def __init__(self, item=None, stock_manager=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.stock_manager = stock_manager
        self.setWindowTitle("Editar Item da OS" if item else "Adicionar Item à OS")
        self.setModal(True)
        self.setMinimumWidth(400)

        self.form_layout = QFormLayout(self)

        self.is_service_checkbox = QCheckBox("É um Serviço (não peça)")
        self.is_service_checkbox.setChecked(bool(item.is_service) if item else False)
        self.is_service_checkbox.stateChanged.connect(self._toggle_item_type_fields)
        self.form_layout.addRow("Tipo:", self.is_service_checkbox)

        self.part_combo = QComboBox()
        self.part_combo.setEditable(True)
        self.part_combo.setPlaceholderText("Selecione ou digite a peça")
        self.part_completer = QCompleter()
        self.part_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.part_combo.setCompleter(self.part_completer)
        self._load_parts()
        self.form_layout.addRow("Peça:", self.part_combo)

        self.description_input = UppercaseLineEdit()
        self.form_layout.addRow("Descrição (Serviço/Outro):", self.description_input)

        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(9999)
        self.form_layout.addRow("Quantidade:", self.quantity_input)

        self.unit_price_input = QDoubleSpinBox()
        self.unit_price_input.setPrefix("R$ "); self.unit_price_input.setDecimals(2); self.unit_price_input.setMaximum(999999.99)
        self.form_layout.addRow("Preço Unitário:", self.unit_price_input)

        if self.item:
            if not self.item.is_service and self.item.part_id:
                part = self.stock_manager.get_part_by_id(self.item.part_id)
                if part:
                    self.part_combo.setCurrentText(f"{part.name} ({part.part_number})")
            self.quantity_input.setValue(self.item.quantity)
            self.unit_price_input.setValue(self.item.unit_price)
            self.description_input.setText(self.item.description)
        
        self._toggle_item_type_fields()

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        self.form_layout.addRow(buttons_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _load_parts(self):
        self.parts_data = self.stock_manager.get_all_parts()
        part_display_names = [f"{p.name} ({p.part_number})" for p in self.parts_data]
        self.part_combo.addItem("NÃO SELECIONAR PEÇA (PARA SERVIÇO)", userData=None)
        self.part_combo.addItems(part_display_names)
        model = QStringListModel(part_display_names)
        self.part_completer.setModel(model)


    def _toggle_item_type_fields(self):
        is_service = self.is_service_checkbox.isChecked()
        self.part_combo.setVisible(not is_service)
        self.part_combo.setEnabled(not is_service)
        self.description_input.setVisible(True)
        self.description_input.setPlaceholderText("Descrição do Serviço" if is_service else "Descrição da Peça (Opcional)")

    def get_item_data(self):
        is_service = self.is_service_checkbox.isChecked()
        part_id = None
        part_name = ""
        
        if not is_service:
            selected_part_text = self.part_combo.currentText().strip()
            selected_part = next((p for p in self.parts_data if f"{p.name} ({p.part_number})" == selected_part_text), None)
            if selected_part:
                part_id = selected_part.id
                part_name = selected_part.name
            elif selected_part_text and selected_part_text != "NÃO SELECIONAR PEÇA (PARA SERVIÇO)":
                 QMessageBox.warning(self, "Erro de Item", "Selecione uma peça válida ou marque como serviço.")
                 logger.warning(f"Tentativa de adicionar item OS: peça inválida ou não selecionada: {selected_part_text}")
                 self.part_combo.setFocus()
                 return None

        quantity = self.quantity_input.value()
        unit_price = self.unit_price_input.value()
        description = self.description_input.text().strip()

        if is_service and not description:
            QMessageBox.warning(self, "Dados Inválidos", "A descrição é obrigatória para serviços.")
            logger.warning("Tentativa de salvar item de serviço sem descrição.")
            self.description_input.setFocus()
            return None
        
        if not is_service and not part_id:
            QMessageBox.warning(self, "Dados Inválidos", "Para um item de peça, uma peça deve ser selecionada.")
            logger.warning("Tentativa de salvar item de peça sem ID da peça.")
            self.part_combo.setFocus()
            return None
        
        if quantity <= 0:
            QMessageBox.warning(self, "Dados Inválidos", "A quantidade deve ser maior que zero.")
            self.quantity_input.setFocus()
            return None
        
        if unit_price <= 0:
            QMessageBox.warning(self, "Dados Inválidos", "O preço unitário deve ser maior que zero.")
            self.unit_price_input.setFocus()
            return None


        return {
            "part_id": part_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": quantity * unit_price,
            "is_service": 1 if is_service else 0,
            "description": description,
            "part_name": part_name
        }

class AddEditServiceOrderDialog(QDialog):
    """
    Diálogo para adicionar ou editar uma Ordem de Serviço completa.
    Permite gerenciar detalhes da OS, veículo, cliente, usuário atribuído e itens (peças/serviços).
    """
    def __init__(self, service_order=None, customer_manager=None, user_manager=None, stock_manager=None, service_order_manager=None, api_integrations=None, parent=None):
        super().__init__(parent)
        self.service_order = service_order
        self.customer_manager = customer_manager
        self.user_manager = user_manager
        self.stock_manager = stock_manager
        self.service_order_manager = service_order_manager
        self.api_integrations = api_integrations
        self.setWindowTitle("Editar Ordem de Serviço" if service_order else "Nova Ordem de Serviço")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self.current_items = []
        if self.service_order:
            existing_items = self.service_order_manager.get_service_order_items(self.service_order.id)
            for item in existing_items:
                item_dict = item.__dict__
                part_name = self.stock_manager.get_part_by_id(item.part_id).name if item.part_id else ""
                item_dict['part_name'] = part_name
                self.current_items.append(item_dict)

        main_layout = QVBoxLayout(self)

        details_group = QGroupBox("Detalhes da Ordem de Serviço")
        details_layout = QFormLayout(details_group)
        main_layout.addWidget(details_group)

        self.order_date_input = QDateEdit(calendarPopup=True); self.order_date_input.setDate(QDate.currentDate()); self.order_date_input.setDisplayFormat("dd/MM/yyyy")
        details_layout.addRow("Data da Ordem*:", self.order_date_input)

        self.customer_combo = QComboBox(); self.customer_combo.setEditable(True); self.customer_combo.setPlaceholderText("Selecione ou digite o cliente"); self.customer_completer = QCompleter(); self.customer_completer.setCaseSensitivity(Qt.CaseInsensitive); self.customer_combo.setCompleter(self.customer_completer); self._load_customers()
        details_layout.addRow("Cliente*:", self.customer_combo)

        self.vehicle_make_input = UppercaseLineEdit(); details_layout.addRow("Marca do Veículo:", self.vehicle_make_input)
        self.vehicle_model_input = UppercaseLineEdit(); details_layout.addRow("Modelo do Veículo:", self.vehicle_model_input)
        self.vehicle_year_input = QLineEdit(); details_layout.addRow("Ano do Veículo:", self.vehicle_year_input)
        
        plate_layout = QHBoxLayout()
        self.vehicle_plate_input = UppercaseLineEdit(); plate_layout.addWidget(self.vehicle_plate_input)
        self.consult_plate_button = QPushButton("Consultar Placa"); self.consult_plate_button.clicked.connect(self._consult_plate); plate_layout.addWidget(self.consult_plate_button)
        details_layout.addRow("Placa do Veículo:", plate_layout)

        self.description_input = UppercaseLineEdit(); self.description_input.setPlaceholderText("Descreva o problema ou o serviço a ser realizado")
        details_layout.addRow("Descrição do Serviço:", self.description_input)

        self.status_combo = QComboBox(); self.status_combo.addItems(["Pendente", "Em Andamento", "Concluída", "Cancelada"])
        details_layout.addRow("Status:", self.status_combo)

        self.payment_status_combo = QComboBox(); self.payment_status_combo.addItems(["Pendente", "Pago", "Parcialmente Pago"])
        details_layout.addRow("Status do Pagamento:", self.payment_status_combo)

        self.assigned_user_combo = QComboBox(); self.assigned_user_combo.addItem("Selecione o Responsável", userData=None); self._load_users()
        details_layout.addRow("Responsável:", self.assigned_user_combo)

        self.start_date_input = QDateEdit(calendarPopup=True); self.start_date_input.setDate(QDate.currentDate()); self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        details_layout.addRow("Data Início:", self.start_date_input)

        self.end_date_input = QDateEdit(calendarPopup=True); self.end_date_input.setDisplayFormat("dd/MM/yyyy"); self.end_date_input.setDate(QDate.currentDate())
        details_layout.addRow("Data Fim Prevista:", self.end_date_input)
        
        self.labor_cost_input = QDoubleSpinBox(); self.labor_cost_input.setPrefix("R$ "); self.labor_cost_input.setDecimals(2); self.labor_cost_input.setMaximum(999999.99); self.labor_cost_input.valueChanged.connect(self._update_totals)
        details_layout.addRow("Custo Mão de Obra:", self.labor_cost_input)
        
        self.parts_cost_label = QLabel("Custo Peças: R$ 0.00"); details_layout.addRow(self.parts_cost_label)
        self.total_amount_label = QLabel("Total Geral: R$ 0.00"); details_layout.addRow(self.total_amount_label)

        items_group = QGroupBox("Peças e Serviços")
        items_layout = QVBoxLayout(items_group)
        main_layout.addWidget(items_group)

        self.items_table = QTableWidget(); self.items_table.setColumnCount(6); self.items_table.setHorizontalHeaderLabels(["Tipo", "Item/Descrição", "Qtd", "Preço Unit.", "Subtotal", "Ações"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); self.items_table.setSelectionBehavior(QTableWidget.SelectRows); self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        items_layout.addWidget(self.items_table)

        add_item_button = QPushButton("Adicionar Peça/Serviço"); add_item_button.clicked.connect(self.add_service_order_item)
        items_layout.addWidget(add_item_button, alignment=Qt.AlignRight)

        buttons_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar"); buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()
        self.save_button = QPushButton("Salvar Ordem de Serviço"); buttons_layout.addWidget(self.save_button)
        main_layout.addLayout(buttons_layout)

        if self.service_order:
            self.order_date_input.setDate(QDate.fromString(self.service_order.order_date.split('T')[0], "yyyy-MM-dd"))
            customer = self.customer_manager.get_customer_by_id(self.service_order.customer_id)
            if customer: self.customer_combo.setCurrentText(customer.name)
            self.vehicle_make_input.setText(self.service_order.vehicle_make)
            self.vehicle_model_input.setText(self.service_order.vehicle_model)
            self.vehicle_year_input.setText(str(self.service_order.vehicle_year))
            self.vehicle_plate_input.setText(self.service_order.vehicle_plate)
            self.description_input.setText(self.service_order.description)
            self.status_combo.setCurrentText(self.service_order.status)
            self.labor_cost_input.setValue(self.service_order.labor_cost)
            self.payment_status_combo.setCurrentText(self.service_order.payment_status)
            self.start_date_input.setDate(QDate.fromString(self.service_order.start_date.split('T')[0], "yyyy-MM-dd") if self.service_order.start_date else QDate.currentDate())
            self.end_date_input.setDate(QDate.fromString(self.service_order.end_date.split('T')[0], "yyyy-MM-dd") if self.service_order.end_date else QDate.currentDate())
            
            if self.service_order.assigned_user_id:
                user = self.user_manager.get_user_by_id(self.service_order.assigned_user_id)
                if user: self.assigned_user_combo.setCurrentText(user.username)
            
            self._populate_items_table()
            self._update_totals()

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _load_customers(self):
        self.customers_data = self.customer_manager.get_all_customers()
        customer_names = [c.name for c in self.customers_data]
        model = QStringListModel(customer_names)
        self.customer_completer.setModel(model)
        self.customer_combo.addItems(customer_names)

    def _load_users(self):
        users = self.user_manager.get_all_users()
        for user in users: self.assigned_user_combo.addItem(user.username, userData=user.id)

    def _consult_plate(self):
        plate = self.vehicle_plate_input.text().strip()
        if not plate:
            QMessageBox.warning(self, "Consulta Placa", "Por favor, insira uma placa para consultar.")
            logger.warning(f"Tentativa de consultar placa sem valor.")
            self.vehicle_plate_input.setFocus()
            return

        if self.api_integrations:
            self.consult_plate_button.setEnabled(False)
            self.consult_plate_button.setText("Consultando...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                logger.info(f"Consultando placa: {plate}")
                vehicle_data = self.api_integrations.get_vehicle_data_by_plate(plate)
                if vehicle_data:
                    QMessageBox.information(self, "Consulta Placa", "Dados do veículo obtidos com sucesso!")
                    self.vehicle_make_input.setText(vehicle_data.get('marca', ''))
                    self.vehicle_model_input.setText(vehicle_data.get('modelo', ''))
                    self.vehicle_year_input.setText(str(vehicle_data.get('ano', '')))
                    logger.info(f"Dados do veículo para placa {plate} obtidos e preenchidos.")
                else:
                    QMessageBox.warning(self, "Consulta Placa", "Não foi possível obter dados para a placa informada.")
                    logger.warning(f"Não foi possível obter dados para a placa: {plate}")
            except Exception as e:
                logger.error(f"Erro inesperado durante consulta de placa {plate}: {e}", exc_info=True)
                QMessageBox.critical(self, "Erro na Consulta", f"Ocorreu um erro inesperado: {e}")
            finally:
                QApplication.restoreOverrideCursor()
                self.consult_plate_button.setEnabled(True)
                self.consult_plate_button.setText("Consultar Placa")
        else:
            QMessageBox.warning(self, "API Não Configurada", "Integração da API de veículos não disponível.")
            logger.warning("Tentativa de consultar placa com API de veículos não configurada.")

    def add_service_order_item(self):
        dialog = AddEditServiceOrderItemDialog(stock_manager=self.stock_manager, parent=self)
        if dialog.exec():
            item_data = dialog.get_item_data()
            if item_data:
                self.current_items.append(item_data)
                self._populate_items_table()
                self._update_totals()
                logger.info(f"Item {item_data.get('description') or item_data.get('part_name')} adicionado à OS.")

    def _remove_service_order_item(self, row_index):
        if 0 <= row_index < len(self.current_items):
            removed_item_name = self.current_items[row_index].get('description') or self.current_items[row_index].get('part_name', 'Item Desconhecido')
            del self.current_items[row_index]
            self._populate_items_table()
            self._update_totals()
            logger.info(f"Item {removed_item_name} removido da OS (linha {row_index}).")

    def _populate_items_table(self):
        self.items_table.setRowCount(0)
        for row_idx, item in enumerate(self.current_items):
            self.items_table.insertRow(row_idx)
            item_type = "Serviço" if item.get('is_service') else "Peça"
            item_name = item.get('description') if item.get('is_service') else item.get('part_name')
            self.items_table.setItem(row_idx, 0, QTableWidgetItem(item_type))
            self.items_table.setItem(row_idx, 1, QTableWidgetItem(item_name))
            self.items_table.setItem(row_idx, 2, QTableWidgetItem(str(item['quantity'])))
            table_item_unit_price = QTableWidgetItem(f"R$ {item['unit_price']:.2f}")
            table_item_unit_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row_idx, 3, table_item_unit_price)
            table_item_subtotal = QTableWidgetItem(f"R$ {item['subtotal']:.2f}")
            table_item_subtotal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row_idx, 4, table_item_subtotal)
            
            remove_button = QPushButton("Remover")
            remove_button.clicked.connect(lambda _, r=row_idx: self._remove_service_order_item(r))
            self.items_table.setCellWidget(row_idx, 5, remove_button)
        
        self.items_table.resizeColumnsToContents()
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _update_totals(self):
        parts_cost = sum(item['subtotal'] for item in self.current_items if not item.get('is_service'))
        labor_cost = self.labor_cost_input.value()
        total_amount = parts_cost + labor_cost
        
        self.parts_cost_label.setText(f"Custo Peças: R$ {parts_cost:.2f}")
        self.total_amount_label.setText(f"Total Geral: R$ {total_amount:.2f}")

    def get_service_order_data(self):
        customer_name_input = self.customer_combo.currentText().strip()
        selected_customer = next((c for c in self.customers_data if c.name == customer_name_input), None)
        if not selected_customer:
            QMessageBox.warning(self, "Cliente Inválido", "Por favor, selecione um cliente válido.")
            logger.warning(f"Tentativa de salvar OS com cliente inválido: {customer_name_input}")
            self.customer_combo.setFocus()
            return None

        assigned_user_id = self.assigned_user_combo.currentData()
        if not assigned_user_id:
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, selecione um responsável pela OS.")
            logger.warning("Tentativa de salvar OS sem responsável atribuído.")
            self.assigned_user_combo.setFocus()
            return None

        if not self.current_items and self.labor_cost_input.value() == 0:
            QMessageBox.warning(self, "Itens/Custos Vazios", "Adicione pelo menos um item ou defina um custo de mão de obra.")
            logger.warning("Tentativa de salvar OS sem itens e sem custo de mão de obra.")
            return None
        
        return {
            "order_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": selected_customer.id,
            "vehicle_make": self.vehicle_make_input.text().strip(),
            "vehicle_model": self.vehicle_model_input.text().strip(),
            "vehicle_year": self.vehicle_year_input.text().strip(),
            "vehicle_plate": self.vehicle_plate_input.text().strip(),
            "description": self.description_input.text().strip(),
            "status": self.status_combo.currentText(),
            "total_amount": float(self.total_amount_label.text().replace("Total Geral: R$", "").strip().replace(",", ".")),
            "labor_cost": self.labor_cost_input.value(),
            "parts_cost": float(self.parts_cost_label.text().replace("Custo Peças: R$", "").strip().replace(",", ".")),
            "assigned_user_id": assigned_user_id,
            "start_date": self.start_date_input.date().toString("yyyy-MM-d HH:MM:SS"),
            "end_date": self.end_date_input.date().toString("yyyy-MM-d HH:MM:SS"),
            "payment_status": self.payment_status_combo.currentText(),
            "items": self.current_items
        }

class AddEditFinancialTransactionDialog(QDialog):
    """Diálogo para adicionar ou editar uma transação financeira."""
    def __init__(self, transaction=None, parent=None):
        super().__init__(parent)
        self.transaction = transaction
        self.setWindowTitle("Editar Transação Financeira" if transaction else "Adicionar Transação Financeira")
        self.setModal(True)
        self.form_layout = QFormLayout(self)

        self.date_input = QDateEdit(calendarPopup=True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.form_layout.addRow("Data*:", self.date_input)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setPrefix("R$ ")
        self.amount_input.setDecimals(2)
        self.amount_input.setMaximum(9999999.99)
        self.form_layout.addRow("Valor*:", self.amount_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Receita", "Despesa"])
        self.form_layout.addRow("Tipo*:", self.type_combo)

        self.category_input = UppercaseLineEdit()
        self.form_layout.addRow("Categoria:", self.category_input)

        self.description_input = UppercaseLineEdit()
        self.form_layout.addRow("Descrição:", self.description_input)

        if self.transaction:
            self.date_input.setDate(QDate.fromString(self.transaction.transaction_date.split('T')[0], "yyyy-MM-dd"))
            self.amount_input.setValue(self.transaction.amount)
            self.type_combo.setCurrentText(self.transaction.type)
            self.category_input.setText(self.transaction.category)
            self.description_input.setText(self.transaction.description)

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        self.form_layout.addRow(buttons_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_transaction_data(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Dados Inválidos", "O 'Valor' da transação deve ser maior que zero.")
            self.amount_input.setFocus()
            return None
        if not self.type_combo.currentText().strip():
            QMessageBox.warning(self, "Dados Inválidos", "O 'Tipo' da transação é obrigatório.")
            self.type_combo.setFocus()
            return None

        return {
            "transaction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount": self.amount_input.value(),
            "type": self.type_combo.currentText(),
            "category": self.category_input.text().strip(),
            "description": self.description_input.text().strip()
        }

class GenerateReportDialog(QDialog):
    """
    Diálogo para selecionar o tipo de relatório, formato e filtros.
    """
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("Gerar Relatório")
        self.setModal(True)
        self.setMinimumWidth(400)

        self.form_layout = QFormLayout(self)

        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["Vendas", "Estoque", "Financeiro", "Ordens de Serviço"])
        self.report_type_combo.currentIndexChanged.connect(self._toggle_filters_visibility)
        self.form_layout.addRow("Tipo de Relatório:", self.report_type_combo)

        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["Excel", "PDF"])
        self.form_layout.addRow("Formato de Exportação:", self.export_format_combo)

        # Filtros de Data
        self.date_filter_group = QGroupBox("Filtro por Data")
        date_layout = QFormLayout(self.date_filter_group)
        self.start_date_input = QDateEdit(calendarPopup=True); self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.end_date_input = QDateEdit(calendarPopup=True); self.end_date_input.setDisplayFormat("dd/MM/yyyy"); self.end_date_input.setDate(QDate.currentDate())
        date_layout.addRow("Data Início:", self.start_date_input)
        date_layout.addRow("Data Fim:", self.end_date_input)
        self.form_layout.addRow(self.date_filter_group)

        # Filtros de Ordem de Serviço
        self.os_filter_group = QGroupBox("Filtros de Ordem de Serviço")
        os_layout = QFormLayout(self.os_filter_group)
        self.os_status_combo = QComboBox(); self.os_status_combo.addItem("Todos", userData=None); self.os_status_combo.addItems(["Pendente", "Em Andamento", "Concluída", "Cancelada"])
        self.os_assigned_user_combo = QComboBox(); self.os_assigned_user_combo.addItem("Todos", userData=None); self._load_users_for_filter()
        os_layout.addRow("Status da OS:", self.os_status_combo)
        os_layout.addRow("Responsável:", self.os_assigned_user_combo)
        self.form_layout.addRow(self.os_filter_group)

        buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("Gerar Relatório")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.cancel_button)
        self.form_layout.addRow(buttons_layout)

        self.generate_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self._toggle_filters_visibility()

    def _load_users_for_filter(self):
        users = self.user_manager.get_all_users()
        for user in users:
            self.os_assigned_user_combo.addItem(user.username, userData=user.id)

    def _toggle_filters_visibility(self):
        report_type = self.report_type_combo.currentText()
        
        date_visible = report_type in ["Vendas", "Financeiro", "Ordens de Serviço"]
        self.date_filter_group.setVisible(date_visible)

        os_visible = report_type == "Ordens de Serviço"
        self.os_filter_group.setVisible(os_visible)

    def get_report_options(self):
        report_type = self.report_type_combo.currentText()
        export_format = self.export_format_combo.currentText().lower()
        
        options = {
            "report_type": report_type,
            "export_format": export_format,
            "filters": {}
        }

        if self.date_filter_group.isVisible():
            options["filters"]["start_date"] = self.start_date_input.date().toString("yyyy-MM-dd HH:MM:SS")
            options["filters"]["end_date"] = self.end_date_input.date().toString("yyyy-MM-dd HH:MM:SS")

        if self.os_filter_group.isVisible():
            options["filters"]["status"] = self.os_status_combo.currentData()
            options["filters"]["assigned_user_id"] = self.os_assigned_user_combo.currentData()

        return options


class MainApplication(QMainWindow):
    """
    Classe principal da aplicação, responsável pela interface gráfica e gerenciamento de telas.
    """
    def __init__(self):
        super().__init__()
        self.current_user = None
        self.setWindowTitle("Sistema de Gestão Spec")
        self.setMinimumSize(QSize(1366, 768))
        
        self._initialize_app_components()
        self._load_and_apply_settings()
        self._setup_ui()
        self._setup_connections()
        self._initial_login_flow()

    def _initialize_app_components(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        os.makedirs(REPORTS_DIR, exist_ok=True)
        os.makedirs(os.path.join(script_dir, 'assets'), exist_ok=True)

        self._run_database_migrations()
        
        self.settings_manager = SettingsManager()
        self.user_manager = UserManager()
        self.customer_manager = CustomerManager()
        self.supplier_manager = SupplierManager()
        self.notification_manager = NotificationManager()
        self.stock_manager = StockManager(self.notification_manager)
        self.sale_manager = SaleManager(self.stock_manager)
        self.service_order_manager = ServiceOrderManager(self.stock_manager, self.user_manager)
        self.financial_manager = FinancialManager()
        self.report_manager = ReportManager(DATA_DIR, REPORTS_DIR, self.user_manager)
        self.api_integrations = APIIntegrations()
        logger.info("Componentes da aplicação inicializados.")


    def _run_database_migrations(self):
        logger.info("A executar migrações da base de dados, se necessário...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT entity_id, entity_type FROM notifications LIMIT 1")
            logger.debug("Tabela 'notifications' já tem colunas entity_id, entity_type.")
        except sqlite3.OperationalError:
            logger.info("  - A migrar tabela 'notifications' (adicionando entity_id, entity_type)...")
            try:
                Notification._create_table()
                
                cursor.execute("PRAGMA table_info(notifications)")
                cols = [col[1] for col in cursor.fetchall()]
                if 'entity_id' not in cols:
                    cursor.execute("ALTER TABLE notifications ADD COLUMN entity_id INTEGER")
                if 'entity_type' not in cols:
                    cursor.execute("ALTER TABLE notifications ADD COLUMN entity_type TEXT")
                conn.commit()
                logger.info("  - Migração da tabela 'notifications' concluída com sucesso.")
            except sqlite3.Error as e:
                logger.error(f"  - ERRO ao alterar a tabela 'notifications': {e}", exc_info=True)
                conn.rollback()
        
        try:
            cursor.execute("SELECT start_date, end_date, payment_status FROM service_orders LIMIT 1")
            logger.debug("Tabela 'service_orders' já tem colunas de data e status de pagamento.")
        except sqlite3.OperationalError:
            logger.info("  - A migrar tabela 'service_orders' (adicionando start_date, end_date, payment_status)...")
            try:
                cursor.execute("ALTER TABLE service_orders ADD COLUMN start_date TEXT")
                cursor.execute("ALTER TABLE service_orders ADD COLUMN end_date TEXT")
                cursor.execute("ALTER TABLE service_orders ADD COLUMN payment_status TEXT DEFAULT 'Pendente'")
                conn.commit()
                logger.info("  - Migração da tabela 'service_orders' concluída com sucesso.")
            except sqlite3.Error as e:
                logger.error(f"  - ERRO ao alterar a tabela 'service_orders': {e}", exc_info=True)
                conn.rollback()

        # NOVA MIGRAÇÃO: Adicionar coluna 'is_quote' à tabela 'sales'
        try:
            cursor.execute("SELECT is_quote FROM sales LIMIT 1")
            logger.debug("Tabela 'sales' já tem a coluna 'is_quote'.")
        except sqlite3.OperationalError:
            logger.info("  - A migrar tabela 'sales' (adicionando is_quote)...")
            try:
                cursor.execute("ALTER TABLE sales ADD COLUMN is_quote BOOLEAN DEFAULT 0")
                conn.commit()
                logger.info("  - Migração da tabela 'sales' (is_quote) concluída com sucesso.")
            except sqlite3.Error as e:
                logger.error(f"  - ERRO ao alterar a tabela 'sales' (is_quote): {e}", exc_info=True)
                conn.rollback()


        conn.close()
        self._create_db_tables_if_not_exist()
        logger.info("Verificação e migração de tabelas de banco de dados concluídas.")


    def _create_db_tables_if_not_exist(self):
        models = [User, Customer, Supplier, Part, Sale, SaleItem, ServiceOrder, ServiceOrderItem, FinancialTransaction, Notification, Report, Setting]
        for model in models:
            try:
                model._create_table()
                logger.debug(f"Verificada/criada tabela para o modelo: {model.__name__}")
            except Exception as e:
                logger.critical(f"Erro CRÍTICO ao criar tabela para {model.__name__}: {e}", exc_info=True)
                print(f"Erro ao criar tabela para {model.__name__}: {e}")

    def _load_and_apply_settings(self):
        theme_color = self.settings_manager.get_setting("theme_color", "#0d47a1")
        self._apply_theme(theme_color)
        logger.info(f"Tema aplicado com cor: {theme_color}")
        
        logo_path = self.settings_manager.get_setting("logo_path")
        if hasattr(self, 'logo_label') and logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.logo_label.setPixmap(pixmap.scaled(180, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logger.info(f"Logótipo carregado de: {logo_path}")
        elif hasattr(self, 'logo_label'):
             self.logo_label.setText("Logótipo")
             logger.info("Logótipo não encontrado ou não configurado, usando texto padrão.")


    def _apply_theme(self, base_color_hex):
        self.setStyleSheet(f"""
            QMainWindow, QDialog {{ background-color: #2b2b2b; color: #d3d3d3; }}
            QWidget {{ background-color: #3c3f41; color: #d3d3d3; font-family: Arial; font-size: 10pt; }}
            QGroupBox {{ font-weight: bold; border: 1px solid #4a4d4f; border-radius: 5px; margin-top: 1ex; padding-top: 5px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }}
            QLabel {{ font-weight: bold; }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, UppercaseLineEdit, ValidatedLineEdit {{ background-color: #45494a; border: 1px solid #5a5d5f; border-radius: 3px; padding: 5px; min-height: 20px; }}
            QPushButton {{ background-color: {base_color_hex}; color: white; font-weight: bold; border: none; padding: 8px 12px; border-radius: 3px; }}
            QPushButton:hover {{ background-color: {self._adjust_color(base_color_hex, 20)}; }}
            QPushButton:pressed {{ background-color: {self._adjust_color(base_color_hex, 40)}; }}
            QTableWidget {{ background-color: #313335; border: 1px solid #4a4d4f; gridline-color: #4a4d4f; selection-background-color: {base_color_hex}; }}
            QHeaderView::section {{ background-color: #45494a; padding: 5px; border: 1px solid #4a4d4f; font-weight: bold; }}
            QWidget#sidebar {{ background-color: #313335; }}
            QWidget#sidebar QPushButton {{ text-align: left; padding: 12px; border: none; font-size: 11pt; color: #d3d3d3; background-color: transparent; }}
            QWidget#sidebar QPushButton:checked, QWidget#sidebar QPushButton:hover {{ background-color: #45494a; font-weight: bold; border-left: 3px solid {base_color_hex}; }}
        """)
        
    def _adjust_color(self, color_hex, amount):
        color_hex = color_hex.lstrip('#')
        rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = tuple(max(0, min(255, c + amount)) for c in rgb)
        return f"#{''.join([f'{c:02x}' for c in new_rgb])}"

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.sidebar = self._create_sidebar()
        self.main_layout.addWidget(self.sidebar)
        
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(content_area, 1)
        
        self._create_all_screens()
        
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        
        self.notification_count_label = QLabel("Notificações: 0")
        self.statusBar.addPermanentWidget(self.notification_count_label)
        
        logger.info("Interface do usuário configurada.")

        
    def _create_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.logo_label = QLabel("Logótipo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setContentsMargins(10, 10, 10, 20)
        self.logo_label.setMinimumHeight(80)
        layout.addWidget(self.logo_label)

        self.nav_buttons = {}
        nav_items = {
            "Dashboard": "SP_DesktopIcon", 
            "Clientes": "SP_DirIcon", 
            "Fornecedores": "SP_DriveNetIcon", 
            "Peças/Estoque": "SP_FileDialogListView", 
            "Vendas": "SP_DialogApplyButton", 
            "Ordens de Serviço": "SP_FileDialogDetailedView", 
            "Financeiro": "SP_FileDialogInfoView", 
            "Relatórios": "SP_FileIcon", 
            "Gerenciar Usuários": "SP_ComputerIcon", 
            "Configurações": "SP_FileDialogOptionsButton",
            "Notificações": "SP_MessageBoxWarningIcon"
        }
        
        for name, icon_name in nav_items.items():
            btn = QPushButton(f" {name}")
            icon = self.style().standardIcon(getattr(QStyle, icon_name, QStyle.SP_CustomBase))
            btn.setIcon(icon)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            layout.addWidget(btn)
            self.nav_buttons[name] = btn
        
        layout.addStretch()
        
        self.btn_logout = QPushButton(" Sair (Logout)")
        self.btn_logout.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        layout.addWidget(self.btn_logout)

        if self.nav_buttons:
            list(self.nav_buttons.values())[0].setChecked(True)
        
        return sidebar

    def _create_all_screens(self):
        self.screens = {
            "Dashboard": self._create_dashboard_screen(),
            "Clientes": self._create_customers_screen(),
            "Fornecedores": self._create_suppliers_screen(),
            "Peças/Estoque": self._create_parts_screen(),
            "Vendas": self._create_sales_screen(),
            "Ordens de Serviço": self._create_service_orders_screen(),
            "Financeiro": self._create_financial_screen(),
            "Relatórios": self._create_reports_screen(),
            "Gerenciar Usuários": self._create_users_screen(),
            "Configurações": self._create_settings_screen(),
            "Notificações": self._create_notifications_screen()
        }
        for name, screen in self.screens.items():
            self.stacked_widget.addWidget(screen)

    def _create_generic_screen_layout(self, screen_name, add_extra_buttons=None, add_filters=False):
        """
        Cria um layout padrão para telas com tabela, busca e botões CRUD.
        Opcionalmente adiciona filtros e botões extras.
        """
        screen = QWidget()
        layout = QVBoxLayout(screen)

        title = QLabel(screen_name)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        layout.addWidget(title)

        controls_group = QGroupBox("Ações")
        controls_layout = QHBoxLayout(controls_group)
        
        search_input = QLineEdit(placeholderText=f"Buscar em {screen_name}...")
        controls_layout.addWidget(search_input)
        
        # Adiciona widgets de filtro se solicitado
        filter_widgets = {}
        if add_filters:
            if screen_name == "Vendas":
                filter_widgets['start_date'] = QDateEdit(calendarPopup=True); filter_widgets['start_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['start_date'].setDate(QDate.currentDate().addYears(-1));
                filter_widgets['end_date'] = QDateEdit(calendarPopup=True); filter_widgets['end_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['end_date'].setDate(QDate.currentDate())
                filter_widgets['status_combo'] = QComboBox(); filter_widgets['status_combo'].addItem("Todos os Status", userData=None); filter_widgets['status_combo'].addItems(["PENDENTE PAGAMENTO", "PAGA", "CANCELADA", "ORÇAMENTO"]);
                filter_widgets['type_combo'] = QComboBox(); filter_widgets['type_combo'].addItem("Todos os Tipos", userData=None); filter_widgets['type_combo'].addItems(["Venda", "Orçamento"])

                controls_layout.addWidget(QLabel("De:"))
                controls_layout.addWidget(filter_widgets['start_date'])
                controls_layout.addWidget(QLabel("Até:"))
                controls_layout.addWidget(filter_widgets['end_date'])
                controls_layout.addWidget(QLabel("Status:"))
                controls_layout.addWidget(filter_widgets['status_combo'])
                controls_layout.addWidget(QLabel("Tipo:"))
                controls_layout.addWidget(filter_widgets['type_combo'])


            elif screen_name == "Ordens de Serviço":
                filter_widgets['start_date'] = QDateEdit(calendarPopup=True); filter_widgets['start_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['start_date'].setDate(QDate.currentDate().addYears(-1));
                filter_widgets['end_date'] = QDateEdit(calendarPopup=True); filter_widgets['end_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['end_date'].setDate(QDate.currentDate())
                filter_widgets['status_combo'] = QComboBox(); filter_widgets['status_combo'].addItem("Todos os Status", userData=None); filter_widgets['status_combo'].addItems(["Pendente", "Em Andamento", "Concluída", "Cancelada"])
                filter_widgets['assigned_user_combo'] = QComboBox(); filter_widgets['assigned_user_combo'].addItem("Todos os Responsáveis", userData=None)
                
                controls_layout.addWidget(QLabel("De:"))
                controls_layout.addWidget(filter_widgets['start_date'])
                controls_layout.addWidget(QLabel("Até:"))
                controls_layout.addWidget(filter_widgets['end_date'])
                controls_layout.addWidget(QLabel("Status:"))
                controls_layout.addWidget(filter_widgets['status_combo'])
                controls_layout.addWidget(QLabel("Responsável:"))
                controls_layout.addWidget(filter_widgets['assigned_user_combo'])

            elif screen_name == "Financeiro":
                filter_widgets['start_date'] = QDateEdit(calendarPopup=True); filter_widgets['start_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['start_date'].setDate(QDate.currentDate().addYears(-1));
                filter_widgets['end_date'] = QDateEdit(calendarPopup=True); filter_widgets['end_date'].setDisplayFormat("dd/MM/yyyy")
                filter_widgets['end_date'].setDate(QDate.currentDate())
                filter_widgets['type_combo'] = QComboBox(); filter_widgets['type_combo'].addItem("Todos os Tipos", userData=None); filter_widgets['type_combo'].addItems(["Receita", "Despesa"])

                controls_layout.addWidget(QLabel("De:"))
                controls_layout.addWidget(filter_widgets['start_date'])
                controls_layout.addWidget(QLabel("Até:"))
                controls_layout.addWidget(filter_widgets['end_date'])
                controls_layout.addWidget(QLabel("Tipo:"))
                controls_layout.addWidget(filter_widgets['type_combo'])
            
            # Armazena os widgets de filtro como atributos do objeto screen
            setattr(self, f"filter_{screen_name.lower().replace(' ', '_')}_widgets", filter_widgets)
        
        controls_layout.addStretch()

        add_button = QPushButton(" Adicionar")
        add_button.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        edit_button = QPushButton(" Editar")
        edit_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        delete_button = QPushButton(" Remover")
        delete_button.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        
        if add_extra_buttons:
            for btn in add_extra_buttons:
                controls_layout.addWidget(btn)
        
        controls_layout.addWidget(add_button)
        controls_layout.addWidget(edit_button)
        controls_layout.addWidget(delete_button)
        layout.addWidget(controls_group)

        table = QTableWidget()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        # Ajusta os nomes dos atributos para serem consistentes e legíveis em Português
        clean_name = screen_name.lower().replace(' ', '_').replace('/', '_')
        # Mapeamento de nomes de tela para nomes de atributos internos
        name_map = {
            "clientes": "clientes",
            "fornecedores": "fornecedores",
            "peças_estoque": "peças_estoque",
            "vendas": "vendas",
            "ordens_de_serviço": "ordens_de_serviço",
            "financeiro": "financeiro",
            "gerenciar_usuários": "gerenciar_usuários",
            "relatórios": "relatórios",
            "notificações": "notificações"
        }
        attr_name_prefix = name_map.get(clean_name, clean_name)

        setattr(self, f"{attr_name_prefix}_table", table)
        setattr(self, f"search_{attr_name_prefix}_input", search_input)
        setattr(self, f"add_{attr_name_prefix}_button", add_button)
        setattr(self, f"edit_{attr_name_prefix}_button", edit_button)
        setattr(self, f"delete_{attr_name_prefix}_button", delete_button)
        
        return screen

    # --- Criação das Telas Específicas ---
    def _create_dashboard_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        
        label = QLabel("Dashboard")
        label.setFont(QFont("Arial", 24, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        self.dashboard_stats_label = QLabel("Carregando estatísticas...")
        self.dashboard_stats_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.dashboard_stats_label)
        
        self.dashboard_low_stock_label = QLabel("Itens com estoque baixo: 0")
        self.dashboard_low_stock_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.dashboard_low_stock_label)

        self.dashboard_balance_label = QLabel("Balanço Financeiro: R$ 0.00")
        self.dashboard_balance_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.dashboard_balance_label)

        return screen

    def _create_customers_screen(self):
        screen = self._create_generic_screen_layout("Clientes")
        self.clientes_table.setColumnCount(9)
        self.clientes_table.setHorizontalHeaderLabels(["ID", "Nome", "CPF/CNPJ", "Telefone", "Email", "Rua", "Nº", "Bairro", "CEP"])
        return screen

    def _create_suppliers_screen(self):
        screen = self._create_generic_screen_layout("Fornecedores")
        self.fornecedores_table.setColumnCount(7)
        self.fornecedores_table.setHorizontalHeaderLabels(["ID", "Nome", "CNPJ", "Contato", "Telefone", "Email", "Endereço"])
        return screen

    def _create_parts_screen(self):
        self.add_stock_button = QPushButton("Adicionar Estoque")
        self.remove_stock_button = QPushButton("Remover Estoque")
        screen = self._create_generic_screen_layout("Peças/Estoque", add_extra_buttons=[self.add_stock_button, self.remove_stock_button])
        self.peças_estoque_table.setColumnCount(13)
        self.peças_estoque_table.setHorizontalHeaderLabels(["ID", "Nome", "Nº Peça", "Fabricante", "Preço", "Custo", "Estoque", "Mínimo", "Localização", "Fornecedor", "Categoria", "Cód. Original", "Cód. Barras"])
        return screen

    def _create_sales_screen(self):
        self.sale_options_button = QPushButton("Opções")
        screen = self._create_generic_screen_layout("Vendas", add_extra_buttons=[self.sale_options_button], add_filters=True)
        self.vendas_table.setColumnCount(8)
        self.vendas_table.setHorizontalHeaderLabels(["ID", "Data", "Cliente", "Total", "Status", "Tipo", "Pagamento", "Registrado por"])
        return screen

    def _create_service_orders_screen(self):
        self.so_options_button = QPushButton("Opções")
        screen = self._create_generic_screen_layout("Ordens de Serviço", add_extra_buttons=[self.so_options_button], add_filters=True)
        self.ordens_de_serviço_table.setColumnCount(12)
        self.ordens_de_serviço_table.setHorizontalHeaderLabels(["ID", "Data OS", "Cliente", "Placa", "Modelo", "Ano", "Status", "Pagamento", "Total", "M. Obra", "Peças", "Responsável"])
        return screen

    def _create_financial_screen(self):
        screen = self._create_generic_screen_layout("Financeiro", add_filters=True)
        self.financeiro_table.setColumnCount(6)
        self.financeiro_table.setHorizontalHeaderLabels(["ID", "Data", "Valor", "Tipo", "Categoria", "Descrição"])
        return screen

    def _create_reports_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        
        title = QLabel("Relatórios")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        layout.addWidget(title)

        self.generate_report_button = QPushButton(" Gerar Novo Relatório")
        self.generate_report_button.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        layout.addWidget(self.generate_report_button, alignment=Qt.AlignLeft)

        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(5)
        self.reports_table.setHorizontalHeaderLabels(["ID", "Tipo", "Data Geração", "Gerado Por", "Caminho do Ficheiro"])
        self.reports_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.reports_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.reports_table)
        return screen

    def _create_users_screen(self):
        screen = self._create_generic_screen_layout("Gerenciar Usuários")
        self.gerenciar_usuários_table.setColumnCount(4)
        self.gerenciar_usuários_table.setHorizontalHeaderLabels(["ID", "Utilizador", "Função", "Ativo"])
        return screen

    def _create_notifications_screen(self):
        """Nova tela para exibir e gerenciar notificações."""
        screen = QWidget()
        layout = QVBoxLayout(screen)

        title = QLabel("Notificações")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        layout.addWidget(title)

        # Botões de ação para notificações
        notification_actions_layout = QHBoxLayout()
        self.mark_as_read_button = QPushButton("Marcar como Lida")
        self.mark_all_as_read_button = QPushButton("Marcar Todas como Lidas")
        self.delete_notification_button = QPushButton("Remover Notificação")

        notification_actions_layout.addWidget(self.mark_as_read_button)
        notification_actions_layout.addWidget(self.mark_all_as_read_button)
        notification_actions_layout.addWidget(self.delete_notification_button)
        notification_actions_layout.addStretch()
        layout.addLayout(notification_actions_layout)

        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(5)
        self.notifications_table.setHorizontalHeaderLabels(["ID", "Data", "Tipo", "Mensagem", "Lida?"])
        self.notifications_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.notifications_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notifications_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.notifications_table.setAlternatingRowColors(True)
        layout.addWidget(self.notifications_table)

        return screen

    def _create_settings_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignTop)
        
        title = QLabel("Configurações")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        layout.addWidget(title)

        settings_group = QGroupBox("Personalização da Aparência")
        form_layout = QFormLayout(settings_group)
        layout.addWidget(settings_group)

        logo_layout = QHBoxLayout()
        self.current_logo_path_label = QLineEdit()
        self.current_logo_path_label.setReadOnly(True)
        self.select_logo_button = QPushButton("Selecionar Logótipo...")
        logo_layout.addWidget(self.current_logo_path_label)
        logo_layout.addWidget(self.select_logo_button)
        form_layout.addRow("Ficheiro do Logótipo:", logo_layout)

        color_layout = QHBoxLayout()
        self.theme_color_label = QLabel()
        self.theme_color_label.setFixedSize(100, 25)
        self.theme_color_label.setAutoFillBackground(True)
        self.select_color_button = QPushButton("Selecionar Cor do Tema...")
        color_layout.addWidget(self.theme_color_label)
        color_layout.addWidget(self.select_color_button)
        form_layout.addRow("Cor Principal:", color_layout)

        email_settings_group = QGroupBox("Configurações de E-mail (SMTP)")
        email_form_layout = QFormLayout(email_settings_group)
        layout.addWidget(email_settings_group)

        self.smtp_server_input = QLineEdit(placeholderText="Ex: smtp.gmail.com")
        email_form_layout.addRow("Servidor SMTP:", self.smtp_server_input)

        self.smtp_port_input = QSpinBox(); self.smtp_port_input.setMinimum(1); self.smtp_port_input.setMaximum(65535); self.smtp_port_input.setValue(587)
        email_form_layout.addRow("Porta SMTP:", self.smtp_port_input)

        self.smtp_username_input = QLineEdit(placeholderText="Seu e-mail")
        email_form_layout.addRow("Usuário SMTP:", self.smtp_username_input)

        self.smtp_password_input = QLineEdit(placeholderText="Senha ou Senha de App", echoMode=QLineEdit.Password)
        email_form_layout.addRow("Senha SMTP:", self.smtp_password_input)

        self.smtp_use_tls_checkbox = QCheckBox("Usar TLS/SSL")
        self.smtp_use_tls_checkbox.setChecked(True)
        email_form_layout.addRow("Criptografia:", self.smtp_use_tls_checkbox)

        self.test_email_button = QPushButton("Testar Envio de Email"); self.test_email_button.clicked.connect(self._test_email_send)
        email_form_layout.addRow(self.test_email_button)

        # Botões de Backup e Restauração
        backup_group = QGroupBox("Backup e Restauração")
        backup_layout = QVBoxLayout(backup_group)
        self.create_backup_button = QPushButton("Criar Backup Agora")
        self.restore_backup_button = QPushButton("Restaurar Backup")
        backup_layout.addWidget(self.create_backup_button)
        backup_layout.addWidget(self.restore_backup_button)
        layout.addWidget(backup_group)


        self.save_settings_button = QPushButton("Salvar e Aplicar")
        layout.addWidget(self.save_settings_button, 0, Qt.AlignLeft)
        
        return screen

    def _populate_settings_fields(self):
        if hasattr(self, 'current_logo_path_label'):
            logo_path = self.settings_manager.get_setting("logo_path", "Nenhum logótipo selecionado.")
            self.current_logo_path_label.setText(logo_path)
            
            theme_color_hex = self.settings_manager.get_setting("theme_color", "#0d47a1")
            palette = self.theme_color_label.palette()
            palette.setColor(QPalette.Window, QColor(theme_color_hex))
            self.theme_color_label.setPalette(palette)
            self.theme_color_label.setText(theme_color_hex)
            
            self.smtp_server_input.setText(self.settings_manager.get_setting("smtp_server", ""))
            self.smtp_port_input.setValue(int(self.settings_manager.get_setting("smtp_port", 587)))
            self.smtp_username_input.setText(self.settings_manager.get_setting("smtp_username", ""))
            self.smtp_password_input.setPlaceholderText("Deixar em branco para não alterar")
            self.smtp_use_tls_checkbox.setChecked(self.settings_manager.get_setting("smtp_use_tls", "True").lower() == "true")
            logger.info("Campos de configurações populados.")


    def _select_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar Logótipo", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            assets_dir = os.path.join(script_dir, 'assets')
            filename = f"logo{os.path.splitext(file_path)[1]}"
            new_path = os.path.join(assets_dir, filename)
            try:
                shutil.copy(file_path, new_path)
                self.current_logo_path_label.setText(new_path)
                self.statusBar.showMessage(f"Logótipo selecionado e copiado: {filename}", 5000)
                logger.info(f"Logótipo selecionado e copiado para: {new_path}")
            except Exception as e:
                QMessageBox.warning(self, "Erro ao Copiar", f"Não foi possível guardar o logótipo: {e}")
                logger.error(f"Erro ao copiar logótipo de {file_path} para {new_path}: {e}", exc_info=True)


    def _select_theme_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.theme_color_label.setText(color.name())
            palette = self.theme_color_label.palette()
            palette.setColor(QPalette.Window, color)
            self.theme_color_label.setPalette(palette)
            self.statusBar.showMessage(f"Cor do tema selecionada: {color.name()}", 3000)
            logger.info(f"Cor do tema selecionada: {color.name()}")


    def _save_settings(self):
        logo_path = self.current_logo_path_label.text()
        if os.path.exists(logo_path):
            self.settings_manager.set_setting("logo_path", logo_path)
        
        color_name = self.theme_color_label.text()
        if color_name:
            self.settings_manager.set_setting("theme_color", color_name)

        self.settings_manager.set_setting("smtp_server", self.smtp_server_input.text().strip())
        self.settings_manager.set_setting("smtp_port", str(self.smtp_port_input.value()))
        self.settings_manager.set_setting("smtp_username", self.smtp_username_input.text().strip())
        if self.smtp_password_input.text():
            self.settings_manager.set_setting("smtp_password", self.smtp_password_input.text())
        self.settings_manager.set_setting("smtp_use_tls", str(self.smtp_use_tls_checkbox.isChecked()))


        QMessageBox.information(self, "Sucesso", "Configurações salvas. A aparência foi atualizada.")
        self._load_and_apply_settings()
        self.load_all_data()
        logger.info("Configurações salvas e aplicadas.")


    def _test_email_send(self):
        test_email_to = self.smtp_username_input.text().strip()
        smtp_server = self.smtp_server_input.text().strip()
        smtp_port = self.smtp_port_input.value()
        smtp_username = self.smtp_username_input.text().strip()
        smtp_password = self.smtp_password_input.text()
        smtp_use_tls = self.smtp_use_tls_checkbox.isChecked()

        if not test_email_to:
            QMessageBox.warning(self, "Erro de Configuração", "Por favor, preencha o campo 'Usuário SMTP' para enviar um e-mail de teste.")
            logger.warning("Tentativa de testar envio de email sem destinatário (usuário SMTP).")
            self.smtp_username_input.setFocus()
            return
        if not smtp_server:
             QMessageBox.warning(self, "Configuração de E-mail", "O campo 'Servidor SMTP' deve ser preenchido para testar o envio.")
             logger.warning("Tentativa de testar envio de email com servidor SMTP vazio.")
             self.smtp_server_input.setFocus()
             return
        if not smtp_username:
             QMessageBox.warning(self, "Configuração de E-mail", "O campo 'Usuário SMTP' deve ser preenchido para testar o envio.")
             logger.warning("Tentativa de testar envio de email com usuário SMTP vazio.")
             self.smtp_username_input.setFocus()
             return
        if not smtp_password:
             QMessageBox.warning(self, "Configuração de E-mail", "O campo 'Senha SMTP' deve ser preenchido para testar o envio.")
             logger.warning("Tentativa de testar envio de email com senha SMTP vazia.")
             self.smtp_password_input.setFocus()
             return


        reply = QMessageBox.question(self, "Confirmar Envio", f"Deseja enviar um e-mail de teste para '{test_email_to}'?")
        if reply == QMessageBox.Yes:
            self.statusBar.showMessage("Enviando e-mail de teste...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            logger.info(f"Iniciando teste de envio de e-mail para: {test_email_to}")
            try:
                success, msg = send_email(test_email_to, "Email de Teste - Sistema Spec", "Este é um email de teste enviado do Sistema Spec.",
                                       smtp_server, smtp_port, smtp_username, smtp_password, smtp_use_tls)
                QMessageBox.information(self, "Resultado do Teste", msg)
                if success:
                    logger.info(f"Teste de e-mail para {test_email_to} bem-sucedido.")
                else:
                    logger.error(f"Teste de e-mail para {test_email_to} falhou: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Erro de Envio de Email", f"Ocorreu um erro inesperado durante o teste de e-mail: {e}")
                logger.critical(f"Erro inesperado durante o teste de e-mail para {test_email_to}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()

    def create_backup_dialog(self):
        """Cria um backup do banco de dados e exibe o resultado."""
        self.statusBar.showMessage("Criando backup...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, msg = create_backup()
            if success:
                QMessageBox.information(self, "Backup Criado", msg)
                logger.info(f"Backup criado com sucesso: {msg}")
            else:
                QMessageBox.warning(self, "Erro no Backup", msg)
                logger.error(f"Falha ao criar backup: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro inesperado ao criar backup: {e}")
            logger.critical(f"Erro inesperado ao criar backup: {e}", exc_info=True)
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar.clearMessage()

    def restore_backup_dialog(self):
        """Permite ao usuário selecionar um arquivo de backup e restaurá-lo."""
        available_backups = get_available_backups()
        if not available_backups:
            QMessageBox.information(self, "Restaurar Backup", "Nenhum arquivo de backup encontrado.")
            return

        # Cria um QInputDialog com um QComboBox para selecionar o backup
        backup_files = [os.path.basename(f) for f in available_backups]
        item, ok = QInputDialog.getItem(self, "Restaurar Backup", "Selecione um arquivo de backup:", backup_files, 0, False)

        if ok and item:
            selected_file_path = next(f for f in available_backups if os.path.basename(f) == item)
            reply = QMessageBox.question(self, "Confirmar Restauração", 
                                         f"Tem certeza que deseja restaurar o banco de dados a partir de:\n\n{item}\n\n"
                                         "Esta ação irá substituir o banco de dados atual e não pode ser desfeita. "
                                         "É altamente recomendável fazer um backup antes de restaurar.")
            if reply == QMessageBox.Yes:
                self.statusBar.showMessage(f"Restaurando backup de {item}...", 0)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    success, msg = restore_backup(selected_file_path)
                    if success:
                        QMessageBox.information(self, "Restauração Concluída", msg)
                        logger.info(f"Backup restaurado com sucesso de: {selected_file_path}")
                        self.load_all_data() # Recarrega todos os dados após a restauração
                    else:
                        QMessageBox.warning(self, "Erro na Restauração", msg)
                        logger.error(f"Falha ao restaurar backup de {selected_file_path}: {msg}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro inesperado ao restaurar backup: {e}")
                    logger.critical(f"Erro inesperado ao restaurar backup de {selected_file_path}: {e}", exc_info=True)
                finally:
                    QApplication.restoreOverrideCursor()
                    self.statusBar.clearMessage()


    def showEvent(self, event):
        super().showEvent(event)
        self._populate_settings_fields()
        if self.current_user:
            self.load_all_data()
            self.update_notification_count()
            logger.info("Evento ShowEvent disparado, dados e configurações carregados.")


    def _initial_login_flow(self):
        initial_admin = User.get_by_username("admin")
        if not initial_admin:
            self.user_manager.add_user("admin", "admin", UserRole.ADMIN.value)
            QMessageBox.information(self, "Primeiro Uso", "Usuário 'admin' com senha 'admin' foi criado. Por favor, faça login.")
            logger.info("Usuário admin inicial 'admin' criado.")
        
        self.show_login_dialog()
        logger.info("Fluxo de login inicial iniciado.")


    def show_login_dialog(self):
        self.hide()
        login_dialog = LoginDialog(self.user_manager, self)
        login_dialog.login_successful.connect(self._handle_login_success)
        
        if login_dialog.exec() == QDialog.Rejected and not self.current_user:
            logger.info("Login cancelado ou falhou. Fechando aplicação.")
            self.close()

    def _handle_login_success(self, user):
        self.current_user = user
        self.setWindowTitle(f"Sistema Spec - Logado como: {user.username} ({user.role})")
        self.update_ui_permissions()
        self.load_all_data()
        self.show()
        self.statusBar.showMessage(f"Bem-vindo, {self.current_user.username}!", 5000)
        self.update_notification_count()
        logger.info(f"Usuário {user.username} logado e UI atualizada.")

    # --- Métodos CRUD para Usuários ---
    def add_user(self):
        logger.info("Abrindo diálogo para adicionar novo usuário.")
        dialog = AddEditUserDialog(parent=self)
        if dialog.exec():
            data = dialog.get_user_data()
            if data:
                success, msg = self.user_manager.add_user(data['username'], data['password'], data['role'], data['is_active'])
                if success: 
                    self.load_users()
                    self.statusBar.showMessage(f"Utilizador '{data['username']}' adicionado com sucesso.", 5000)
                    logger.info(f"Utilizador '{data['username']}' adicionado com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.warning(f"Falha ao adicionar usuário '{data['username']}': {msg}")

    def edit_user(self):
        selected_rows = self.gerenciar_usuários_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um utilizador para editar.")
            logger.warning("Tentativa de editar usuário sem seleção.")
            return
        
        user_id = int(self.gerenciar_usuários_table.item(selected_rows[0].row(), 0).text())
        user = self.user_manager.get_user_by_id(user_id)
        
        if user:
            logger.info(f"Abrindo diálogo para editar usuário ID: {user_id} ({user.username}).")
            dialog = AddEditUserDialog(user=user, parent=self)
            if dialog.exec():
                data = dialog.get_user_data()
                if data:
                    success, msg = self.user_manager.update_user(user_id, data['username'], data['role'], data['is_active'], data['password'])
                    if success: 
                        self.load_users()
                        self.statusBar.showMessage(f"Utilizador '{data['username']}' atualizado com sucesso.", 5000)
                        logger.info(f"Utilizador ID {user_id} atualizado com sucesso para '{data['username']}'.")
                    else:
                        QMessageBox.warning(self, "Resultado", msg)
                        logger.warning(f"Falha ao atualizar usuário ID {user_id}: {msg}")

    def delete_user(self):
        selected_rows = self.gerenciar_usuários_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um utilizador para apagar.")
            logger.warning("Tentativa de deletar usuário sem seleção.")
            return
        
        user_id = int(self.gerenciar_usuários_table.item(selected_rows[0].row(), 0).text())
        
        if self.current_user and self.current_user.id == user_id:
            QMessageBox.warning(self, "Ação Inválida", "Não pode apagar o seu próprio utilizador.")
            logger.warning(f"Tentativa de auto-deleção pelo usuário ID {user_id}.")
            return
        
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar o utilizador ID {user_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para usuário ID: {user_id}.")
            success, msg = self.user_manager.delete_user(user_id)
            if success: 
                self.load_users()
                self.statusBar.showMessage(f"Utilizador ID {user_id} apagado com sucesso.", 5000)
                logger.info(f"Utilizador ID {user_id} apagado com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.error(f"Falha ao deletar usuário ID {user_id}: {msg}")


    # --- Métodos CRUD para Clientes ---
    def add_customer(self):
        logger.info("Abrindo diálogo para adicionar novo cliente.")
        dialog = AddEditCustomerDialog(api_integrations=self.api_integrations, parent=self)
        if dialog.exec():
            data = dialog.get_customer_data()
            if data:
                success, msg = self.customer_manager.add_customer(**data)
                if success: 
                    self.load_customers()
                    self.statusBar.showMessage(f"Cliente '{data['name']}' adicionado com sucesso.", 5000)
                    logger.info(f"Cliente '{data['name']}' adicionado com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.warning(f"Falha ao adicionar cliente '{data['name']}': {msg}")


    def edit_customer(self):
        selected_rows = self.clientes_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um cliente para editar.")
            logger.warning("Tentativa de editar cliente sem seleção.")
            return
        
        customer_id = int(self.clientes_table.item(selected_rows[0].row(), 0).text())
        customer = self.customer_manager.get_customer_by_id(customer_id)
        
        if customer:
            logger.info(f"Abrindo diálogo para editar cliente ID: {customer_id} ({customer.name}).")
            dialog = AddEditCustomerDialog(customer=customer, api_integrations=self.api_integrations, parent=self)
            if dialog.exec():
                data = dialog.get_customer_data()
                if data:
                    success, msg = self.customer_manager.update_customer(customer_id, **data)
                    if success: 
                        self.load_customers()
                        self.statusBar.showMessage(f"Cliente '{data['name']}' atualizado com sucesso.", 5000)
                        logger.info(f"Cliente ID {customer_id} atualizado com sucesso para '{data['name']}'.")
                    else:
                        QMessageBox.warning(self, "Resultado", msg)
                        logger.warning(f"Falha ao atualizar cliente ID {customer_id}: {msg}")
    
    def delete_customer(self):
        selected_rows = self.clientes_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um cliente para apagar.")
            logger.warning("Tentativa de deletar cliente sem seleção.")
            return
        
        customer_id = int(self.clientes_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar o cliente ID {customer_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para cliente ID: {customer_id}.")
            success, msg = self.customer_manager.delete_customer(customer_id)
            if success: 
                self.load_customers()
                self.statusBar.showMessage(f"Cliente ID {customer_id} apagado com sucesso.", 5000)
                logger.info(f"Cliente ID {customer_id} apagado com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.error(f"Falha ao deletar cliente ID {customer_id}: {msg}")
            
    # --- Métodos CRUD para Fornecedores ---
    def add_supplier(self):
        logger.info("Abrindo diálogo para adicionar novo fornecedor.")
        dialog = AddEditSupplierDialog(parent=self)
        if dialog.exec():
            data = dialog.get_supplier_data()
            if data:
                success, msg = self.supplier_manager.add_supplier(**data)
                if success:
                    self.load_suppliers()
                    self.statusBar.showMessage(f"Fornecedor '{data['name']}' adicionado com sucesso.", 5000)
                    logger.info(f"Fornecedor '{data['name']}' adicionado com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.warning(f"Falha ao adicionar fornecedor '{data['name']}': {msg}")

    def edit_supplier(self):
        selected_rows = self.fornecedores_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um fornecedor para editar.")
            logger.warning("Tentativa de editar fornecedor sem seleção.")
            return
        
        supplier_id = int(self.fornecedores_table.item(selected_rows[0].row(), 0).text())
        supplier = self.supplier_manager.get_supplier_by_id(supplier_id)
        if supplier:
            logger.info(f"Abrindo diálogo para editar fornecedor ID: {supplier_id} ({supplier.name}).")
            dialog = AddEditSupplierDialog(supplier=supplier, parent=self)
            if dialog.exec():
                data = dialog.get_supplier_data()
                if data:
                    success, msg = self.supplier_manager.update_supplier(supplier_id, **data)
                    if success:
                        self.load_suppliers()
                        self.statusBar.showMessage(f"Fornecedor '{data['name']}' atualizado com sucesso.", 5000)
                        logger.info(f"Fornecedor ID {supplier_id} atualizado com sucesso para '{data['name']}'.")
                    else:
                        QMessageBox.warning(self, "Resultado", msg)
                        logger.warning(f"Falha ao atualizar fornecedor ID {supplier_id}: {msg}")

    def delete_supplier(self):
        selected_rows = self.fornecedores_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um fornecedor para apagar.")
            logger.warning("Tentativa de deletar fornecedor sem seleção.")
            return
        
        supplier_id = int(self.fornecedores_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar o fornecedor ID {supplier_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para fornecedor ID: {supplier_id}.")
            success, msg = self.supplier_manager.delete_supplier(supplier_id)
            if success:
                self.load_suppliers()
                self.statusBar.showMessage(f"Fornecedor ID {supplier_id} apagado com sucesso.", 5000)
                logger.info(f"Fornecedor ID {supplier_id} apagado com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.error(f"Falha ao deletar fornecedor ID {supplier_id}: {msg}")

    # --- Métodos CRUD para Peças/Estoque ---
    def add_part(self):
        logger.info("Abrindo diálogo para adicionar nova peça.")
        dialog = AddEditPartDialog(supplier_manager=self.supplier_manager, parent=self)
        if dialog.exec():
            data = dialog.get_part_data()
            if data:
                success, msg = self.stock_manager.add_part(**data)
                if success: 
                    self.search_peças_estoque_input.clear()
                    self.load_parts()
                    self.statusBar.showMessage(f"Peça '{data['name']}' adicionada com sucesso.", 5000)
                    logger.info(f"Peça '{data['name']}' adicionada com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.warning(f"Falha ao adicionar peça '{data['name']}': {msg}")

    def edit_part(self):
        selected_rows = self.peças_estoque_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma peça para editar.")
            logger.warning("Tentativa de editar peça sem seleção.")
            return
        
        part_id = int(self.peças_estoque_table.item(selected_rows[0].row(), 0).text())
        part = self.stock_manager.get_part_by_id(part_id)
        if part:
            logger.info(f"Abrindo diálogo para editar peça ID: {part_id} ({part.name}).")
            dialog = AddEditPartDialog(part=part, supplier_manager=self.supplier_manager, parent=self)
            if dialog.exec():
                data = dialog.get_part_data()
                if data:
                    success, msg = self.stock_manager.update_part(part_id, **data)
                    if success: 
                        self.search_peças_estoque_input.clear()
                        self.load_parts()
                        self.statusBar.showMessage(f"Peça '{data['name']}' atualizada com sucesso.", 5000)
                        logger.info(f"Peça ID {part_id} atualizada com sucesso para '{data['name']}'.")
                    else:
                        QMessageBox.warning(self, "Resultado", msg)
                        logger.warning(f"Falha ao atualizar peça ID {part_id}: {msg}")

    def delete_part(self):
        selected_rows = self.peças_estoque_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma peça para apagar.")
            logger.warning("Tentativa de deletar peça sem seleção.")
            return
        
        part_id = int(self.peças_estoque_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar a peça ID {part_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para peça ID: {part_id}.")
            success, msg = self.stock_manager.delete_part(part_id)
            if success: 
                self.search_peças_estoque_input.clear()
                self.load_parts()
                self.statusBar.showMessage(f"Peça ID {part_id} apagada com sucesso.", 5000)
                logger.info(f"Peça ID {part_id} apagada com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.error(f"Falha ao deletar peça ID {part_id}: {msg}")

    def add_stock_dialog(self):
        selected_rows = self.peças_estoque_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma peça para adicionar estoque.")
            logger.warning("Tentativa de adicionar estoque sem seleção de peça.")
            return
        
        part_id = int(self.peças_estoque_table.item(selected_rows[0].row(), 0).text())
        part_name = self.peças_estoque_table.item(selected_rows[0].row(), 1).text()
        
        quantity, ok = QInputDialog.getInt(self, "Adicionar Estoque", f"Quantidade para '{part_name}':", 1, 1, 9999)
        if ok and quantity > 0:
            logger.info(f"Adicionando {quantity} unidades ao estoque da peça ID {part_id} ({part_name}).")
            success, msg = self.stock_manager.add_stock(part_id, quantity, self.current_user.id)
            if success: 
                self.load_parts()
                self.statusBar.showMessage(f"Estoque para '{part_name}' atualizado com sucesso.", 5000)
                logger.info(f"Estoque da peça ID {part_id} atualizado com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.warning(f"Falha ao remover estoque da peça ID {part_id}: {msg}")
            
    def remove_stock_dialog(self):
        selected_rows = self.peças_estoque_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma peça para remover estoque.")
            logger.warning("Tentativa de remover estoque sem seleção de peça.")
            return
        
        part_id = int(self.peças_estoque_table.item(selected_rows[0].row(), 0).text())
        part_name = self.peças_estoque_table.item(selected_rows[0].row(), 1).text()
        
        current_stock_text = self.peças_estoque_table.item(selected_rows[0].row(), 6).text()
        current_stock = int(current_stock_text) if current_stock_text.isdigit() else 0
        
        quantity, ok = QInputDialog.getInt(self, "Remover Estoque", f"Quantidade de '{part_name}' (Atual: {current_stock}):", 1, 1, current_stock)
        if ok and quantity > 0:
            logger.info(f"Removendo {quantity} unidades do estoque da peça ID {part_id} ({part_name}).")
            success, msg = self.stock_manager.remove_stock(part_id, quantity, self.current_user.id)
            if success: 
                self.load_parts()
                self.statusBar.showMessage(f"Estoque para '{part_name}' atualizado com sucesso (remoção).", 5000)
                logger.info(f"Estoque da peça ID {part_id} atualizado com sucesso (remoção).")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.warning(f"Falha ao remover estoque da peça ID {part_id}: {msg}")
            
    # --- Métodos para Vendas ---
    def add_sale(self):
        logger.info("Abrindo diálogo para adicionar nova venda/orçamento.")
        dialog = AddEditSaleDialog(customer_manager=self.customer_manager, stock_manager=self.stock_manager, parent=self)
        if dialog.exec():
            data = dialog.get_sale_data()
            if data:
                success, msg, sale_id = self.sale_manager.add_sale(**data, user_id=self.current_user.id, is_quote=dialog.is_quote)
                if success: 
                    self.load_sales()
                    self.load_parts()
                    self.statusBar.showMessage(f"Nova {'venda' if not dialog.is_quote else 'orçamento'} adicionada com sucesso.", 5000)
                    logger.info(f"Nova {'venda' if not dialog.is_quote else 'orçamento'} adicionada com sucesso. ID: {sale_id}")
                    if not dialog.is_quote:
                        customer = self.customer_manager.get_customer_by_id(data['customer_id'])
                        customer_name = customer.name if customer else "N/A"
                        self.notification_manager.notify_new_sale(sale_id, customer_name, data['total_amount'])
                        self.update_notification_count()
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.error(f"Falha ao adicionar venda/orçamento: {msg}")

    def edit_sale(self):
        """Abre o diálogo para editar uma venda/orçamento existente."""
        selected_rows = self.vendas_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma venda ou orçamento para editar.")
            logger.warning("Tentativa de editar venda sem seleção.")
            return
        
        sale_id = int(self.vendas_table.item(selected_rows[0].row(), 0).text())
        sale = Sale.get_by_id(sale_id)
        
        if sale:
            sale.items = self.sale_manager.get_sale_items(sale_id)
            
            logger.info(f"Abrindo diálogo para editar venda/orçamento ID: {sale_id}.")
            dialog = AddEditSaleDialog(
                sale=sale,
                customer_manager=self.customer_manager,
                stock_manager=self.stock_manager,
                parent=self
            )
            if dialog.exec():
                data = dialog.get_sale_data()
                if data:
                    self.statusBar.showMessage(f"Atualizando venda/orçamento {sale_id}...", 0)
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    try:
                        items_data = data.pop('items')
                        success, msg, _ = self.sale_manager.update_sale(sale_id, **data, user_id=self.current_user.id, is_quote=dialog.is_quote, items=items_data)
                        if success:
                            self.load_sales()
                            self.load_parts()
                            self.statusBar.showMessage(f"Venda/Orçamento ID {sale_id} atualizado com sucesso.", 5000)
                            logger.info(f"Venda/Orçamento ID {sale_id} atualizado com sucesso.")
                        else:
                            QMessageBox.warning(self, "Resultado", msg)
                            logger.error(f"Falha ao atualizar venda/orçamento ID {sale_id}: {msg}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao atualizar venda: {e}")
                        logger.critical(f"Erro inesperado ao atualizar venda ID {sale_id}: {e}", exc_info=True)
                    finally:
                        QApplication.restoreOverrideCursor()
                        self.statusBar.clearMessage()

    def delete_sale(self):
        """Deleta uma venda/orçamento selecionado."""
        selected_rows = self.vendas_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma venda ou orçamento para apagar.")
            logger.warning("Tentativa de deletar venda sem seleção.")
            return
        
        sale_id = int(self.vendas_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar a venda/orçamento ID {sale_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para venda/orçamento ID: {sale_id}.")
            self.statusBar.showMessage(f"Removendo venda/orçamento {sale_id}...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                success, msg = self.sale_manager.delete_sale(sale_id, user_id=self.current_user.id)
                if success: 
                    self.load_sales()
                    self.load_parts()
                    self.statusBar.showMessage(f"Venda/Orçamento ID {sale_id} apagado com sucesso.", 5000)
                    logger.info(f"Venda/Orçamento ID {sale_id} apagado com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.error(f"Falha ao deletar venda/orçamento ID {sale_id}: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao apagar venda: {e}")
                logger.critical(f"Erro inesperado ao deletar venda ID {sale_id}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()


    def show_sale_options(self):
        selected_rows = self.vendas_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma venda ou orçamento da lista.")
            logger.warning("Tentativa de mostrar opções de venda sem seleção.")
            return
        
        row = selected_rows[0].row()
        sale_id = int(self.vendas_table.item(row, 0).text())
        is_quote_text = self.vendas_table.item(row, 5).text()
        is_quote = (is_quote_text == 'Orçamento')
        
        logger.info(f"Mostrando opções para {'orçamento' if is_quote else 'venda'} ID: {sale_id}.")

        menu = QMenu(self)
        
        email_action = QAction("Enviar por Email", self)
        email_action.triggered.connect(lambda: self.send_sale_email(sale_id))
        menu.addAction(email_action)
        
        if is_quote:
            convert_action = QAction("Converter em Venda", self)
            convert_action.triggered.connect(lambda: self.convert_quote(sale_id))
            menu.addAction(convert_action)
        else:
            pay_action = QAction("Marcar como Paga", self)
            pay_action.triggered.connect(lambda: self.mark_sale_paid(sale_id))
            menu.addAction(pay_action)
        
        menu.exec(self.sale_options_button.mapToGlobal(self.sale_options_button.rect().bottomLeft()))

    def send_sale_email(self, sale_id):
        sale = Sale.get_by_id(sale_id)
        if not sale: 
            logger.error(f"Tentativa de enviar email para venda ID {sale_id}, mas venda não encontrada.")
            return
        
        customer = self.customer_manager.get_customer_by_id(sale.customer_id)
        if not customer or not customer.email:
            QMessageBox.warning(self, "Email não encontrado", "O cliente selecionado não possui um email cadastrado.")
            logger.warning(f"Tentativa de enviar email para venda {sale_id}, mas cliente {sale.customer_id} não tem email.")
            return
        
        subject = f"Seu {'Orçamento' if sale.is_quote else 'Comprovante de Venda'} - ID: {sale.id}"
        body = self.sale_manager.get_sale_details_for_email(sale_id)
        
        smtp_server = self.settings_manager.get_setting("smtp_server")
        smtp_port = int(self.settings_manager.get_setting("smtp_port", 587))
        smtp_username = self.settings_manager.get_setting("smtp_username")
        smtp_password = self.settings_manager.get_setting("smtp_password")
        smtp_use_tls_str = self.settings_manager.get_setting("smtp_use_tls", "True")
        smtp_use_tls = smtp_use_tls_str.lower() == "true"


        if not smtp_server or not smtp_username or not smtp_password:
             QMessageBox.warning(self, "Configuração de E-mail", "As configurações SMTP estão incompletas em 'Configurações'. Por favor, preencha-as.")
             logger.warning("Tentativa de enviar e-mail com configurações SMTP incompletas em settings.")
             return

        self.statusBar.showMessage("Enviando e-mail...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        logger.info(f"Enviando {'orçamento' if sale.is_quote else 'venda'} ID {sale_id} por e-mail para {customer.email}.")
        try:
            success, msg = send_email(customer.email, subject, body, 
                                      smtp_server, smtp_port, smtp_username, smtp_password, smtp_use_tls)
            QMessageBox.information(self, "Envio de Email", msg)
            if success:
                logger.info(f"E-mail para venda/orçamento ID {sale_id} enviado com sucesso.")
            else:
                logger.error(f"Falha ao enviar e-mail para venda/orçamento ID {sale_id}: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Envio de Email", f"Ocorreu um erro inesperado: {e}")
            logger.critical(f"Erro inesperado ao enviar e-mail para venda/orçamento ID {sale_id}: {e}", exc_info=True)
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar.clearMessage()


    def convert_quote(self, sale_id):
        logger.info(f"Tentando converter orçamento ID {sale_id} para venda.")
        reply = QMessageBox.question(self, 'Confirmar Conversão', 'Tem a certeza que quer converter este orçamento em uma venda? Esta ação irá deduzir o stock.')
        if reply == QMessageBox.Yes:
            self.statusBar.showMessage(f"Convertendo orçamento {sale_id}...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                success, msg = self.sale_manager.convert_quote_to_sale(sale_id, self.current_user.id)
                if success: 
                    self.load_sales()
                    self.load_parts()
                    self.statusBar.showMessage(f"Orçamento ID {sale_id} convertido para venda com sucesso.", 5000)
                    logger.info(f"Orçamento ID {sale_id} convertido para venda com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado da Conversão", msg)
                    logger.error(f"Falha ao converter orçamento ID {sale_id}: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Erro na Conversão", f"Ocorreu um erro inesperado: {e}")
                logger.critical(f"Erro inesperado ao converter orçamento ID {sale_id}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()
    
    def mark_sale_paid(self, sale_id):
        logger.info(f"Tentando marcar venda ID {sale_id} como paga.")
        self.statusBar.showMessage(f"Marcando venda {sale_id} como paga...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, msg = self.sale_manager.mark_sale_as_paid(sale_id, self.current_user.id)
            if success: 
                self.load_sales()
                self.load_financial_transactions()
                self.update_dashboard_stats()
                self.statusBar.showMessage(f"Venda ID {sale_id} marcada como paga com sucesso.", 5000)
                logger.info(f"Venda ID {sale_id} marcada como paga com sucesso.")
            else:
                QMessageBox.warning(self, "Resultado", msg)
                logger.warning(f"Falha ao marcar venda ID {sale_id} como paga: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Pagar", f"Ocorreu um erro inesperado: {e}")
            logger.critical(f"Erro inesperado ao marcar venda ID {sale_id} como paga: {e}", exc_info=True)
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar.clearMessage()

    # --- Métodos para Ordens de Serviço ---
    def add_service_order(self):
        logger.info("Abrindo diálogo para adicionar nova Ordem de Serviço.")
        dialog = AddEditServiceOrderDialog(
            customer_manager=self.customer_manager,
            user_manager=self.user_manager,
            stock_manager=self.stock_manager,
            service_order_manager=self.service_order_manager,
            api_integrations=self.api_integrations,
            parent=self
        )
        if dialog.exec():
            data = dialog.get_service_order_data()
            if data:
                self.statusBar.showMessage("Adicionando Ordem de Serviço...", 0)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    items_data = data.pop('items')
                    success, msg, so_id = self.service_order_manager.add_service_order(**data, items=items_data)
                    if success: 
                        self.load_service_orders()
                        customer = self.customer_manager.get_customer_by_id(data['customer_id'])
                        customer_name = customer.name if customer else "N/A"
                        self.notification_manager.notify_new_service_order(so_id, customer_name, data['vehicle_plate'])
                        self.load_parts()
                        self.statusBar.showMessage(f"Ordem de Serviço ID {so_id} adicionada com sucesso.", 5000)
                        logger.info(f"Ordem de Serviço ID {so_id} adicionada com sucesso.")
                        self.update_notification_count()
                    else:
                        QMessageBox.warning(self, "Resultado", msg)
                        logger.error(f"Falha ao adicionar Ordem de Serviço: {msg}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao adicionar OS: {e}")
                    logger.critical(f"Erro inesperado ao adicionar OS: {e}", exc_info=True)
                finally:
                    QApplication.restoreOverrideCursor()
                    self.statusBar.clearMessage()


    def edit_service_order(self):
        selected_rows = self.ordens_de_serviço_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma Ordem de Serviço para editar.")
            logger.warning("Tentativa de editar OS sem seleção.")
            return

        so_id = int(self.ordens_de_serviço_table.item(selected_rows[0].row(), 0).text())
        service_order = self.service_order_manager.get_service_order_by_id(so_id)

        if service_order:
            logger.info(f"Abrindo diálogo para editar Ordem de Serviço ID: {so_id}.")
            dialog = AddEditServiceOrderDialog(
                service_order=service_order,
                customer_manager=self.customer_manager,
                user_manager=self.user_manager,
                stock_manager=self.stock_manager,
                service_order_manager=self.service_order_manager,
                api_integrations=self.api_integrations,
                parent=self
            )
            if dialog.exec():
                data = dialog.get_service_order_data()
                if data:
                    self.statusBar.showMessage(f"Atualizando Ordem de Serviço {so_id}...", 0)
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    try:
                        items_data = data.pop('items')
                        success, msg, _ = self.service_order_manager.update_service_order(so_id, **data, items=items_data)
                        if success: 
                            self.load_service_orders()
                            self.load_parts()
                            self.statusBar.showMessage(f"Ordem de Serviço ID {so_id} atualizada com sucesso.", 5000)
                            logger.info(f"Ordem de Serviço ID {so_id} atualizada com sucesso.")
                        else:
                            QMessageBox.warning(self, "Resultado", msg)
                            logger.error(f"Falha ao atualizar Ordem de Serviço ID {so_id}: {msg}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao atualizar OS: {e}")
                        logger.critical(f"Erro inesperado ao atualizar OS ID {so_id}: {e}", exc_info=True)
                    finally:
                        QApplication.restoreOverrideCursor()
                        self.statusBar.clearMessage()

    def delete_service_order(self):
        selected_rows = self.ordens_de_serviço_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma Ordem de Serviço para apagar.")
            logger.warning("Tentativa de deletar OS sem seleção.")
            return
        
        so_id = int(self.ordens_de_serviço_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar a Ordem de Serviço ID {so_id}? Peças serão devolvidas ao estoque.')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para Ordem de Serviço ID: {so_id}.")
            self.statusBar.showMessage(f"Removendo Ordem de Serviço {so_id}...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                success, msg = self.service_order_manager.delete_service_order(so_id, user_id=self.current_user.id)
                if success: 
                    self.load_service_orders()
                    self.load_parts()
                    self.statusBar.showMessage(f"Ordem de Serviço ID {so_id} apagada com sucesso.", 5000)
                    logger.info(f"Ordem de Serviço ID {so_id} apagada com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.error(f"Falha ao deletar Ordem de Serviço ID {so_id}: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao apagar OS: {e}")
                logger.critical(f"Erro inesperado ao deletar OS ID {so_id}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()

    def show_service_order_options(self):
        selected_rows = self.ordens_de_serviço_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma Ordem de Serviço da lista.")
            logger.warning("Tentativa de mostrar opções de OS sem seleção.")
            return
        
        row = selected_rows[0].row()
        so_id = int(self.ordens_de_serviço_table.item(selected_rows[0].row(), 0).text())
        current_status = self.ordens_de_serviço_table.item(row, 6).text()
        current_payment_status = self.ordens_de_serviço_table.item(row, 7).text()

        logger.info(f"Mostrando opções para Ordem de Serviço ID: {so_id} (Status: {current_status}, Pagamento: {current_payment_status}).")

        menu = QMenu(self)

        edit_action = QAction("Editar OS", self); edit_action.triggered.connect(self.edit_service_order); menu.addAction(edit_action)
        delete_action = QAction("Apagar OS", self); delete_action.triggered.connect(self.delete_service_order); menu.addAction(delete_action)
        menu.addSeparator()

        if current_status == "Pendente":
            menu.addAction(QAction("Marcar como 'Em Andamento'", self, triggered=lambda: self._update_so_status(so_id, "Em Andamento")))
        if current_status == "Em Andamento":
            menu.addAction(QAction("Marcar como 'Concluída'", self, triggered=lambda: self._update_so_status(so_id, "Concluída")))
        if current_status != "Cancelada":
             menu.addAction(QAction("Marcar como 'Cancelada'", self, triggered=lambda: self._update_so_status(so_id, "Cancelada")))
        
        menu.addSeparator()

        if current_payment_status == "Pendente" or current_payment_status == "Parcialmente Pago":
            menu.addAction(QAction("Marcar Pagamento como 'Pago'", self, triggered=lambda: self._update_so_payment_status(so_id, "Pago")))
        
        menu.exec(self.so_options_button.mapToGlobal(self.so_options_button.rect().bottomLeft()))

    def _update_so_status(self, so_id, new_status):
        logger.info(f"Atualizando status da OS {so_id} para '{new_status}'.")
        self.statusBar.showMessage(f"Atualizando status da OS {so_id}...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, msg = self.service_order_manager.update_service_order_status(so_id, new_status)
            if success: 
                self.load_service_orders()
                self.statusBar.showMessage(f"Status da OS {so_id} atualizado para '{new_status}'.", 5000)
                logger.info(f"Status da OS {so_id} atualizado com sucesso.")
                if new_status == "Concluída":
                    so = self.service_order_manager.get_service_order_by_id(so_id)
                    if so:
                        customer = self.customer_manager.get_customer_by_id(so.customer_id)
                        customer_name = customer.name if customer else "N/A"
                        self.notification_manager.notify_new_service_order(so_id, customer_name, so.vehicle_plate)
                        self.update_notification_count()
            else:
                QMessageBox.warning(self, "Atualização de Status", msg)
                logger.error(f"Falha ao atualizar status da OS {so_id}: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao atualizar status da OS: {e}")
            logger.critical(f"Erro inesperado ao atualizar status da OS {so_id}: {e}", exc_info=True)
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar.clearMessage()

    def _update_so_payment_status(self, so_id, new_payment_status):
        logger.info(f"Atualizando status de pagamento da OS {so_id} para '{new_payment_status}'.")
        self.statusBar.showMessage(f"Atualizando pagamento da OS {so_id}...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, msg = self.service_order_manager.update_service_order_payment_status(so_id, new_payment_status)
            if success: 
                self.load_service_orders()
                self.statusBar.showMessage(f"Status de pagamento da OS {so_id} atualizado para '{new_payment_status}'.", 5000)
                logger.info(f"Status de pagamento da OS {so_id} atualizado com sucesso.")
            else:
                QMessageBox.warning(self, "Atualização de Pagamento", msg)
                logger.error(f"Falha ao atualizar status de pagamento da OS {so_id}: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao atualizar pagamento da OS: {e}")
            logger.critical(f"Erro inesperado ao atualizar pagamento da OS {so_id}: {e}", exc_info=True)
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar.clearMessage()

    # --- Métodos para Finanças ---
    def add_financial_transaction(self):
        logger.info("Abrindo diálogo para adicionar nova transação financeira.")
        dialog = AddEditFinancialTransactionDialog(parent=self)
        if dialog.exec():
            data = dialog.get_transaction_data()
            if data:
                self.statusBar.showMessage("Adicionando transação financeira...", 0)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    success, message = self.financial_manager.add_transaction(**data)
                    if success:
                        self.statusBar.showMessage(f"Transação ({data['type']}: R$ {data['amount']:.2f}) adicionada com sucesso.", 5000)
                        self.load_financial_transactions()
                        self.update_dashboard_stats()
                        logger.info(f"Transação financeira ({data['type']}: R$ {data['amount']:.2f}) adicionada com sucesso.")
                    else:
                        QMessageBox.warning(self, "Erro", message)
                        logger.error(f"Falha ao adicionar transação financeira: {message}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao adicionar transação: {e}")
                    logger.critical(f"Erro inesperado ao adicionar transação financeira: {e}", exc_info=True)
                finally:
                    QApplication.restoreOverrideCursor()
                    self.statusBar.clearMessage()


    def edit_financial_transaction(self):
        selected_rows = self.financeiro_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma transação para editar.")
            logger.warning("Tentativa de editar transação financeira sem seleção.")
            return
        
        transaction_id = int(self.financeiro_table.item(selected_rows[0].row(), 0).text())
        transaction = self.financial_manager.get_transaction_by_id(transaction_id)
        if transaction:
            logger.info(f"Abrindo diálogo para editar transação financeira ID: {transaction_id}.")
            dialog = AddEditFinancialTransactionDialog(transaction=transaction, parent=self)
            if dialog.exec():
                data = dialog.get_transaction_data()
                if data:
                    self.statusBar.showMessage(f"Atualizando transação {transaction_id}...", 0)
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    try:
                        success, msg = self.financial_manager.update_transaction(transaction_id, **data)
                        if success: 
                            self.load_financial_transactions()
                            self.update_dashboard_stats()
                            self.statusBar.showMessage(f"Transação ID {transaction_id} atualizada com sucesso.", 5000)
                            logger.info(f"Transação financeira ID {transaction_id} atualizada com sucesso.")
                        else:
                            QMessageBox.warning(self, "Resultado", msg)
                            logger.error(f"Falha ao atualizar transação financeira ID {transaction_id}: {msg}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao atualizar transação: {e}")
                        logger.critical(f"Erro inesperado ao atualizar transação financeira ID {transaction_id}: {e}", exc_info=True)
                    finally:
                        QApplication.restoreOverrideCursor()
                        self.statusBar.clearMessage()

    def delete_financial_transaction(self):
        selected_rows = self.financeiro_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma transação para apagar.")
            logger.warning("Tentativa de deletar transação financeira sem seleção.")
            return
        
        transaction_id = int(self.financeiro_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer apagar a transação ID {transaction_id}?')
        if reply == QMessageBox.Yes:
            logger.info(f"Confirmado deleção para transação financeira ID: {transaction_id}.")
            self.statusBar.showMessage(f"Removendo transação {transaction_id}...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                success, msg = self.financial_manager.delete_transaction(transaction_id)
                if success: 
                    self.load_financial_transactions()
                    self.update_dashboard_stats()
                    self.statusBar.showMessage(f"Transação ID {transaction_id} apagada com sucesso.", 5000)
                    logger.info(f"Transação ID {transaction_id} apagada com sucesso.")
                else:
                    QMessageBox.warning(self, "Resultado", msg)
                    logger.error(f"Falha ao deletar transação financeira ID {transaction_id}: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Ocorreu um erro inesperado ao apagar transação: {e}")
                logger.critical(f"Erro inesperado ao deletar transação financeira ID {transaction_id}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()
    
    # --- Métodos para Relatórios ---
    def generate_report(self):
        logger.info("Abrindo diálogo para gerar relatório.")
        dialog = GenerateReportDialog(user_manager=self.user_manager, parent=self)
        if dialog.exec():
            options = dialog.get_report_options()
            report_type = options["report_type"]
            export_format = options["export_format"]
            filters = options["filters"]
            
            success, message, file_path = False, "Erro desconhecido.", None

            self.statusBar.showMessage(f"Gerando relatório de {report_type}...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            logger.info(f"Gerando relatório: {report_type}, Formato: {export_format}, Filtros: {filters}")
            try:
                if report_type == "Vendas":
                    sales_data = self.sale_manager.get_all_sales_for_display(
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date"),
                        status_filter=None, # Relatório de vendas não filtra por status aqui
                        is_quote_filter=False # Apenas vendas, não orçamentos
                    )
                    success, message, file_path = self.report_manager.generate_sales_report(
                        sales_data=sales_data,
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date"),
                        export_format=export_format
                    )
                elif report_type == "Estoque":
                    stock_data = self.stock_manager.get_all_parts_for_display()
                    success, message, file_path = self.report_manager.generate_stock_report(
                        stock_data=stock_data,
                        export_format=export_format
                    )
                elif report_type == "Financeiro":
                    financial_data = self.financial_manager.search_transactions(
                        query_text="", # Não há busca por texto no relatório financeiro
                        transaction_type_filter=None, # Não filtra por tipo aqui
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date")
                    )
                    success, message, file_path = self.report_manager.generate_financial_report(
                        financial_data=financial_data,
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date"),
                        export_format=export_format
                    )
                elif report_type == "Ordens de Serviço":
                    service_order_data = self.service_order_manager.get_all_service_orders(
                        query_text="", # Não há busca por texto no relatório de OS
                        status_filter=filters.get("status"),
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date"),
                        assigned_user_id=filters.get("assigned_user_id")
                    )
                    success, message, file_path = self.report_manager.generate_service_order_report(
                        service_order_data=service_order_data,
                        start_date=filters.get("start_date"),
                        end_date=filters.get("end_date"),
                        export_format=export_format
                    )
                
                if success:
                    self.load_reports()
                    QMessageBox.information(self, "Gerar Relatório", f"Relatório de {report_type} gerado com sucesso em:\n{file_path}")
                    self.statusBar.showMessage(f"Relatório de {report_type} gerado com sucesso.", 5000)
                    logger.info(f"Relatório '{report_type}' gerado com sucesso em: {file_path}")
                else:
                    QMessageBox.warning(self, "Gerar Relatório", message)
                    logger.error(f"Falha ao gerar relatório '{report_type}': {message}")
            except Exception as e:
                QMessageBox.critical(self, "Erro na Geração de Relatório", f"Ocorreu um erro inesperado: {e}")
                logger.critical(f"Erro inesperado durante a geração de relatório para {report_type}: {e}", exc_info=True)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar.clearMessage()


    # --- Métodos de Carregamento de Dados para as Tabelas ---
    def load_all_data(self):
        if not self.current_user: return
        logger.info("Iniciando carregamento de todos os dados.")
        self.load_users()
        self.load_customers()
        self.load_suppliers()
        self.load_parts()
        self.load_sales()
        self.load_service_orders()
        self.load_financial_transactions()
        self.load_reports()
        self.load_notifications()
        self.update_dashboard_stats()
        logger.info("Carregamento de todos os dados concluído.")

    def load_users(self):
        query = self.search_gerenciar_usuários_input.text()
        table = self.gerenciar_usuários_table
        table.setRowCount(0)
        
        users = self.user_manager.search_users(query) if query else self.user_manager.get_all_users()
        
        for row, user in enumerate(users):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            table.setItem(row, 1, QTableWidgetItem(user.username))
            table.setItem(row, 2, QTableWidgetItem(user.role))
            table.setItem(row, 3, QTableWidgetItem("Sim" if user.is_active else "Não"))
        logger.info(f"Carregados {len(users)} usuários na tabela de Gerenciar Usuários.")
            
    def load_customers(self):
        query = self.search_clientes_input.text()
        table = self.clientes_table
        table.setRowCount(0)
        
        customers = self.customer_manager.search_customers(query) if query else self.customer_manager.get_all_customers()
        
        for row, customer in enumerate(customers):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(customer.id)))
            table.setItem(row, 1, QTableWidgetItem(customer.name))
            table.setItem(row, 2, QTableWidgetItem(customer.cpf_cnpj))
            table.setItem(row, 3, QTableWidgetItem(customer.phone))
            table.setItem(row, 4, QTableWidgetItem(customer.email))
            table.setItem(row, 5, QTableWidgetItem(customer.street))
            table.setItem(row, 6, QTableWidgetItem(customer.number))
            table.setItem(row, 7, QTableWidgetItem(customer.neighborhood))
            table.setItem(row, 8, QTableWidgetItem(customer.zip_code))
        logger.info(f"Carregados {len(customers)} clientes na tabela de Clientes.")


    def load_suppliers(self):
        query = self.search_fornecedores_input.text()
        table = self.fornecedores_table
        table.setRowCount(0)
        
        suppliers = self.supplier_manager.search_suppliers(query) if query else self.supplier_manager.get_all_suppliers()
        
        for row, supplier in enumerate(suppliers):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(supplier.id)))
            table.setItem(row, 1, QTableWidgetItem(supplier.name))
            table.setItem(row, 2, QTableWidgetItem(supplier.cnpj))
            table.setItem(row, 3, QTableWidgetItem(supplier.contact_person))
            table.setItem(row, 4, QTableWidgetItem(supplier.phone))
            table.setItem(row, 5, QTableWidgetItem(supplier.email))
            table.setItem(row, 6, QTableWidgetItem(supplier.address))
        logger.info(f"Carregados {len(suppliers)} fornecedores na tabela de Fornecedores.")

    
    def load_parts(self):
        query = self.search_peças_estoque_input.text()
        table = self.peças_estoque_table
        table.setRowCount(0)
        
        parts = self.stock_manager.search_parts(query) if query else self.stock_manager.get_all_parts()
        
        for row, part in enumerate(parts):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(part.id)))
            table.setItem(row, 1, QTableWidgetItem(part.name))
            table.setItem(row, 2, QTableWidgetItem(part.part_number))
            table.setItem(row, 3, QTableWidgetItem(part.manufacturer))
            table.setItem(row, 4, QTableWidgetItem(f"R$ {part.price:.2f}"))
            table.setItem(row, 5, QTableWidgetItem(f"R$ {part.cost:.2f}"))
            table.setItem(row, 6, QTableWidgetItem(str(part.stock)))
            table.setItem(row, 7, QTableWidgetItem(str(part.min_stock)))
            table.setItem(row, 8, QTableWidgetItem(part.location))
            
            supplier = self.supplier_manager.get_supplier_by_id(part.supplier_id) if part.supplier_id else None
            table.setItem(row, 9, QTableWidgetItem(supplier.name if supplier else "N/A"))
            table.setItem(row, 10, QTableWidgetItem(part.category))
            table.setItem(row, 11, QTableWidgetItem(part.original_code))
            table.setItem(row, 12, QTableWidgetItem(part.barcode))
            
            if part.stock <= part.min_stock:
                for col_idx in range(table.columnCount()):
                    item = table.item(row, col_idx)
                    if item:
                        item.setBackground(QColor(255, 50, 50))
        logger.info(f"Carregados {len(parts)} peças/estoque na tabela de Peças/Estoque.")


    def load_sales(self):
        query = self.search_vendas_input.text()
        table = self.vendas_table
        table.setRowCount(0)
        
        filters = self.filter_vendas_widgets
        start_date = filters['start_date'].date().toString("yyyy-MM-dd HH:MM:S")
        end_date = filters['end_date'].date().toString("yyyy-MM-dd HH:MM:S")
        status_filter = filters['status_combo'].currentData()
        is_quote_filter = None
        if filters['type_combo'].currentText() == "Venda": is_quote_filter = False
        elif filters['type_combo'].currentText() == "Orçamento": is_quote_filter = True

        sales_data = self.sale_manager.get_all_sales_for_display(
            query=query, 
            start_date=start_date, 
            end_date=end_date, 
            status_filter=status_filter,
            is_quote_filter=is_quote_filter
        )
        
        for row, sale in enumerate(sales_data):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(sale['id'])))
            table.setItem(row, 1, QTableWidgetItem(sale['sale_date'].split('T')[0]))
            table.setItem(row, 2, QTableWidgetItem(sale['customer_name']))
            table.setItem(row, 3, QTableWidgetItem(f"R$ {sale['total_amount']:.2f}"))
            table.setItem(row, 4, QTableWidgetItem(sale['status']))
            table.setItem(row, 5, QTableWidgetItem("Orçamento" if sale['is_quote'] else "Venda"))
            table.setItem(row, 6, QTableWidgetItem(sale['payment_method']))
            table.setItem(row, 7, QTableWidgetItem(sale['registered_by']))
        logger.info(f"Carregados {len(sales_data)} vendas na tabela de Vendas com filtros.")

    def load_service_orders(self):
        query = self.search_ordens_de_serviço_input.text()
        table = self.ordens_de_serviço_table
        table.setRowCount(0)

        filters = self.filter_ordens_de_serviço_widgets
        if filters['assigned_user_combo'].count() <= 1:
            users = self.user_manager.get_all_users()
            for user in users:
                filters['assigned_user_combo'].addItem(user.username, userData=user.id)

        start_date = filters['start_date'].date().toString("yyyy-MM-dd HH:MM:S")
        end_date = filters['end_date'].date().toString("yyyy-MM-dd HH:MM:S")
        status_filter = filters['status_combo'].currentData()
        assigned_user_id_filter = filters['assigned_user_combo'].currentData()


        service_orders = self.service_order_manager.get_all_service_orders(
            query_text=query,
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
            assigned_user_id=assigned_user_id_filter
        )
        
        for row_idx, so_data in enumerate(service_orders):
            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(str(so_data['so_id'])))
            table.setItem(row_idx, 1, QTableWidgetItem(so_data['order_date'].split('T')[0]))
            table.setItem(row_idx, 2, QTableWidgetItem(so_data['customer_name']))
            table.setItem(row_idx, 3, QTableWidgetItem(so_data['vehicle_plate']))
            table.setItem(row_idx, 4, QTableWidgetItem(so_data['vehicle_model']))
            table.setItem(row_idx, 5, QTableWidgetItem(str(so_data['vehicle_year'])))
            table.setItem(row_idx, 6, QTableWidgetItem(so_data['status']))
            table.setItem(row_idx, 7, QTableWidgetItem(so_data['payment_status']))
            table.setItem(row_idx, 8, QTableWidgetItem(f"R$ {so_data['total_amount']:.2f}"))
            table.setItem(row_idx, 9, QTableWidgetItem(f"R$ {so_data['labor_cost']:.2f}"))
            table.setItem(row_idx, 10, QTableWidgetItem(f"R$ {so_data['parts_cost']:.2f}"))
            table.setItem(row_idx, 11, QTableWidgetItem(so_data['assigned_user_name']))
        logger.info(f"Carregadas {len(service_orders)} Ordens de Serviço na tabela de Ordens de Serviço com filtros.")


    def load_financial_transactions(self):
        query = self.search_financeiro_input.text()
        table = self.financeiro_table
        table.setRowCount(0)
        
        filters = self.filter_financeiro_widgets
        start_date = filters['start_date'].date().toString("yyyy-MM-dd HH:MM:S")
        end_date = filters['end_date'].date().toString("yyyy-MM-dd HH:MM:S")
        type_filter = filters['type_combo'].currentData()

        transactions = self.financial_manager.search_transactions(
            query_text=query,
            transaction_type_filter=type_filter,
            start_date=start_date,
            end_date=end_date
        )
        
        for row, transaction in enumerate(transactions):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(transaction.id)))
            table.setItem(row, 1, QTableWidgetItem(transaction.transaction_date.split('T')[0]))
            table.setItem(row, 2, QTableWidgetItem(f"R$ {transaction.amount:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(transaction.type))
            table.setItem(row, 4, QTableWidgetItem(transaction.category))
            table.setItem(row, 5, QTableWidgetItem(transaction.description))
        logger.info(f"Carregadas {len(transactions)} transações financeiras na tabela Financeiro com filtros.")


    def load_reports(self):
        table = self.reports_table
        table.setRowCount(0)
        
        reports = self.report_manager.get_all_reports_metadata()
        
        for row, report in enumerate(reports):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(report['id'])))
            table.setItem(row, 1, QTableWidgetItem(report['report_type']))
            table.setItem(row, 2, QTableWidgetItem(report['generation_date'].split('T')[0]))
            table.setItem(row, 3, QTableWidgetItem(report['generated_by_username'] or "N/A"))
            
            open_button = QPushButton("Abrir Ficheiro")
            file_path = report['file_path']
            open_button.clicked.connect(lambda _, p=file_path: self.open_report_file(p))
            table.setCellWidget(row, 4, open_button)
        logger.info(f"Carregados {len(reports)} metadados de relatórios na tabela de Relatórios.")


    def open_report_file(self):
        selected_rows = self.reports_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione um relatório para abrir.")
            return

        file_path = self.reports_table.item(selected_rows[0].row(), 4).text()

        if os.path.exists(file_path):
            try:
                os.startfile(file_path)
                logger.info(f"Arquivo de relatório {file_path} aberto com sucesso.")
                self.statusBar.showMessage(f"Ficheiro aberto: {os.path.basename(file_path)}", 5000)
            except AttributeError:
                if sys.platform == "darwin":
                    os.system(f"open \"{file_path}\"")
                    logger.info(f"Arquivo de relatório {file_path} aberto via 'open' (macOS).")
                elif sys.platform.startswith("linux"):
                    os.system(f"xdg-open \"{file_path}\"")
                    logger.info(f"Arquivo de relatório {file_path} aberto via 'xdg-open' (Linux).")
                else:
                    QMessageBox.warning(self, "Erro", "Não foi possível abrir o arquivo automaticamente. Sistema operacional não suportado.")
                    logger.warning(f"Não foi possível abrir o arquivo {file_path}: Sistema operacional não suportado ({sys.platform}).")
            except Exception as e:
                QMessageBox.warning(self, "Erro ao Abrir", f"Erro ao tentar abrir o arquivo: {e}")
                logger.error(f"Erro inesperado ao abrir arquivo de relatório {file_path}: {e}", exc_info=True)
        else:
            QMessageBox.warning(self, "Arquivo Não Encontrado", f"O arquivo de relatório não foi encontrado: {file_path}")
            logger.warning(f"Tentativa de abrir arquivo de relatório não encontrado: {file_path}")


    def load_notifications(self):
        """Carrega e exibe as notificações na tabela de Notificações."""
        table = self.notifications_table
        table.setRowCount(0)
        
        notifications = self.notification_manager.get_all_notifications()
        
        for row, notification in enumerate(notifications):
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(notification.id)))
            table.setItem(row, 1, QTableWidgetItem(notification.timestamp.split('T')[0]))
            table.setItem(row, 2, QTableWidgetItem(notification.type))
            table.setItem(row, 3, QTableWidgetItem(notification.message))
            table.setItem(row, 4, QTableWidgetItem("Sim" if notification.is_read else "Não"))

            if not notification.is_read:
                for col_idx in range(table.columnCount()):
                    item = table.item(row, col_idx)
                    if item:
                        item.setBackground(QColor(255, 255, 200))
        logger.info(f"Carregadas {len(notifications)} notificações na tabela de Notificações.")

    def update_notification_count(self):
        """Atualiza o contador de notificações não lidas na barra de status e no botão da sidebar."""
        unread_count = self.notification_manager.get_unread_notifications_count()
        self.notification_count_label.setText(f"Notificações: {unread_count}")
        
        notif_button = self.nav_buttons.get("Notificações")
        if notif_button:
            if unread_count > 0:
                notif_button.setText(f" Notificações ({unread_count})")
                notif_button.setStyleSheet("QPushButton { color: yellow; }")
            else:
                notif_button.setText(" Notificações")
                notif_button.setStyleSheet("")
        logger.info(f"Contador de notificações não lidas atualizado: {unread_count}.")


    def mark_notification_as_read(self):
        """Marca uma notificação selecionada como lida."""
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma notificação para marcar como lida.")
            return
        
        notification_id = int(self.notifications_table.item(selected_rows[0].row(), 0).text())
        success, msg = self.notification_manager.mark_notification_as_read(notification_id)
        if success:
            self.statusBar.showMessage(msg, 5000)
            self.load_notifications()
            self.update_notification_count()
        else:
            QMessageBox.warning(self, "Erro", msg)

    def mark_all_notifications_as_read(self):
        """Marca todas as notificações como lidas."""
        reply = QMessageBox.question(self, 'Confirmar', 'Tem a certeza que quer marcar TODAS as notificações como lidas?')
        if reply == QMessageBox.Yes:
            success, msg = self.notification_manager.mark_all_notifications_as_read()
            if success:
                self.statusBar.showMessage(msg, 5000)
                self.load_notifications()
                self.update_notification_count()
            else:
                QMessageBox.warning(self, "Erro", msg)

    def delete_notification(self):
        """Deleta uma notificação selecionada."""
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Seleção Necessária", "Por favor, selecione uma notificação para remover.")
            return
        
        notification_id = int(self.notifications_table.item(selected_rows[0].row(), 0).text())
        reply = QMessageBox.question(self, 'Confirmar', f'Tem a certeza que quer remover a notificação ID {notification_id}?')
        if reply == QMessageBox.Yes:
            success, msg = self.notification_manager.delete_notification(notification_id)
            if success:
                self.statusBar.showMessage(msg, 5000)
                self.load_notifications()
                self.update_notification_count()
            else:
                QMessageBox.warning(self, "Erro", msg)


    def update_dashboard_stats(self):
        logger.info("Atualizando estatísticas do Dashboard.")
        low_stock_parts = self.stock_manager.get_parts_below_min_stock()
        self.dashboard_low_stock_label.setText(f"Itens com estoque baixo: {len(low_stock_parts)}")

        balance = self.financial_manager.get_balance()
        self.dashboard_balance_label.setText(f"Balanço Financeiro (Total): R$ {balance:.2f}")

        total_sales_amount = sum(s['total_amount'] for s in self.sale_manager.get_all_sales_for_display(query=None, is_quote_filter=False))
        pending_oss_count = len([so for so in self.service_order_manager.get_all_service_orders(status_filter='Pendente')])
        in_progress_oss_count = len([so for so in self.service_order_manager.get_all_service_orders(status_filter='Em Andamento')])
        
        self.dashboard_stats_label.setText(
            f"Total de Vendas Registradas: R$ {total_sales_amount:.2f}\n"
            f"OS Pendentes: {pending_oss_count}\n"
            f"OS Em Andamento: {in_progress_oss_count}"
        )
        logger.info(f"Estatísticas do Dashboard atualizadas: Estoque Baixo={len(low_stock_parts)}, Balanço={balance:.2f}, Vendas={total_sales_amount:.2f}, OS Pendentes={pending_oss_count}.")


    def update_ui_permissions(self):
        is_logged_in = self.current_user is not None
        is_admin = is_logged_in and self.current_user.role == UserRole.ADMIN.value
        is_manager = is_logged_in and self.current_user.role == UserRole.MANAGER.value
        is_financial = is_logged_in and self.current_user.role == UserRole.FINANCIAL.value
        is_caixa = is_logged_in and self.current_user.role == UserRole.CAIXA.value
        is_employee = is_logged_in and self.current_user.role == UserRole.EMPLOYEE.value
        
        for name, btn in self.nav_buttons.items():
            btn.setVisible(is_logged_in)
        
        if is_logged_in:
            self.nav_buttons["Gerenciar Usuários"].setVisible(is_admin)
            self.nav_buttons["Configurações"].setVisible(is_admin)

            self.nav_buttons["Financeiro"].setVisible(is_financial or is_admin or is_caixa or is_manager)
            if hasattr(self, 'add_financeiro_button'):
                self.add_financeiro_button.setVisible(is_financial or is_admin or is_caixa or is_manager)
                self.edit_financeiro_button.setVisible(is_financial or is_admin or is_caixa or is_manager)
                self.delete_financeiro_button.setVisible(is_financial or is_admin or is_caixa or is_manager)
                self.search_financeiro_input.setVisible(True)

            self.nav_buttons["Fornecedores"].setVisible(is_manager or is_admin)
            self.nav_buttons["Peças/Estoque"].setVisible(is_manager or is_admin)
            self.nav_buttons["Vendas"].setVisible(is_manager or is_admin or is_caixa)
            self.nav_buttons["Ordens de Serviço"].setVisible(is_manager or is_admin or is_employee)
            self.nav_buttons["Relatórios"].setVisible(is_manager or is_admin or is_financial)
            self.nav_buttons["Notificações"].setVisible(is_logged_in)

            if hasattr(self, 'add_gerenciar_usuários_button'):
                self.add_gerenciar_usuários_button.setVisible(is_admin)
                self.edit_gerenciar_usuários_button.setVisible(is_admin)
                self.delete_gerenciar_usuários_button.setVisible(is_admin)
                self.search_gerenciar_usuários_input.setVisible(is_admin)

            if hasattr(self, 'add_peças_estoque_button'):
                self.add_peças_estoque_button.setVisible(is_manager or is_admin)
                self.edit_peças_estoque_button.setVisible(is_manager or is_admin)
                self.delete_peças_estoque_button.setVisible(is_manager or is_admin)
                self.add_stock_button.setVisible(is_manager or is_admin)
                self.remove_stock_button.setVisible(is_manager or is_admin)
            
            if hasattr(self, 'add_vendas_button'):
                self.add_vendas_button.setVisible(is_manager or is_admin or is_caixa)
                self.edit_vendas_button.setVisible(is_manager or is_admin or is_caixa)
                self.delete_vendas_button.setVisible(is_manager or is_admin or is_caixa)
                self.sale_options_button.setVisible(is_manager or is_admin or is_caixa)

            if hasattr(self, 'add_ordens_de_serviço_button'):
                self.add_ordens_de_serviço_button.setVisible(is_manager or is_admin or is_employee)
                self.edit_ordens_de_serviço_button.setVisible(is_manager or is_admin or is_employee)
                self.delete_ordens_de_serviço_button.setVisible(is_manager or is_admin)
                self.so_options_button.setVisible(is_manager or is_admin or is_employee)

            if hasattr(self, 'generate_report_button'):
                self.generate_report_button.setVisible(is_manager or is_admin or is_financial)
            
            if hasattr(self, 'mark_as_read_button'):
                self.mark_as_read_button.setVisible(is_logged_in)
                self.mark_all_as_read_button.setVisible(is_logged_in)
                self.delete_notification_button.setVisible(is_admin)
            
            if hasattr(self, 'create_backup_button'):
                self.create_backup_button.setVisible(is_admin)
            if hasattr(self, 'restore_backup_button'):
                self.restore_backup_button.setVisible(is_admin)

            logger.info(f"Permissões da UI atualizadas para o papel do usuário: {self.current_user.role}")
        else:
            for name, btn in self.nav_buttons.items():
                btn.setVisible(False)
            self.btn_logout.setVisible(False)
            
            for attr_name in dir(self):
                if attr_name.startswith(('add_', 'edit_', 'delete_', 'search_', 'sale_options_', 'so_options_', 'generate_report_')):
                    widget = getattr(self, attr_name)
                    if isinstance(widget, (QPushButton, QLineEdit, QComboBox)):
                        widget.setVisible(False)
            
            if hasattr(self, 'search_clientes_input') and isinstance(self.search_clientes_input, ValidatedLineEdit):
                 self.search_clientes_input.setVisible(False)
            if hasattr(self, 'search_fornecedores_input') and isinstance(self.search_fornecedores_input, ValidatedLineEdit):
                 self.search_fornecedores_input.setVisible(False)

            logger.info("Permissões da UI redefinidas para estado 'não logado'.")


    def logout(self):
        logger.info(f"Usuário {self.current_user.username} está fazendo logout.")
        self.current_user = None
        self.update_ui_permissions()
        self.statusBar.showMessage("Você foi desconectado.", 5000)
        self.show_login_dialog()


    def _setup_connections(self):
        for name, btn in self.nav_buttons.items():
            btn.clicked.connect(lambda checked=False, n=name: self.stacked_widget.setCurrentWidget(self.screens[n]))
        
        self.btn_logout.clicked.connect(self.logout)

        # Conecta inputs de busca para funções de carregamento
        self.search_clientes_input.textChanged.connect(self.load_customers)
        self.search_fornecedores_input.textChanged.connect(self.load_suppliers)
        self.search_peças_estoque_input.textChanged.connect(self.load_parts)
        self.search_vendas_input.textChanged.connect(self.load_sales)
        self.search_ordens_de_serviço_input.textChanged.connect(self.load_service_orders)
        self.search_financeiro_input.textChanged.connect(self.load_financial_transactions)
        self.search_gerenciar_usuários_input.textChanged.connect(self.load_users)

        # Conecta mudanças de filtro para funções de carregamento
        # Filtros de Vendas
        self.filter_vendas_widgets['start_date'].dateChanged.connect(self.load_sales)
        self.filter_vendas_widgets['end_date'].dateChanged.connect(self.load_sales)
        self.filter_vendas_widgets['status_combo'].currentIndexChanged.connect(self.load_sales)
        self.filter_vendas_widgets['type_combo'].currentIndexChanged.connect(self.load_sales)

        # Filtros de Ordens de Serviço
        self.filter_ordens_de_serviço_widgets['start_date'].dateChanged.connect(self.load_service_orders)
        self.filter_ordens_de_serviço_widgets['end_date'].dateChanged.connect(self.load_service_orders)
        self.filter_ordens_de_serviço_widgets['status_combo'].currentIndexChanged.connect(self.load_service_orders)
        self.filter_ordens_de_serviço_widgets['assigned_user_combo'].currentIndexChanged.connect(self.load_service_orders)

        # Filtros de Financeiro
        self.filter_financeiro_widgets['start_date'].dateChanged.connect(self.load_financial_transactions)
        self.filter_financeiro_widgets['end_date'].dateChanged.connect(self.load_financial_transactions)
        self.filter_financeiro_widgets['type_combo'].currentIndexChanged.connect(self.load_financial_transactions)


        # Conexões CRUD
        self.add_gerenciar_usuários_button.clicked.connect(self.add_user)
        self.edit_gerenciar_usuários_button.clicked.connect(self.edit_user)
        self.delete_gerenciar_usuários_button.clicked.connect(self.delete_user)

        self.add_clientes_button.clicked.connect(self.add_customer)
        self.edit_clientes_button.clicked.connect(self.edit_customer)
        self.delete_clientes_button.clicked.connect(self.delete_customer)

        self.add_fornecedores_button.clicked.connect(self.add_supplier)
        self.edit_fornecedores_button.clicked.connect(self.edit_supplier)
        self.delete_fornecedores_button.clicked.connect(self.delete_supplier)

        self.add_peças_estoque_button.clicked.connect(self.add_part)
        self.edit_peças_estoque_button.clicked.connect(self.edit_part)
        self.delete_peças_estoque_button.clicked.connect(self.delete_part)
        self.add_stock_button.clicked.connect(self.add_stock_dialog)
        self.remove_stock_button.clicked.connect(self.remove_stock_dialog)
        
        self.add_vendas_button.clicked.connect(self.add_sale)
        self.edit_vendas_button.clicked.connect(self.edit_sale)
        self.delete_vendas_button.clicked.connect(self.delete_sale)
        self.sale_options_button.clicked.connect(self.show_sale_options)

        self.add_ordens_de_serviço_button.clicked.connect(self.add_service_order)
        self.edit_ordens_de_serviço_button.clicked.connect(self.edit_service_order)
        self.delete_ordens_de_serviço_button.clicked.connect(self.delete_service_order)
        self.so_options_button.clicked.connect(self.show_service_order_options)

        self.add_financeiro_button.clicked.connect(self.add_financial_transaction)
        self.edit_financeiro_button.clicked.connect(self.edit_financial_transaction)
        self.delete_financeiro_button.clicked.connect(self.delete_financial_transaction)

        self.generate_report_button.clicked.connect(self.generate_report)
        self.reports_table.doubleClicked.connect(lambda: self.open_report_file(self.reports_table.item(self.reports_table.currentRow(), 4).text()))

        # Conexões de Notificações
        self.mark_as_read_button.clicked.connect(self.mark_notification_as_read)
        self.mark_all_as_read_button.clicked.connect(self.mark_all_notifications_as_read)
        self.delete_notification_button.clicked.connect(self.delete_notification)
        self.notifications_table.doubleClicked.connect(self.mark_notification_as_read)

        # Conexões para Configurações (incluindo Backup/Restauração)
        self.select_logo_button.clicked.connect(self._select_logo_file)
        self.select_color_button.clicked.connect(self._select_theme_color)
        self.save_settings_button.clicked.connect(self._save_settings)
        self.create_backup_button.clicked.connect(self.create_backup_dialog)
        self.restore_backup_button.clicked.connect(self.restore_backup_dialog)
        logger.info("Conexões de UI configuradas.")


# --- Main Execution ---
if __name__ == "__main__":
    logger = logging.getLogger('sistema_spec_logger')
    if not logger.handlers:
        from utils.logger_config import setup_logging
        logger = setup_logging()

    app = QApplication(sys.argv)
    main_window = MainApplication()
    sys.exit(app.exec())
