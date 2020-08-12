from datetime import datetime, timedelta
from utils.IQ import IQ_API
import threading, traceback, time, re, sys
from pprint import pprint

LOCALERROR = "errors.log"
LOCALLOG = ""

def escreve_erros(erro):
    linhas = " -> ".join(re.findall(r'line \d+', str(traceback.extract_tb(erro.__traceback__))))
    with open(LOCALERROR, "a") as file:
        file.write(f"{type(erro)} - {erro}:\n{linhas}\n")

def escreve_log(email, mensagem):
    with open(LOCALLOG + email + ".txt", "a", encoding = "utf-8") as file:
        file.write(mensagem + "\n")

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

    def __init__(self, config, comandos, 
        maximo = 0, verboso = False):
        self.maximo = maximo
        self.cadeado = threading.Lock()

        self.config = config
        self.comandos = comandos
        self.ganho_total = 0
        self.perda_total = 0
        self.verboso = verboso

        if self.maximo < 3:
            try:
                print(self.logo, flush = True)
                print(self.welcome, flush = True)

                if self.verboso:
                    import amanobot
                    self.telegram = amanobot.Bot("1354635217:AAG1EbTt772cwPh008Ud3uBqyxyS28LXZao")

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

                if config['soros']:
                    self.valor_inicial = config['valor']
                    self.soros_atual = 0

                self.valor = config['valor']
                self.tempo = config['tempo']
                self.max_gale = config["max_gale"]
                if config['tendencia']:
                    self.config['correcao'] += 3

                self.computar()
            except KeyboardInterrupt:
                sys.exit(0)
            except Exception as e:
                if type(e) == ConnectionError:
                    self.mostrar_mensagem("Não conseguiu se conectar na conta")
        
                    self.maximo = 3
                else:
                    print("Aconteceu um erro na API, tentando novamente.")
                escreve_erros(e)
                
                try:
                    print("Continuando as operações...")
                    self.maximo += 1
                    self.__init__(self.config, self.comandos, self.maximo)
                except:
                    print("Deu erro novamente! Finalizando o programa.")
                    escreve_erros(e)
        else:
            self.mostrar_mensagem("Ultrapassou o máximo de tentativas.")

    def mostrar_mensagem(self, mensagem):
        print(mensagem)
        if self.verboso:
            try:
                self.telegram.sendMessage(self.verboso, mensagem)
            except Exception as e:
                print("Tentando se reconectar ao telegram...")
                try:
                    import amanobot
                    self.telegram = amanobot.Bot("1354635217:AAG1EbTt772cwPh008Ud3uBqyxyS28LXZao")
                    self.telegram.sendMessage(self.verboso, mensagem)
                except Exception as e:
                    print(type(e), e)

    def operar(self, valor, par, ordem, payout, tipo):
        '''
        Faz a operação e a depender da configuração faz:
        Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
        '''
        resultado = None
        for i in range(2):
            try:
                resultado, lucro = self.ordem(
                    par, ordem, self.tempo, valor, tipo, 
                    self.cadeado, self.config['delay'])
                break
            except Exception as e:
                print(f"Ocorreu um erro na operação:\n {type(e)}: {e}")
                self.conectar()
        if resultado == None:
            raise ConnectionAbortedError(
                "Não estou conseguindo fazer as operações, reinicie o bot.")
        
        if resultado == "win" and self.config['soros']:
            if self.soros_atual < self.max_gale:
                with self.cadeado:
                    novo = (valor + lucro if self.config["percent_soros"] == 0 
                        else valor + valor * self.config["percent_soros"] / 100)
                    print(f"\n [SOROS] : {round(valor, 2)} -> {round(novo, 2)}")
                    self.valor = novo
                    self.soros_atual += 1
            else:
                self.soros_atual = 0
                print(f" [SOROS] Preservando capital: R$ {valor} -> R$ {self.valor_inicial}")
                self.valor = self.valor_inicial
        
        if resultado == "loose":
            if self.config['soros']:
                self.soros_atual = 0
                print(f" [SOROS] Preservando capital: R$ {valor} -> R$ {self.valor_inicial}")
                self.valor = self.valor_inicial
            
            perda = 0
            num_gales = 0
            while (self.config['goal'] > self.ganho_total):
                with self.cadeado:
                    if lucro < 0: # Sorosgale tem win
                        self.ganho_total -= round(abs(lucro), 2)
                        self.perda_total -= round(abs(lucro), 2)
                    self.mostrar_mensagem(
                    f"\n | {round(self.ganho_total/self.config['goal'] * 100, 2)}% perto do objetivo |\
    {round(-self.perda_total/self.config['stoploss'] * 100, 2)}% perto do stoploss |\n")
        
                # self.esperar_anteriores(threading.currentThread().name)
                # threading.currentThread().setName(str(time.time()))

                if self.perda_total <= -(self.config['stoploss']):
                    self.mostrar_mensagem(f"BATEU NO STOPLOSS: R$ {round(self.perda_total, 2)}!")
                    sys.exit(0)

                if lucro < 0:
                    perda += abs(lucro)
                else:
                    perda -= lucro

                if self.config['tipo_gale'] == "martin":
                    print(f"\n [MARTINGALE] do tipo {self.config['tipo_martin']} na operação {par}|{ordem}")
                        
                    lucro = (self.valor * payout if self.config["tipo_martin"] != "porcento" 
                            else self.config["percent_martin"] / 100)
                    valor = self.martingale(self.config['tipo_martin'], 
                        payout, perda, valor, lucro)
                else:
                    # Sorosgale
                    if lucro < 0:
                        valor = perda / 2
                    else:
                        valor += lucro
                valor = 1 if valor < 1 else valor # Caso der doji ou divisão < 2

                resultado, lucro = self.ordem(
                    par, ordem, self.tempo, valor, tipo, 
                    self.cadeado, self.config['delay'])
                
                num_gales += 1
                if self.config['tipo_gale'] == "martin" and (
                    self.max_gale > num_gales or lucro >= 0):
                    break
                elif self.config['tipo_gale'] != "martin" and (
                    resultado == "win" and (perda - lucro) <= 0):
                        break

        if resultado not in ["error", "equal"]:
            with self.cadeado:
                if resultado == "win":
                    self.ganho_total += round(lucro, 2)
                else:
                    self.ganho_total -= round(abs(lucro), 2)
                    self.perda_total -= round(abs(lucro), 2)
                
            self.mostrar_mensagem(
                f"\n | {round(self.ganho_total/self.config['goal'] * 100, 2)}% perto do objetivo |\
 {round(-self.perda_total/self.config['stoploss'] * 100, 2)}% perto do stoploss |\n")

        elif resultado == "error":
            print(f"\nErro na operação às {str(datetime.utcnow())[:-7]}")

    def computar(self):
        '''
        1 - Percorre todos os comandos.
        2 - Pausa o script até a próxima hora:min
        3 - Calcula o payout da paridade
        4 - Cria uma thread para o método operar
        '''
        self.espera = []

        if self.tipo == "auto":
            ultima_vez = time.time()
            paridades = []
            for par in self.comandos:
                paridade = par['par']
                paridade = paridade + "-OTC" if self.config['otc'] else paridade
                paridades.append(paridade)
            payouts = self.aberta_profit(self.tempo, paridades)

            def atualizar_profits(comando):
                '''
                Atualiza os payouts do comando em diante.
                '''
                paridades = []
                for par in self.comandos[self.comandos.index(comando):]:
                    paridade = par['par']
                    paridade = paridade + "-OTC" if self.config['otc'] else paridade
                    paridades.append(paridade)
                novo = self.aberta_profit(self.tempo, paridades)
                if novo == None:
                    raise ConnectionAbortedError("Não estou conseguindo pegar as paridades. Reinicie o bot")
                payouts.update(novo)

        self.mostrar_mensagem("Conectado com sucesso.")
        for comando in self.comandos:
            
            data = comando["data"]
            horas, minutos = comando["hora"]
            segundos = 0
            if self.esperarAte(horas, minutos, segundos, data, self.config['correcao'] + 1, True):

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
                        print(f"\n [...] A paridade {par} está fechada no timeframe M{self.tempo} [...]\n")
                        continue
                else:
                    payout = self.payout_binaria(par) / 100 if self.tipo == "binary" else self.payout_digital(par) / 100
                    tipo = self.tipo

                if self.config['tendencia'] and not self.calcular_tendencia(
                    self.config['tipo_tendencia'], par, ordem, self.tempo, 
                    self.config['periodo_tendencia'], self.config['desvio_tendecia']
                ):
                    self.mostrar_mensagem(f"[ ❗️] {par}|{ordem} às {horas}:{minutos} entrou contra a tendência. [ ❗️]")
                    continue
                
                # self.esperar_anteriores()

                with self.cadeado:
                    if -self.config['stoploss'] >= self.perda_total or self.ganho_total >= self.config['goal']:
                        self.mostrar_mensagem(f'''{"- " * 20}
    Stopwin: {self.config['goal']}
    Total ganho: {round(self.ganho_total, 2)}
    Stoploss: {-self.config['stoploss']}
    Total perdido: {round(self.perda_total, 2)}''')
                        break

                if self.config["minimo"] / 100 <= payout:
                    thread = threading.Thread(
                        target = self.operar, 
                        name = f"{time.time()}", 
                        args = (valor, par, ordem, payout, tipo)
                        )
                    self.espera.append(thread)
                    thread.start()

                if self.tipo == "auto":
                    if time.time() - ultima_vez > 900:
                        threading.Thread(
                        target = atualizar_profits,
                        args = (comando,)
                        ).start()
            else:
                momento = datetime.utcnow().timestamp() - 10800 # -3Horas
                print(f" - {datetime.fromtimestamp(momento).strftime('dia %d - %H:%M')} | {comando['par']} - {horas}:{minutos} passou da hora - ")
        for thread in self.espera:
            thread.join()

        self.mostrar_mensagem(f"\nFim da operação resultado final: R$ {round(self.ganho_total, 2)}\n")
        
        try:
            if self.tipo == "auto":
                for comando in self.comandos:
                    par = comando["par"]
                    par += "-OTC" if self.config["otc"] else ""
                    self.API.unsubscribe_strike_list(par, self.config["tempo"])
        except:
            pass
    
    def esperar_anteriores(self, atual = 0):
        esperar_anteriores = True

        while esperar_anteriores:
            esperar_anteriores = False
            ativos = [
                datetime.fromtimestamp(float(x.name)) for x in threading.enumerate() if self.istime(x.name) and x.name != atual]
            for timing in ativos:
                momento_atual = datetime.fromtimestamp(time.time())
                anteriores = (atual == 0 or datetime.fromtimestamp(float(atual)) > timing)

                perto_de_terminar = (self.tempo * 60 + 30 >= 
                                 (momento_atual - timing).seconds >= 
                                 self.tempo * 60 - 30)
                if anteriores and perto_de_terminar:
                    time.sleep(1)
                    print("Esperando as operações anteriores acabar...")
                    esperar_anteriores = True
                    break

    def istime(self, string):
        try:
            float(string)
            return True
        except:
            return False