from IQ import IQ_API
from configparser import RawConfigParser
from sys import argv
import re, threading

print("\n[Comando para parar: Ctrl + C]\n")

def ver_gales(perdaInicial, taxa):
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
    arquivo = RawConfigParser()
    arquivo.read("config.txt")

    config = {
        "email": arquivo.get("CONTA", "email"),
        "senha": arquivo.get("CONTA", "senha"),
        "tipo_conta": arquivo.get("CONTA", "tipo"),
        "goal": float(arquivo.get("WIN", "goal")),
        "soros": bool(arquivo.get("WIN", "soros")),
        "stoploss": float(arquivo.get("LOSS", "stoploss")),
        "martin": bool(arquivo.get("LOSS", "martin")),
        "tipo_gale": arquivo.get("LOSS", "tipo_gale").lower(),
        "arquivo": arquivo.get("ENTRADAS", "arquivo"),
        "valor": float(arquivo.get("ENTRADAS", "valor")),
        "tipo_par": arquivo.get("ENTRADAS", "tipo_par").lower(),
        "tempo": int(arquivo.get("ENTRADAS", "tempo")),
        "minimo": int(arquivo.get("ENTRADAS", "profit_minimo")),
        "correcao": int(arquivo.get("ENTRADAS", "correcao_entrada")),
        "otc": bool(arquivo.get("ENTRADAS", "otc"))
    }

    return config

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

            self.tipo = "binary" if config['tipo_par'].lower() == 'binaria' else "digital"

            self.valor = config['valor']
            self.tempo = config['tempo']

            self.computar()
        except Exception as e:
            print("Aconteceu um erro, tente novamente.")
            print("Se o erro persistir, chame o técnico.")
            with open("errors.log", "a") as file:
                file.write(f"{type(e)} - {e}\n")

    def operar(self, par, ordem, payout):

        resultado, lucro = self.ordem(par, ordem, self.tempo, self.valor, self.tipo)
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
                resultado, lucro = self.ordem(par, ordem, self.tempo, valor, self.tipo)
            lucro = perda if resultado == 'loose' else 0
        if resultado not in ["error", "equal"]:
            with self.cadeado:
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
        espera = []

        for comando in self.comandos:

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
                
                payout = self.payout_binaria(par) / 100 if self.tipo == "binary" else self.payout_digital(par) / 100

                if self.config["minimo"] / 100 <= payout:
                    thread = threading.Thread(target = self.operar, name = f"{horas}:{minutos}", args = (par, ordem, payout))
                    espera.append(thread)
                    thread.start()

                if self.perdaTotal >= self.config['stoploss'] or self.ganhoTotal >= self.config['goal']:
                    break
        
        for thread in espera:
            thread.join()

        print(f"\nFim da operação ganho total: {self.ganhoTotal}\nPerda total {self.perdaTotal}")

def recebe_comandos(comandos):
    if comandos != []:
        for i in range(len(comandos)):
            if comandos[i] in ["-o", "arquivo"] and comandos[i:] != []:
                comandos = abrir_arquivo(comandos[i+1])
                for comando in comandos:
                    print(f"Hora: {comando['hora']}\nParidade: {comando['par']}\nOrdem: {comando['ordem']}")
            elif comandos[i] in ["-m", "martin"]:
                perdaInicial = float(input("Digite a perda inicial: "))
                taxa = float(input("Digite a taxa (profit) [0 - 1]: "))
                ver_gales(perdaInicial, taxa)
            elif comandos[i] in ['-c', 'config']:
                config = configuracoes()
                for key, value in config.items():
                    print(key, value)
            elif comandos[i] in ["-h", "ajuda"]:
                with open("ajuda.txt", "r+") as file:
                    for i in file:
                        print(i.strip())
            else:
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
        recebe_comandos(argv[1:])
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        print("Aconteceu um erro, tente novamente.")
        print("Se o erro persistir, chame o técnico.")
        with open("errors.log", "a") as file:
            file.write(f"{type(e)} - {e}\n")
api.ordem("AUDCAD-OTC", "put", 1, 2, "binary")