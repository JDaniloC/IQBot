from datetime import datetime, timedelta
from utils.operar import Operacao
import time

def is_in_list(estrategia, lista):
    for item in lista:
        if item in estrategia:
            return True
    return False

class Estrategias(Operacao):
    def pegar_velas(self, paridade = "EURUSD", quantidade = 0, 
        timeframe = 1, modo = "colors", velas = [], start = None):
        if velas == []:
            if start == None: start = time.time()
            velas = self.API.get_candles(paridade, 
                60 * timeframe, quantidade, start)
            if modo == "pure": return velas
        else:
            velas = velas[-quantidade:]

        if modo != "colors":
            return [x['close'] for x in velas]

        resultado = []
        if velas != [] and velas != None:
            for i in range(len(velas)):
                direcao = ('CALL' if velas[i]['open'] < 
                    velas[i]['close'] else 'PUT' if velas[i]['open'] 
                    > velas[i]['close'] else 'DOJI')
                resultado.append((direcao, datetime.fromtimestamp(
                        velas[i]['from']).strftime("%H:%M")))
        return resultado

    def proxima_entrada(self, min_list, estrategia, isM1 = False):
        minutos = str((datetime.now() + timedelta(minutes = 1)).minute).zfill(2)

        is_the_last = False
        for i in range(len(min_list)):
            if isM1:
                option = int(f"{minutos[0]}{min_list[i]}"
                    ) if estrategia != "daka" else min_list[i]
            else:
                option = min_list[i]
            
            if option >= int(minutos):
                entrar = option
                break
            elif i == len(min_list) - 1:
                entrar = min_list[0] if (
                    not isM1 or estrategia == "daka"
                ) else int(f"{minutos[0]}{min_list[0]}")
                is_the_last = True

        agora = datetime.fromtimestamp(
            datetime.utcnow().timestamp() - 10800).replace(
            minute = entrar, second = 0) + timedelta(minutes = 1)

        if agora.timestamp() - time.time() < 0 and is_the_last:
            if isM1: agora += timedelta(minutes = 10)
            else: agora += timedelta(hours = 1)
        horario = agora.strftime(f'%H:%M')
        
        if not self.verificar_stop():
            self.mostrar_mensagem(f"⏰ Próxima entrada será às {horario} ⏰")

    def entrada_estrategias_m1(self, estrategia, minutos, proxima = False):
        if estrategia == "daka":
            entrada = [x for x in range(0, 60, 4)]
        else:
            if minutos >= 10: minutos = int(str(minutos)[1])
        
            if estrategia in ['padrão 3x1', 'quinto elemento',
                "msf", "hope", "torres gêmeas", 'três vizinhos']:
                entrada = [3, 8] # 5° vela
            elif estrategia in ["três mosqueteiros"]:
                entrada = [2, 7] # 4° vela
            elif is_in_list(estrategia, ["melhor de 3", "vituxo", "mhi3"]):
                entrada = [1, 6] # 3° vela
            elif is_in_list(estrategia, ["padrão 23", "mhi2"]):
                entrada = [0, 5] # 2° vela
            elif estrategia == "seven flip":
                entrada = [6]
            elif estrategia == "r7":
                entrada = [5]
            else:
                entrada = [4, 9] # 1° vela

        if proxima: self.proxima_entrada(entrada, estrategia, True)
        return minutos in entrada

    def velas_por_estrategia_m1(self, par, estrategia, preset = []):
        if "impar" in estrategia:
            velas = [self.pegar_velas(par, 3, velas = preset)[0]]
        elif estrategia == "hope":
            velas = self.pegar_velas(par, 4, velas = preset)[::2]
        elif estrategia == "torres gêmeas":
            velas = [self.pegar_velas(par, 4, velas = preset)[0]]
        elif estrategia == "melhor de 3":
            velas = self.pegar_velas(par, 6, velas = preset)[:3]
        elif "milhão" in estrategia:
            velas = self.pegar_velas(par, 5, velas = preset)
        elif estrategia == "vituxo":
            velas = self.pegar_velas(par, 7, velas = preset)[:3]
        elif estrategia == "c3":
            velas = self.pegar_velas(par, 5, velas = preset)[::2]
        elif estrategia == "msf":
            velas = [self.pegar_velas(par, 9, velas = preset)[0]]
        elif estrategia == "r7":
            velas = [self.pegar_velas(par, 7, velas = preset)[0]]
        elif 'seven' in estrategia:
            velas = [self.pegar_velas(par, 7, velas = preset)[-1]]
        elif is_in_list(estrategia, ["mhi3"]):
            velas = self.pegar_velas(par, 5, velas = preset)[:3]
        elif is_in_list(estrategia, ['padrão 3x1', "mhi2"]):
            velas = self.pegar_velas(par, 4, velas = preset)[:3]
        elif is_in_list(estrategia, ["mhi"]):
            velas = self.pegar_velas(par, 3, velas = preset)
        else:
            velas = self.pegar_velas(par, 1, velas = preset)

        if len(velas) > 0: 
            velas, _ = zip(*velas)

        return list(velas)

    def entrada_estrategias_m5(self, estrategia, minutos, proxima = False):
        if estrategia in ["três mosqueteiros", 
            "triplicação", "não triplicação"]:
            entrada = [9, 24, 39, 54]
        elif estrategia in ["torres gêmeas", "five flip"]:
            entrada = [24, 54]
        elif estrategia in ["power", "gaba"]: 
            entrada = [14, 29, 44, 59]
        elif is_in_list(estrategia, ['três vizinhos']):
            entrada = [19, 49]
        elif is_in_list(estrategia, ["mhi2"]):
            entrada = [4, 34]
        elif is_in_list(estrategia, ["mhi3"]):
            entrada = [9, 39]
        else:
            entrada = [29, 59]

        if proxima: self.proxima_entrada(entrada, estrategia)
        return minutos in entrada

    def velas_por_estrategia_m5(self, par, estrategia, preset = []):
        if "last of five" in estrategia:
            velas = self.pegar_velas(par, 5, 5, velas = preset)
        elif estrategia in ["três mosqueteiros", 
            "triplicação", "não triplicação"]:
            velas = self.pegar_velas(par, 2, 5, velas = preset)
        elif "milhão" in estrategia:
            velas = self.pegar_velas(par, 6, 5, velas = preset)
        elif estrategia in ["torres gêmeas"]:
            velas = [self.pegar_velas(par, 6, 5, velas = preset)[0]]
        elif estrategia in ["five flip", 'três vizinhos']:
            velas = [self.pegar_velas(par, 1, 5, velas = preset)[0]]
        elif "mhi3" in estrategia:
            velas = self.pegar_velas(par, 5, 5, velas = preset)[:3]
        elif "mhi2" in estrategia:
            velas = self.pegar_velas(par, 4, 5, velas = preset)[:3]
        else:
            velas = self.pegar_velas(par, 3, 5, velas = preset)
        
        if len(velas) > 0: 
            velas, horarios = zip(*velas)
            self.chart_control("quadrante", horarios)

        return list(velas)

    def entrada_estrategias_m15(self, estrategia, minutos, proxima = False):
        if is_in_list(estrategia, ["torres gêmeas",  
            "mhi ", "milhão", "turn over"]):
            entrada = [59]
        elif estrategia == "torres gêmeas":
            entrada = [44]
        elif "mhi2" in estrategia:
            entrada = [14]
        else:
            entrada = [29]

        if proxima: self.proxima_entrada(entrada, estrategia)
        return minutos in entrada

    def velas_por_estrategia_m15(self, par, estrategia, preset = []):
        if estrategia == "half hour":
            velas = [self.pegar_velas(par, 2, 15, velas = preset)[0]]
        elif estrategia == "primeiros trocados":
            velas = [self.pegar_velas(par, 2, 15, velas = preset)[0]]
        elif estrategia == "turn over":
            velas = [self.pegar_velas(par, 1, 15, velas = preset)[0]]
        elif "mhi3" in estrategia:
            velas = self.pegar_velas(par, 5, 15, velas = preset)[:3]
        elif "mhi2" in estrategia:
            velas = self.pegar_velas(par, 4, 15, velas = preset)[:3]
        elif "mhi " in estrategia:
            velas = self.pegar_velas(par, 3, 15, velas = preset)
        elif estrategia == "torres gêmeas":
            velas = [self.pegar_velas(par, 4, 15, velas = preset)[0]]
        else:
            velas = self.pegar_velas(par, 4, 15, velas = preset)
        
        if len(velas) > 0: 
            velas, _ = zip(*velas)

        return list(velas)

    def velas_por_entrada_dupla(self, paridade, estrategia, preset = []):
        clear = lambda x: False if x == "DOJI" else x

        if estrategia in ["mhi + padrão impar", "mhi2 + r7",
            "mhi3 + seven flip", "torres gêmeas + padrão 3x1",
            "três vizinhos + torres gêmeas"]:
            if preset == []:
                velas = self.pegar_velas(paridade, 10, 1, "pure")
            else: velas = preset
            
            if estrategia == "mhi + padrão impar":
                primeiro = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m1(paridade, "mhi", velas))
                segundo = clear(self.velas_por_estrategia_m1(
                    paridade, "impar", velas)[0])
            
            elif estrategia == "mhi2 + r7":
                primeiro = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m1(paridade, "mhi2", velas))
                segundo = clear(self.velas_por_estrategia_m1(
                    paridade, "r7", velas)[0])

            elif estrategia == "mhi3 + seven flip":
                primeiro = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m1(paridade, "mhi3", velas))
                segundo = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m1(paridade, "seven", velas))
                
            elif estrategia == "torres gêmeas + padrão 3x1":
                primeiro = clear(self.velas_por_estrategia_m1(
                    paridade, "torres gêmeas", velas)[0])
                segundo = self.pegar_maioria_minoria("minoria", 
                    self.velas_por_estrategia_m1(paridade, "padrão 3x1", velas))

            elif estrategia == "três vizinhos + torres gêmeas":
                primeiro = clear(self.velas_por_estrategia_m1(
                    paridade, "vizinhos", velas)[0])
                segundo = clear(self.velas_por_estrategia_m1(
                    paridade, "torres gêmeas", velas)[0])
            
        elif estrategia != "turn over + mhi":
            if preset == []:
                velas = self.pegar_velas(paridade, 10, 5, "pure")
            else: velas = preset

            if estrategia == "five flip + não triplicação":
                primeiro = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m5(paridade, "five flip", velas))
                segundo = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m5(paridade, "não triplicação", velas))
            elif estrategia == "five flip + torres gêmeas":
                primeiro = self.pegar_maioria_minoria("minoria",
                    self.velas_por_estrategia_m5(paridade, "five flip", velas))
                segundo = clear(self.velas_por_estrategia_m5(
                    paridade, "torres gêmeas", velas)[0])
            elif estrategia == "triplicação + torres gêmeas":
                a, b = self.velas_por_estrategia_m5(paridade, "triplicação", velas)
                primeiro = self.pegar_maioria_minoria("minoria", [a, b])
                if a != b: primeiro = False
                segundo = clear(self.velas_por_estrategia_m5(
                    paridade, "torres gêmeas", velas)[0])
        
        elif estrategia == "turn over + mhi":
            primeiro = self.pegar_maioria_minoria("minoria",
                self.velas_por_estrategia_m15(paridade, "turn over", preset))
            segundo = self.pegar_maioria_minoria("minoria",
                self.velas_por_estrategia_m15(paridade, "mhi", preset))

        if not primeiro or not segundo:
            self.mostrar_mensagem("⏰ A entrada foi cancelada: DOJI")
            self.esperar_proximo_minuto()
            return [], False

        estr1, estr2 = estrategia.split("+")
        self.mostrar_mensagem(self.format_candles(
            f"➡️ {estr1.upper()}: {primeiro.upper()} | {estr2.upper()}: {segundo.upper()}"))
        return ([primeiro.lower()], primeiro.lower()) if (
            primeiro.lower() == segundo.lower()
        ) else ([], False)

    def verifica_entrada(self, estrategia, timeframe, 
        minutos, proxima = False):
        if proxima: proxima = timeframe

        if "+" in estrategia:
            estrategia = estrategia.split("+")[1].strip()

        if timeframe == 1:
            permitir = self.entrada_estrategias_m1(
                estrategia, minutos, proxima)
        elif timeframe == 5:
            permitir = self.entrada_estrategias_m5(
                estrategia, minutos, proxima)
        else:
            permitir = self.entrada_estrategias_m15(
                estrategia, minutos, proxima)
            
        return permitir

    def recebe_velas(self, paridade, estrategia, timeframe, preset = []):
        if "+" in estrategia:
            return self.velas_por_entrada_dupla(
                paridade, estrategia, preset)
            
        if timeframe == 1:
            velas = self.velas_por_estrategia_m1(
                paridade, estrategia, preset)
        elif timeframe == 5:
            velas = self.velas_por_estrategia_m5(
                paridade, estrategia, preset)
        else:
            velas = self.velas_por_estrategia_m15(
                paridade, estrategia, preset)
        
        return self.mostrar_velas(estrategia, velas)

    def mostrar_velas(self, estrategia, velas):
        self.mostrar_mensagem(f"{estrategia.upper()}: " + 
            self.format_candles(" ".join(velas)))
        return velas

    def pegar_maioria_minoria(self, estrategia, velas, verify = True):
        if verify and velas.count("DOJI") > 0:
            return False
        
        direcao = velas.count('CALL') > velas.count('PUT')
        direcao = "call" if direcao else "put"
        if is_in_list(estrategia, 
            ["msf", "padrão 3x1", "minoria", "flip",
            "power", "gaba", "elemento", "turn over", 
            "primeiros trocados"]):
            direcao = "put" if direcao == "call" else "call"
        return direcao

    def esperar_poshit(self, paridade, estrategia, 
        timeframe, hits = 3, trade_now = True):
        '''
        Espera ocorrer um hit, de acordo com o especificado.
        '''
        if trade_now:
            self.mostrar_mensagem(f"🔹 Filtro Bear {hits}: Analisando...")
        else:
            self.mostrar_mensagem(f"🔹 Procurando por HIT {hits} em {paridade}...")
        
        while not self.verificar_stop():
            horario = (datetime.now() - timedelta(
                minutes = timeframe * hits)) 
            entrada = self.verifica_entrada(
                estrategia, timeframe, horario.minute) 

            if entrada:
                velas = self.pegar_velas(paridade, 10, timeframe, 
                    "pure", start = horario.timestamp())
                velas, direcao = self.determina_direcao(
                    paridade, estrategia, timeframe, velas)

                if direcao:
                    ultimas = self.pegar_velas(paridade, hits, timeframe)
                    ultimas, _ = zip(*ultimas)
                    if not trade_now:
                        self.mostrar_velas(self.format_candles(
                            f"Deveria dar: {direcao}"), ultimas)
                    if all(map(lambda x: 
                        x.lower() != direcao.lower(), ultimas)):
                        return velas, direcao
                    elif trade_now:
                        self.mostrar_mensagem("Sem ciclo operável...")
            self.esperar_proximo_minuto()
        return [], False

    def determina_direcao(self, paridade, estrategia, timeframe, preset=[]):
        try:
            velas = self.recebe_velas(paridade, estrategia, timeframe, preset)
        except Exception as e:
            velas = ([], False)
            self.mostrar_mensagem(f"❌ Não consegui pegar as velas...")
            self.mostrar_mensagem(f"determina_direcao() {type(e)} {e}", True)
        if type(velas) != list:
            return velas
        
        direcao = False
        if len(velas) > 0 and velas.count("DOJI") == 0:
            if is_in_list(estrategia, 
                ["gaba", "msf", 'padrão 3x1', "power",
                'elemento', "minoria", "maioria", "vituxo",
                "turn over", "primeiros trocados", "flip"]):
                direcao = self.pegar_maioria_minoria(
                    estrategia, velas, False)
                if (estrategia == "power" and len(velas) > 1 and
                    direcao.upper() != velas[1]):
                    direcao = False
                elif (timeframe == 5 and "milhão" in estrategia and
                    velas.count("PUT") == velas.count("CALL")):
                    direcao = False
            elif timeframe == 5 and estrategia == "três mosqueteiros":
                if velas[0] != velas[1]: direcao = velas[0].lower()
            elif "triplicação" in estrategia:
                if velas[0] == velas[1]:
                    vela = velas[0].lower()
                    if estrategia == "triplicação": direcao = vela
                    else: direcao = "put" if vela == "call" else "call"
            else:
                if estrategia == "hope":
                    primeira, segunda = velas[0].lower(), velas[1].lower()
                    direcao = primeira if primeira == segunda else segunda
                else:
                    direcao = velas[0].lower()
        elif len(velas) > 0 and (velas.count("DOJI") < 3 and 
            "milhão" in estrategia and timeframe == 5):
            if velas.count("CALL") != velas.count("PUT"):
                direcao = self.pegar_maioria_minoria(estrategia, velas, False)
        elif len(velas) == 0:
            self.mostrar_mensagem("❌ Não consegui pegar as velas...")
        else:
            self.mostrar_mensagem("⏰ A entrada foi cancelada: DOJI")
            self.esperar_proximo_minuto()
        return velas, direcao
    
    def pegar_catalogacao(self):
        ciclos = self.config.get("autocycles", 0)
        is_poshit = self.config.get("poshit", 0) > 0
        gales_number = self.config.get("autogale", 2)
        auto_timeframe = self.config.get("autotime", 1)
        catalogador = self.config.get("catalogador", "old")
        posgale = self.config.get('posgale', 0)
        _assert = self.config.get("assert", 0)
        hits = self.config.get("hits", 0)

        timeframe = int(auto_timeframe[1:])
        porcentagem = False
        
        proximo_minuto = (datetime.now().minute + 1) % 60
        if timeframe == 1:
            min_func = lambda x: x == proximo_minuto
        else:
            min_func = lambda x: (x + 1) % timeframe == 0 

        minuto_atual = datetime.now().minute
        self.mostrar_mensagem(f"🔹 Esperando o tempo propício para catalogar...")
        while not self.verificar_stop() and not min_func(minuto_atual):
            self.esperar_proximo_minuto(segundos = 10)
            minuto_atual = datetime.now().minute

        if is_poshit:
            self.mostrar_mensagem(
                f"🔹 Procurando por um ativo com hit...")
        
        while not self.verificar_stop() and not porcentagem:
            porcentagem, paridade, estrategia = self.catalogar_estrategia(
                auto_timeframe, gales_number, is_poshit, posgale,
                ciclos, hits, _assert, catalogador)

            if not porcentagem:
                self.mostrar_mensagem(
                    "🔹 Catalogação: Nenhum atendeu os requisitos...")
                self.esperar_proximo_minuto(timeframe)
        else: 
            if not porcentagem: 
                self.mostrar_mensagem("pegar_catalogacao() not porcentagem", True)
                return "EURUSD", "mhi minoria"

        payout = round(100 * self.recebe_payout(
            paridade, timeframe)[1])
        self.mostrar_mensagem(f"""
🔹 {estrategia.upper()} | Paridade: {paridade} ♦️
🎯 Assertividade: {porcentagem}% | Payout: {payout}% ❇️""")
        self.esperar_proximo_minuto(0)
        return paridade, estrategia.lower()

    def mudar_estrategia(self, paridade, estrategia, 
        timeframe, result = False, force = False):
        self.num_operacoes += 1
        if (self.num_operacoes == self.config['max_trades'] 
            or result == "error" or force): 
            if self.config["auto"]:
                paridade, estrategia = self.pegar_catalogacao()
            elif self.config["poshit"] > 0:
                self.esperar_poshit(paridade, estrategia, 
                    timeframe, self.config["poshit"], False)
            self.num_operacoes = 0
        return paridade, estrategia

    def operar(self):
        self.valor = self.valor_inicial
        self.config["autotime"] = f"M{self.config['autotime']}" if (
            type(self.config["autotime"]) == int
        ) else self.config["autotime"]

        timeframe = int(self.config["autotime"][1:])
        if self.config["auto"]:
            paridade, estrategia = self.pegar_catalogacao()
        else:
            paridade = self.config['paridade']
            estrategia = self.config['estrategia'].lower()
            payout = round(100 * self.recebe_payout(
                paridade.upper(), timeframe)[1])
            self.mostrar_mensagem(f"""
🔹 {estrategia.capitalize()} | Paridade: {paridade}
❇️ Payout: {payout}%""")

            self.mostrar_mensagem("🔹 Iniciando... Esperando próximo minuto...")
            self.esperar_proximo_minuto()

        self.num_operacoes = 0
        if not self.config["auto"] and self.config["poshit"] > 0:
            self.esperar_poshit(paridade, estrategia, 
                timeframe, self.config["poshit"], False)
            
        self.verifica_entrada(estrategia, timeframe, 
            datetime.now().minute,  True)
        
        while not self.verificar_stop():   
            minutos = datetime.now().minute
            posgale = self.config.get('posgale', 0)

            if self.verifica_entrada(estrategia, timeframe, minutos
                ) or posgale > 0: # Filtro Bear
                if posgale > 0:
                    velas, direcao = self.esperar_poshit(paridade, 
                        estrategia, timeframe, posgale)
                else:
                    velas, direcao = self.determina_direcao(
                        paridade, estrategia, timeframe)

                if direcao:
                    self.mostrar_mensagem(self.format_dir(
                        f'Direção: {direcao.upper()}'))
                    tipo, payout = self.recebe_payout(paridade, timeframe)
                    
                    following_trend = self.verificar_tendencia(
                        paridade, direcao, timeframe)
                    following_news = self.verificar_noticias(paridade)
                    following_payout = self.verificar_payout(
                        paridade, payout)

                    if following_payout and following_news and following_trend:
                        gale = False
                        if estrategia in ["msf", "padrão impar"]: 
                            gale = estrategia
                        elif estrategia == "c3": gale = velas

                        result = self.realizar_trade(
                            self.valor, paridade, direcao, 
                            timeframe, payout, tipo, gale)
                        paridade, estrategia = self.mudar_estrategia(
                            paridade, estrategia, timeframe, result)
                    else:
                        paridade, estrategia = self.mudar_estrategia(
                            paridade, estrategia, timeframe, force = True)
                        self.esperar_proximo_minuto()
                        continue

                minutos = (datetime.now() + timedelta(minutes = 1)).minute
                self.verifica_entrada(estrategia, timeframe, minutos, True)
            self.esperar_proximo_minuto()
        self.verificar_stop()
