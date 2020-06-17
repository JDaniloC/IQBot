from IQ import IQ_API
from configparser import RawConfigParser
from sys import argv
from datetime import datetime
import re, threading, traceback

print("\n[Comando para parar: Ctrl + C]\n")

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
  ____          _           _                                _             _             
 / ___|   ___  (_)  __ _   | |__    ___  _ __ ___    __   __(_) _ __    __| |  ___       
 \___ \  / _ \ | | / _` |  | '_ \  / _ \| '_ ` _ \   \ \ / /| || '_ \  / _` | / _ \      
  ___) ||  __/ | || (_| |  | |_) ||  __/| | | | | |   \ V / | || | | || (_| || (_) |     
 |____/  \___|_/ | \__,_|  |_.__/  \___||_| |_| |_|    \_/  |_||_| |_| \__,_| \___/      
             |__/                                                                        
                  ____         _               __  __     __  __       ___    ___  _____ 
   __ _   ___    |  _ \  ___  | |__    ___    |  \/  |   |  \/  |     / _ \  / _ \|___  |
  / _` | / _ \   | |_) |/ _ \ | '_ \  / _ \   | |\/| |   | |\/| |    | | | || | | |  / / 
 | (_| || (_) |  |  _ <| (_) || |_) || (_) |  | |  | | _ | |  | |    | |_| || |_| | / /  
  \__,_| \___/   |_| \_\\\\___/ |_.__/  \___/   |_|  |_|(_)|_|  |_|_____\___/  \___/ /_/   
                                                                |_____|                  
''')

    def __init__(self, config, comandos):
        self.cadeado = threading.Lock()

        self.config = config
        self.comandos = comandos
        self.total = 0

        try:
            super().__init__(config['email'], config['senha'])
            
            print(self.logo, flush = True)
            print(self.welcome, flush = True)

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
            print("Aconteceu na API, tente novamente.")
            print("Se o erro persistir, chame o técnico.")
            
            linhas = " -> ".join(re.findall(r'line \d+', str(traceback.extract_tb(e.__traceback__))))
            with open("errors.log", "a") as file:
                file.write(f"{type(e)} - {e}:\n{linhas}\n")

    def operar(self, valor, par, ordem, payout, tipo):
        '''
        Faz a operação e a depender da configuração faz:
        Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
        '''
        resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo, self.cadeado)
        perda = 0
        if resultado == "win" and self.config['soros']:
            print(f"\n [SOROS GALE] : {self.valor} -> {self.valor + lucro}")
            self.valor += lucro
        if resultado == "loose" and self.config['martin']:
            num_gales = 0
            print(f"\n [MARTIN GALE] do tipo {self.config['tipo_gale']} na operação {par}|{ordem}")
            while resultado != "win" and -(self.total - perda) < self.config['stoploss'] and self.max_gale > num_gales and self.config['goal'] > self.total:
                perda += abs(lucro)
                valor = self.martingale(self.config['tipo_gale'], payout, perda, valor, self.valor * payout)
                resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo, self.cadeado)
                num_gales += 1
        
        if resultado not in ["error", "equal"]:
            with self.cadeado:
                if resultado == "win":
                    self.total += round(lucro, 2) - perda
                else:
                    self.total -= round(perda, 2)
                
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

        for comando in self.comandos:
            
            data = comando["data"]
            horas, minutos = comando["hora"]
            if self.config['correcao'] != 0:
                novo = datetime.fromtimestamp(datetime(*data[::-1] + [horas, minutos]).timestamp() - self.config["correcao"])
                horas, minutos, segundos = novo.hour, novo.minute, novo.second 
            else:
                segundos = 0
            if self.esperarAte(horas, minutos, segundos, data):
                if not (-self.config['stoploss'] < self.total < self.config['goal']):
                    break

                binarias = self.abertas("binary") if self.tipo == "auto" else {}
                digitais = self.abertas() if self.tipo == "auto" else {}

                par = comando['par']
                par += "-OTC" if self.config["otc"] else ""
                ordem = comando['ordem']
                valor = self.valor
                
                if self.tipo == "auto":
                    if (binarias.get(par) and digitais.get(par)) and (binarias[par] < digitais[par]):
                        tipo = "digital"
                        payout = digitais[par] / 100
                    elif binarias.get(par):
                        tipo = "binary"
                        payout = binarias.get(par) / 100
                    else:
                        tipo = "digital"
                        payout = digitais[par] / 100
                else:
                    payout = self.payout_binaria(par) / 100 if self.tipo == "binary" else self.payout_digital(par) / 100
                    tipo = self.tipo
                
                if self.config["minimo"] / 100 <= payout:
                    thread = threading.Thread(
                        target = self.operar, 
                        name = f"{horas}:{minutos}", 
                        args = (valor, par, ordem, payout, tipo)
                        )
                    espera.append(thread)
                    thread.start()
                        
        for thread in espera:
            thread.join()

        print(f"\nFim da operação resultado final: {round(self.total, 2)}\n")

def pegar_comando(texto):
    '''
    Recebe um texto e devolve a hora/par/ordem em forma de dicionário
    '''
    try:
        data = re.search(r'\d{2}\W\d{2}\W\d{4}', texto)[0]
        data = [int(x) for x in re.split(r"\W", data)]
        hora = re.search(r'\d{2}:\d{2}', texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]
        par = re.search(r'\w{6}', texto)[0]
        ordem = re.search(r'CALL|PUT|call|put', texto)[0].lower()
    except:
        print("Ocorreu um erro no arquivo de entradas, revise-as por favor.")
        data = [1, 1, 2000]
        hora = [00, 00]
        par = "EURUSD"
        ordem = "PUT"
    
    comando = {
        "data": data,
        "hora": hora,
        "par": par,
        "ordem": ordem
    }

    return comando

def abrir_arquivo(nome):
    '''
    Abre o arquivo entradas.txt.
    Usa a função pegar_comando em cada comando
    E devolve uma lista de cada um deles
    '''
    nome = re.sub(r'.txt', "", nome)
    with open(nome + ".txt") as file:
        entradas = file.readlines()
    
    comandos = []
    for entrada in entradas:
        if entrada not in ['', '\n']:
            comando = pegar_comando(entrada)
            comandos.append(comando)
    return comandos

def configuracoes(nome = None):
    '''
    Carrega o arquivo de configuração e devolve um dicionário
    '''
    if nome == None: nome = "config.txt"
    arquivo = RawConfigParser()
    arquivo.read(nome)
 
    config = {
        "email": arquivo.get("CONTA", "email"),
        "senha": arquivo.get("CONTA", "senha"),
        "tipo_conta": arquivo.get("CONTA", "tipo").lower(),
        "goal": float(arquivo.get("WIN", "goal").replace(",", ".")),
        "soros": arquivo.get("WIN", "soros").capitalize() == "True",
        "stoploss": float(arquivo.get("LOSS", "stoploss").replace(",", ".")),
        "martin": arquivo.get("LOSS", "martin").capitalize() == "True",
        "tipo_gale": arquivo.get("LOSS", "tipo_gale").lower(),
        "max_gale": int(arquivo.get("LOSS", "max_gale")),
        "arquivo": arquivo.get("ENTRADAS", "arquivo"),
        "valor": float(arquivo.get("ENTRADAS", "valor").replace(",", ".")),
        "tipo_par": arquivo.get("ENTRADAS", "tipo_par").lower(),
        "tempo": int(arquivo.get("ENTRADAS", "tempo")),
        "minimo": int(arquivo.get("ENTRADAS", "profit_minimo")),
        "correcao": int(arquivo.get("ENTRADAS", "correcao_entrada")),
        "otc": arquivo.get("ENTRADAS", "otc").capitalize() == "True"
    }

    return config

def ver_gales(perdaInicial, taxa):
    '''
    Mostra na tela os tipos de martingale até a 10° perda
    '''
    tipos = ["SIMPLES", "LEVE", "AGRESSIVO", "SEGURO"]
    for tipo in tipos:
        print(tipo, "\n")
        perda = perdaInicial
        valor = perdaInicial
        for j in range(10):
            valor = IQ_API.martingale(tipo, taxa, perda, valor, perdaInicial//taxa)
            print(f"Perdeu {round(perda, 2)} vai investir {round(valor, 2)} se ganhar {round(valor * taxa, 2)} onde o lucro vai ser {round(valor * taxa - perda, 2)}")
            perda += valor
        print()

def recebe_comandos(comandos):
    '''
    Recebe os comandos do terminal e computa algum resultado
    Se nenhum comando for passado:
        1 - Carrega as informações
        2 - Segue a operação do entradas.txt
    '''
    if comandos != []:
        for i in range(len(comandos)):
            if comandos[i] in ["-t", "teste"]:
                config = configuracoes()
                for key, value in config.items():
                    print(key, value)
                
                print()
                
                operacoes = abrir_arquivo(config["arquivo"])
                for operacao in operacoes:
                    data = "/".join([str(x) for x in operacao['data']])
                    hora = ":".join([str(x) for x in operacao['hora']])
                    print(f"Data: {data}\nHora: {hora}\nParidade: {operacao['par']}\nOrdem: {operacao['ordem']}")
                
                return config
            elif comandos[i] in ["-m", "martin"]:
                perdaInicial = float(input("Digite a perda inicial: "))
                taxa = float(input("Digite a taxa (profit) [0 - 1]: "))
                ver_gales(perdaInicial, taxa)
            elif comandos[i] in ['-c', 'config'] and len(comandos[i:]) != 1:
                config = configuracoes(comandos[i+1])
                comandos = abrir_arquivo(config["arquivo"])
                Operacao(config, comandos)
            elif comandos[i] in ["-h", "ajuda"]:
                with open("ajuda.txt", "r+") as file:
                    for i in file:
                        print(i.strip())
            elif comandos[i] in ["-p", "perfil"]:
                config = configuracoes()
                api = IQ_API(config["email"], config["senha"])
                api.perfil()
                return api
            elif (i != 0 and comandos[i-1] not in ["-o", "-m", "-c", "-h", "-p"]) or i == 0:
                print('''
                [COMANDOS]
                Ajuda: -h
                Testar a leitura do arquivo/configuração: -t
                Rodar o bot a partir de uma configuração: -c nomeDoArquivo
                Verificar tipos de martingale: -m
                ''')
    else:
        config = configuracoes()
        comandos = abrir_arquivo(config["arquivo"])
        Operacao(config, comandos)
        
if __name__ == "__main__":
    try:
        result = recebe_comandos(argv[1:])
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        print("\nAconteceu um erro, tente novamente.")
        print("Se o erro persistir, chame o técnico.")
		
        linhas = " -> ".join(re.findall(r'line \d+', str(traceback.extract_tb(e.__traceback__))))
        with open("errors.log", "a") as file:
            file.write(f"{type(e)} - {e}:\n{linhas}\n")
    finally:
        input("\nDigite Enter para sair")