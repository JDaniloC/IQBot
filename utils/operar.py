from datetime import datetime
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

    def __init__(self, config, comandos, maximo = 0, verboso = False):
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

                self.valor = config['valor']
                self.tempo = config['tempo']
                self.max_gale = config["max_gale"]

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
                print(e)

    def operar(self, valor, par, ordem, payout, tipo):
        '''
        Faz a operação e a depender da configuração faz:
        Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
        '''
        resultado = None
        for i in range(2):
            try:
                resultado, lucro = self.ordem(par, ordem, self.tempo, valor,    tipo, self.cadeado, self.config['delay'])
                break
            except Exception as e:
                print(f"Ocorreu um erro na operação:\n {type(e)}: {e}")
                self.conectar()
        if resultado == None:
            raise ConnectionAbortedError("Não estou conseguindo fazer as operações, reinicie o bot.")
        perda = 0
        if resultado == "win" and self.config['soros']:
            with self.cadeado:
                novo = self.valor + lucro if self.config["percent_soros"] == 0 else self.valor + self.valor * self.config["percent_soros"] / 100
                print(f"\n [SOROS GALE] : {round(self.valor, 2)} -> {round(novo, 2)}")
                self.valor = novo
        if resultado == "loose" and self.config['martin'] and self.perda_total - round(abs(lucro), 2) > -(self.config['stoploss']):
            num_gales = 0
            print(f"\n [MARTIN GALE] do tipo {self.config['tipo_gale']} na operação {par}|{ordem}")
            while (
                resultado == "loose" and 
                self.max_gale > num_gales and 
                self.config['goal'] > self.ganho_total):
                
                with self.cadeado:
                    self.ganho_total -= round(abs(lucro), 2)
                    self.perda_total -= round(abs(lucro), 2)
                    self.mostrar_mensagem(
                        f"\n | {round(self.ganho_total/self.config['goal'] * 100, 2)}% perto do objetivo |\
 {round(-self.perda_total/self.config['stoploss'] * 100, 2)}% perto do stoploss |\n")
                if self.perda_total <= -(self.config['stoploss']):
                    self.mostrar_mensagem(f"MARTINGALE CANCELADO: BATEU NO STOPLOSS: {self.perda_total}!")
                    sys.exit(0)

                perda += abs(lucro)
                lucro = self.valor * payout if self.config["tipo_gale"] != "porcento" else self.config["percent_martin"] / 100
                valor = self.martingale(self.config['tipo_gale'], payout, perda, valor, lucro)
                valor = 1 if valor < 1 else valor # Caso der doji

                resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo, self.cadeado, self.config['delay'])
                num_gales += 1
        elif resultado == "loose":
            self.perda_total -= round(abs(lucro), 2)
            self.ganho_total -= round(abs(lucro), 2)

        if resultado not in ["error", "equal"]:
            with self.cadeado:
                if resultado == "win":
                    self.ganho_total += round(lucro, 2)
                elif not self.config["martin"]:
                    self.ganho_total -= round(abs(lucro), 2)
                    self.perda_total -= round(abs(lucro), 2)
                
            self.mostrar_mensagem(
                f"\n | {round(self.ganho_total/self.config['goal'] * 100, 2)}% perto do objetivo |\
 {round(-self.perda_total/self.config['stoploss'] * 100, 2)}% perto do stoploss |\n")

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
            paridades = []
            for par in self.comandos:
                paridade = par['par']
                paridade = paridade + "-OTC" if self.config['otc'] else paridade
                paridades.append(paridade)
            for par in paridades:
                try:
                    self.API.subscribe_strike_list(par, self.tempo)
                except KeyError:
                    print(f"Remova a paridade {par} da lista.")
            payouts = self.aberta_profit(paridades, self.tempo)

            def atualizar_profits(comando):
                '''
                Atualiza os payouts do comando em diante.
                '''
                print("Atualizando profits...")
                paridades = []
                for par in self.comandos[self.comandos.index(comando):]:
                    paridade = par['par']
                    paridade = paridade + "-OTC" if self.config['otc'] else paridade
                    paridades.append(paridade)
                novo = self.aberta_profit(paridades, self.tempo)
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
                        print(f"{par} não está disponível nem binária nem digital na modalidade M{self.tempo}")
                        continue
                else:
                    payout = self.payout_binaria(par) / 100 if self.tipo == "binary" else self.payout_digital(par) / 100
                    tipo = self.tipo

                with self.cadeado:
                    if -self.config['stoploss'] >= self.perda_total or self.ganho_total >= self.config['goal']:
                        self.mostrar_mensagem(f'''
        Stopwin: {self.config['goal']}
    Total ganho: {self.ganho_total}
    Stoploss: {-self.config['stoploss']}
    Total perdido: {self.perda_total}''')
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
                print(f"UTC-3: {datetime.fromtimestamp(momento).strftime('dia %d - %H:%M')} | {comando['par']} - {horas}:{minutos} passou da hora.")
        for thread in espera:
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