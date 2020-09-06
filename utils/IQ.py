from iqoptionapi.stable_api import IQ_Option
from datetime import datetime
import time

class IQ_API:
    def __init__(self, login, senha, output = None):
        '''
        Recebe o login, e tenta se conectar
        '''
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
                print(" ✅ Conectado com sucesso ✅\n")
                return True
            else:
                print(" ⏱ Tentando se conectar ⏱")
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
Saldo: {profile["currency_char"]} {round(profile["balance"], 2)}
Todas as carteiras:\n"""
        for tipo in profile['balances']:
            resultado += tipo['currency'] + ": " + str(round(tipo["amount"], 2)) + "\n"
        print(resultado)
        return profile

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
        '''
        Devolve o payout de uma paridade digital
        '''
        try:
            contador = 0
            self.API.subscribe_strike_list(par, timeframe)
            while True:
                resultado = self.API.get_digital_current_profit(
                    par, timeframe)
                if resultado:
                    resultado = int(resultado)
                    break
                time.sleep(0.5)
                contador += 1
                if contador == 30:
                    return 0.5
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
            return 100
        return valor['binary'] * 100 if valor.get("binary") else valor["turbo"] * 100

    def abertas(self, paridades):
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
        print(" ⚙️  Buscando paridades abertas ⚙️")
        payouts = {"binary":{
            "turbo": {},
            "binary": {}
        }, "digital":{}}
        abertas, todos_binary = None, None
        for i in range(2):
            abertas = self.API.get_all_open_time()
            todos_binary = self.API.get_all_profit()
            if abertas == None or todos_binary == None:
                print(" ❌ Algo deu errado, se conectando novamente. ❌")
                self.conectar()
            else:
                break
        if abertas == None or todos_binary == None:
            print(" ❌❌ Reinicie o bot ❌❌")
            return None

        print(" ⚙️  Buscando payouts ⚙️")
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
                    print(
                        f" [ ❗️] Não consegui pegar o payout de {par} [ ❗️]")
                    payouts['digital'][par] = [True, 0.7]
            else:
                payouts["digital"][par] = [False]
        
        for par in paridades:
            if par not in payouts['binary']['binary']:
                payouts['binary']['binary'][par] = [False]
            if par not in payouts['binary']['turbo']:
                payouts['binary']['turbo'][par] = [False]
            if par not in payouts['digital']:
                payouts['digital'][par] = [False]

        return payouts
    
    def top_ranking(self, quantidade, filtro = "Worldwide"):
        '''
        Devolve a lista de ID's do top ranking ou uma lista vazia.
        '''
        ranking = []
        contador = 0
        while contador < 2 and ranking == []:
            ranking = API.get_leader_board(filtro, 1, quantidade, 0)
            contador += 1

        if ranking == []:
            print(" [❗️] Não consegui pegar os top ranking [❗️]")
            return []
        else:
            return [ranking['result']['positional'][trader]['user_id']
                for trader in ranking['result']['positional']]
   
    def ordem(
        self, par, direcao = "call", tempo = 1, valor = 1, 
        tipo = "binary", bloqueador = None, delay = False):
        '''
        Faz uma ordem e devolve o resultado.
        Params:
            par: paridade
            direcao: "call" para comprar ou "put" para vender
            tempo: 1, 10, 15
            valor: dinheiro investido 2 - saldo
            tipo: binary ou digital
            bloqueador: caso estiver trabalhando com threads, um threading.Lock para não pegar o mesmo resultado.
            delay: tempo para pegar o resultado antes/depois
        return:
            (resultado, lucro)
        '''
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
                    status, identificador = self.API.buy(valor, par, direcao, tempo)
                else:
                    status, identificador = self.API.buy_digital_spot(par, valor, direcao, tempo)
        else:
            if tipo == "binary":
                status, identificador = self.API.buy(valor, par, direcao, tempo)
            else:
                status, identificador = self.API.buy_digital_spot(par, valor, direcao, tempo)
            
        if not status:
            if tipo == "digital":
                identificador = identificador['message']
            self.output(str(identificador))
            print(f"  ❌ {par}-{tipo} {direcao} fechada ou máximo de operações ❌")
            return "error", 0

        self.output(
            f"{par} {tipo} {direcao.upper()} ${round(valor, 2)} M{tempo}")

        if delay == False:
            # Versão que pega no histórico
            if tipo == "binary":
                resultado, lucro = self.API.check_win_v4(identificador) # binary
            else:
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

        print(f'''

        {"- " * 18}
        Paridade: {par}|{tipo}
        Direção:  {direcao.upper()}
        tempo:    M{tempo}
        
        Hora:     {hora_atual.strftime("%H:%M")}
        Valor:    R${round(valor, 2)}
        {resultado.capitalize()}: R${round(lucro, 2)} 
        {"- " * 18}
        
        ''')

        return resultado, lucro

    def calcular_tendencia(
        self, tipo, par, direcao, timeframe, 
        periodo = 21, desvio = 0.1):
        '''
        Devolve se a decisão está de acordo com a estratégia M.M_007
        tipo: velas|SMA|bollinger
        '''
        # from talib import BBANDS
        import numpy
        
        # pega a última vela
        dados = [
            x['close'] for x in self.API.get_candles(
            par, timeframe * 60, periodo * 2, time.time())
        ]
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
                return velas[0] == direcao
        return True if (
            direcao.lower() == "call" 
            and diferenca > 0) or (
            direcao.lower() == "put" 
            and diferenca < 0) else False
        # else:
        #     superior, meio, inferior = BBANDS(
        #     numpy.array(dados), timeperiod = periodo, 
        #     nbdevup = desvio, nbdevdn = desvio)
        #     dado = dados[-1]

        #     '''
        #     Pega as linhas de suporte e resistência e devolve
        #     um dicionário no estilo:
        #     {
        #         "s1": 0.8772134,
        #         "p": 0.86213412
        #         ...
        #     }
        #     '''
        #     indicadores = self.API.get_technical_indicators(par)
        #     if type(indicadores) == list:
        #         suporte_resistencia = {
        #             indicator['name'].replace("Classic ", ""): indicator['value']
        #             for indicator in indicadores 
        #             if indicator['candle_size'] == timeframe * 60 and 
        #             "Classic" in indicator['name']
        #         }
        #     else:
        #         print(f" [ ❗️] {par} não tem linhas de suporte/resistência [ ❗️]")
        #         return ((
        #             (desvio < 2 and superior[-1] < dado) or
        #             (desvio >= 2 and superior[-1] >= dado))
        #             if direcao.lower() == "call" else 
        #             ((desvio < 2 and inferior[-1] > dado) or
        #             (desvio >= 2 and inferior[-1] <= dado))
        #         )
        #     '''
        #     Pega o suporte e resistência imediato de determinado valor
        #     '''
        #     resistencia = suporte_resistencia['r1']
        #     suporte = suporte_resistencia['s1']
        #     for nome, linha in suporte_resistencia.items():
        #         if resistencia > linha > dado:
        #             resistencia = linha
        #         elif suporte < linha < dado:
        #             suporte = linha
        #     proximidade = (dado - suporte) / (resistencia - suporte) * 100

        #     if direcao.lower() == "call":
        #         return proximidade < 80 if (
        #             (desvio < 2 and superior[-1] < dado) or
        #             (desvio >= 2 and superior[-1] >= dado)
        #         ) else False
        #     else:
        #         return proximidade > 20 if (
        #             (desvio < 2 and inferior[-1] > dado) or
        #             (desvio >= 2 and inferior[-1] <= dado)
        #         ) else False

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
                "paridade": operacao['raw_event']['instrument_underlying'] if tipo == "turbo-option" else operacao['raw_event'].get('active'),
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
    
    def pegar_velas(self, par, timeframe, quantidade, fim = None):
        if fim == None:
            fim = time.time()
        return [
            x['close'] for x in self.api.API.get_candles(
            par, timeframe, quantidade, fim)
        ]

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
                print(f"\n ⏳ Esperando para fazer a operação das {alvo.strftime('%d/%m/%Y %H:%M:%S')} ⏳")
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
