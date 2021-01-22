from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta
import time, numpy, requests, json

class IQ_API:
    def __init__(self, login, senha, output):
        '''
        Recebe o login, e tenta se conectar
        '''
        self.saida = output
        self.API = IQ_Option(login, senha)
        if output != None:
            self.output = output
        else:
            output = print
        if not self.conectar():
            raise ConnectionError(" ❌ Não conseguiu se conectar, reveja a senha ❌ ")

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
        self.API.connect()
        for tentativas in range(tentativas):
            if self.API.check_connect():
                self.saida("✅ Conectado com sucesso ✅")
                return True
            else:
                self.saida(" ⏱ Tentando se conectar ⏱")
                self.API.connect()
                time.sleep(1)
        return False

    def mudar_treino(self):
        '''
        Muda para a conta treino
        '''
        self.saida(" - Usando a conta treino -\n")
        self.API.change_balance("PRACTICE")
    
    def mudar_real(self):
        '''
        Muda para a conta real
        '''
        self.saida(" - Usando a conta real -\n")
        self.API.change_balance("REAL")

    def payout_digital(self, paridade):
        '''
        Devolve o payout de uma paridade digital
        '''
        try:
            return self.API.get_digital_payout(paridade) / 100
        except:
            return False

    def payout_binaria(self, par, tempo = 1):
        '''
        Devolve o payout de uma paridade binária
        caso não tem esse par, então devolve False
        '''
        payouts = self.API.get_all_profit()
        valor = payouts.get(par)
        if valor == None:
            return False
        if tempo > 5:
            return valor['binary'] if valor.get(
                "binary"
            ) else False
        else:
            return valor['turbo'] if valor.get(
                "turbo"
            ) else False

    def abertas(self, paridades = False):
        '''
        Verifica se a paridade está aberta e devolve o profit
        de forma que seja otimizado, devolvendo ambos os tipos
        Se nao estiver aberta, irá devolver False, 0
        Irá devolver (statusBinary, profitBinary, statusDigital, profitDigital)
        Lembrando que ele considera que você já se inscreveu na digital
        Params:
            - par: paridade
        return:
            {
            "binary": {
                "turbo": {
                    "EURUSD": [True, 0.76]},
                "binary": {
                    "EURUSD": [False]}
            },
            "digital": {
                "EURUSD": [False, 0.95]
            }
        }
        '''
        payouts = {"binary":{
            "turbo": {},
            "binary": {}
        }, "digital":{}}
        abertas, todos_binary = None, None
        for i in range(2):
            abertas = self.API.get_all_open_time()
            if paridades == False: 
                paridades = list(abertas["binary"].keys())
            todos_binary = self.API.get_all_profit()
            if abertas == None or todos_binary == None:
                self.saida(" ❌ Algo deu errado, se conectando novamente. ❌")
                self.conectar()
            else:
                break
        if abertas == None or todos_binary == None:
            self.saida(" ❌❌ Reinicie o bot ❌❌")
            return None

        for tipo_binaria in ['turbo', 'binary']:
            for par in abertas[tipo_binaria]:
                if abertas[tipo_binaria][par]["open"]:
                    payouts["binary"][tipo_binaria][par] = [
                        True, todos_binary[par][tipo_binaria]]
                else:
                    payouts["binary"][tipo_binaria][par] = [False]
        
        for par in abertas['digital']:
            if abertas['digital'][par]["open"] and (
                par in paridades or paridades == []):
                self.API.subscribe_strike_list(par, 1)
                payout_digital = False
                contador_limite = 0
                while not payout_digital:
                    time.sleep(0.8)
                    payout_digital = self.API.get_digital_current_profit(
                        par, 1)
                    contador_limite += 1
                    if contador_limite == 5:
                        break
                if contador_limite != 5:
                    payouts["digital"][par] = [
                        True, round(payout_digital / 100, 2)]
                else:
                    self.saida(
        f" [ ❗️] Não consegui pegar o payout de {par} [ ❗️]")
                    payouts['digital'][par] = [True, 0.7]
            else:
                payouts["digital"][par] = [False]
        
        for par in paridades:
            if par not in payouts['binary']:
                payouts['binary'][par] = [False]
            if par not in payouts['digital']:
                payouts['digital'][par] = [False]

        return payouts
    
    def ordem(self, paridade, direcao = "call", tempo = 1, 
        valor = 1, tipo = "binary", bloqueador = None, 
        delay = False, scalper = False):
        '''
        Faz uma ordem e devolve o resultado.
        Params:
            direcao: "call" para comprar ou "put" para vender
            tempo: 1, 10, 15
            valor: dinheiro investido 2 - saldo
            tipo: binary ou digital
            bloqueador: caso estiver trabalhando com threads, um threading.Lock para não pegar o mesmo resultado.
            delay: tempo para pegar o resultado antes/depois
            Scalper: porcentagem de ganho sobre o valor investido
        return:
            (resultado, lucro)
        '''
        direcao = direcao.lower()
        hora_atual = datetime.fromtimestamp(
            datetime.utcnow().timestamp() - 10800)

        if tipo == "binary" and tempo == 5:
            atual = datetime.utcnow()
            if ((atual.minute % 5 == 4 and atual.second < 30) 
                or atual.minute % 5 < 4): 
                tempo = 5 - (atual.minute % 5)

        if bloqueador != None:
            with bloqueador:
                if tipo == "binary":
                    status, identificador = self.API.buy(valor, paridade, direcao, tempo)
                else:
                    status, identificador = self.API.buy_digital_spot(paridade, valor, direcao, tempo)
        else:
            if tipo == "binary":
                status, identificador = self.API.buy(valor, paridade, direcao, tempo)
            else:
                status, identificador = self.API.buy_digital_spot(paridade, valor, direcao, tempo)
            
        if not status:
            if tipo == "digital":
                identificador = identificador['message']
            self.saida(str(identificador))
            self.saida(
    f"❌ {paridade}-{tipo} {direcao} fechada ou máximo de operações ❌")
            return "error", 0

        self.saida(
f"{paridade}-{tipo} {direcao.upper()} ${round(valor, 2)} M{tempo}")

        lucro = 0
        if delay == False:
            # Versão que pega no histórico
            if tipo == "binary":
                resultado, lucro = self.API.check_win_v4(identificador) # binary
            else:
                if scalper:
                    self.API.subscribe_strike_list(paridade, 1)
                    self.scalper(identificador, valor, scalper)
                    self.API.unsubscribe_strike_list(paridade, 1)
                status = False
                time.sleep((tempo * 60) - 10)
                while not status:
                    status, lucro = self.API.check_win_digital_v2(identificador)
                    time.sleep(0.5)
                if lucro > 0:
                    resultado = "win"
                elif lucro < 0:
                    resultado = "loose"
                else:
                    resultado = "equal"
        else:
            # Versão que pega na hora
            resultado, lucro = self.API.check_win_v5(identificador, tipo, delay)

        self.saida(f"""
\t- - - - - - - - - - - - - - - - - - - - 
    Paridade: {paridade}|{tipo.capitalize()}
    Direção: {direcao.upper()}
    tempo: M{tempo}

    Hora: {hora_atual.strftime("%H:%M")}
    Valor: R$ {valor}
    {resultado.capitalize()}: R$ {round(lucro, 2)} 
\t- - - - - - - - - - - - - - - - - - - - """)

        return resultado, round(lucro, 2)

    def scalper(self, identificador, valor, infos):
        aberto = True
        win = infos["win"] * valor / 100 if valor != 0 else valor * 2
        loss = infos["loss"] * valor / 100 if valor != 0 else valor * 2
        while aberto:
            atual = self.API.get_digital_spot_profit_after_sale(
                    identificador)
            if (round(atual, 2) >= round(win, 2) or 
                round(atual, 2) <= round(-loss, 2)):
                self.API.close_digital_option(identificador)
            aberto = self.API.get_async_order(
                identificador
            )['position-changed']['msg']['status'] == 'open'
            time.sleep(0.3)

    def calcular_tendencia(
        self, tipo, par, direcao, timeframe, periodo = 21):
        '''
        Devolve se a decisão está de acordo com a estratégia M.M_007
        tipo: velas|SMA|bollinger
        '''
        # from talib import BBANDS        
        # pega a última vela
        try:
            dados = [
                x['close'] for x in self.API.get_candles(
                par, timeframe * 60, periodo * 2, time.time())
            ]
        except:
            return True
        # Calcula a SMA
        pesos = numpy.repeat(1.0, periodo) / periodo
        smas = numpy.convolve(
            dados, pesos, 'valid').tolist()
        diferenca = smas[-1] - smas[-periodo]

        if tipo == "velas":
            velas = self.API.get_candles(
                par, timeframe * 60, 3, time.time())

            velas = [
                1 if x['close'] - x['open'] > 0 else 
                0 if x['close'] - x['open'] == 0 else 
                -1 for x in velas
            ]

            if velas[0] == velas[1] == velas[2]:
                direcao = 1 if direcao.lower() == "call" else -1
                return velas[0] == direcao.lower()
        return True if (
            direcao.lower() == "call" 
            and diferenca > 0) or (
            direcao.lower() == "put" 
            and diferenca < 0) else False
    
    def pegar_velas(self, par, timeframe, quantidade, fim = None):
        if fim == None:
            fim = time.time()
        return [
            x['close'] for x in self.API.get_candles(
            par, timeframe, quantidade, fim)
        ]
    
    @staticmethod
    def catalogar(timeframe, gale):
        def traduzir(estrategia):
            maioria = "Minoria"
            pedaco = estrategia.capitalize().split()
            if len(pedaco) == 2 and pedaco[1] == "maioria":
                estrategia = pedaco[0]
                maioria = "Maioria"
            if pedaco[0] == "Milhão":
                estrategia = "Milhão"
            elif "Mhi" == estrategia[:3]:
                estrategia = estrategia.upper()
            return estrategia, maioria

        if   gale == 2:   gale = "porcentagemGale2"
        elif gale == 1:   gale = "porcentagemGale1"
        else:             gale = "porcentagemWinDePrimeira"
        data = requests.get(f"https://catalogador.ml/api/{gale}/M{timeframe}")
        resultado = json.loads(data.text)['Todos']
        for estrategia in resultado:
            return estrategia[1].upper(), traduzir(estrategia[2])

    @staticmethod
    def esperarAte(horas, minutos, segundos = 0, data = (), tolerancia = 0, output = False):
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
            if output:
                # Isso daqui é a correção
                alvo = alvo.fromtimestamp(
                    alvo.timestamp() + tolerancia
                )
                output(f"\n ⏳ Esperando para fazer a operação das {alvo.strftime('%d/%m/%Y %H:%M:%S')} ⏳")
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

    @staticmethod
    def esperar_proximo_minuto(minutos = 1):
        time.sleep((datetime.now() + timedelta(
            seconds = 50 * minutos)
        ).replace(second = 58).timestamp() - time.time())

    def istime(self, string):
        '''
        Verifica se é numérico (timestamp)
        '''
        try:
            float(string)
            return True
        except:
            return False