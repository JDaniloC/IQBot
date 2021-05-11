from utils.operar import Operacao
import threading, time

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
        
        for paridade, taxas in par_taxa.items():
            thread = threading.Thread(
                target = self.esperar_taxa, 
                name = f"{time.time()}", 
                args = (paridade, taxas),
                daemon = True)
            self.espera.append(thread)
            thread.start()

        # Lista
        self.comandos.sort(key = lambda x: x["timestamp"])
        if len(self.comandos) == 0:
            self.mostrar_mensagem("Nenhuma lista de sinais encontrada.")
        for index, comando in enumerate(self.comandos):
            if comando["tipo"] == "taxas": continue

            data = comando["data"]
            horas, minutos = comando["hora"]
            tempo = comando['timeframe'] if comando['timeframe'] != 0 else self.config["tempo"]
            segundos = 0

            if self.esperarAte(horas, minutos, segundos, data, 
                self.config['correcao'] + 1, self.mostrar_mensagem):

                par = comando['par']
                ordem = comando['ordem']
                valor = self.valor
                tipo, payout = self.recebe_payout(par, tempo)

                if self.verificar_tendencia(par, ordem, tempo):
                    continue

                if (self.ativar_noticias and
                    not self.verificar_noticias(par)):
                        continue
                # self.esperar_anteriores()

                if self.verificar_stop():
                    break

                if self.ocorreu_gale and self.config.get("no_posgale", False):
                    self.ocorreu_gale = False
                    self.mostrar_mensagem(
                        "Cancelando entrada devido gale na última operação.")
                    continue
                
                if self.config["minimo"] / 100 <= payout:
                    thread = threading.Thread(
                        target = self.realizar_trade, 
                        name = f"{time.time()}", 
                        args = (valor, par, ordem, tempo, payout, tipo),
                        daemon = True)
                    self.espera.append(thread)
                    thread.start()
                    self.valor = self.valor_inicial
                else:
                    self.mostrar_mensagem(f"{par} não atende o payout mínimo {payout * 100}% < {self.config['minimo']}%")
                self.mostrar_mensagem(f"Operando lista: {len(self.comandos) - index} sinais restantes.")
            else:
                self.mostrar_mensagem(f" ⏰ {comando['par']} - {formatHour(horas)}:{formatHour(minutos)} passou da hora ⏰ ")
        
        for thread in self.espera:
            thread.join()

        time.sleep(1)
        self.verificar_stop(True)

    def esperar_taxa(self, par, taxas):
        '''
        1 - Verifica se a taxa atual ultrapassou alguma das especificadas
        2 - Cria uma thread para o método operar
        '''
        def normalize(number):
            return int(str(number).replace(".", "")[3:])

        self.API.start_candles_stream(par, 60, 1)
        ultimo = {}
        while ultimo == {}:
            ultimo = self.API.get_realtime_candles(par, 60)
            ultimo = ultimo[list(ultimo.keys())[0]]['close']
            time.sleep(1)

        taxa_time = lambda x: f"{x[0]} M{x[1]}".replace(
            "M0", f"M{self.config['tempo']}")
        self.mostrar_mensagem(f"{par.upper()} esperando bater nas taxas:\n" + 
            '\n'.join(list(map(taxa_time, taxas))))
        chegou_perto = 0
        while not self.verificar_stop() and taxas != []:
            velas = self.API.get_realtime_candles(par, 60)
            abertura = velas[list(velas.keys())[0]]['open']
            fechamento = velas[list(velas.keys())[0]]['close']

            for taxa, timeframe in taxas:
                timeframe = self.config["tempo"] if timeframe == 0 else timeframe
                if (fechamento >= taxa and ultimo < taxa or 
                    fechamento <= taxa and ultimo > taxa):

                    direcao = "call" if abertura > fechamento else "put"
                    tipo, payout = self.recebe_payout(par, timeframe)

                    if (self.ativar_noticias and
                        not self.verificar_noticias(par)):
                        continue

                    if self.config["minimo"] / 100 <= payout:
                        self.mostrar_mensagem(f"Taxas: {par} {taxa} ")

                        if self.config.get("taxas_vela", "atual") != "atual":
                            self.esperar_proximo_minuto()

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

                    taxas.remove((taxa, timeframe))
                else:
                    if (abs(normalize(taxa) - normalize(fechamento)) <= 2 and 
                        chegou_perto != abs(taxa - fechamento)):
                        chegou_perto = abs(taxa - fechamento)
                        self.mostrar_mensagem(f"{par} perto da taxa {taxa}")
            ultimo = fechamento
            time.sleep(self.config['correcao'])
        self.API.stop_candles_stream(par, 60)