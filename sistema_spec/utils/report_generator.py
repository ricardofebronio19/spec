# utils/report_generator.py
import os
import pandas as pd
from datetime import datetime
import json # Para lidar com filters_json
from config.settings import REPORTS_DIR
from models.report_model import Report
from utils.helpers import get_current_timestamp

class ReportGenerator:
    def __init__(self, user_id=None):
        # Garante que a tabela de relatórios é criada quando o manager é inicializado
        Report._create_table()
        os.makedirs(REPORTS_DIR, exist_ok=True)
        self.user_id = user_id # ID do usuário logado

    def _save_report_record(self, report_type, file_path, filters_dict=None):
        """Salva um registro do relatório gerado no banco de dados."""
        try:
            filters_json = json.dumps(filters_dict) if filters_dict else None
            report = Report(
                report_type=report_type,
                generation_date=get_current_timestamp(),
                generated_by_user_id=self.user_id,
                file_path=file_path,
                filters_json=filters_json
            )
            report.save()
            print(f"Registro de relatório salvo: {file_path}")
            return True
        except Exception as e:
            print(f"Erro ao salvar registro de relatório: {e}")
            return False

    def generate_sales_report(self, sales_data, start_date=None, end_date=None, export_format="excel"):
        """Gera um relatório de vendas."""
        if not sales_data:
            return False, "Nenhum dado de vendas para gerar relatório."

        df = pd.DataFrame(sales_data)
        
        # Formatar colunas financeiras
        df['total_amount'] = df['total_amount'].apply(lambda x: f"R$ {x:.2f}".replace('.', ','))
        df['discount_applied'] = df['discount_applied'].apply(lambda x: f"R$ {x:.2f}".replace('.', ','))

        filename = f"relatorio_vendas_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = os.path.join(REPORTS_DIR, f"{filename}.{export_format}")

        filters = {"start_date": start_date, "end_date": end_date}

        try:
            if export_format == "excel":
                df.to_excel(file_path, index=False)
            elif export_format == "pdf":
                # Para PDF, você precisaria de uma biblioteca como FPDF ou ReportLab
                # Esta é uma implementação MUITO básica e pode precisar de mais trabalho.
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Relatório de Vendas", ln=True, align='C')
                pdf.cell(200, 10, txt=f"Período: {start_date or 'Início'} a {end_date or 'Fim'}", ln=True, align='C')
                pdf.ln(10) # Line break

                # Adicionar cabeçalhos
                col_widths = [15, 25, 40, 25, 25, 30] # Ajustar conforme necessário
                headers = ["ID", "Data", "Cliente", "Total", "Desc.", "Pagamento"]
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header, 1, 0, 'C')
                pdf.ln()

                # Adicionar dados
                for _, row in df.iterrows():
                    pdf.cell(col_widths[0], 10, str(row['id']), 1)
                    pdf.cell(col_widths[1], 10, str(row['sale_date'].split('T')[0]), 1)
                    pdf.cell(col_widths[2], 10, row['customer_name'], 1)
                    pdf.cell(col_widths[3], 10, str(row['total_amount']), 1, 0, 'R')
                    pdf.cell(col_widths[4], 10, str(row['discount_applied']), 1, 0, 'R')
                    pdf.cell(col_widths[5], 10, row['payment_method'], 1)
                    pdf.ln()
                
                pdf.output(file_path)
            else:
                return False, "Formato de exportação não suportado."

            self._save_report_record("Vendas", file_path, filters)
            return True, file_path
        except Exception as e:
            return False, f"Erro ao gerar relatório de vendas: {e}"

    def generate_stock_report(self, stock_data, export_format="excel"):
        """Gera um relatório de estoque."""
        if not stock_data:
            return False, "Nenhum dado de estoque para gerar relatório."

        df = pd.DataFrame(stock_data)
        
        # Formatar colunas financeiras
        df['price'] = df['price'].apply(lambda x: f"R$ {x:.2f}".replace('.', ','))
        df['cost'] = df['cost'].apply(lambda x: f"R$ {x:.2f}".replace('.', ','))

        filename = f"relatorio_estoque_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = os.path.join(REPORTS_DIR, f"{filename}.{export_format}")

        try:
            if export_format == "excel":
                df.to_excel(file_path, index=False)
            elif export_format == "pdf":
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Relatório de Estoque", ln=True, align='C')
                pdf.ln(10)

                col_widths = [15, 50, 25, 25, 20, 20, 30] # Ajustar conforme necessário
                headers = ["ID", "Nome", "Nº Peça", "Fabricante", "Estoque", "Min. Est.", "Fornecedor"]
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header, 1, 0, 'C')
                pdf.ln()

                for _, row in df.iterrows():
                    pdf.cell(col_widths[0], 10, str(row['id']), 1)
                    pdf.cell(col_widths[1], 10, row['name'], 1)
                    pdf.cell(col_widths[2], 10, row['part_number'], 1)
                    pdf.cell(col_widths[3], 10, row['manufacturer'], 1)
                    pdf.cell(col_widths[4], 10, str(row['stock']), 1, 0, 'R')
                    pdf.cell(col_widths[5], 10, str(row['min_stock']), 1, 0, 'R')
                    pdf.cell(col_widths[6], 10, row['supplier_name'], 1)
                    pdf.ln()
                
                pdf.output(file_path)
            else:
                return False, "Formato de exportação não suportado."

            self._save_report_record("Estoque", file_path)
            return True, file_path
        except Exception as e:
            return False, f"Erro ao gerar relatório de estoque: {e}"

    def generate_financial_report(self, financial_data, start_date=None, end_date=None, export_format="excel"):
        """Gera um relatório financeiro."""
        if not financial_data:
            return False, "Nenhum dado financeiro para gerar relatório."

        # Converte a lista de objetos FinancialTransaction para uma lista de dicionários
        # antes de criar o DataFrame.
        financial_data_dicts = [transaction.__dict__ for transaction in financial_data]
        df = pd.DataFrame(financial_data_dicts)

        # Formatar colunas financeiras
        df['amount'] = df['amount'].apply(lambda x: f"R$ {x:.2f}".replace('.', ','))

        filename = f"relatorio_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = os.path.join(REPORTS_DIR, f"{filename}.{export_format}")

        filters = {"start_date": start_date, "end_date": end_date}

        try:
            if export_format == "excel":
                df.to_excel(file_path, index=False)
            elif export_format == "pdf":
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Relatório Financeiro", ln=True, align='C')
                pdf.cell(200, 10, txt=f"Período: {start_date or 'Início'} a {end_date or 'Fim'}", ln=True, align='C')
                pdf.ln(10)

                col_widths = [15, 30, 20, 25, 40, 50] # Ajustar conforme necessário
                headers = ["ID", "Data", "Tipo", "Valor", "Categoria", "Descrição"]
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header, 1, 0, 'C')
                pdf.ln()

                for _, row in df.iterrows():
                    pdf.cell(col_widths[0], 10, str(row['id']), 1)
                    pdf.cell(col_widths[1], 10, str(row['transaction_date'].split('T')[0]), 1)
                    pdf.cell(col_widths[2], 10, row['type'], 1)
                    pdf.cell(col_widths[3], 10, str(row['amount']), 1, 0, 'R')
                    pdf.cell(col_widths[4], 10, row['category'], 1)
                    pdf.cell(col_widths[5], 10, row['description'], 1)
                    pdf.ln()
                
                pdf.output(file_path)
            else:
                return False, "Formato de exportação não suportado."

            self._save_report_record("Financeiro", file_path, filters)
            return True, file_path
        except Exception as e:
            return False, f"Erro ao gerar relatório financeiro: {e}"

