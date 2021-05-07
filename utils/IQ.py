from iqoptionapi.stable_api import IQ_Option
from datetime import datetime, timedelta
import time, numpy, requests, json

class IQ_API:
    def __init__(self, login, senha):
        '''
        Recebe o login, e tenta se conectar
        '''
        self.payout_cache = {}
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
            print("Pegando payout digital")
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
        print("Pegando payout binária")
        payouts = self.API.get_all_profit()
        valor = payouts.get(paridade)
        if valor == None:
            result = False
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
    
    def ordem(self, paridade, direcao = "call", tempo = 1, 
        valor = 1, tipo = "binary", bloqueador = None, 
        delay = False, scalper = False, trying = False):
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

        if self.config.get('prestoploss', False) and (
            self.perda_total - valor <= -self.stoploss):
            self.mostrar_mensagem("❌ Pré-stoploss: Fim da operação ❌")
            self.verificar_stop(True)
            return 'error', 0, tipo
        elif self.config.get('prestopwin', 0) > 0:
            missing = (100 - self.config['prestopwin']) / 100
            if self.ganho_total >= self.stopwin * missing:
                self.mostrar_mensagem("✅ Pré-stopwin: Fim da operação ✅")
                self.verificar_stop(True)
                return 'error', 0, tipo

        if tipo == "binary" and tempo == 5:
            atual = datetime.utcnow()
            if ((atual.minute % 5 == 4 and atual.second < 30) 
                or atual.minute % 5 < 4): 
                tempo = 5 - (atual.minute % 5)

        with bloqueador:
            if tipo == "binary":
                status, identificador = self.API.buy(
                    valor, paridade, direcao, tempo)
            else:
                status, identificador = self.API.buy_digital_spot(
                    paridade, valor, direcao, tempo)

        if not status:
            if tipo == "digital":
                identificador = str(identificador['message'])
            else: identificador = str(identificador)
            self.mostrar_mensagem("❌ Não consegui operar: " + identificador)
            
            if not trying:
                if self.tipo != "auto": 
                    self.tipo = "binary" if self.tipo == "digital" else "digital"
                self.mostrar_mensagem("❌ Erro na operação, tentando operar na " + 
                    ("binária" if tipo == "digital" else "digital"))
                tipo = "binary" if tipo == "digital" else "digital"
                
                paridade = paridade.upper()
                payout_atual = (round(self.payout_cache[paridade][tipo] * 100)
                    if self.payout_cache[paridade][tipo] else -1)
                if payout_atual >= self.config['minimo']:
                    return self.ordem(paridade, direcao, tempo, valor, 
                        tipo, bloqueador, delay, scalper, True)
                else:
                    self.mostrar_mensagem(f"Payout na {tipo} está abaixo do aceitável {payout_atual}% < {self.config['minimo']}%")
            return "error", 0, tipo

        self.mostrar_mensagem(self.format_dir(
            f" 🔸 {paridade} | {tipo.capitalize()} | M{tempo} | $ {round(valor, 2)} | {direcao.upper()}"))
        
        lucro = 0
        if delay == False:
            # Versão que pega no histórico
            if tipo == "binary":
                resultado, lucro = self.API.check_win_v4(identificador) 
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
            resultado, lucro = self.API.check_win_v5(
                identificador, tipo, delay)

        print(f"""
Paridade: {paridade}|{tipo.capitalize()}
Direção:  {direcao.upper()}
tempo:    M{tempo}

Hora: {hora_atual.strftime("%H:%M")}
Valor: R$ {round(valor, 2)}
{resultado.capitalize()}:  R$ {round(lucro, 2)}""")

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
                return velas[0] == direcao
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

    @staticmethod
    def catalogar_estrategia(timeframe, gale, poshit):
        def is_hit(res):
            hit = False
            if res == "H":
                hit = True 
            elif res == "G2" and gale != "2":
                hit = True
            elif res == "G1" and gale == "0":
                hit = True
            return hit

        def verify_minoria(response):
            pct, par, estrategia = response

            estrategia = estrategia.lower()
            if ("mhi" in estrategia and
                "maioria" not in estrategia):
                estrategia = f"{estrategia} minoria"

            return pct, par, estrategia

        if   gale == "2": gName = "porcentagemGale2"
        elif gale == "1": gName = "porcentagemGale1"
        else:             gName = "porcentagemWinDePrimeira"
        data = requests.get(f"https://ocatalogador.com/api/{gName}/{timeframe}")
        try:
            resultado = json.loads(data.text)['Todos']
            for analise in resultado:
                candle = analise[3][0][-1]
                print(analise[1:3], candle)
                if poshit and is_hit(candle):
                    return verify_minoria(analise[:3])
                elif not poshit:
                    return verify_minoria(analise[:3])
            return False, False, False
        except Exception as e:
            print("Catalogar_estrategia()", e) 
            return 50, "EURUSD", "MHI minoria"

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
        elif tipo_martin == "percent":
            return round(abs(perca) * lucro / payout, 2)
        else:
            return round((abs(perca) + abs(perca) * lucro)/payout, 2)

    def esperar_proximo_minuto(self, minutos = 1):
        time.sleep(((datetime.now() + timedelta(
            seconds = 50 * minutos)
        ).replace(second = 56).timestamp() - time.time()) % 60)