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
    def __init__(self):        
        self.client   =  MongoClient(autenticacao)
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
        self.infos = self.database.infos.find_one()

    def adicionar_cadastro(self, email):
        '''
        Adiciona o e-mail na fila de aprovação
        '''
        self.users_em_aprovacao.insert_one({"email": email})

    def verifica_cadastro(self, email):
        '''
        Verifica se o e-mail está em aprovação
        '''
        objct = self.users_em_aprovacao.find_one({'email':email})
        if not objct:
            return False
        return True

    def verifica_licenca(self, email):
        objct = self.users_collection.find_one({'email':email})
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
            elif plano == "mensal":
                user['timestamp'] = time.time() + 2592000
            elif plano == "trimestral":
                user['timestamp'] = time.time() + 7776000
            else:
                user['timestamp'] = time.time() + 31104000
            user['plano'] = plano
            user["_id"] = time.time()
            self.users_collection.insert_one(user)

    def renovar_licenca(self, email, plano):
        '''
        Aumenta a licença de determinado e-mail
        '''
        if plano == "teste":
            data = time.time() + 43200
        if plano == "semanal":
            data = time.time() + 604800
        elif plano == "mensal":
            data = time.time() + 2592000
        elif plano == "trimestral":
            data = time.time() + 7776000
        else:
            data = time.time() + 31104000
        self.users_collection.find_one_and_update(
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
        self.ADMS_collection.insert_one(adm)

    def modifica_usuario(self, info, email):
        '''
        Modifica as informações do usuário de determinado e-mail
        '''
        user = self.remover_usuario(email)
        user.update(info)
        self.users_collection.insert_one(user)

    def modifica_avancadas(self, info, valor):
        '''
        Modifica alguma informação das configurações avançadas
        '''
        # Pega o ID do documento para deleta-lo depois
        object_id = self.default_config.find_one()['_id'] 
        default = self.default_config.find_one_and_delete(
            {'_id': object_id}) 
        default[info] = valor
        self.default_config.insert_one(default) #Insere o doc alterado no banco

    def remover_usuario(self, email):
        '''
        Remove o usuário de determinado e-mail
        Devolve o usuário removido
        '''
        return self.users_collection.find_one_and_delete(
            {'email': email})

    def apagar_cadastro(self, email):
        '''
        Tira o e-mail da fila de cadastro
        Devolve o objeto removido
        '''
        return self.users_em_aprovacao.find_one_and_delete(
            {"email": email})

    def get_avancadas(self):
        '''
        Devolve as configurações avançadas
        '''
        return self.default_config.find_one()

    def get_user(self, email):
        '''
        Devolve as informações do usuário a partir do e-mail
        '''
        return self.users_collection.find_one({'email': email})

    def usuarios_cadastrados(self):
        return self.users_collection.find()
    def usuarios_em_cadastro(self):
        return self.users_em_aprovacao.find()

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
        elif opcao == "off":
            self.users_collection.update_many(
                {}, {'$set': {'operando': False}})
        elif opcao == "time":
            data = time.time() + 2592000
            self.users_collection.update_many(
                {}, {'$set': {'timestamp': data}})
        elif opcao == "clear":
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