from iqoptionapi.stable_api import IQ_Option
import time

class IQ_API:
    def __init__(self, login, senha):
        self.login = login
        self.senha = senha
        self.API = IQ_Option(login, senha)
        self.conectar()

    def conectar(self, tentativas = 5):
        '''
        Método para se conectar a plataforma.

        1 - Verifica se está conectado
        2 - Se não, espera 1 segundo e tenta se conectar

        Params:
            tentativas: Quantas vezes irá tentar se conectar caso falhar
        Return:
            Boolean True/False dependente do sucesso.
        '''
        for tentativas in range(tentativas):
            if self.API.check_connect():
                print("Conectado com sucesso\n")
                return True
            else:
                print("Tentando se conectar")
                self.API.connect()
                time.sleep(1)
        return False

    def mudar_tipo_conta(self):
        '''
        Muda o tipo de conta.
        Se estiver na conta PRACTICE irá para real
        E vice-versa
        '''
        modo = self.API.get_balance_mode()
        if modo == "PRACTICE":
            self.API.change_balance("REAL")
            print("Usando a conta real")
        else:
            self.API.change_balance("PRACTICE")
            print("usando a conta treino")

    def perfil(self):
        profile = self.API.get_profile_ansyc()
        print(profile)

    def ver_saldo(self):
        '''
        Mostra qual o saldo atual da conta.
        '''
        print(f"Saldo na conta {self.API.get_balance_mode()}:", self.API.get_balance())
        return self.API.get_balance()