import time, numpy, requests, json, threading
from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta
from messages import *

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
        self.asset, self.timeframe, self.payout_cache = False, False, {}
        self.cadeado = threading.Lock()
        self.API = IQ_Option(login, senha)
        if not self.conectar():
            raise ConnectionError(connection_error_msg())
        
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
                self.mostrar_mensagem(connection_success_msg())
                return True
            else:
                self.mostrar_mensagem(connection_trying_msg())
                self.API.connect()
                time.sleep(1)
        return False

    def mudar_treino(self):
        '''
        Muda para a conta treino
        '''
        if self.API.get_balance_mode() != "PRACTICE":
            self.mostrar_mensagem(demo_account_msg())
            self.API.change_balance("PRACTICE")
    
    def mudar_real(self):
        '''
        Muda para a conta real
        '''
        if self.API.get_balance_mode() != "REAL":
            self.mostrar_mensagem(real_account_msg())
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
        for _ in range(2):
            abertas = self.API.get_all_open_time()
            if paridades == False: 
                paridades = list(abertas["binary"].keys())
            todos_binary = self.API.get_all_profit()
            if abertas == None or todos_binary == None:
                self.mostrar_mensagem(without_payout_msg())
                self.conectar()
            else:
                break
        if abertas == None or todos_binary == None:
            self.mostrar_mensagem(restart_bot_msg())
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
                    payout_digital = self.API.get_digital_current_profit(par, 1)
                    contador_limite += 1
                    if contador_limite == 5:
                        break
                if contador_limite != 5:
                    payouts["digital"][par] = [
                        True, round(payout_digital / 100, 2)]
                else:
                    self.mostrar_mensagem(cannot_get_payout_msg(par))
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
            self.mostrar_mensagem(closed_asset_msg())
        elif "invalid instrument" in mensagem:
            self.mostrar_mensagem(invalid_asset_msg())
        else: 
            self.mostrar_mensagem(trade_error_msg())

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

        if self.config.get('prestoploss', False) and (
            self.perda_total - valor <= -self.stoploss):
            self.mostrar_mensagem(pre_stop_loss_msg())
            self.verificar_stop(True)
            return 'error', 0, tipo
        elif self.config.get('prestopwin', 0) > 0:
            missing = (100 - self.config['prestopwin']) / 100
            if self.ganho_total >= self.stopwin * missing:
                self.mostrar_mensagem(pre_stop_win_msg())
                self.verificar_stop(True)
                return 'error', 0, tipo

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

                tipo = "binary" if tipo == "digital" else "digital"
                self.mostrar_mensagem(switch_trade_type_msg(tipo))
                
                opcoes_modalidade = self.payout_cache.get(paridade.upper())
                payout_modalidade = opcoes_modalidade.get(tipo) if opcoes_modalidade else -1
                payout_atual = round(payout_modalidade * 100) if payout_modalidade else -1
                if payout_atual >= self.config['minimo']:
                    return self.ordem(paridade, direcao, tempo, 
                        valor, tipo, delay, scalper, True)
                else:
                    if payout_atual < 0:
                        reason = payout_not_found_msg()
                    else:
                        reason = f"{payout_atual}% < {self.config['minimo']}%"
                    self.mostrar_mensagem(payout_below_minimum_msg(tipo, reason))
            return "error", 0, tipo

        self.mostrar_mensagem(self.format_dir(
            f" 🔸 {paridade} | {tipo.capitalize()} | M{tempo} | $ {round(valor, 2)} | {direcao.upper()}"))
                
        lucro = 0
        if delay == False:
            # Versão que pega no histórico
            if tipo == "binary":
                resultado, lucro = self.API.check_win_v4(identificador) 
            else:
                status = False
                start = time.time()
                time.sleep((tempo * 60) - 10)
                while not status:
                    status, lucro = self.API.check_win_digital_v2(identificador)
                    time.sleep(0.5)
                    if time.time() - start > ((tempo + 1) * 60):
                        raise Exception('Não consegui pegar o resultado...')
                if lucro > 0:
                    resultado = "win"
                elif lucro < 0:
                    resultado = "loose"
                else:
                    resultado = "equal"
        else:
            # Versão que pega na hora
            resultado, lucro = self.API.check_win_v5(
                identificador, tipo, delay)

        return resultado, round(lucro, 2), tipo

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
        # Calcula a SMA
        pesos = numpy.repeat(1.0, periodo) / periodo
        smas = numpy.convolve(
            dados, pesos, 'valid').tolist()
        diferenca = smas[-1] - smas[-periodo]

        return True if (
            direcao.lower() == "call" 
            and diferenca > 0) or (
            direcao.lower() == "put" 
            and diferenca < 0) else False

    def format_dir(self, text):
        return text.replace("CALL", "⬆️").replace("PUT", "⬇️")

    def format_candles(self, text):
        return text.replace("CALL", "🟢"
            ).replace("PUT", "🔴").replace("DOJI", "⚪️")

    def get_all_open_time(self):
        '''
        Retorna todos os horários de abertura de todas as opções
        '''
        result = None
        def wait_for_all_open_time():
            nonlocal result
            result = self.API.get_all_open_time()
        thread = threading.Thread(target=wait_for_all_open_time)
        thread.start()
        thread.join(10)
        return result

    def catalogar_estrategia(self, timeframe, gale, poshit, posgale,
            ciclos = 0, hits = 0,  _assert = 0, catalogador = "old"):
        try:
            if catalogador == "novo":
                if not poshit: hits = 0
                assets = self.config.get("assets", [])
                strategies = self.config.get("strategies", [])
                
                resultado = self.bear_catalogador(timeframe, 
                    gale, ciclos, hits, posgale, _assert, 
                    assets, strategies)
            else:
                resultado = self.ocatalogador(timeframe, 
                    gale, poshit, ciclos, hits, _assert, 
                    self.get_all_open_time())
        except Exception as e: 
            self.mostrar_mensagem(abort_cataloguer_msg())
            self.mostrar_mensagem(str(type(e)) + str(e), True)
            resultado = False, False, False

        return resultado

    def verify_payouts(self, paridade, payouts):
        if not payouts: return True

        if_err = {"open": False}
        binaria = payouts["turbo"].get(paridade, if_err)["open"]
        digital = payouts["digital"].get(paridade, if_err)["open"]
        
        if self.tipo == "digital":
            its_ok = digital                        
        elif self.tipo == "binary": 
            its_ok = binaria
        else:
            its_ok = digital or binaria

        if its_ok:
            timeframe = int(self.config["autotime"][1:])
            payout = round(100 * self.recebe_payout(
                paridade, timeframe)[1])
            if payout < self.config['minimo']:
                its_ok = False
        return its_ok
    
    def verify_payouts_bear(self, analise):
        its_ok = True
        if analise.get("payout"):
            digital = analise["payout"]["digital"]
            binaria = analise["payout"]["binary"]
            if self.tipo == "digital":
                payout = digital 
            elif self.tipo == "binary": 
                payout = binaria
            else:
                payout = digital if digital > binaria else binaria

            if (payout * 100) < self.config['minimo']:
                its_ok = False
        else:
            paridades_abertas = self.get_all_open_time()
            its_ok = self.verify_payouts(
                analise["asset"], paridades_abertas)
        return its_ok

    def bear_catalogador(self, timeframe: int, gale: int, ciclos: int, hits: int, 
        posgale: int, _assert: int, assets: list, strategies: list) -> tuple:

        payout_min = self.config.get("minimo", 0)
        data = requests.get(
            f"https://catalogador.herokuapp.com/api/catalogacao/{timeframe}/{gale}/",
            headers = { 
                "poshit": str(hits), 
                "cycles": str(ciclos),
                "posgale": str(posgale),
                "assert": str(_assert),
                "tipo": str(self.tipo),
                "payout": str(payout_min),
                "assets": ",".join(assets),
                "strategies": ",".join(strategies),
            })
        resultado = json.loads(data.text)
        trades = resultado['trades']
        for analise in trades:
            paridade = analise["asset"]
            estrategia = analise["strategy"]
            percentage = analise["percents"][0]
                
            return percentage, paridade, estrategia
        
        reason = resultado.get("reason", "Está catalogando...")
        if reason == "": reason = "Desconhecido..."
        self.mostrar_mensagem(cataloguer_error_msg(reason))

        return False, False, False

    def ocatalogador(self, timeframe, gale, 
        poshit, ciclos, hits, _assert, payouts):
        def is_hit(candles):
            hit = True
            for candle in candles:
                if candle in ["W", "D"] or (
                    candle == "G1" and gale != "0"
                ) or (candle == "G2" and gale == "2"):
                    hit = False
            return hit

        def verify_minoria(response):
            pct = response["win"]
            par = response["par"]
            estrategia = response["estrategia"]

            estrategia = estrategia.lower()
            if ("mhi" in estrategia and
                "maioria" not in estrategia):
                estrategia = f"{estrategia} minoria"

            return pct, par, estrategia

        def verify_ciclos(trades: list):
            return ciclos < (len(trades) - trades.count("D"))

        if   gale == "2": gName = "G2"
        elif gale == "1": gName = "G1"
        else:             gName = "G0"
        data = requests.get(f"https://backend.ocatalogador.com/api/v1/catalogue/Todos/{timeframe}/Todas/24/{gName}")
        resultado = data.json()
        for analise in resultado:
            if not verify_ciclos(analise["quadrantes"]
                ) or _assert > analise["win"]:
                continue
            
            candle = analise["quadrantes"][-hits:]   
            if (poshit and is_hit(candle)) or not poshit:
                if payouts:
                    its_ok = self.verify_payouts(analise["par"], payouts)
                    if not its_ok: continue
       
                return verify_minoria(analise)
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
        elif tipo_martin == "porcento":
            return round((abs(perca) + lucro) / payout, 2)
        else:
            return round((abs(perca) + abs(perca) * lucro)/payout, 2)

    def esperar_proximo_minuto(self, minutos = 1, segundos = 56):
        correcao = self.config.get('correcao', 0)
        espera = (((datetime.now() + timedelta(
            seconds = 50 * minutos)
        ).replace(second = segundos) - timedelta(
            seconds = correcao)
        ).timestamp() - time.time())
        
        if espera > 0: 
            time.sleep(espera)

    def is_number(self, number):
        try:
            float(number)
            return True
        except:
            return False
