import time, numpy, requests, json, threading, finta, pandas, statistics
from .conversor import convert_lines_to_list
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta
from functools import reduce

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
        self.asset, self.timeframe, self.payout_cache = False, False, {}
        self.display_time = lambda x, y = False: x
        self.cadeado = threading.Lock()
        self.API = IQ_Option(login, senha)
        if not self.conectar():
            raise ConnectionError(" ❌ Não conseguiu se conectar, reveja a senha ❌ ")

    def mostrar_mensagem(self, msg): print(msg)
    def conectar(self, tentativas = 5, mensagem = True):
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
                if mensagem:
                    self.mostrar_mensagem("✅ Conectado com sucesso ✅")
                return True
            else:
                if mensagem:
                    self.mostrar_mensagem(" ⏱ Tentando se conectar ⏱")
                self.API.connect()
                time.sleep(1)
        return False

    def mudar_treino(self):
        '''
        Muda para a conta treino
        '''
        if self.API.get_balance_mode() != "PRACTICE":
            self.mostrar_mensagem(" - Usando a conta treino -\n")
            self.API.change_balance("PRACTICE")
    
    def mudar_real(self):
        '''
        Muda para a conta real
        '''
        if self.API.get_balance_mode() != "REAL":
            self.mostrar_mensagem(" - Usando a conta real -\n")
            self.API.change_balance("REAL")

    def add_payout_cache(self, paridade, modalidade, payout):
        if paridade not in self.payout_cache:
            self.payout_cache[paridade] = {
                "binary": 0, "digital": 0
            }
        paridade = paridade.upper()
        self.payout_cache[paridade][modalidade] = payout

    def payout_digital(self, paridade):
        '''
        Devolve o payout de uma paridade digital
        '''
        try:
            payout = self.API.get_digital_payout(paridade) / 100
            self.add_payout_cache(paridade, "digital", payout)
            return payout
        except:
            return False

    def payout_binaria(self, paridade, tempo = 1):
        '''
        Devolve o payout de uma paridade binária
        caso não tiver este par, então devolve False
        '''
        payouts = self.API.get_all_profit()
        valor = payouts.get(paridade)
        if valor == None:
            result = False
        else:
            if tempo > 5:
                result = valor['binary'] if valor.get(
                    "binary"
                ) else False
            else:
                result = valor['turbo'] if valor.get(
                    "turbo"
                ) else False
        self.add_payout_cache(paridade, "binary", result)
        return result

    def payout_abertas(self, paridades = False):
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
                self.mostrar_mensagem(
                    " ❌ Algo deu errado, se conectando novamente. ❌")
                self.conectar()
            else:
                break
        if abertas == None or todos_binary == None:
            self.mostrar_mensagem(" ❌❌ Reinicie o bot ❌❌")
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
                    self.mostrar_mensagem(
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
    
    def catalogar_erros(self, mensagem, tipo, trying):
        def is_in_list(nome, lista):
            for item in lista:
                if item in nome.lower():
                    return True
            return False
        
        if is_in_list(mensagem, ["is not available", "active_suspended"]):
            mensagem = "Ativo fechado nesta modalidade/timeframe."
        elif "invalid instrument" in mensagem:
            mensagem = "Paridade não encontrada na digital pela IQ." 
        novo_tipo = "binária" if tipo == "digital" else "digital"
        self.mostrar_mensagem(f"❌ A IQ não permitiu a operação: \n\
{mensagem}" + f" tentando operar na {novo_tipo}" if trying else "")

    def ordem(self, paridade, direcao = "call", tempo = 1, 
        valor = 1, tipo = "binary", delay = False, 
        scalper = False, trying = False):
        '''
        Faz uma ordem e devolve o resultado.
        Params:
            direcao: "call" para comprar ou "put" para vender
            tempo: 1, 10, 15
            valor: dinheiro investido 2 - saldo
            tipo: binary ou digital
            delay: tempo para pegar o resultado antes/depois
            Scalper: porcentagem de ganho sobre o valor investido
        return:
            (resultado, lucro)
        '''
        direcao = direcao.lower()
        with self.cadeado:
            if tipo == "binary":
                status, identificador = self.API.buy(
                    valor, paridade, direcao, tempo)
            else:
                status, identificador = self.API.buy_digital_spot_v2(
                    paridade, valor, direcao, tempo)

        if not status:
            if tipo == "digital":
                identificador = str(identificador['message'])
            else: identificador = str(identificador)
            self.catalogar_erros(identificador, tipo, trying)
            
            if not trying:
                if self.tipo != "auto": 
                    self.tipo = "binary" if self.tipo == "digital" else "digital"
                tipo = "binary" if tipo == "digital" else "digital"
                
                opcoes_modalidade = self.payout_cache.get(paridade.upper())
                payout_modalidade = opcoes_modalidade.get(tipo) if opcoes_modalidade else -1
                payout_atual = round(payout_modalidade * 100) if payout_modalidade else -1
                if payout_atual >= self.config['minimo'] or -1:
                    return self.ordem(paridade, direcao, tempo, 
                        valor, tipo, delay, scalper, True)
                else:
                    payout_atual = f"{payout_atual}% < {self.config['minimo']}%"
                    self.mostrar_mensagem(
                        f"Payout na {tipo} está abaixo do aceitável: {payout_atual}")
            return "error", 0, tipo

        self.mostrar_mensagem(self.format_dir(
            f" 🔸 {paridade} | {tipo.capitalize()} | M{tempo} | $ {round(valor, 2)} | {direcao.upper()}"))
        
        lucro = 0
        if delay == False:            
            # Versão que pega no histórico
            if tipo == "binary":
                resultado, lucro = self.API.check_win_v4(identificador) 
            else:
                if scalper: pass
                    # self.API.subscribe_strike_list(paridade, 1)
                    # self.scalper(identificador, valor, scalper)
                    # self.API.unsubscribe_strike_list(paridade, 1)
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
            resultado, lucro = self.API.check_win_v5(
                identificador, tipo, delay)

        return resultado, round(lucro, 2), tipo

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
            aberto = self.API.get_async_order(identificador
            )['position-changed']['msg']['status'] == 'open'
            time.sleep(0.3)

    def calcular_tendencia(self, par, direcao, timeframe, periodo = 21):
        '''
        Verifica se está em uma tendência forte
        '''
        # pega a última vela
        try:
            dados = [
                x['close'] for x in self.API.get_candles(
                par, timeframe * 60, periodo * 2, time.time())
            ]
        except:
            return True
        if periodo <= 0:
            self.mostrar_mensagem("Aumente o período da tendência!")
            return True
        # Calcula a SMA
        pesos = numpy.repeat(1.0, periodo) / periodo
        smas = numpy.convolve(dados, pesos, 'valid').tolist()
        diferenca = smas[-1] - smas[-periodo]

        return True if (
            direcao.lower() == "call" 
            and diferenca > 0) or (
            direcao.lower() == "put" 
            and diferenca < 0) else False

    def pegar_velas(self, par, quantidade, timeframe = 1, fim = None):
        if fim == None:
            fim = time.time()
        return [
            x['close'] for x in self.API.get_candles(
            par, timeframe, quantidade, fim)
        ]
    
    def format_dir(self, text):
        return text.replace("CALL", "⬆️").replace("PUT", "⬇️")

    def berman_strategy(self, paridade: str, 
        ema_period: int, bbands_period: int) -> tuple:
        from talib.abstract import BBANDS, EMA

        quantidade = 1000
        velas = self.API.get_candles(
            paridade, self.tempo * 60, 
            quantidade, time.time())
        if velas is None or len(velas) == 0:
            return 0, 0, 0, 0

        dados = {
            'open': numpy.empty(quantidade),
            'high': numpy.empty(quantidade), 
            'low': numpy.empty(quantidade),
            'close': numpy.empty(quantidade),
            'volume': numpy.empty(quantidade)
        }
        
        for x in range(quantidade):
            for key in dados:
                new_key = key.replace(
                    "high", "max"
                ).replace("low", "min")
                dados[key][x] = velas[x][new_key]

        saida = EMA(dados, timeperiod=ema_period)
        up, _, low = BBANDS(dados, matype=0, nbdevdn=2.5,
            timeperiod=bbands_period, nbdevup=2.5)
        
        up = round(up[len(up) - 2], 5)
        low = round(low[len(low) - 2], 5)
        taxa_atual = round(velas[-1]['close'], 5)
        emma = round(saida[-1], 5)

        return taxa_atual, up, low, emma

    def get_dataframe_candles(self, asset: str, 
            timeframe: int, periods: int = 200
        ) -> pandas.DataFrame:
        """
        Recebe X velas e transforma em um dataframe
        Por fim renomeia as colunas max e min
        """
        velas = self.API.get_candles(
            asset, timeframe * 60, 
            periods, time.time())
        
        dataframe = pandas.DataFrame(velas)
        dataframe.rename(columns={ 
            "max": "high", "min": "low" 
        }, inplace=True)
        
        return dataframe
        
    def update_abertas(self) -> tuple:
        try:
            abertas = self.API.get_all_open_time()
            turbo, last_update = abertas["turbo"], time.time()
            paridades = set([x for x in turbo if turbo[x]["open"]])
        except:
            self.mostrar_mensagem(f"Não consegui obter as paridades abertas...")
            self.API.connect()
            last_update, paridades = time.time() + 500, []
        return last_update, paridades

    @staticmethod
    def moving_average_deviation(
        dataframe: pandas.DataFrame, 
        periods: int = 20) -> str:
        '''
        Devolve a direção do indicador moving average deviation
        Com base na diferença do penúltimo com o último MAD
        '''
        src = finta.TA.SSMA(dataframe, periods)
        
        diff_right_now = dataframe.iloc[-1]['close'] - src.iloc[-1]
        diff_before_now = dataframe.iloc[-2]['close'] - src.iloc[-2]
        is_increasing = diff_right_now >= diff_before_now

        return 'CALL' if is_increasing else 'PUT'			
        
    @staticmethod
    def indicator_lines_colision(
            first: pandas.core.series.Series, 
            second: pandas.core.series.Series
        ) -> tuple:
        """
        Devolve se as linhas colidiram e o sentido
        """
        BEFORE, NOW = -2, -1
        is_greater_before = first.iloc[BEFORE] > second.iloc[BEFORE]
        is_less_right_now = first.iloc[NOW] <= second.iloc[NOW]
        is_decreasing = is_greater_before and is_less_right_now

        if is_decreasing:
            return True, "PUT"

        is_less_before = first.iloc[BEFORE] < second.iloc[BEFORE]
        is_greater_now = first.iloc[NOW] >= second.iloc[NOW]
        is_increasing = is_less_before and is_greater_now

        if is_increasing:
            return True, "CALL"

        return False, "DOJI"

    @staticmethod
    def get_SSMA(dataframe: pandas.DataFrame, period: int):
        return finta.TA.SSMA(dataframe, period)
    
    @staticmethod
    def list_sma(candles, periodo):
        candles = candles[:periodo]
        candle_sum = reduce((lambda last, x: last + x), candles)
        return candle_sum / len(candles)
    
    def candle_chart_range(self, candle_amount: int, 
                           high: list, low: list, close: list) -> float:
        def access(array, index):
            if abs(round(index)) >= len(array):
                return 0
            return array[abs(round(index))]
        
        if candle_amount > 7:
            quadrantes = round(candle_amount / 5)
            high_sorted = sorted(high[quadrantes:], reverse=True)
            low_sorted = sorted(low[quadrantes:])

            if len(high_sorted) < 1 or len(low_sorted) < 1: return 0

            has_one_quadrante = quadrantes == 1
            previous = high_sorted[0] - low_sorted[0]

            var_1 = abs(close[0] - close[quadrantes]) if (
                previous == 0 and has_one_quadrante) else -quadrantes
            previous = access(high_sorted, -quadrantes+1) - access(low_sorted, -quadrantes)

            var_2 = abs(access(close, -quadrantes) - access(close, -quadrantes*2)) if (
                previous == 0 and has_one_quadrante) else previous
            previous = access(high_sorted, -quadrantes*2) - access(low_sorted, -quadrantes*2)
            
            var_3 = abs(access(close, -quadrantes*2) - access(close, -quadrantes*3)) if (
                previous == 0 and has_one_quadrante) else previous
            previous = access(high_sorted, -quadrantes*3) - access(low_sorted, -quadrantes*3)
            
            var_4 = abs(access(close, -quadrantes*3) - access(close, -quadrantes*4)) if (
                previous == 0 and has_one_quadrante) else previous
            previous = access(high_sorted, -quadrantes*4) - access(low_sorted, -quadrantes*4)
            
            var_5 = abs(access(close, -quadrantes*4) - access(close, -quadrantes*5)) if (
                previous == 0 and has_one_quadrante) else previous
            
            left_range = ((var_1 + var_2 + var_3 + var_4 + var_5) / 5) * .2
        else:
            candle_delta = [abs(x - close[1]) for x in close]
            var0 = candle_delta if (
                candle_delta[0] > (high[0] - low[0]) or high[0] == low[0]
            ) else [high[x] - low[x] for x in range(len(high))]
            
            left_range = self.list_sma(var0, 5) * .2
        
        return left_range

    def catalogar_estrategia(self, timeframe: int, gale: int, poshit: bool, 
                             hits: int, _assert: int) -> tuple:

        def verify_minoria(estrategia):
            maioria = "minoria"
            fatias = estrategia.lower().split()
            if len(fatias) == 2 and fatias[1] == "maioria":
                estrategia = fatias[0]
                maioria = "maioria"
            if fatias[0] == "milhão":
                estrategia = "milhão"
            elif "mhi" == estrategia[:3].lower():
                estrategia = fatias[0]
            
            return estrategia.lower(), maioria

        email = self.config.get("licensor_email")
        password = self.config.get("licensor_password")
        data = requests.get(
            f"https://catalogador.herokuapp.com/api/catalogacao/M{timeframe}/{gale}/",
            headers = { 
                "email": email,
                "password": password,
                "poshit": str(hits) if poshit else "0", 
                "assert": str(_assert),
                "strategies": ",".join([
                    'C3', 'DAKA','FIVE FLIP', 'GABA', 'HALF HOUR','HOPE',
                    'LAST OF FIVE','MELHOR DE 3', 'MHI MAIORIA','MHI MINORIA','VITUXO'
                    'MHI2 MAIORIA','MHI2 MINORIA', 'MHI3 MAIORIA','MHI3 MINORIA',
                    'MILHÃO MAIORIA','MILHÃO MINORIA', 'MSF', 'PADRÃO 23', 'PADRÃO 3X1',
                    'PADRÃO IMPAR', 'POWER','PRIMEIROS TROCADOS','R7','SEVEN FLIP',
                    'TORRES GÊMEAS','TRIPLICAÇÃO','TRÊS MOSQUETEIROS','TRÊS VIZINHOS',
                    'TURN OVER',
                ]),
            })

        resultado = json.loads(data.text)
        trades = resultado['trades']
        for analise in trades:
            paridade = analise["asset"]
            estrategia = analise["strategy"]
            percentage = analise["percents"][0]
                
            return percentage, paridade, verify_minoria(estrategia)
        
        if len(trades) == 0:
            self.mostrar_mensagem(f'Motivo: {resultado["reason"]}')
        
        return False, False, False

    @staticmethod
    def esperarAte(horas, minutos, segundos = 0, 
        data = (), tolerancia = 0, output = False):
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
                output(f"\n ⏳ Próxima operação às {alvo.strftime('%H:%M:%S')} ⏳")
            time.sleep(segundos)
            return True
        if segundos > (-10 - tolerancia):
            return True
        return False
    
    @staticmethod
    def martingale(tipo_martin, payout, 
        perca, valor = 1, lucro = 1):
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

    def esperar_proximo_minuto(self, minutos = 1, seconds = 56):
        correcao = self.config.get('correcao', 0)
        espera = (((datetime.now() + timedelta(
            seconds = 50 * minutos)
        ).replace(second = seconds) - timedelta(seconds = correcao)
        ).timestamp() - time.time())

        time.sleep(espera)

    def format_candles(self, text):
        if type(text) != str: return text
        return (text.replace("CALL", "🟢")
                    .replace("PUT", "🔴")
                    .replace("DOJI", "⚪️"))

    def mostrar_velas(self, estrategia, velas):
        self.mostrar_mensagem(f"{estrategia.upper()}: " + 
            self.format_candles(" ".join(velas)))
        return velas

    def is_number(self, number):
        try:
            float(number)
            return True
        except:
            return False

    def catalogar_taxas(self, timeframe: int, candles: int, 
                        hits: int, paridades: list) -> list:
        def intersect_range(x: range, y: range) -> bool:
            return x[0] <= y[-1] and x[-1] >= y[0]
        
        def middle_intersection(x, y):
            intersection = set(x).intersection(set(y))
            return statistics.median(intersection)
        
        def create_range(number: int, multiply_factor: int = 1) -> range:
            number = round(multiply_factor * number)
            return range(number - RANGE_UNIT, number + RANGE_UNIT)

        RANGE_UNIT = 1
        result = []
        
        all_paridades = self.API.get_all_open_time()
        for par in all_paridades['digital']:
            if par not in paridades: continue
            velas = self.API.get_candles(par, timeframe * 60, candles, time.time())

            multiply_factor = 100000
            intersect_list = set()
            range_list = set()
            hit_dict = dict()
            for candle in velas:
                for value in [candle["open"], candle["close"], candle["min"], candle["max"]]:
                    value = create_range(value, multiply_factor)
                    was_intersected = False
                    for range_item in range_list:
                        if intersect_range(range_item, value):
                            range_list.remove(range_item)
                            new_value = middle_intersection(range_item, value)
                            new_range = create_range(new_value)
                            range_list.add(new_range)
                            if new_range not in hit_dict:
                                hit_dict[new_range] = hit_dict.get(range_item, 0)
                            hit_dict[new_range] += 1
                            
                            range_hits = hit_dict[new_range]
                            if range_hits >= hits:
                                taxas_value = round(new_value / multiply_factor, 5)
                                intersect_list.add(taxas_value)
                            was_intersected = True
                            break
                    if not was_intersected:
                        range_list.add(value)

            result.append((par, intersect_list))
        
        list_string = ""
        for paridade, intersect in result:
            for value in intersect:
                string = f"{paridade} {value}"
                list_string += string + "\n"
        entradas = convert_lines_to_list(list_string.split("\n"), False)

        return entradas