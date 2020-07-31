from iqoptionapi.stable_api import IQ_Option
from talib import BBANDS
from datetime import datetime
import numpy, time

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
        self.API = IQ_Option(login, senha)
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
        print(f"\n ⚙️ Checando as paridades abertas ⚙️\n")
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
        print(" ⚙️  Buscando paridades abertas ⚙️")
        payouts = {"binary":{}, "digital":{}}
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

        print(" ⚙️ Buscando payouts ⚙️")
        for par in paridades:
            
            tipo_binaria = "turbo" if timeframe == 1 else "binary"
            if abertas[tipo_binaria][par]["open"]:
                payouts["binary"][par] = [True, todos_binary[par][tipo_binaria]]
            else:
                payouts["binary"][par] = [False]

            if abertas['digital'][par]["open"]:
                self.API.subscribe_strike_list(par, timeframe)
                payout_digital = False
                contador_limite = 0
                while not payout_digital:
                    time.sleep(0.8)
                    payout_digital = self.API.get_digital_current_profit(par, timeframe)
                    contador_limite += 1
                    if contador_limite == 5:
                        break
                if contador_limite != 5:
                    payouts["digital"][par] = [
                        True, round(payout_digital / 100, 2)]
                else:
                    print(f" [❗️] Não consegui pegar o payout de {par} [❗️]")
                    payouts['digital'][par] = [False]
            else:
                payouts["digital"][par] = [False]
        return payouts

    def ordem(self, par, direcao = "call", tempo = 1, valor = 1, tipo = "binary", bloqueador = None, delay = 0):
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
            print(f"  ❌ Um erro aconteceu: {par}-{tipo} {direcao} {valor} ❌")
            return "error", 0

        print(f'''
               |operação realizada|
            {par}-{tipo} {direcao.upper()} ${round(valor, 2)} M{tempo}
        ''')

        # Versão que pega no histórico
        if tipo == "binary":
            resultado, lucro = self.API.check_win_v4(identificador) # binary
        else:
            status = False
            time.sleep(tempo * 60 - 10)
            while not status:
                status, lucro = self.API.check_win_digital_v2(identificador)
                time.sleep(0.5)
            if lucro > 0:
                resultado = "win"
            elif lucro < 0:
                resultado = "loose"
            else:
                resultado = "equal"
        
        # Versão que pega na hora
        # resultado, lucro = self.API.check_win_v5(identificador, tipo, delay)

        print(f'''

        {"- " * 20}
        Paridade: {par}|{tipo}
        Direção: {direcao.upper()}
        tempo: M{tempo}
        
        Hora: {datetime.now().strftime("%H:%M")}
        Valor: R${round(valor, 2)}
        {resultado.capitalize()}: R${round(lucro, 2)} 
        {"- " * 20}
        
        ''')

        return resultado, lucro

    def calcular_tendencia(self, par, direcao, timeframe, periodo, desvio):
        '''
        Devolve se a decisão está de acordo com a estratégia M.M_007
        '''
        # pega a última vela  e calcula a banda de bollinger
        dados = [
            x['close'] for x in self.API.get_candles(
            par, timeframe * 60, periodo + 5, time.time())
        ]
        superior, meio, inferior = BBANDS(
            numpy.array(dados), timeperiod = periodo, 
            nbdevup = desvio, nbdevdn = desvio)
        
        dado = dados[-1]

        '''
        Pega as linhas de suporte e resistência e devolve
        um dicionário no estilo:
        {
            "s1": 0.8772134,
            "p": 0.86213412
            ...
        }
        '''
        indicadores = self.API.get_technical_indicators(par)
        if type(indicadores) == list:
            suporte_resistencia = {
                indicator['name'].replace("Classic ", ""): indicator['value']
                for indicator in indicadores 
                if indicator['candle_size'] == timeframe * 60 and 
                "Classic" in indicator['name']
            }
        else:
            print(f"[ ❗️] {par} não tem linhas de suporte/resistência [ ❗️]")
            return (superior[-1] < dado if direcao.lower() == "call"
                else inferior[-1] > dado)
        '''
        Pega o suporte e resistência imediato de determinado valor
        '''
        resistencia = suporte_resistencia['r1']
        suporte = suporte_resistencia['s1']
        for nome, linha in suporte_resistencia.items():
            if resistencia > linha > dado:
                resistencia = linha
            elif suporte < linha < dado:
                suporte = linha
        proximidade = (dado - suporte) / (resistencia - suporte) * 100

        if direcao.lower() == "call":
            return proximidade < 80 if superior[-1] < dado else False
        else:
            return proximidade > 20 if inferior[-1] > dado else False

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
