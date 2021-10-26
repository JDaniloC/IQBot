import time, numpy, requests, json, threading, random, finta, pandas
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta

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
                self.mostrar_mensagem("✅ Conectado com sucesso ✅")
                return True
            else:
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

    def abertas(self):
        paridades = { "turbo": [], "binary": [] }
        abertas = self.API.get_all_open_time()
        turbo = abertas["turbo"]
        binaria = abertas["binary"]
        digital = abertas["digital"]
        paridades["turbo"] = set(
            [x for x in turbo if turbo[x]["open"]] + 
            [x for x in digital if digital[x]["open"]])
        paridades["binary"] = set([x for x in binaria if binaria[x]["open"]])
        paridades["binary"] = paridades["binary"].intersection(paridades["turbo"])
        return paridades

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
    
    def catalogar_erros(self, mensagem):
        def is_in_list(nome, lista):
            for item in lista:
                if item in nome.lower():
                    return True
            return False
        
        if is_in_list(mensagem, ["is not available", "active_suspended"]):
            mensagem = "Ativo fechado nesta modalidade/timeframe."
        elif "invalid instrument" in mensagem:
            mensagem = "Paridade não encontrada na digital pela IQ." 
        self.mostrar_mensagem("❌ A IQ não permitiu: \n" + mensagem)

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
            self.catalogar_erros(identificador)
            
            if not trying:
                if self.tipo != "auto": 
                    self.tipo = "binary" if self.tipo == "digital" else "digital"
                self.mostrar_mensagem("❌ Erro na operação, tentando operar na " + 
                    ("binária" if tipo == "digital" else "digital"))
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

    def online_top_ranking(self, inicio = 1, final = 100, filtro = "Worldwide"):
        '''
        Procura o primeiro dos X traders online.
        '''
        ranking = []
        contador = 0
        while contador < 2 and ranking == []:
            ranking = self.API.get_leader_board(filtro, inicio, final, 0)
            contador += 1

        if ranking != [] and ranking is not None:
            paridades_abertas = self.abertas()['turbo']
            for position in ranking['result']['positional']:
                trader = ranking['result']['positional'][position]
                user_id = trader['user_id']
                if user_id == self.last_user_id: continue
                info = self.API.get_users_availability(user_id)

                if info["statuses"][0]["status"] == "online":    
                    self.last_user_id = user_id
                    ativos = self.API.get_all_ACTIVES_OPCODE()
                    key_list = list(ativos.keys())
                    value_list = list(ativos.values())

                    if "selected_asset_id" in info["statuses"][0]:
                        asset_id = info["statuses"][0]["selected_asset_id"]
                    else: asset_id = 1

                    paridade = key_list[value_list.index(asset_id)]
                    if paridade not in paridades_abertas: 
                        paridade = random.choice(list(paridades_abertas))
                        print(paridade)
                    return f"[{trader['flag']}] {position}° {trader['user_name']}", paridade
        return [], ""

    def berman_strategy(self, paridade: str, 
        ema_period: int, bbands_period: int) -> tuple:
        from talib.abstract import BBANDS, EMA

        quantidade = 1000
        velas = self.API.get_candles(
            paridade, self.tempo * 60, 
            quantidade, time.time())
        dados = {
            'open': numpy.empty(quantidade),
            'high': numpy.empty(quantidade), 
            'low': numpy.empty(quantidade),
            'close': numpy.empty(quantidade),
            'volume': numpy.empty(quantidade)
        }
        
        for x in range(0, quantidade):
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
        abertas = self.abertas()
        last_update = time.time()
        paridades = set(abertas["turbo"]).union(abertas["binary"])
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
    def catalogar_estrategia(timeframe, gale, poshit, hits = 0, _assert = 0):
        def is_hit(candles):
            hit = True
            for candle in candles:
                if candle in ["W", "D"] or (
                    candle == "G1" and gale != 0
                ) or (candle == "G2" and gale == 2):
                    hit = False
            return hit

        def traduzir(response):
            pct, par, estrategia = response[:3]

            maioria = "minoria"
            fatias = estrategia.lower().split()
            if len(fatias) == 2 and fatias[1] == "maioria":
                estrategia = fatias[0]
                maioria = "maioria"
            if fatias[0] == "milhão":
                estrategia = "milhão"
            elif "mhi" == estrategia[:3].lower():
                estrategia = estrategia.upper()
            return pct, par.upper(), (estrategia, maioria)

        if   gale == 2: _gale = "porcentagemGale2"
        elif gale == 1: _gale = "porcentagemGale1"
        else:           _gale = "porcentagemWinDePrimeira"
        data = requests.get(
            f"https://ocatalogador.com/api/{_gale}/M{timeframe}")
        try:
            resultado = json.loads(data.text)['Todos']
            for analise in resultado:
                if _assert > analise[0]:
                    continue

                candles = analise[3][0][-hits:]
                if (poshit and is_hit(candles)) or not poshit:
                    return traduzir(analise)
            return False, False, False
        except Exception as e:
            print("Catalogar:", e) 
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
        print("espera", espera)
        time.sleep(espera)

    def is_number(self, number):
        try:
            float(number)
            return True
        except:
            return False
