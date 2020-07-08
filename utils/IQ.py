from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
import time

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
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

    def perfil(self):
        '''
        Mostra o perfil de forma simplificada e devolve o dicionário com mais informações
        return: dict
        '''
        profile = self.API.get_profile()['result']
        resultado = f"""
        [Perfil]
Email: {profile['email']}
Nome: {profile["name"]}
TimeZone: {profile["tz"]} {profile["tz_offset"]}
Diferença de tempo: {profile["timediff"]}\n
Saldo: {profile["currency_char"]} {profile["balance"]}
Todas as carteiras:\n"""
        for tipo in profile['balances']:
            resultado += tipo['currency'] + ": " + str(tipo["amount"]/1000000) + "\n"
        print(resultado)
        return profile

    def payout_digital(self, par, timeframe = 1):
        '''
        Devolve o payout de uma paridade digital
        '''
        try:
            contador = 0
            self.API.subscribe_strike_list(par, timeframe)
            while True:
                resultado = self.API.get_digital_current_profit(par, timeframe)
                if resultado:
                    resultado = int(resultado)
                    break
                time.sleep(0.5)
                contador += 1
                if contador == 60:
                    return False
            self.API.unsubscribe_strike_list(par, timeframe)
            return resultado
        except:
            return False

    def payout_binaria(self, par):
        '''
        Devolve o payout de uma paridade binária
        caso não tem esse par, então devolve False
        '''
        payouts = self.API.get_all_profit()
        valor = payouts.get(par)
        if valor == None:
            return False
        return valor['binary'] * 100 if valor.get("binary") else valor["turbo"] * 100
    
    def abertas(self):
        '''
        Exibe todas as paridades abertas
        Devolve um dicionário onde a chave é a paridade
        E o valor é a rentabilidade
        return:
            dict: tuple
        '''
        print(f"\nChecando as paridades abertas...\n")
        paridades = self.API.get_all_open_time()
        abertas = {}

        payouts = self.API.get_all_profit()
        for par in paridades["turbo"]:
            if paridades['turbo'][par]["open"]: 
                abertas[str(par)] = payouts[par]['turbo'] * 100
                
                print(f"[TURBO] {par} - {int(payouts[par]['turbo'] * 100) if type(payouts[par]['turbo']) != dict else '00'}%")
        for par in paridades["digital"]:
            if paridades['digital'][par]["open"]: 
                abertas[str(par)] = self.payout_digital(par)
                print(f"[DIGITAL] {par} {self.payout_digital(par)}%")

        return abertas

    def aberta_profit(self, paridades, timeframe):
        '''
        Verifica se a paridade está aberta e devolve o profit
        de forma que seja otimizado, devolvendo ambos os tipos
        Se nao estiver aberta, irá devolver False, 0
        Irá devolver (statusBinary, profitBinary, statusDigital, profitDigital)
        Lembrando que ele considera que você já se inscreveu na digital
        Params:
            - par: paridade
            - timeframe: 1|5|15...
        return:
            {
            "binary": {
                "EURUSD": [True, 0.76]
            },
            "digital": {
                "EURUSD": [False, 0.95]
            }
        }
        '''
        print("Buscando pariadades...")
        payouts = {"binary":{}, "digital":{}}
        abertas = self.API.get_all_open_time()
        todos_binary = self.API.get_all_profit()

        for par in paridades:
            
            tipo_binaria = "turbo" if timeframe == 1 else "binary"
            if abertas[tipo_binaria][par]["open"]:
                payouts["binary"][par] = [True, todos_binary[par][tipo_binaria]]
            else:
                payouts["binary"][par] = [False]

            if abertas['digital'][par]["open"]:
                self.API.subscribe_strike_list(par, timeframe)
                time.sleep(0.8)
                payout_digital = False
                while not payout_digital:
                    payout_digital = self.API.get_digital_current_profit(par, timeframe)
                payouts["digital"][par] = [
                    True, round(payout_digital / 100, 2)]
            else:
                payouts["digital"][par] = [False]
        return payouts

    def ordem(self, par, direcao = "call", tempo = 1, valor = 1, tipo = "binary", bloqueador = None):
        '''
        Faz uma ordem e devolve o resultado.
        Params:
            par: paridade
            direcao: "call" para comprar ou "put" para vender
            tempo: 1, 10, 15
            valor: dinheiro investido 2 - saldo
            tipo: binary ou digital
            bloqueador: caso estiver trabalhando com threads, um threading.Lock para não pegar o mesmo resultado.
        return:
            (resultado, lucro)
        '''
        if tipo == "binary":
            if bloqueador != None:
                with bloqueador:
                    status, identificador = self.API.buy(valor, par, direcao, tempo)
            else:
                status, identificador = self.API.buy(valor, par, direcao, tempo)
            if not status:
                print(f"  ! Um erro aconteceu: {par}-{tipo} {direcao} {valor}!")
                return "error", 0
        else:
            if bloqueador:
                with bloqueador:
                    identificador = self.API.buy_digital_spot(par, valor, direcao, tempo)
            else:        
                identificador = self.API.buy_digital_spot(par, valor, direcao, tempo)
            
            if not isinstance(identificador, int):
                print(f"  ! Um erro aconteceu: {par}-{tipo} {direcao} {valor}!")
                resultado, lucro = "erro", 0

        print(f"Operação realizada: {par}-{tipo} {direcao} ${round(valor, 2)} {tempo}min")

        resultado, lucro = self.API.check_win_v5(identificador, tipo, 0.6)

        if resultado == "win":
            print(f"\n  WIN: R${lucro}  ")
        else:
            print(f"\n  {resultado.upper()}: R${lucro}  ")

        return resultado, lucro
    
    @staticmethod
    def esperarAte(horas, minutos, segundos = 0, data = (), tolerancia = 0, verboso = False):
        '''
        Espera até determinada data/hora:minuto:segundo do dia
        Se a data não for passada, será considerada a data atual
        formato da data: (dia, mes, ano)
        '''
        if data == ():
            data = datetime.now()
        else:
            data = datetime(*data[::-1])
        alvo = datetime.fromtimestamp(
            data.replace(
                hour = horas, 
                minute = minutos, 
                second = segundos, 
                microsecond = 0
            ).timestamp() - tolerancia)
        agora = datetime.utcnow().timestamp() - 10800 # -3Horas
        segundos = alvo.timestamp() - agora
        if segundos > 10:
            if verboso:
                # Isso daqui é a correção
                alvo = alvo.fromtimestamp(
                    alvo.timestamp() + tolerancia
                )
                print(f"\n [...] Esperando para fazer a operação das {alvo.strftime('%d/%m/%Y %H:%M:%S')} UTC-3 [...]")
            time.sleep(segundos)
            return True
        if segundos > (-10 - tolerancia):
            return True
        return False
    
    @staticmethod
    def martingale(tipo_martin, payout, perca, valor = 1, lucro = 1):
        '''
        Calcula o martingale onde:
            tipo_martin:
                type: float (valor * tipo_martin)
                type: string
                    simples (valor * 2)
                    agressivo (perca * 2.3)
                    leve (vai manter o lucro inicial)
                    seguro (apenas recupera o valor)
                    porcento (vai aumentar uma porcentagem)
            payout: profit da paridade
            perca: valor perdido
            valor: entrada do valor
            lucro: alvo inicial
        '''
        if type(tipo_martin) == float:
            return round(valor * tipo_martin, 2)
        tipo_martin = tipo_martin.lower()
        if tipo_martin == "agressivo":
            return round(abs(perca) * 2.3, 2)
        elif tipo_martin == "simples":
            return round(valor * 2)
        elif tipo_martin == "leve":
            return (abs(perca) + lucro) / payout
        elif tipo_martin == "seguro":
            return round(abs(perca)/payout, 2)
        else:
            return round((abs(perca) + abs(perca) * lucro)/payout, 2)
