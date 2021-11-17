from configparser import RawConfigParser
from pymongo import MongoClient
from schema import users_schema
from schema import adms_schema
from utils import ENV_NAME
import time, requests

config = RawConfigParser()
config.read(ENV_NAME)

DB_AUTH = config.get("DATABASE", "authentication")
LICENSOR_URL = config.get("LICENSOR", "licensorURL")
SELLER_EMAIL = config.get("LICENSOR", "sellerEmail")

class Mongo:
    def __init__(self):        
        self.client   =  MongoClient(DB_AUTH)
        self.database = self.client.iqbot 

        self.users_collection = self.database.user
        self.users_em_aprovacao = self.database.queue
        self.default_config = self.database.default
        self.ADMS_collection = self.database.ADMS
        self.entradas01 = self.database.entradas1
        self.entradas02 = self.database.entradas2
        self.entradas03 = self.database.entradas3
        self.infos = {}
        
        self.atualizar_infos()
        self.modificar_banco_users("off")
        self.modificar_banco_users("clear")

    def atualizar_infos(self):
        """ Atualiza o atributo infos """
        self.infos = self.database.infos.find_one()

    def usuarios_em_cadastro(self) -> list:
        """ Devolve todos da fila """
        return list(self.users_em_aprovacao.find())
    
    def apagar_cadastro(self, email):
        """ Remove o e-mail da fila """
        self.users_em_aprovacao.find_one_and_delete(
            {"email": email})

    def limpar_cadastro(self):
        """ Remove todos da fila """
        self.users_em_aprovacao.delete_many({})

    def adicionar_cadastro(self, email: str):
        """ Adiciona o e-mail na fila """
        self.users_em_aprovacao.insert_one(
            { "email": email })

    def verifica_cadastro(self, email: str) -> bool:
        """ Verifica se o e-mail está na fila """
        return self.users_em_aprovacao.find_one(
            { 'email': email }) != None

    def verifica_licenca(self, email: str):
        """
        Verifica se tem a licença
        Se tiver, aprova e devolve os dados
        Se não tiver remove por segurança
        """
        try:
            response = requests.get(f"{LICENSOR_URL}/clients", 
                params = { "email": email, "botName": "telegram" }
            ).json()
            if "timestamp" in response:
                tempo_restante = int(response["timestamp"])
                if tempo_restante > 0:
                    return self.aprovar_usuario(
                        email, response["message"])
                self.remover_usuario(email)
                return response["message"]
        except Exception as e:
            print(type(e), e)

        return False

    def aprovar_usuario(self, email: str, tempo_restante: str) -> dict:
        """
        Verifica se já existe um usuário
        - Se houver, devolve os dados
        - Se não houver, tira do cadastro
        E cria um novo usuário, devolvendo os dados
        """
        user_data = self.usuario_cadastrado(email)
        if user_data: 
            user_data["timestamp"] = tempo_restante
            return user_data

        self.apagar_cadastro(email)
        user_data = users_schema.user
        user_data['email'] = email
        user_data["_id"] = time.time()
        self.users_collection.insert_one(user_data)
        user_data["timestamp"] = tempo_restante
        return user_data

    def usuario_cadastrado(self, email: str) -> dict:
        """ Devolve as informações do usuário """
        return self.users_collection.find_one({'email': email})
    
    def modifica_usuario(self, email: str, info: dict):
        """ Atualiza informações do usuário """
        self.users_collection.find_one_and_update(
            { 'email': email }, { "$set": info }
        )

    def remover_usuario(self, email):
        """ Remove o usuário de determinado e-mail """
        return self.users_collection.find_one_and_delete(
            {'email': email})

    def adiciona_adm(self, _id: int):
        """
        Adiciona o ID do telegram no grupo de administradores
        """
        adm = adms_schema.ADMS
        adm['_id'] = _id
        self.ADMS_collection.insert_one(adm)

    def modifica_avancadas(self, info, valor):
        '''
        Modifica alguma informação das configurações avançadas
        '''
        # Pega o ID do documento para deleta-lo depois
        object_id = self.default_config.find_one()['_id'] 
        default = self.default_config.find_one_and_delete(
            {'_id': object_id}) 
        default[info] = valor
        self.default_config.insert_one(default)
    
    def get_avancadas(self):
        '''
        Devolve as configurações avançadas
        '''
        return self.default_config.find_one()

    def get_adms(self):
        '''
        Devolve a lista do ID dos ADMS
        '''
        return [x[0] for x in [list(value.values()) 
            for value in list(self.ADMS_collection.find())]]

    def remover_adm(self, id):
        '''
        Remove um ADM com certo ID da lista de ADMS
        '''
        return self.ADMS_collection.find_one_and_delete({"_id": id})

    def get_entradas(self, modo):
        '''
        Devolve as lista de entradas (modo 1/2)
        A depender da quantidade de gales
        '''
        resultado = []
        if modo == 1:
            resultado =  list(self.entradas01.find())
        elif modo == 2:
            resultado = list(self.entradas02.find())
        elif modo == 3:
            resultado = list(self.entradas03.find())
        return resultado

    def set_entradas(self, modo, entradas):
        '''
        Modifica a lista de entradas (modo 1/2/3)
        A depender da quantidade de gales
        '''
        if modo == 1:
            self.entradas01.delete_many({"tipo": 'taxas'})
            self.entradas01.delete_many({"tipo": 'lista'})
            self.entradas01.insert_many(entradas)
        elif modo == 2:
            self.entradas02.delete_many({"tipo": 'taxas'})
            self.entradas02.delete_many({"tipo": 'lista'})
            self.entradas02.insert_many(entradas)
        elif modo == 3:
            self.entradas03.delete_many({"tipo": 'taxas'})
            self.entradas03.delete_many({"tipo": 'lista'})
            self.entradas03.insert_many(entradas)

    def modificar_banco_users(self, opcao):
        '''
        Modifica a tabela de usuários onde:
            delete: Deleta todos os usuários
            off: Seta operando como falso em todos
            time: Renova todas as licenças
            clear: Limpa todos os que passaram as licença
        '''
        if opcao == "delete":
            self.users_collection.delete_many({})
            self.users_em_aprovacao.delete_many({})
        elif opcao == "off":
            self.users_collection.update_many(
                {}, {'$set': {'operando': False}})
        elif opcao == "time":
            data = time.time() + 2592000
            self.users_collection.update_many(
                {}, {'$set': {'timestamp': data}})
        elif opcao == "clear":
            self.users_em_aprovacao.delete_many({})
            users = self.users_collection.find(
                {"timestamp": {"$lt": time.time()}})
            for user in users:
                print("Removing:", user["email"])
                self.remover_usuario(user["email"])

    def parar_operacao(self, email):
        self.users_collection.find_one_and_update(
            {'email': email}, 
            {'$set' : {'operando': False}}
        )

    def close(self):
        '''
        Fecha a conexão com o banco de dados
        Não esqueça de fazer após as operações.
        '''
        self.client.close()
