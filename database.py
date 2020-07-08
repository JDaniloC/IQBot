from pymongo import MongoClient #Lib pra auxiliar o trabalho com o mongo
from mongodb_py import users_schema
from mongodb_py import waiting_schema
from mongodb_py import adms_schema
import time

class Mongo:
    def __init__(self, database, users_collection, users_em_aprovacao, default_infos, adms):
        self.database = database
        self.Users_collection = users_collection
        self.Users_em_aprovacao = users_em_aprovacao
        self.Default = default_infos
        self.ADMS = adms

    def check_email(self, email):
        objct = self.Users_em_aprovacao.find_one()['_id']
        _id = self.Users_em_aprovacao.find_one(objct)
        for wait in _id['waiting']:
            if email in wait:
                return True
        return False

    def aprovar(self, email, _ID = 0):

        objct = self.Users_em_aprovacao.find_one()['_id']
        _id = self.Users_em_aprovacao.find_one(objct)
        aux = _id['waiting']
        for key in aux:
            if (email in key):
                _id['waiting'].pop(_id['waiting'].index(key))
        user = users_schema.user
        if(_ID != 0):
            user['id'] = _ID
        user['email'] = email
        self.Users_collection.insert_one(user)
        self.set_timestamp(email)
        self.Users_em_aprovacao.update_one({'_id': objct}, {'$set': {'waiting': _id['waiting']}})

    def set_timestamp(self, email):
        data = time.time() + 2592000
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

client =  MongoClient('')
IQ_DataBase = client.iqbot
Users_collection = IQ_DataBase.user
Users_em_aprovacao = IQ_DataBase.queue
default_infos = IQ_DataBase.default
ADMS = IQ_DataBase.ADMS
aprovacao = waiting_schema.queue

MongoDB = Mongo(IQ_DataBase, Users_collection, Users_em_aprovacao, default_infos, ADMS)
