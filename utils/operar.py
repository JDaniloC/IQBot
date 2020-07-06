from datetime import datetime
from utils.IQ import IQ_API
import threading, traceback, time, re, sys

LOCALERROR = "config/errors.log"

def escreve_erros(erro):
    linhas = " -> ".join(re.findall(r'line \d+', str(traceback.extract_tb(erro.__traceback__))))
    with open(LOCALERROR, "a") as file:
        file.write(f"{type(erro)} - {erro}:\n{linhas}\n")

class Operacao(IQ_API):
    logo = ('''
       ******                                               
    ***********                                             
   ************                                             
     ***********                                            
             *****       .,,,,,,,,,,,,,,,,,                 
                *****,,,,,/(((((((#(((((,,,,,,              
                  ,*****/(((,,,,,,,,,((((#(,*,,             
                 ,,,,*****,,,.*//,,,,,,,((((.,,,*           
               ,,*((((,*****,///(/((/,,,,((((,,,,*          
              ,,,(((,,,,//,,*,,,,/(((,,,,#(((,,,,*/         
             ,,,((((,,,////,,.,..////,,,/(((*,,,***         
   @@@@@##   .,,//@@@@@//////(//(//..*@@@@@/,,,,,*. ((@@@@  
   @&@@@@##  ,,,/@@@@@@/,,(///(/,,,,,*@@@@@@/,,,,, ((@@@@@  
   @&*@@@@## ,,,@@*&@@@/,,,,,,,,,,/(//@@,@@@@/,,  ((@&*@@@  
   @&**@@@@##,,@@*.@@@@/((//(((((((((*@@,,&@@@/  ((@@**@@@  
   @&/* @@@@##@@*.,&@@@/(((((((*,,*,,*@@..,&@@@@/(@  **@@@  
   @&/*  @@@@@@*   &@@@/,,,,,,,,,,,..*@@.  ,%@@@@@   **@@@  
   @&/*   @@@@*    %@@@/......&(.....,@@    .#@@@    **@@@  
   @&/,    @@*     %@@@      @*@      @@      /@      *@@@  
                                                           
''')

    welcome = ('''                                                          
  ___       _        _                      _         _         
 / __| ___ (_)__ _  | |__  ___ _ __ _____ _(_)_ _  __| |___     
 \__ \/ -_)| / _` | | '_ \/ -_) '  \___\ V / | ' \/ _` / _ \    
 |___/\___|/ \__,_| |_.__/\___|_|_|_|   \_/|_|_||_\__,_\___/    
         |__/                                                   
             ___     _           __  __   __  __   __   __ ____ 
  __ _ ___  | _ \___| |__  ___  |  \/  | |  \/  | /  \ /  \__  |
 / _` / _ \ |   / _ \ '_ \/ _ \ | |\/| |_| |\/| || () | () |/ / 
 \__,_\___/ |_|_\___/_.__/\___/ |_|  |_(_)_|  |_|_\__/ \__//_/  
                                               |___|           
''')

    def __init__(self, config, comandos, maximo = 0):
        self.maximo = maximo
        self.cadeado = threading.Lock()

        self.config = config
        self.comandos = comandos
        self.total = 0

        if self.maximo < 3:
            try:
                print(self.logo, flush = True)
                print(self.welcome, flush = True)

                print(f"Entrando na {config['email']}")
                super().__init__(config['email'], config['senha'])

                if config['tipo_conta'] == "treino":
                    self.mudar_treino()
                else:
                    self.mudar_real()

                if config['tipo_par'] == "auto":
                    self.tipo = config['tipo_par']
                else:
                    self.tipo = "digital" if config['tipo_par'] == 'digital' else "binary"

                self.valor = config['valor']
                self.tempo = config['tempo']
                self.max_gale = config["max_gale"]

                self.computar()
            except Exception as e:
                print("Aconteceu um erro na API, tentando novamente.")
                escreve_erros(e)
                
                try:
                    print("Continuando as operações...")
                    self.maximo += 1
                    self.__init__(self.config, self.comandos, self.maximo)
                except:
                    print("Deu erro novamente! Finalizando o programa.")
                    escreve_erros(e)

    def operar(self, valor, par, ordem, payout, tipo):
        '''
        Faz a operação e a depender da configuração faz:
        Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
        '''
        resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo, self.cadeado)
        perda = 0
        if resultado == "win" and self.config['soros']:
            with self.cadeado:
                novo = self.valor + lucro if self.config["percent_soros"] == 0 else self.valor + self.valor * self.config["percent_soros"] / 100
                print(f"\n [SOROS GALE] : {round(self.valor, 2)} -> {round(novo, 2)}")
                self.valor = novo
        if resultado == "loose" and self.config['martin'] and self.total - round(abs(lucro), 2) > -(self.config['stoploss']):
            num_gales = 0
            print(f"\n [MARTIN GALE] do tipo {self.config['tipo_gale']} na operação {par}|{ordem}")
            while (
                resultado != "win" and 
                self.max_gale > num_gales and 
                self.config['goal'] > self.total):
                
                with self.cadeado:
                    self.total -= round(abs(lucro), 2)
                    if self.total <= -(self.config['stoploss']):
                        print(f"MARTINGALE CANCELADO: BATEU NO STOPLOSS: {self.total}!")
                        sys.exit(0)

                perda += abs(lucro)
                lucro = self.valor * payout if self.config["tipo_gale"] != "porcento" else self.config["percent_martin"] / 100
                valor = self.martingale(self.config['tipo_gale'], payout, perda, valor, lucro)
                
                resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo, self.cadeado)
                num_gales += 1
        elif resultado == "loose":
            self.total -= round(abs(lucro), 2)

        if resultado not in ["error", "equal"]:
            with self.cadeado:
                if resultado == "win":
                    self.total += round(lucro, 2)
                elif not self.config["martin"]:
                    self.total -= round(abs(lucro), 2)
                
            print(f"\n | {round(self.total/self.config['goal'] * 100, 2)}% perto do objetivo | {round(-self.total/self.config['stoploss'] * 100, 2)}% perto do stoploss |\n")
        elif resultado == "error":
            print(f"\nErro na operação das {threading.current_thread().name}")

    def computar(self):
        '''
        1 - Percorre todos os comandos.
        2 - Pausa o script até a próxima hora:min
        3 - Calcula o payout da paridade
        4 - Cria uma thread para o método operar
        '''
        espera = []

        if self.tipo == "auto":
            ultima_vez = time.time()
            paridades = [x["par"] for x in self.comandos]
            for par in paridades:
                self.API.subscribe_strike_list(par, self.config["otc"])
            payouts = self.aberta_profit(paridades, self.config["otc"])

            def atualizar_profits(comando):
                '''
                Atualiza os payouts do comando em diante.
                '''
                print("Atualizando profits...")
                paridades = [x["par"] for x in self.comandos[self.comandos.index(comando):]]
                payouts.update(self.aberta_profit(paridades, self.config["otc"]))

        for comando in self.comandos:
            
            data = comando["data"]
            horas, minutos = comando["hora"]
            segundos = 0
            if self.esperarAte(horas, minutos, segundos, data, self.config['correcao'] + 30, True):

                par = comando['par']
                par += "-OTC" if self.config["otc"] else ""

                ordem = comando['ordem']
                valor = self.valor

                if self.tipo == "auto":
                    if ((payouts["binary"][par][0] and payouts["digital"][par][0]) 
                        and 
                        (payouts["binary"][par][1] < payouts["digital"][par][1])):
                        tipo = "digital"
                        payout = payouts["digital"][par][1]
                    elif payouts["binary"][par][0]:
                        tipo = "binary"
                        payout = payouts["binary"][par][1]
                    elif payouts["digital"][par][0]:
                        tipo = "digital"
                        payout = payouts["digital"][par][1]
                    else:
                        print(f"{par} não está disponível nem binária nem digital")
                        continue
                else:
                    payout = self.payout_binaria(par) / 100 if self.tipo == "binary" else self.payout_digital(par) / 100
                    tipo = self.tipo

                delay = 2 # Tempo de calcular, windows/linux = 3/2
                self.esperarAte(horas, minutos, segundos, data, delay) 
                with self.cadeado:
                    if not (-self.config['stoploss'] < self.total < self.config['goal']):
                        break
                
                if self.config["minimo"] / 100 <= payout:
                    thread = threading.Thread(
                        target = self.operar, 
                        name = f"{horas}:{minutos}", 
                        args = (valor, par, ordem, payout, tipo)
                        )
                    espera.append(thread)
                    thread.start()

                if self.tipo == "auto":
                    if time.time() - ultima_vez > 1800:
                        threading.Thread(
                        target = atualizar_profits,
                        args = (comando,)
                        ).start()
            else:
                momento = datetime.utcnow().timestamp() - 10800 # -3Horas
                print(f"UTC-3: {datetime.fromtimestamp(momento).strftime('dia %d - %H:%M')} | {comando['par']} - {horas}:{minutos} passou da hora.") # Consertar aqui
        for thread in espera:
            thread.join()

        print(f"\nFim da operação resultado final: {round(self.total, 2)}\n")

        try:
            if self.tipo == "auto":
                for comando in self.comandos:
                    par = comando["par"]
                    par += "-OTC" if self.config["otc"] else ""
                    self.API.unsubscribe_strike_list(par, self.config["tempo"])
        except:
            pass