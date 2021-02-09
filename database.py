from configparser import RawConfigParser
from schema import waiting_schema
from schema import users_schema
from schema import adms_schema
from pymongo import MongoClient
import time


config = RawConfigParser()
config.read(".env")

autenticacao = config.get("DATABASE", "autentication")

class Mongo:
    def __init__(self, database, users_collection, 
        users_em_aprovacao, default_infos, adms, 
        entrada1, entrada2, entrada3, infos):
        self.database = database
        self.Users_collection = users_collection
        self.Users_em_aprovacao = users_em_aprovacao
        self.Default = default_infos
        self.ADMS = adms
        self.entradas01 = entrada1
        self.entradas02 = entrada2
        self.entradas03 = entrada3
        self.infos_collection = infos
        self.infos = infos.find_one()

    def atualizar_infos(self):
        self.infos = infos.find_one()

    def adicionar_cadastro(self, email):
        '''
        Adiciona o e-mail na fila de aprovação
        '''
        self.Users_em_aprovacao.insert_one({"email": email})

    def verifica_cadastro(self, email):
        '''
        Verifica se o e-mail está em aprovação
        '''
        objct = self.Users_em_aprovacao.find_one({'email':email})
        if not objct:
            return False
        return True

    def aprovar(self, email, plano):
        '''
        Tira o e-mail de em aprovação e coloca no rol de usuários
        '''
        user = self.apagar_cadastro(email)
        if user:
            user = users_schema.user
            user['email'] = email
            if plano == "teste":
                user['timestamp'] = time.time() + 43200
            else:
                user['timestamp'] = time.time() + 2592000
            user['plano'] = plano
            user["_id"] = time.time()
            self.Users_collection.insert_one(user)

    def renovar_licenca(self, email, plano):
        '''
        Aumenta a licença de determinado e-mail
        '''
        if plano == "teste":
            data = time.time() + 43200
        else:
            data = time.time() + 2592000
        self.Users_collection.find_one_and_update(
            {'email':email}, {'$set': {
                'timestamp': data,
                'plano': plano
        }})

    def adiciona_adm(self, _id):
        '''
        Adiciona o ID do telegram no grupo de admnistradores
        '''
        adm = adms_schema.ADMS
        adm['_id'] = _id
        self.ADMS.insert_one(adm)

    def modifica_usuario(self, info, email):
        '''
        Modifica as informações do usuário de determinado e-mail
        '''
        user = self.remover_usuario(email)
        user.update(info)
        self.Users_collection.insert_one(user)

    def modifica_avancadas(self, info, valor):
        '''
        Modifica alguma informação das configurações avançadas
        '''
        # Pega o ID do documento para deleta-lo depois
        object_id = self.Default.find_one()['_id'] 
        default = self.Default.find_one_and_delete({'_id': object_id}) 
        default[info] = valor
        self.Default.insert_one(default) #Insere o doc alterado no banco

    def remover_usuario(self, email):
        '''
        Remove o usuário de determinado e-mail
        Devolve o usuário removido
        '''
        return self.Users_collection.find_one_and_delete(
            {'email': email})

    def apagar_cadastro(self, email):
        '''
        Tira o e-mail da fila de cadastro
        Devolve o objeto removido
        '''
        return self.Users_em_aprovacao.find_one_and_delete(
            {"email": email})

    def get_avancadas(self):
        '''
        Devolve as configurações avançadas
        '''
        return self.Default.find_one()

    def get_user(self, email):
        '''
        Devolve as informações do usuário a partir do e-mail
        '''
        return self.Users_collection.find_one({'email': email})

    def get_adms(self):
        '''
        Devolve a lista do ID dos ADMS
        '''
        return [x[0] for x in [list(value.values()) 
            for value in list(self.ADMS.find())]]

    def remover_adm(self, id):
        '''
        Remove um ADM com certo ID da lista de ADMS
        '''
        return self.ADMS.find_one_and_delete({"_id": id})

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
        if opcao == "delete":
            self.Users_collection.delete_many({})
        elif opcao == "off":
            self.Users_collection.update_many(
                {}, {'$set': {'operando': False}})
        elif opcao == "time":
            data = time.time() + 2592000
            self.Users_collection.update_many(
                {}, {'$set': {'timestamp': data}})
        elif opcao == "clear":
            data = time.time()
            users = self.Users_collection.find()
            for user in users:
                if user["timestamp"] < data:
                    print("Removing:", user["email"])
                    self.remover_usuario(user["email"])
                break


client =  MongoClient(autenticacao)
database = client.iqbot 
users_list = database.user
queue_list = database.queue
default = database.default
ADMS = database.ADMS
aprovacao = waiting_schema.queue
entrada1 = database.entradas1
entrada2 = database.entradas2
entrada3 = database.entradas3
infos = database.infos

MongoDB = Mongo(
    database, users_list, queue_list, default, 
    ADMS, entrada1, entrada2, entrada3, infos
)
MongoDB.modificar_banco_users("clear")