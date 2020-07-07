from pymongo import MongoClient #Lib pra auxiliar o trabalho com o mongo
from mongodb_py import Users_schema
from mongodb_py import In_waiting
from mongodb_py import adms
from telegram import *
import telepot, json



class Mongo:
    def __init__(self, cliente, database, users_collection, users_em_aprovacao, adms):
        self.cliente = cliente
        self.database = database
        self.Users_collection = users_collection
        self.Users_em_aprovacao = users_em_aprovacao
        self.ADMS = adms

    def check_email(self, email):
        objct = self.Users_em_aprovacao.find_one()['_id']
        _id = self.Users_em_aprovacao.find_one(objct)
        for i in _id['waiting']:
            if(email in i):
                return True
        return False

    def aprovar(self, email, _ID=0):

        objct = self.Users_em_aprovacao.find_one()['_id']
        _id = self.Users_em_aprovacao.find_one(objct)
        aux = _id['waiting']
        for key in aux:
            if (email in key):
                _id['waiting'].pop(_id['waiting'].index(key))
        user = Users_schema.User
        if(_ID != 0):
            user['id'] = _ID
        user['email'] = email
        user['aprovado'] = True
        self.Users_collection.insert_one(user)
        self.set_timestamp(email);
        self.Users_em_aprovacao.update_one({'_id': objct}, {'$set': {'waiting': _id['waiting']}})

    def set_timestamp(self, email):
        data = time.time() + 2592000
        self.Users_collection.find_one_and_update({'email':email}, {'$set': {'timestamp': data}})

    def setAdm(self, _id):
        Adm['_id'] = _id
        self.ADMS.insert_one(Adm)

    def renovarLicenca(self, email):
        objc = self.Users_collection.find_one({'email': email})
        objc['timestamp'] = time.time() + 2592000;

    def changeInfos(self, info, valor, email):
        user = self.Users_collection.find_one({'email': email});
        if (info == 'Valor de entrada'):
            user['valor'] = float(valor)
        elif (info == 'Payout mínimo'):
            user['minimo'] = int(valor)
        elif (info == 'StopWin'):
            user['goal'] = float(valor)
        elif (info == 'StopLoss'):
            user['stoploss'] = float(valor)
        elif (info == 'Soros'):
            user['soros'] = (True if valor == "Sim" else False)
        elif (info == 'Percentual da soros'):
            user['percent_soros'] = int(valor)
        elif (info == 'Martingale'):
            user['martin'] = (True if valor == 'Sim' else False)
        elif (info == 'Percentual do martin'):
            user['percent_martin'] = int(valor)
        elif (info == 'Máximo de gales'):
            user['max_gale'] = int(valor)
        elif (info == 'Tipo de martingale'):
            user['tipo_gale'] = valor
        self.Users_collection.find_one_and_delete({'email':email});
        self.Users_collection.insert_one(user);

    def getInfos(self, email):
        avoid = ['_id', 'id', 'adm', 'email', 'timestamp', 'operando', 'aprovado']
        aux = ["Tipo de conta",
                "Valor de entrada",
                "Payout mínimo",
                "StopWin",
                "Soros",
                "Percentual da soros",
                "StopLoss",
                "Martingale",
                "Percentual do martin",
                "Máximo de gales",
                "Tipo de martingale"]
        msg = ''
        for key, value in self.Users_collection.find_one({'email': email}).items():
            if (key not in avoid):
                msg += str(aux.pop(0)) + " : " + str(value) + '\n'
        return msg


client =  MongoClient('localhost', 27017)
IQ_DataBase = client.IQBot
Users_collection = IQ_DataBase.Users_Collection
Users_em_aprovacao = IQ_DataBase.In_wating
ADMS = IQ_DataBase.ADMS
aprovacao = In_waiting.em_aprovacao
Adm = adms.ADMS 

MongoDB = Mongo(client, IQ_DataBase, Users_collection, Users_em_aprovacao, ADMS)
