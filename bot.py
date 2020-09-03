from utils.operar import Operacao, escreve_erros, IQ_API
from configparser import RawConfigParser
from sys import argv
import re, logging, json, datetime

if argv[1:] and argv[1] == "-o":
    from database import MongoDB

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
        "ordem": ordem,
        "timeframe": int
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
        par = re.search(
        r'[A-Za-z]{6}(-OTC)?', texto.upper().replace("/", ""))[0]
        ordem = re.search(r'CALL|PUT', texto.upper())[0].lower()
        timeframe = re.search(
            r'[MH][1-6]?[0-5]', texto.upper())
        if timeframe: 
            if "M" in timeframe[0]: 
                timeframe = int(timeframe[0].strip("M"))
            else: 
                timeframe = int(timeframe[0].strip("H")) * 60
        else: timeframe = 0
    except Exception as e:
        print(type(e), e)
        print(f"Revise o comando {texto}")
        return {}

    comando = {
        "data": data,
        "hora": hora,
        "par": par,
        "ordem": ordem,
        "timeframe": timeframe
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
            if comando != {}:
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
        "goal": float(
            arquivo.get("WIN", "goal").replace(",", ".")),
        "soros": arquivo.get(
            "WIN", "soros").capitalize() == "True",
        "max_soros": arquivo.get(
            "WIN", "max_soros").capitalize() == "True",
        "percent_soros": float(arquivo.get(
            "WIN", "percent_soros").replace(",", ".")),
        "stoploss": float(
            arquivo.get("LOSS", "stoploss").replace(",", ".")),
        "tipo_gale": arquivo.get("LOSS", "tipo_gale").lower(),
        "tipo_martin": arquivo.get("LOSS", "tipo_martin").lower(),
        "max_gale": int(arquivo.get("LOSS", "max_gale")),
        "percent_martin": float(arquivo.get(
            "LOSS", "percent_martin").replace(",", ".")),
        "arquivo": arquivo.get("ENTRADAS", "arquivo"),
        "valor": float(
            arquivo.get("ENTRADAS", "valor").replace(",", ".")),
        "tipo_par": arquivo.get("ENTRADAS", "tipo_par").lower(),
        "tempo": int(arquivo.get("ENTRADAS", "tempo")),
        "minimo": int(arquivo.get("ENTRADAS", "profit_minimo")),
        "correcao": int(
            arquivo.get("AJUSTES", "correcao_entrada")),
        "delay": arquivo.get(
            "AJUSTES", "delay").replace(",", "."),
        "tendencia": arquivo.get(
            "TENDENCIA", "tendencia").capitalize() == "True",
        "tipo_tendencia": arquivo.get(
            "TENDENCIA", "tipo_tendencia"),
        "periodo_tendencia": int(arquivo.get(
            "TENDENCIA", "periodo_tendencia")),
        "desvio_tendencia": float(arquivo.get(
            "TENDENCIA", "desvio_tendencia").replace(",", ".")),
        "noticias": arquivo.get(
            "NOTICIAS", "noticias").capitalize() == "True",
        "noticias_hora": int(arquivo.get(
            "NOTICIAS", "noticias_hora")),
        "noticias_minuto": int(arquivo.get(
            "NOTICIAS", "noticias_minuto"))
    }

    # Caso colocar um float pra multiplicar
    config["tipo_martin"] = config["tipo_martin"] if not numerico(
        config['tipo_martin'].replace(",", ".")
    ) else float(config['tipo_martin'].replace(",", "."))

    # No caso queira pegar o resultado no histórico
    config['delay'] = float(config['delay']
        ) if numerico(config['delay']) else False

    return config

def ver_gales(perdaInicial, taxa):
    '''
    Mostra na tela os tipos de martingale até a 10° perda
    '''
    tipos = ["SIMPLES", "LEVE", "AGRESSIVO", "SEGURO", "PORCENTO", "PESSOAL"]
    for tipo in tipos:
        print(tipo, "\n")
        if tipo == "PORCENTO":
            lucro = float(input("Porcentagem encima da perda [0 - 1]: "))
        elif tipo == "PESSOAL":
            tipo = float(input("Digite o fator multiplicativo: "))
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
        if comandos[0] in ["-t", "teste"]:
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
        elif comandos[0] in ["-m", "martin"]:
            perdaInicial = float(input("Digite a perda inicial: "))
            taxa = float(input("Digite a taxa (profit) [0 - 1]: "))
            ver_gales(perdaInicial, taxa)
        elif comandos[0] in ['-c', 'config'] and len(comandos[0:]) != 1:
            config = configuracoes(comandos[1])
            comandos = abrir_arquivo(config["arquivo"])
            Operacao(config, comandos)
        elif comandos[0] in ["-h", "ajuda"]:
            with open(LOCALAJUDA, "r+") as file:
                for i in file:
                    print(i.strip())
        elif comandos[0] in ["-p", "perfil"]:
            config = configuracoes()
            api = IQ_API(config["email"], config["senha"])
            api.perfil()
            return api
        elif comandos[0] in ['-o', 'online'] and len(comandos[0:]) > 3:
            # Carrega o arquivo de configurações a partir do e-mail
            config = MongoDB.get_user(comandos[1])
            config['senha'] = comandos[2]
  
            # Define o arquivo de entradas a partir do gale máximo/própria
            if config['tipo_lista'] == "casa":
                # Une com as informações gerais
                config.update(MongoDB.get_avancadas())
                entradas = MongoDB.get_entradas(int(config['max_gale']))
            else:
                entradas = config['lista']
            Operacao(config, entradas, 0, comandos[3])
        else:
            print('''
            [COMANDOS]
            Ajuda: -h
            Testar a leitura do arquivo/configuração: -t
            Rodar o bot a partir de uma configuração: -c nomeDoArquivo
            Verificar tipos de martingale: -m
            Loga na conta e devolve a API: -p
            Para telegram: -o email senha
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
            try: # Dizer que terminou
                email = argv[2]
                dados = MongoDB.get_user(email)
                dados["operando"] = False
                MongoDB.modifica_usuario(dados, email)
            except Exception as e:
                print(e)
                input()
