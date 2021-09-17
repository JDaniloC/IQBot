import threading, time, traceback
from utils.operar import Operacao
from datetime import datetime

class ListaTaxa(Operacao):
    def __init__(self, config, comandos = [], chat_id = False):
        super().__init__(config, comandos, chat_id)

    def operar(self):
        '''
        1 - Percorre todos os comandos.
        2 - Pausa o script até a próxima hora:min
        3 - Calcula o payout da paridade
        4 - Cria uma thread para o método operar
        '''
        def formatHour(number):
            '''
            Converte números de 1 dígito para 2 dígitos:
                0:0 -> 00:00
                2/1/2000 -> 02/01/2000
            '''
            return str(number) if len(str(number)) != 1 else "0" + str(number)

        self.espera = []
        par_taxa = {}  
        for comando in self.comandos:
            if comando["tipo"] == "taxas":
                paridade = comando['par']
                valor = (comando['taxa'], comando['timeframe'])
                if paridade not in par_taxa:
                    par_taxa[paridade] = [valor]
                else:
                    par_taxa[paridade].append(valor)
        
        self.tempo = self.config.get("tempo", 5)
        taxa_time = lambda x: f"{x[0]} M{x[1]}".replace("M0", f"M{self.tempo}")
        mensagem = ""
        for paridade, taxas in par_taxa.items():
            mensagem += f"{paridade.upper()} esperando bater nas taxas:\n" + \
                '\n'.join(list(map(taxa_time, taxas))) + "\n\n"
            thread = threading.Thread(
                target = self.esperar_taxa, 
                name = f"{time.time()}", 
                args = (paridade, taxas),
                daemon = True)
            self.espera.append(thread)
            thread.start()

        linhas = mensagem.split("\n")
        for i in range(0, len(linhas), 50):
            self.mostrar_mensagem("\n".join(linhas[i:i+50]))

        # Lista
        self.comandos.sort(key = lambda x: x["timestamp"])
        if len(self.comandos) == 0:
            self.mostrar_mensagem("Nenhuma lista de sinais encontrada.")
        for index, comando in enumerate(self.comandos):
            if comando["tipo"] == "taxas": continue

            data = comando["data"]
            horas, minutos = comando["hora"]
            timeframe = comando['timeframe'] if comando['timeframe'] != 0 else self.config["tempo"]
            segundos = 0

            if self.esperarAte(horas, minutos, segundos, data, 
                self.config['correcao'] + 1, self.mostrar_mensagem):

                paridade = comando['par']
                direcao = comando['ordem']
                valor = self.valor

                tipo, payout = self.recebe_payout(paridade, timeframe)
                following_trend = self.verificar_tendencia(
                    paridade, direcao, timeframe)
                following_news = self.verificar_noticias(paridade)
                following_payout = self.verificar_payout(paridade, payout)
                not_posgale = self.verificar_posgale()

                if self.verificar_stop():
                    break
                
                if (following_payout and following_news 
                    and following_trend and not_posgale):
                    thread = threading.Thread(
                        target = self.realizar_trade, 
                        name = f"{time.time()}", 
                        args = (valor, paridade, direcao, 
                            timeframe, payout, tipo),
                        daemon = True)
                    self.espera.append(thread)
                    thread.start()
                    self.valor = self.valor_inicial
                self.mostrar_mensagem(f"Operando lista: {len(self.comandos) - index} sinais restantes.")
            else:
                self.mostrar_mensagem(
                    f" ⏰ {comando['par']} - {formatHour(horas)}:{formatHour(minutos)} passou da hora ⏰ ")
        
        for thread in self.espera:
            thread.join()

        time.sleep(1)
        self.verificar_stop(True)

    def esperar_taxa(self, par, taxas):
        '''
        1 - Verifica se a taxa atual ultrapassou alguma das especificadas
        2 - Cria uma thread para o método operar
        '''
        self.API.start_candles_stream(par, 60, 1)
        ultimo = {}
        while ultimo == {}:
            ultimo = self.API.get_realtime_candles(par, 60)
            ultimo = ultimo[list(ultimo.keys())[0]]['close']
            time.sleep(1)

        while not self.verificar_stop() and taxas != []:
            velas = self.API.get_realtime_candles(par, 60)
            try:
                abertura = velas[list(velas.keys())[0]]['open']
                fechamento = velas[list(velas.keys())[0]]['close']
            except:
                traceback.print_exc()
                time.sleep(1)
                continue

            
            for index, (taxa, timeframe) in enumerate(taxas.copy()):
                timeframe = self.tempo if timeframe == 0 else timeframe
                if (fechamento >= taxa and ultimo < taxa or 
                    fechamento <= taxa and ultimo > taxa):

                    direcao = "call" if abertura > fechamento else "put"
                    tipo, payout = self.recebe_payout(par, timeframe)

                    if (self.ativar_noticias and
                        not self.verificar_noticias(par)):
                        continue

                    if self.config["minimo"] / 100 <= payout:
                        self.mostrar_mensagem(f"Taxas: {par} {taxa} ")

                        if self.config.get("taxas_vela", "retração") != "retração":
                            self.esperar_proximo_minuto(seconds = 59)
                            velas = self.API.get_candles(par, 
                                60 * timeframe, 1, time.time())
                            direcao = velas[0]["close"] - velas[0]["open"]
                            direcao = "call" if direcao < 0 else "put"

                        if tipo == "binary" and timeframe == 5:
                            atual = datetime.utcnow()
                            if ((atual.minute % 5 == 4 and atual.second < 30) 
                                or atual.minute % 5 < 4): 
                                timeframe = 5 - (atual.minute % 5)

                        thread = threading.Thread(
                            target = self.realizar_trade, 
                            name = f"{time.time()}", 
                            args = (self.valor, par, direcao, 
                                timeframe, payout, tipo),
                            daemon = True)
                        self.espera.append(thread)
                        thread.start()
                    else:
                        self.mostrar_mensagem(f"{par} {taxa} não atende o payout mínimo {payout} {self.config['minimo']}")

                    try: taxas.pop(index)
                    except: traceback.print_exc()
            ultimo = fechamento
            time.sleep(self.config.get('correcao', 0) + 0.1)
        self.API.stop_candles_stream(par, 60)