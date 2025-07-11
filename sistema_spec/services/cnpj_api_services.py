# services/cnpj_api_service.py
import requests
import json
from config.settings import API_CNPJ_URL, CNPJA_API_TOKEN

class CnpjApiService:
    def __init__(self, api_url=API_CNPJ_URL, api_token=CNPJA_API_TOKEN):
        self.api_url = api_url
        self.api_token = api_token
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
        # Verifica se as configurações básicas estão presentes
        if not self.api_url or not self.api_token:
            print("AVISO: URL da API de CNPJ ou Token ausente em config/settings.py. A consulta de CNPJ não funcionará.")
            self.headers = None # Desabilita a API se não configurada

    def consult_cnpj(self, cnpj):
        """
        Consulta dados de CNPJ usando a API.
        Retorna os dados da empresa (dict) ou None em caso de erro/não encontrado.
        A API CNPJA.COM (ex-CNPJ.WS) espera o CNPJ no path: /office/{cnpj}
        """
        if not self.headers:
            return {"error": "API de CNPJ não configurada."}

        cleaned_cnpj = ''.join(filter(str.isdigit, cnpj))
        if len(cleaned_cnpj) != 14:
            return {"error": "CNPJ inválido. Deve conter 14 dígitos."}
        
        request_url = f"{self.api_url}{cleaned_cnpj}"

        try:
            response = requests.get(request_url, headers=self.headers, timeout=15)
            response.raise_for_status() # Lança HTTPError para respostas de erro (4xx ou 5xx)
            data = response.json()
            
            if data and data.get("status") == "ok" and "data" in data:
                return data["data"]
            elif data and "errors" in data:
                error_messages = [err.get('message', 'Erro desconhecido') for err in data['errors']]
                return {"error": ", ".join(error_messages)}
            else:
                return {"error": "Resposta inesperada da API de CNPJ."}

        except requests.exceptions.HTTPError as errh:
            return {"error": f"Erro HTTP {errh.response.status_code}: {errh.response.text}"}
        except requests.exceptions.ConnectionError as errc:
            return {"error": f"Erro de conexão com a API de CNPJ: {errc}"}
        except requests.exceptions.Timeout as errt:
            return {"error": f"Timeout na API de CNPJ: {errt}"}
        except requests.exceptions.RequestException as err:
            return {"error": f"Erro geral na API de CNPJ: {err}"}
        except json.JSONDecodeError:
            return {"error": "Resposta inválida da API de CNPJ (não é JSON válido)."}
        except Exception as e:
            return {"error": f"Erro inesperado ao consultar API de CNPJ: {e}"}