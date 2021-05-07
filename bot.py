from utils.operar import escreve_erros, IQ_API
from utils.estrategias import Estrategias
from configparser import RawConfigParser
from utils.lista_taxa import ListaTaxa
from datetime import datetime
from sys import argv, exit
import re, logging

if argv[1:] and argv[1] == "-o":
    from database import Mongo
    MongoDB = Mongo()

logging.disable(level = (logging.DEBUG))

LOCALAJUDA = "misc/ajuda.txt"
LOCALCONFIG = "config/config.txt"

print("\n[Comando para parar: Ctrl + C]\n")

def datetime_brazil():
    return datetime.fromtimestamp(
        datetime.utcnow().timestamp() - 10800)

def pegar_comando_lista(texto):
    '''
    Recebe um texto e devolve:
    {
        "data": [dia, mes, ano],
        "hora": [hora, minuto]
        "par": paridade,
        "ordem": ordem,
        "timeframe": int
        "tipo": "lista"
    }
    No qual o conteúdo das listas são inteiros
    '''
    def timestamp(data, hora):
        return datetime(
            data[2], data[1], data[0], hora[0], hora[1]
        ).timestamp()
    try:
        data = re.search(r'\d{2}\W\d{2}\W\d{4}', texto)
        if data:
            data = [int(x) for x in re.split(r"\W", data[0])]
        else:
            hoje = datetime_brazil()
            data = [hoje.day, hoje.month, hoje.year]
        hora = re.search(r'\d{2}:\d{2}', texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]
        par = re.search(r'[A-Za-z]{6}(-OTC)?', 
            texto.upper().replace("/", ""))[0]
        ordem = re.search(r'CALL|PUT', texto.upper())[0].lower()
        timeframe = re.search(
            r'[MH][1-6]?[0-5]', texto.upper())
        if timeframe: 
            if "M" in timeframe[0].upper(): 
                timeframe = int(timeframe[0].strip("M"))
            else: 
                timeframe = int(timeframe[0].strip("H")) * 60
        else: timeframe = 0
    except Exception as e:
        return {}

    return {
        "data": data,
        "hora": hora,
        "par": par,
        "ordem": ordem,
        "timeframe": timeframe,
        "tipo": "lista",
        "timestamp": timestamp(data, hora)
    }

def pegar_comando_taxas(texto):
    '''
    Recebe um texto e devolve:
    {
        "par": paridade,
        "taxa": int
        "tipo": "taxas"
    }
    '''
    try:
        primeiro, segundo = re.split(r"[^\w.-]", texto.strip())
        par = re.search(r'[A-Za-z]{6}(-OTC)?', 
            primeiro.upper().replace("/", ""))
        if not par:
            par = re.search(r'[A-Za-z]{6}(-OTC)?', 
                segundo.upper().replace("/", ""))[0]
            taxa = float(primeiro)
        else:
            par = par[0]
            taxa = float(segundo)
    except Exception as e:
        print(type(e), e)
        print(f"Revise o comando {texto}")
        return {}
        
    return {
        "par": par, 
        "taxa": taxa, 
        "tipo": "taxas",
        "timestamp": datetime_brazil()
    }

def pegar_comando(texto):
    '''
    Verifica se a entrada é de lista ou taxas
    e devolve um dicionário no qual um dos valores
    é {tipo: lista|taxa}.
    '''
    comando = pegar_comando_lista(texto)
    if comando == {}:
        comando = pegar_comando_taxas(texto)
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
    comandos.sort(key = lambda x: x["timestamp"])
    for entrada in comandos:
        del entrada["timestamp"]
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

def atualizar(config, arquivo, tipo, label, func = str, error = ""):
    try:
        valor = arquivo.get(tipo, label)
        if func == float: valor = valor.replace(",", ".")
        config[label] = func(valor)
    except: 
        config[label] = error

