from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime
import os

# Necessário: pip install reportlab

def generate_pdf(data, headers, title="Relatório", filename="report", directory="."):
    """
    Gera um arquivo PDF a partir de dados tabulares.

    Args:
        data (list of lists): Dados para a tabela do PDF (cada lista interna é uma linha).
        headers (list of str): Cabeçalhos da tabela.
        title (str): Título do relatório.
        filename (str): Nome base do arquivo (sem extensão).
        directory (str): Diretório onde o arquivo será salvo.
    Returns:
        tuple: (bool, str) - True e caminho do arquivo, ou False e mensagem de erro.
    """
    if not data:
        return False, "Nenhum dado para gerar PDF."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_filename = os.path.join(directory, f"{filename}_{timestamp}.pdf")

    try:
        os.makedirs(directory, exist_ok=True)
        doc = SimpleDocTemplate(full_filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Título
        elements.append(Paragraph(title, styles['h1']))
        elements.append(Spacer(1, 0.2 * letter[1]))

        # Tabela
        table_data = [headers] + data
        # Define a largura das colunas para tentar encaixar no tamanho da página
        col_widths = [doc.width / len(headers) for _ in headers]
        table = Table(table_data, colWidths=col_widths) # Passa colWidths

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

        doc.build(elements)
        return True, full_filename
    except Exception as e:
        return False, f"Erro ao gerar PDF: {e}"