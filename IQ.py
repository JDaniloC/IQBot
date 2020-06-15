from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
import time

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
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
                print("+ Conectado com sucesso!\n")
                return True
            else:
                print("Tentando se conectar...")
                self.API.connect()
                time.sleep(1)
        return False

    def mudar_treino(self):
        '''
        Muda para a conta treino
        '''
        print(" - Usando a conta treino -\n")
        self.API.change_balance("PRACTICE")
    
    def mudar_real(self):
        '''
        Muda para a conta real
        '''
        print(" - Usando a conta real -\n")
        self.API.change_balance("REAL")

    def tipo_conta(self):
        '''
        Devolve o tipo de conta
        '''
        return self.API.get_balance_mode()

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

    def payout_digital(self, par, timeframe = 1):
        '''
        Devolve o payout de uma paridade digital
        '''
        self.API.subscribe_strike_list(par, timeframe)
        while True:
            resultado = self.API.get_digital_current_profit(par, timeframe)
            if resultado:
                resultado = int(resultado)
                break
            time.sleep(1)
        self.API.unsubscribe_strike_list(par, timeframe)
        return resultado

    def payout_binaria(self, par):
        '''
        Devolve o payout de uma paridade binária
        '''
        payouts = self.API.get_all_profit()
        return payouts[par]['binary'] * 100
    
    def ordem(self, par, direcao = "call", tempo = 1, valor = 1, tipo = "binary"):
        '''
        Faz uma ordem e devolve o resultado.
        Params:
            par: paridade
            direcao: "call" para comprar ou "put" para vender
            tempo: 1, 10, 15
            valor: dinheiro investido 2 - saldo
            tipo: binary ou digital
        return:
            (resultado, lucro)
        '''
        if tipo == "binary":
            status, identificador = self.API.buy(valor, par, direcao, tempo)
            if status:
                print(f"Operação realizada: {par}-{tipo} {direcao} ${valor} {tempo}s")

                resultado, lucro = self.API.check_win_v4(identificador)

                print(f"\n $$$ {resultado}: {round(lucro, 2)} $$$")
            else:
                print(f"  ! Um erro aconteceu: {par}-{tipo} {direcao} {valor}!")
                resultado, lucro = "error", 0
        else:
            identificador = self.API.buy_digital_spot(par, valor, direcao, tempo)
            
            if isinstance(identificador, int):
                print(f"Operação realizada: {par}-{tipo} {direcao} ${valor} {tempo}s")

                status = False
                while not status:
                    status, lucro = self.API.check_win_digital_v2(identificador)

                if lucro > 0:
                    resultado = "win"
                    print(f"WIN: {round(lucro, 2)}")
                else:
                    resultado = "loose"
                    print(f"LOSS: {round(lucro, 2)}")
                verificador = False

            else:
                print(f"  ! Um erro aconteceu: {par}-{tipo} {direcao} {valor}!")
                resultado, lucro = "erro", 0
                print(identificador)
        return resultado, round(lucro, 2)
    
    @staticmethod
    def esperarAte(horas, minutos, segundos = 0):
        '''
        Espera até determinada hora:minuto:segundo do dia
        '''
        alvo = datetime.now().replace(hour = horas, minute = minutos, second = segundos, microsecond = 0)
        segundos = alvo.timestamp() - datetime.now().timestamp()
        if segundos > 10:
            print(f" [...] Esperando até {alvo} [...]")
            time.sleep(segundos)
            return True
        if segundos > -10:
            if segundos < 0:
                print(f"Fazendo operação {round(abs(segundos), 2)} atrasado")
            return True
        return False
    
    @staticmethod
    def martingale(tipo_martin, payout, perca, valor = 1, lucro = 1):
        '''
        Calcula o martingale onde:
            tipo_martin: 
                simples (valor * 2)
                agressivo (perca * 2.3)
                leve (vai manter o lucro inicial)
                seguro (apenas recupera o valor)
            payout: profit da paridade
            perca: valor perdido
            valor: entrada do valor
            lucro: alvo inicial
        '''
        tipo_martin = tipo_martin.lower()
        if tipo_martin == "agressivo":
            return round(abs(perca) * 2.3, 2)
        elif tipo_martin == "simples":
            return round(valor * 2)
        elif tipo_martin == "leve":
            return (abs(perca) + lucro) / payout
        else:
            return round(abs(perca)/payout, 2)
