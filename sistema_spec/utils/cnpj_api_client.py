# utils/cnpj_api_client.py
import requests
from config.settings import API_CNPJ_URL, CNPJA_API_TOKEN

class CnpjAPIClient:
    def __init__(self):
        self.api_base_url = API_CNPJ_URL
        self.api_token = CNPJA_API_TOKEN

        self.headers = None

        if self.api_token and self.api_token != "SEU_TOKEN_CNPJA_AQUI":
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json" # Adicionado Accept header para boa prática
            }
            print("INFO: CNPJA API token configurado e em uso.")
        else:
            if "brasilapi.com.br" in self.api_base_url.lower():
                print("INFO: Usando BrasilAPI para consulta de CNPJ (não requer token).")
            elif "open.cnpja.com" in self.api_base_url.lower() and (not self.api_token or self.api_token == "SEU_TOKEN_CNPJA_AQUI"):
                print("AVISO: CNPJA API token não configurado ou é um placeholder em settings.py. A consulta de CNPJ pode falhar.")
            else:
                print("AVISO: Configuração de API de CNPJ incompleta/inválida em settings.py. A consulta de CNPJ pode não funcionar.")


    def consult_cnpj(self, cnpj: str) -> dict | None:
        """
        Consulta os dados de uma empresa pelo CNPJ usando a API CNPJA.com ou BrasilAPI.
        Retorna um dicionário com os dados da empresa ou None em caso de erro/não encontrado.
        """
        if not self.headers and "brasilapi.com.br" not in self.api_base_url.lower():
            print("Erro: API de CNPJ não configurada corretamente para requerer autenticação ou token ausente.")
            return None

        cnpj_cleaned = ''.join(filter(str.isdigit, cnpj))
        if not cnpj_cleaned or (len(cnpj_cleaned) != 14 and len(cnpj_cleaned) != 11):
            print(f"CNPJ/CPF '{cnpj}' inválido. Deve conter 11 ou 14 dígitos numéricos.")
            return None

        url = f"{self.api_base_url}{cnpj_cleaned}"
        
        try:
            print(f"Consultando CNPJ: {cnpj_cleaned} na URL: {url}")
            if self.headers:
                response = requests.get(url, headers=self.headers, timeout=10)
            else:
                response = requests.get(url, timeout=10)

            response.raise_for_status()

            raw_data = response.json()
            print(f"Resposta bruta da API para {cnpj_cleaned}: {raw_data}")

            # --- Lógica de Parseamento Refinada ---
            company_info = {}
            if "open.cnpja.com" in self.api_base_url.lower():
                # Dados principais da empresa
                company_details = raw_data.get('company', {})
                address_details = raw_data.get('address', {})
                phones_list = raw_data.get('phones', [])
                emails_list = raw_data.get('emails', [])

                # Extrair Razão Social / Nome Fantasia
                razao_social = company_details.get("name", "N/A") # 'name' é o campo principal para a razão social/nome

                # Extrair Telefone
                telefone = ""
                if phones_list and isinstance(phones_list, list):
                    for phone_entry in phones_list:
                        if isinstance(phone_entry, dict) and 'area' in phone_entry and 'number' in phone_entry:
                            telefone = f"({phone_entry['area']}) {phone_entry['number']}"
                            break # Pega o primeiro telefone válido

                # Extrair Email
                email = ""
                if emails_list and isinstance(emails_list, list):
                    for email_entry in emails_list:
                        if isinstance(email_entry, dict) and 'address' in email_entry:
                            email = email_entry['address']
                            break # Pega o primeiro email válido

                # Mapear para a estrutura esperada pelo formulário
                return_data = {
                    "razao_social": razao_social,
                    "telefone": telefone,
                    "email": email,
                    "endereco": {
                        "logradouro": address_details.get("street", ""),
                        "numero": address_details.get("number", ""),
                        "bairro": address_details.get("district", ""), # 'district' no CNPJA, não 'bairro'
                        "municipio": address_details.get("city", ""), # 'city' no CNPJA, não 'municipio'
                        "cep": address_details.get("zip", "") # 'zip' no CNPJA, não 'cep'
                    }
                }
                
                # A razão social precisa ser preenchida para considerar os dados válidos
                if return_data.get('razao_social') == 'N/A' or not return_data.get('razao_social'):
                    print(f"AVISO: Dados de razão social não encontrados ou vazios na resposta da CNPJA API para CNPJ {cnpj_cleaned}.")
                    return None # Retorna None para que o QMessageBox de erro seja exibido
                return return_data

            elif "brasilapi.com.br" in self.api_base_url.lower():
                # Lógica de parseamento para BrasilAPI (se você fosse usá-la)
                return_data = {
                    "razao_social": raw_data.get("razao_social", "N/A"),
                    "telefone": raw_data.get("ddd_telefone_1", "") or raw_data.get("ddd_telefone_2", ""),
                    "email": raw_data.get("email", ""),
                    "endereco": {
                        "logradouro": raw_data.get("logradouro", ""),
                        "numero": raw_data.get("numero", ""),
                        "bairro": raw_data.get("bairro", ""),
                        "municipio": raw_data.get("municipio", ""),
                        "cep": raw_data.get("cep", "")
                    }
                }
                if return_data.get('razao_social') == 'N/A' or not return_data.get('razao_social'):
                    print(f"AVISO: Dados de razão social não encontrados na resposta da BrasilAPI para CNPJ {cnpj_cleaned}.")
                    return None
                return return_data
            else:
                print(f"AVISO: Nenhuma lógica de parseamento específica para a URL da API: {self.api_base_url}. Retornando None.")
                return None # Retorna None se não houver lógica de parseamento específica

        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 404:
                print(f"CNPJ {cnpj_cleaned} não encontrado ou inválido na API. Status 404.")
                # Não exibe QMessageBox aqui, a lógica no gui_app.py fará isso.
            else:
                print(f"Erro HTTP ao consultar CNPJ {cnpj_cleaned}: {http_err} - Resposta: {response.text}")
            return None
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Erro de conexão ao consultar CNPJ {cnpj_cleaned}: {conn_err}. Verifique sua conexão com a internet.")
            return None # O gui_app.py vai exibir o erro genérico
        except requests.exceptions.Timeout as timeout_err:
            print(f"Tempo esgotado ao consultar CNPJ {cnpj_cleaned}: {timeout_err}. A API demorou muito para responder.")
            return None # O gui_app.py vai exibir o erro genérico
        except requests.exceptions.RequestException as req_err:
            print(f"Erro na requisição ao consultar CNPJ {cnpj_cleaned}: {req_err}")
            return None # O gui_app.py vai exibir o erro genérico
        except Exception as e:
            print(f"Exceção inesperada ao consultar CNPJ {cnpj_cleaned}: {e}")
            return None # O gui_app.py vai exibir o erro genérico
