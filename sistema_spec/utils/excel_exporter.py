import pandas as pd # Necessário: pip install pandas openpyxl
from datetime import datetime
import os

def export_to_excel(data, headers, filename="report", directory="."):
    """
    Exporta uma lista de dicionários para um arquivo Excel.

    Args:
        data (list of dict): Lista de dicionários, onde cada dicionário é uma linha.
        headers (list of str): Lista de strings para os cabeçalhos das colunas.
        filename (str): Nome base do arquivo (sem extensão).
        directory (str): Diretório onde o arquivo será salvo.
    Returns:
        tuple: (bool, str) - True e caminho do arquivo, ou False e mensagem de erro.
    """
    if not data:
        return False, "Nenhum dado para exportar."

    # Certifica-se de que todas as colunas do header estão presentes nos dados
    # E que a ordem seja mantida
    df = pd.DataFrame(data, columns=headers)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_filename = os.path.join(directory, f"{filename}_{timestamp}.xlsx")

    try:
        os.makedirs(directory, exist_ok=True)
        df.to_excel(full_filename, index=False)
        return True, full_filename
    except Exception as e:
        return False, f"Erro ao exportar para Excel: {e}"