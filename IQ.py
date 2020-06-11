from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
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

    def mudar_treino(self):
        self.API.change_balance("PRACTICE")
    
    def mudar_real(self):
        self.API.change_balance("REAL")

    def tipo_conta(self):
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

    def conversor_timestamp(self, timestamp):
        '''
        Converte o timestamp para horário normal
        '''
        return datetime.fromtimestamp(timestamp)

    def perfil(self):
        '''
        Mostra o perfil de forma simplificada e devolve o dicionário com mais informações
        return: dict
        '''
        profile = self.API.get_profile_ansyc()
        resultado = f"""
        [Perfil]
Email: {profile['email']}
Nome: {profile["name"]}
TimeZone: {profile["tz"]} {profile["tz_offset"]}
Diferença de tempo: {profile["timediff"]}\n
Saldo: {profile["currency_char"]} {profile["balance"]}
Todas as carteiras:\n"""
        for tipo in profile['balances']:
            resultado += tipo['currency'] + ": " + str(tipo["amount"]) + "\n"
        print(resultado)
        return profile

    def ver_saldo(self):
        '''
        Mostra qual o saldo atual da conta.
        '''
        print(f"Saldo na conta {self.API.get_balance_mode()}:", self.API.get_balance())
        return self.API.get_balance()
    
    def velas(self, par, segundos, quantidade):
        '''
        Devolve as velas de forma simplificada
        return:
            dict list: [{}]
        '''
        velas = self.API.get_candles(par, segundos, quantidade, time.time())
        for vela in velas:
            print(f"{self.conversor_timestamp(vela['from'])} - {self.conversor_timestamp(vela['to'])}")
            print(f"abertura: {vela['open']}\nFechamento: {vela['close']}")
        return velas

    def humor(self, par):
        '''
        Devolve o humor ATUAL dos traders
        '''
        self.API.start_mood_stream(par)
        resultado = int(100 * round(self.API.get_traders_mood(par), 2))
        self.API.stop_mood_stream(par)
        print(f"{par}: {resultado}")
        return resultado

    def payout_digital(self, par, timeframe = 1):
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
        payouts = self.API.get_all_profit()
        return payouts[par]['binary'] * 100

    def abertas(self, tipo = "digital"):
        '''
        Exibe todas as paridades abertas
        Devolve um dicionário onde a chave é a paridade
        E o valor é a rentabilidade
        return:
            dict: tuple
        '''
        print(f"\nParidades abertas\n")
        paridades = self.API.get_all_open_time()
        abertas = {}

        if tipo != "digital":
            payouts = self.API.get_all_profit()
            for par in paridades["turbo"]:
                if paridades['turbo'][par]["open"]: 
                    abertas[str(par)] = (payouts[par]['turbo'], payouts[par]['binary'])
                    print(f"[TURBO] {par} - {int(payouts[par]['turbo'] * 100) if type(payouts[par]['turbo']) != dict else '00'}% {int(payouts[par]['binary'] * 100) if type(payouts[par]['binary']) != dict else '00'}%")
        else:
            for par in paridades["digital"]:
                if paridades['digital'][par]["open"]: 
                    abertas[str(par)] = self.payout_digital(par)
                    print(f"[DIGITAL] {par} {self.payout_digital(par)}%")

        return abertas
    
    def historico(self, quantidade, tipo = "binary-option"):
        '''
        Devolve o histórico das operações anteriores
        Params:
            quantidade: int (quantas operações)
            tipo: binary-option ou turbo-option
        '''
        # Como pega a digital?
        status, historico = self.API.get_position_history_v2(tipo, quantidade, 0, 0, 0)
        lista = []
        for operacao in historico['positions']:
            lucro = operacao['close_profit']
            resultado = {
                "paridade": operacao['raw_event']['instrument_underlying'] if tipo == "turbo-binary" else operacao['raw_event']['active'],
                "abertura":  self.conversor_timestamp(operacao['open_time'] / 1000),
                "fechamento": self.conversor_timestamp(operacao['close_time'] / 1000),
                "lucro": lucro if lucro == 0 else round(lucro -  operacao['invest'], 2),
                "direcao": operacao['raw_event']['instrument_dir'] if tipo == "turbo-option" else operacao['raw_event']['direction']
            }
            lista.append(resultado)

        for operacao in lista:
            for key, value in operacao.items():
                print(f"{key}: {value}")
            print()

        return lista
    
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

                print(f"{resultado}: {round(lucro, 2)}")
            else:
                print("Um erro aconteceu!")
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
                resultado, lucro = "erro", 0
                print(identificador)
        return resultado, round(lucro, 2)
    
    def esperarAte(self, horas, minutos, segundos = 0):
        '''
        '''
        alvo = datetime.now().replace(hour = horas, minute = minutos, second = segundos, microsecond = 0)
        segundos = alvo.timestamp() - datetime.now().timestamp()
        time.sleep(segundos)
    
    def martingale(self, tipo_martin, payout, valor, perca, lucro = None):
        '''
        Calcula o martingale onde:
            tipo_martin: simples (valor * 2.2) ou auto
            payout: profit da paridade
            valor: entrada do valor
            lucro_esperado: alvo
            perca: limite de LOSS
        '''
        if tipo_martin == "simples":
            return round(valor * 2.25, 2)
        else:
            if lucro != None:
                alvo = round(abs(perca) + lucro / payout, 2)
            else:
                alvo = round(abs(perca) + valor * payout, 2)
            return round(alvo/payout, 2)
    