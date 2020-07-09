from utils.operar import Operacao, escreve_erros, IQ_API
from configparser import RawConfigParser
from sys import argv
import re, logging, json, datetime

logging.disable(level = (logging.DEBUG))

LOCALAJUDA = "misc/ajuda.txt"
LOCALCONFIG = "config/config.txt"

print("\n[Comando para parar: Ctrl + C]\n")

def pegar_comando(texto):
    '''
    Recebe um texto e devolve:
    {
        "data": [dia, mes, ano],
        "hora": [hora, minuto]
        "par": par,
        "ordem": ordem
    }
    No qual o conteúdo das listas são inteiros
    '''
    try:
        data = re.search(r'\d{2}\W\d{2}\W\d{4}', texto)
        if data:
            data = [int(x) for x in re.split(r"\W", data[0])]
        else:
            hoje = datetime.datetime.now()
            data = [hoje.day, hoje.month, hoje.year]
        hora = re.search(r'\d{2}:\d{2}', texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]
        par = re.search(r'[A-Za-z]{6}', texto.replace("/", ""))[0]
        ordem = re.search(r'CALL|PUT|call|put', texto)[0].lower()
    except:
        print(f"Ocorreu um erro no arquivo de entradas, revise o comando {texto}")
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
    try:
        with open(nome + ".txt") as file:
            entradas = file.readlines()
    except:
        with open("config/" + nome + ".txt") as file:
            entradas = file.readlines()
    comandos = []
    for entrada in entradas:
        if entrada not in ['', '\n']:
            comando = pegar_comando(entrada)
            comandos.append(comando)
    return comandos

def numerico(x):
    '''
    Verifica se a string pode ser convertida para float
    '''
    try:
        float(x)
        return True
    except:
        return False

def configuracoes(nome = LOCALCONFIG):
    '''
    Carrega o arquivo de configuração e devolve um dicionário
    '''
    arquivo = RawConfigParser()
    arquivo.read(nome)
 
    config = {
        "email": arquivo.get("CONTA", "email"),
        "senha": arquivo.get("CONTA", "senha"),
        "tipo_conta": arquivo.get("CONTA", "tipo").lower(),
        "goal": float(arquivo.get("WIN", "goal").replace(",", ".")),
        "soros": arquivo.get("WIN", "soros").capitalize() == "True",
        "percent_soros": float(arquivo.get("WIN", "percent_soros").replace(",", ".")),
        "stoploss": float(arquivo.get("LOSS", "stoploss").replace(",", ".")),
        "martin": arquivo.get("LOSS", "martin").capitalize() == "True",
        "tipo_gale": arquivo.get("LOSS", "tipo_gale").lower(),
        "max_gale": int(arquivo.get("LOSS", "max_gale")),
        "percent_martin": float(arquivo.get("LOSS", "percent_martin").replace(",", ".")),
        "arquivo": arquivo.get("ENTRADAS", "arquivo"),
        "valor": float(arquivo.get("ENTRADAS", "valor").replace(",", ".")),
        "tipo_par": arquivo.get("ENTRADAS", "tipo_par").lower(),
        "tempo": int(arquivo.get("ENTRADAS", "tempo")),
        "minimo": int(arquivo.get("ENTRADAS", "profit_minimo")),
        "correcao": int(arquivo.get("ENTRADAS", "correcao_entrada")),
        "otc": arquivo.get("ENTRADAS", "otc").capitalize() == "True"
    }

    config["tipo_gale"] = config["tipo_gale"] if not numerico(config['tipo_gale'].replace(",", ".")) else float(config['tipo_gale'].replace(",", "."))

    return config

def ver_gales(perdaInicial, taxa):
    '''
    Mostra na tela os tipos de martingale até a 10° perda
    '''
    tipos = ["SIMPLES", "LEVE", "AGRESSIVO", "SEGURO", "PORCENTO"]
    for tipo in tipos:
        print(tipo, "\n")
        if tipo == "PORCENTO":
            lucro = float(input("Porcentagem encima da perda [0 - 1]: "))
        lucro = perdaInicial//taxa if tipo != "PORCENTO" else lucro
        perda = perdaInicial
        valor = perdaInicial
        for j in range(10):
            valor = IQ_API.martingale(tipo, taxa, perda, valor, lucro)
            print(f"Perdeu {round(perda, 2)} vai investir {round(valor, 2)} e vai ganhar {round(valor * taxa, 2)} onde o lucro vai ser {round(valor * taxa - perda, 2)}")
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
                
                operacoes = abrir_arquivo("config/entradas")
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
                with open(LOCALAJUDA, "r+") as file:
                    for i in file:
                        print(i.strip())
            elif comandos[i] in ["-p", "perfil"]:
                config = configuracoes()
                api = IQ_API(config["email"], config["senha"])
                api.perfil()
                return api
            elif comandos[i] in ['-o', 'online'] and len(comandos[i:]) != 2:
                from database import MongoDB
                # Carrega o arquivo de configurações a partir do e-mail
                config = MongoDB.get_user(comandos[i + 1])
                config['senha'] = comandos[i + 2]

                # Une com as informações gerais
                config.update(MongoDB.get_avancadas())
                
                # Define o arquivo de entradas a partir do gale máximo
                entradas = MongoDB.get_entradas(int(config['max_gale']))
                Operacao(config, entradas)
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
		
        escreve_erros(e)
    finally:
        if not argv[1:] or argv[1] != "-o":
            input("\nDigite Enter para sair")
        elif argv[1] == "-o":
            from database import MongoDB
            try: # Dizer que terminou
                dados = MongoDB.get_user(argv[2])
                dados["operando"] = False
                MongoDB.change_user(dados, argv[2])
            except Exception as e:
                print(e)
                input()