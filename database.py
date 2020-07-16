from pymongo import MongoClient #Lib pra auxiliar o trabalho com o mongo
from mongodb_py import users_schema
from mongodb_py import waiting_schema
from mongodb_py import adms_schema
import time, pprint

class Mongo:
    def __init__(self, database, users_collection, users_em_aprovacao, default_infos, adms, entrada1, entrada2):
        self.database = database
        self.Users_collection = users_collection
        self.Users_em_aprovacao = users_em_aprovacao
        self.Default = default_infos
        self.ADMS = adms
        self.Entrada1 = entrada1
        self.Entrada2 = entrada2

    def check_email(self, email):
        objct = self.Users_em_aprovacao.find_one({'email':email})
        if not objct:
            return False
        return True

    def aprovar(self, email):
        user = self.Users_em_aprovacao.find_one_and_delete(
            {"email": email})
        if user:
            user = users_schema.user
            user['email'] = email
            user['timestamp'] = time.time() + 604800 # 2592000
            user["_id"] = time.time()
            self.Users_collection.insert_one(user)

    def renovar_licenca(self, email):
        data = time.time() + 604800 # 2592000
        self.Users_collection.find_one_and_update({'email':email}, {'$set': {'timestamp': data}})

    def add_adm(self, _id):
        adm = adms_schema.ADMS
        adm['_id'] = _id
        self.ADMS.insert_one(adm)

    def change_user(self, info, email):
        user = self.Users_collection.find_one_and_delete({'email':email})
        user.update(info)
        self.Users_collection.insert_one(user)

    def change_avancadas(self, info, valor):
        # Pega o ID do documento para deleta-lo depois
        object_id = self.Default.find_one()['_id'] 
        default = self.Default.find_one_and_delete({'_id': object_id}) 
        default[info] = valor
        self.Default.insert_one(default) #Insere o doc alterado no banco

    def get_avancadas(self):
        default = self.Default.find_one()
        return default

    def get_user(self, email):
        user = self.Users_collection.find_one({'email': email})
        return user

    def get_entradas(self, modo):
        if modo == 1:
            return list(self.Entrada1.find())
        else:
            return list(self.Entrada2.find())

    def set_entradas(self, modo, entradas):
        if modo == 1:
            self.Entrada1.delete_many({"ordem": 'call'})
            self.Entrada1.delete_many({"ordem": 'put'})
            self.Entrada1.insert_many(entradas)
        else:
            self.Entrada2.delete_many({"ordem": 'call'})
            self.Entrada2.delete_many({"ordem": 'put'})
            self.Entrada2.insert_many(entradas)


client =  MongoClient('mongodb+srv://Danilo:Donilo123@cluster0-6cyzb.mongodb.net/iqbot?retryWrites=true&w=majority')
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
