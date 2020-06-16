from IQ import IQ_API
from configparser import RawConfigParser
from sys import argv
import re, threading, traceback

print("\n[Comando para parar: Ctrl + C]\n")

class Operacao(IQ_API):
    def __init__(self, config, comandos):
        self.cadeado = threading._allocate_lock()

        self.config = config
        self.comandos = comandos
        self.ganhoTotal = 0
        self.perdaTotal= 0

        try:
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

            self.computar()
        except Exception as e:
            print("Aconteceu um erro, tente novamente.")
            print("Se o erro persistir, chame o técnico.")
            with open("errors.log", "a") as file:
                file.write(f"{type(e)} - {e}\n")

    def operar(self, par, ordem, payout, tipo):
        '''
        Faz a operação e a depender da configuração faz:
        Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
        '''
        
        resultado, lucro = self.ordem(par, ordem, self.tempo, self.valor, tipo)
        if resultado == "win" and self.config['soros']:
            print(f"\n [SOROS GALE] : {self.valor} -> {self.valor + lucro}")
            self.valor += lucro # Mudar a soros
        if resultado == "loose" and self.config['martin']:
            with self.cadeado:
                valor = self.valor
            perda = 0
            print(f"[MARTIN GALE] do tipo {self.config['tipo_gale']} na operação {par}|{ordem}")
            while resultado != "win" and perda < self.config['stoploss']:
                perda += abs(lucro)
                valor = self.martingale(self.config['tipo_gale'], payout, perda, valor, self.valor / payout)
                resultado, lucro = self.ordem(par, ordem, self.tempo, valor, tipo)
            lucro = perda if resultado == 'loose' else 0
        if resultado not in ["error", "equal"]:
            if resultado == "win":
                self.ganhoTotal += lucro
                self.perdaTotal -= lucro
                self.perdaTotal = 0 if self.perdaTotal < 0 else self.perdaTotal
            elif resultado == "loose":
                self.perdaTotal += lucro
                self.ganhoTotal -= lucro
                self.ganhoTotal = 0 if self.ganhoTotal < 0 else self.ganhoTotal
            
            print(f"\n | {round(self.ganhoTotal/self.config['goal'] * 100, 2)}% perto do objetivo | {round(self.perdaTotal/self.config['stoploss'] * 100, 2)} perto do stoploss |\n")
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

            binarias = self.abertas("binary") if self.tipo == "auto" else {}
            digitais = self.abertas() if self.tipo == "auto" else {}

            horas, minutos = comando["hora"]
            if self.config['correcao'] != 0:
                if minutos == 0:
                    horas -= 1
                    minutos = 59
                else:
                    minutos -= 1
                segundos = 60 - self.config['correcao']
            else:
                segundos = 0
            if self.esperarAte(horas, minutos, segundos):

                par = comando['par']
                par += "-OTC" if self.config["otc"] else ""
                ordem = comando['ordem']
                
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
                    thread = threading.Thread(target = self.operar, name = f"{horas}:{minutos}", args = (par, ordem, payout, tipo))
                    espera.append(thread)
                    thread.start()

                if self.perdaTotal >= self.config['stoploss'] or self.ganhoTotal >= self.config['goal']:
                    break
        
        for thread in espera:
            thread.join()

        print(f"\nFim da operação ganho total: {self.ganhoTotal}\nPerda total {self.perdaTotal}")

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

def pegar_comando(texto):
    '''
    Recebe um texto e devolve a hora/par/ordem em forma de dicionário
    '''
    # data = re.search(r'\d{2}\W\d{2}\W\d{4}', texto)
    hora = re.search(r'\d{2}:\d{2}', texto)[0]
    hora = [int(x) for x in re.split(r'\W', hora)]
    par = re.search(r'\w{6}', texto)[0]
    ordem = re.search(r'CALL|PUT|call|put', texto)[0].lower()

    comando = {
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
        if entrada != '':
            comando = pegar_comando(entrada)
            comandos.append(comando)
    return comandos

def configuracoes():
    '''
    Carrega o arquivo de configuração e devolve um dicionário
    '''
    arquivo = RawConfigParser()
    arquivo.read("config.txt")

    config = {
        "email": arquivo.get("CONTA", "email"),
        "senha": arquivo.get("CONTA", "senha"),
        "tipo_conta": arquivo.get("CONTA", "tipo").lower(),
        "goal": float(arquivo.get("WIN", "goal")),
        "soros": arquivo.get("WIN", "soros").capitalize() == "True",
        "stoploss": float(arquivo.get("LOSS", "stoploss")),
        "martin": arquivo.get("LOSS", "martin").capitalize() == "True",
        "tipo_gale": arquivo.get("LOSS", "tipo_gale").lower(),
        "arquivo": arquivo.get("ENTRADAS", "arquivo"),
        "valor": float(arquivo.get("ENTRADAS", "valor").capitalize()),
        "tipo_par": arquivo.get("ENTRADAS", "tipo_par").lower(),
        "tempo": int(arquivo.get("ENTRADAS", "tempo")),
        "minimo": int(arquivo.get("ENTRADAS", "profit_minimo")),
        "correcao": int(arquivo.get("ENTRADAS", "correcao_entrada")),
        "otc": arquivo.get("ENTRADAS", "otc").capitalize() == "True"
    }

    return config

def recebe_comandos(comandos):
    '''
    Recebe os comandos do terminal e computa algum resultado
    Se nenhum comando for passado:
        1 - Carrega as informações
        2 - Segue a operação do entradas.txt
    '''
    if comandos != []:
        for i in range(len(comandos)):
            if comandos[i] in ["-o", "arquivo"] and comandos[i:] != []:
                comandos = abrir_arquivo(comandos[i+1])
                for comando in comandos:
                    hora = ":".join([str(x) for x in comando['hora']])
                    print(f"Hora: {hora}\nParidade: {comando['par']}\nOrdem: {comando['ordem']}")
            elif comandos[i] in ["-m", "martin"]:
                perdaInicial = float(input("Digite a perda inicial: "))
                taxa = float(input("Digite a taxa (profit) [0 - 1]: "))
                ver_gales(perdaInicial, taxa)
            elif comandos[i] in ['-c', 'config']:
                config = configuracoes()
                for key, value in config.items():
                    print(key, value)
                return config
            elif comandos[i] in ["-h", "ajuda"]:
                with open("ajuda.txt", "r+") as file:
                    for i in file:
                        print(i.strip())
            elif comandos[i] in ["-p", "perfil"]:
                config = configuracoes()
                api = IQ_API(config["email"], config["senha"])
                return api
            elif (i != 0 and comandos[i-1] not in ["-o", "-m", "-c", "-h", "-p"]) or i == 0:
                print('''
                [COMANDOS]
                Ajuda: -h
                Testar a leitura do arquivo: -o nomeDoArquivo
                Testar a leitura da configuração: -c
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
        input("Tecle Enter para sair")