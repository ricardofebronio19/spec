# utils/api_integrations.py
import requests
import json
import os
from config.settings import API_VEICULOS_URL, VEICULOS_API_BEARER_TOKEN, VEICULOS_API_DEVICE_TOKEN, API_CNPJ_URL, CNPJA_API_TOKEN

class APIIntegrations:
    def __init__(self):
        # Inicializa com tokens do settings.py
        self.veiculos_api_url = API_VEICULOS_URL
        self.veiculos_bearer_token = VEICULOS_API_BEARER_TOKEN
        self.veiculos_device_token = VEICULOS_API_DEVICE_TOKEN
        
        self.cnpj_api_url = API_CNPJ_URL
        self.cnpj_api_token = CNPJA_API_TOKEN

    def get_vehicle_data_by_plate(self, plate):
        """
        Consulta dados de veículos por placa usando uma API externa.
        Esta é uma implementação de exemplo. Você precisará adaptá-la à API real que usar.
        """
        if not self.veiculos_api_url or self.veiculos_api_url == "https://example.com/api/veiculos/placa":
            print("AVISO: URL da API de veículos não configurada. Retornando dados de exemplo.")
            # Retorna dados de exemplo se a API não estiver configurada
            return {
                "marca": "FIAT",
                "modelo": "PALIO WEEKEND ADVENTURE",
                "ano": 2015,
                "cor": "PRATA",
                "chassi": "9BD172XXXXX00000",
                "uf": "SP",
                "municipio": "SAO PAULO"
            }

        headers = {
            "Authorization": f"Bearer {self.veiculos_bearer_token}",
            "DeviceToken": self.veiculos_device_token, # Se a API exigir
            "Content-Type": "application/json"
        }
        payload = {"placa": plate}

        try:
            response = requests.post(self.veiculos_api_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status() # Lança exceções para status de erro HTTP (4xx ou 5xx)
            
            data = response.json()
            # Adapte a lógica abaixo para o formato de resposta da sua API de veículos
            if data and data.get("status") == "success": # Exemplo de verificação de sucesso
                return {
                    "marca": data.get("marca"),
                    "modelo": data.get("modelo"),
                    "ano": data.get("ano"),
                    "cor": data.get("cor"),
                    "chassi": data.get("chassi"),
                    "uf": data.get("uf"),
                    "municipio": data.get("municipio")
                }
            elif data and data.get("message"): # Exemplo de mensagem de erro
                print(f"Erro na API de veículos: {data.get('message')}")
                return None
            else:
                print(f"Resposta inesperada da API de veículos: {data}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao consultar API de veículos: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Erro: Resposta da API de veículos não é um JSON válido: {response.text}")
            return None

    def get_cnpj_data(self, cnpj):
        """
        Consulta dados de CNPJ usando a API da CNPJA com método GET.
        O CNPJ é anexado diretamente à URL.
        """
        if not self.cnpj_api_url or self.cnpj_api_token == "SEU_CNPJA_API_TOKEN_AQUI":
            print("AVISO: URL ou Token da API de CNPJ não configurados. Retornando dados de exemplo.")
            # Retorna dados de exemplo se a API não estiver configurada
            return {
                "razao_social": "EMPRESA EXEMPLO LTDA",
                "nome_fantasia": "EXEMPLO NEGÓCIOS",
                "logradouro": "RUA DAS FLORES",
                "numero": "123",
                "bairro": "CENTRO",
                "municipio": "CIDADE DEMO",
                "uf": "MG",
                "cep": "30000-000",
                "ddd_telefone_1": "31987654321",
                "email": "contato@exemplo.com.br",
                "atividade_principal": "COMERCIO VAREJISTA"
            }

        # Constrói a URL completa com o CNPJ no caminho
        full_url = f"{self.cnpj_api_url}{cnpj}" 

        headers = {
            "Authorization": f"Bearer {self.cnpj_api_token}",
            "Content-Type": "application/json" 
        }

        try:
            print(f"Chamando API CNPJ (GET): {full_url}")
            response = requests.get(full_url, headers=headers, timeout=10)
            response.raise_for_status() # Lança exceções para status de erro HTTP (4xx ou 5xx)
            
            data = response.json()
            print(f"Resposta bruta da API CNPJ: {json.dumps(data, indent=2)}") # Imprime a resposta bruta
            
            if data:
                if "error" in data: 
                    print(f"Erro da API CNPJ: {data.get('message', 'Erro desconhecido')}")
                    return {"error": data.get('message', 'Erro desconhecido da API CNPJ')}
                
                # Extrai dados da resposta e mapeia para as chaves esperadas pelo GUI
                razao_social = data.get('company', {}).get('name')
                logradouro = data.get('address', {}).get('street')
                numero = data.get('address', {}).get('number')
                bairro = data.get('address', {}).get('district')
                municipio = data.get('address', {}).get('city')
                uf = data.get('address', {}).get('state')
                cep = data.get('address', {}).get('zip') # Corrigido aqui

                # Pega o primeiro telefone, se houver
                phone = None
                if data.get('phones') and len(data['phones']) > 0:
                    area = data['phones'][0].get('area', '')
                    number = data['phones'][0].get('number', '')
                    if area and number:
                        phone = f"({area}) {number}"
                    elif number: # Caso só tenha o número
                        phone = number

                # Pega o primeiro email, se houver
                email = None
                if data.get('emails') and len(data['emails']) > 0:
                    email = data['emails'][0].get('address')
                
                return {
                    "razao_social": razao_social,
                    "logradouro": logradouro,
                    "numero": numero,
                    "bairro": bairro,
                    "municipio": municipio,
                    "uf": uf,
                    "cep": cep,
                    "ddd_telefone_1": phone, # Mapeia para o nome que o GUI espera
                    "email": email,
                    "atividade_principal": data.get('mainActivity', {}).get('text')
                }
            else:
                print("Resposta vazia da API CNPJ.")
                return {"error": "Resposta vazia da API de CNPJ."}
        except requests.exceptions.RequestException as e:
            print(f"Erro ao consultar API CNPJ: {e}")
            return {"error": f"Erro de conexão ou na API de CNPJ: {e}"}
        except json.JSONDecodeError:
            print(f"Erro: Resposta da API de CNPJ não é um JSON válido: {response.text}")
            return {"error": "Resposta da API de CNPJ não é um JSON válido."}

    def buscar_endereco_por_cep(self, cep):
        """
        Busca informações de endereço usando a API ViaCEP.
        Args:
            cep (str): O CEP a ser consultado (apenas números).
        Returns:
            dict: Um dicionário com os dados do endereço, ou None se o CEP não for encontrado ou houver erro.
        """
        cep = ''.join(filter(str.isdigit, cep))

        if len(cep) != 8:
            print("Erro: CEP deve conter 8 dígitos.")
            return None

        url = f"https://viacep.com.br/ws/{cep}/json/"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # Lança um erro para códigos de status HTTP 4xx/5xx

            data = response.json()

            if "erro" in data and data["erro"] is True: # ViaCEP retorna {"erro": true} para CEPs não encontrados
                print(f"CEP '{cep}' não encontrado pela ViaCEP.")
                return None
            
            # Mapeia as chaves da ViaCEP para as chaves esperadas na GUI
            return {
                "street": data.get('logradouro'),
                "neighborhood": data.get('bairro'),
                "city": data.get('localidade'),
                "uf": data.get('uf'),
                "zip_code": data.get('cep', '').replace('-', '') # Retorna o CEP limpo
            }

        except requests.exceptions.HTTPError as http_err:
            print(f"Erro HTTP ao consultar ViaCEP {cep}: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Erro de conexão ao consultar ViaCEP {cep}: {conn_err}. Verifique sua conexão com a internet.")
        except requests.exceptions.Timeout as timeout_err:
            print(f"Tempo esgotado ao consultar ViaCEP {cep}: {timeout_err}. O servidor não respondeu a tempo.")
        except requests.exceptions.RequestException as req_err:
            print(f"Ocorreu um erro inesperado ao consultar ViaCEP {cep}: {req_err}")
        except json.JSONDecodeError: 
            print(f"Erro: Resposta da ViaCEP não é um JSON válido para CEP {cep}: {response.text}")
        return None