def configuracoes(nome = LOCALCONFIG):
    '''
    Carrega o arquivo de configuração e devolve um dicionário
    '''
    arquivo = RawConfigParser()
    arquivo.read(nome, encoding='utf-8')
 
    config = {}
    boolean = lambda x: x.capitalize() == "True"
    atualizar(config, arquivo, "CONTA", "email")
    atualizar(config, arquivo, "CONTA", "senha")
    atualizar(config, arquivo, "CONTA", "tipo_conta")

    atualizar(config, arquivo, "ENTRADAS", "arquivo")
    atualizar(config, arquivo, "ENTRADAS", "tipo_par")
    atualizar(config, arquivo, "ENTRADAS", "valor", float, 1)
    atualizar(config, arquivo, "ENTRADAS", "tempo", int, 1)
    atualizar(config, arquivo, "ENTRADAS", "minimo", int, 0)

    atualizar(config, arquivo, "WIN", "stopwin", float, 1)
    atualizar(config, arquivo, "WIN", "max_soros", int, 0)
    atualizar(config, arquivo, "WIN", "scalper_win", int, 0)

    atualizar(config, arquivo, "LOSS", "stoploss", float, 1)
    atualizar(config, arquivo, "LOSS", "max_gale", int, 2)
    atualizar(config, arquivo, "LOSS", "scalper_loss", int, 0)
    atualizar(config, arquivo, "LOSS", "tipo_gale", error = "martingale")
    atualizar(config, arquivo, "LOSS", "tipo_martin", error = "simples")
    atualizar(config, arquivo, "LOSS", "vez_gale", error = "vela")

    atualizar(config, arquivo, "AJUSTE", "correcao", int, 0)
    atualizar(config, arquivo, "AJUSTE", "delay", float, False)

    atualizar(config, arquivo, "TENDENCIA", "tendencia", boolean, False)
    atualizar(config, arquivo, "TENDENCIA", "tipo_tendencia", error = "sma")
    atualizar(config, arquivo, "TENDENCIA", "periodo_tendencia", int, 21)
    
    atualizar(config, arquivo, "NOTICIAS", "toros", int, 0)
    atualizar(config, arquivo, "NOTICIAS", "noticias_hora", int, 0)
    atualizar(config, arquivo, "NOTICIAS", "noticias_minuto", int, 0)

    atualizar(config, arquivo, "ESTRATEGIA", "auto", boolean, False)
    atualizar(config, arquivo, "ESTRATEGIA", "autotime", int, 1)
    atualizar(config, arquivo, "ESTRATEGIA", "autogale", int, 2)
    atualizar(config, arquivo, "ESTRATEGIA", "estrategia", error = "MHI")
    atualizar(config, arquivo, "ESTRATEGIA", "tipo_milhao", error = "Minoria")
    atualizar(config, arquivo, "ESTRATEGIA", "paridade", error = "EURUSD")

    return config

def ver_gales(perdaInicial, taxa):
    '''
    Mostra na tela os tipos de martingale até a 10° perda
    '''
    tipos = ["SIMPLES", "LEVE", "AGRESSIVO", "SEGURO", "PESSOAL"]
    for tipo in tipos:
        print(tipo, "\n")
        if tipo == "PESSOAL":
            tipo = float(input("Digite o fator multiplicativo: "))
        lucro = perdaInicial//taxa
        perda = perdaInicial
        valor = perdaInicial
        for j in range(10):
            valor = IQ_API.martingale(tipo, taxa, perda, valor, lucro)
            print(f"Perdeu {round(perda, 2)} vai investir {round(valor, 2)} e vai ganhar {round(valor * taxa, 2)} onde o lucro vai ser {round(valor * taxa - perda, 2)}")
            perda += valor
        print()

def captura_erros(params, operar_lista, tentativas = 0):      
    try:
        if operar_lista: bot = ListaTaxa(*params)
        else: bot = Estrategias(*params)
        bot.operar()
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        if type(e) == ConnectionError:
            bot.mostrar_mensagem("Não conseguiu se conectar na conta")
            tentativas = 2
        else:
            print("Aconteceu um erro na API, tentando novamente.")
        escreve_erros(e)
        
        if tentativas == 2: 
            bot.mostrar_mensagem(
                "Ultrapassou o máximo de tentativas.")
            return

        try:
            print("Continuando as operações...")
            captura_erros(params, operar_lista, tentativas + 1)
        except:
            print("Deu erro novamente! Finalizando o programa.")
            escreve_erros(e)   

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
            ListaTaxa(config, comandos).operar_lista()
        elif comandos[0] in ["-h", "ajuda"]:
            with open(LOCALAJUDA, "r+") as file:
                for i in file:
                    print(i.strip())
        elif comandos[0] in ['-o', 'online'] and len(comandos[1:]) > 3:
            # Carrega o arquivo de configurações a partir do e-mail
            config = MongoDB.get_user(comandos[1])
            config['senha'] = comandos[2]
  
            # Define o arquivo de entradas a partir do gale máximo/própria
            if config['tipo_lista'] == "casa":
                # Une com as informações gerais
                config.update(MongoDB.get_avancadas())
                maximo = int(config['max_gale'])
                if maximo < 1:
                    maximo = 1
                elif maximo > 3:
                    maximo = 3
                entradas = MongoDB.get_entradas(maximo)
            else:
                entradas = config['lista']
            
            params = config, entradas, int(comandos[3])
            captura_erros(params, comandos[4] == "True")

        else:
            print('''
            [COMANDOS]
            Ajuda: -h
            Testar a leitura do arquivo/configuração: -t
            Rodar o bot a partir de uma configuração: -c nomeDoArquivo
            Verificar tipos de martingale: -m
            Para telegram: -o email senha
            ''')
    else:
        config = configuracoes()
        comandos = abrir_arquivo(config["arquivo"])
        ListaTaxa(config, comandos).operar_lista()
        
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
                MongoDB.close()
            except Exception as e:
                print(e)
                input()
