# utils/vehicle_api_client.py
import requests
from config.settings import API_VEICULOS_URL, VEICULOS_API_BEARER_TOKEN, VEICULOS_API_DEVICE_TOKEN

class VehicleAPIClient:
    def __init__(self):
        self.api_base_url = API_VEICULOS_URL
        self.bearer_token = VEICULOS_API_BEARER_TOKEN
        self.device_token = VEICULOS_API_DEVICE_TOKEN

        # Verifica se os tokens estão configurados
        if self.bearer_token == "SEU_BEARER_TOKEN_DA_API_VEICULOS_AQUI" or \
           self.device_token == "SEU_DEVICE_TOKEN_DA_API_VEICULOS_AQUI":
            self.headers = None # Desabilita a API se os tokens não forem configurados
            print("AVISO: Tokens da API de veículos não configurados em settings.py. A consulta de placa não funcionará.")
        else:
            self.headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Device-Token": self.device_token,
                "Content-Type": "application/json"
            }

    def consult_plate(self, plate):
        """
        Consulta dados de um veículo pela placa usando a API configurada.
        A URL da API deve ser capaz de aceitar a placa como parte da URL ou query param.
        Adapte 'api_url' e o formato da requisição conforme a documentação da sua API.
        """
        if not self.headers:
            print("Erro: API de veículos não configurada. Verifique os tokens em settings.py.")
            return None

        # Exemplo de como construir a URL para uma API que espera a placa no path
        # Adapte esta linha para a API real que você está utilizando.
        # Por exemplo, se a API for tipo: https://minhaapi.com/v1/veiculos?placa=ABC1234
        # api_url = f"{self.api_base_url}?placa={plate}"
        # Ou se a API for tipo: https://minhaapi.com/v1/placa/ABC1234
        api_url = f"{self.api_base_url}{plate}" # Supondo que a URL base já termina em '/'

        try:
            print(f"Consultando placa: {plate} na URL: {api_url}")
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()  # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)
            
            data = response.json()
            print(f"Resposta da API para {plate}: {data}") # Para depuração

            # Adapte o parsing da resposta JSON conforme a estrutura da sua API.
            # Este é um exemplo de como a API pode retornar os dados do veículo:
            vehicle_info = {
                "marca": data.get("marca", "N/A"),
                "modelo": data.get("modelo", "N/A"),
                "ano": data.get("anoFabricacao", "N/A"), # Ou 'anoModelo', 'ano'
                "cor": data.get("cor", "N/A")
                # Adicione outros campos conforme necessário
            }
            return vehicle_info

        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição à API de veículos para placa {plate}: {e}")
            return None
        except ValueError as e:
            print(f"Erro ao decodificar JSON da API de veículos: {e}")
            return None
        except Exception as e:
            print(f"Ocorreu um erro inesperado ao consultar a placa {plate}: {e}")
            return None

