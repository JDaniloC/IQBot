from pymongo import MongoClient #Lib pra auxiliar o trabalho com o mongo
from mongodb_py import users_schema
from mongodb_py import waiting_schema
from mongodb_py import adms_schema
import time, pprint

autenticacao = "mongodb+srv://Daniel:1231231414@cluster0.o6fxw.gcp.mongodb.net/iqbot?retryWrites=true&w=majority"

class Mongo:
    def __init__(self, database, users_collection, users_em_aprovacao, default_infos, adms, entrada1, entrada2):
        self.database = database
        self.Users_collection = users_collection
        self.Users_em_aprovacao = users_em_aprovacao
        self.Default = default_infos
        self.ADMS = adms
        self.Entrada1 = entrada1
        self.Entrada2 = entrada2

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
            user['timestamp'] = time.time() + 2592000
            user['plano'] = plano
            user["_id"] = time.time()
            self.Users_collection.insert_one(user)

    def renovar_licenca(self, email, plano):
        '''
        Aumenta a licença de determinado e-mail
        '''
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

    def get_entradas(self, modo):
        '''
        Devolve as lista de entradas (modo 1/2)
        A depender da quantidade de gales
        '''
        if modo == 1:
            return list(self.Entrada1.find())
        else:
            return list(self.Entrada2.find())

    def set_entradas(self, modo, entradas):
        '''
        Modifica a lista de entradas (modo 1/2)
        A depender da quantidade de gales
        '''
        if modo == 1:
            self.Entrada1.delete_many({"ordem": 'call'})
            self.Entrada1.delete_many({"ordem": 'put'})
            self.Entrada1.insert_many(entradas)
        elif modo == 2:
            self.Entrada2.delete_many({"ordem": 'call'})
            self.Entrada2.delete_many({"ordem": 'put'})
            self.Entrada2.insert_many(entradas)

    def modificar_banco_users(self, opcao):
        if opcao == "clear":
            self.Users_collection.delete_many({})
        elif opcao == "off":
            self.Users_collection.update_many(
                {}, {'$set': {'operando': False}})
        elif opcao == "time":
            data = time.time() + 2592000
            self.Users_collection.update_many(
                {}, {'$set': {'timestamp': data}})

client =  MongoClient(autenticacao)
IQ_DataBase = client.iqbot 
Users_collection = IQ_DataBase.user
Users_em_aprovacao = IQ_DataBase.queue
default_infos = IQ_DataBase.default
ADMS = IQ_DataBase.ADMS
aprovacao = waiting_schema.queue
entrada1 = IQ_DataBase.entradas1
entrada2 = IQ_DataBase.entradas2

MongoDB = Mongo(
    IQ_DataBase, Users_collection, Users_em_aprovacao, default_infos, ADMS, entrada1, entrada2
)
