from utils.conversor import convert_lines_to_list
from utils.operar import Operacao, escreve_erros
from configparser import RawConfigParser
from sys import argv
import re, logging

if argv[1:] and argv[1] == "-o":
    from database import Mongo
    MongoDB = Mongo()

logging.disable(level = (logging.DEBUG))

LOCALAJUDA = "misc/ajuda.txt"
LOCALCONFIG = "config/config.txt"

print("\n[Comando para parar: Ctrl + C]\n")

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
            comando = convert_lines_to_list(entrada)
            if comando != {}:
                comandos.append(comando)
    return comandos

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

def recebe_comandos(comandos):
    '''
    Recebe os comandos do terminal e computa algum resultado
    Se nenhum comando for passado:
        1 - Carrega as informações
        2 - Segue a operação do entradas.txt
    '''
    if comandos != []:
        if comandos[0] in ["-h", "ajuda"]:
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
            Operacao(config, entradas, int(comandos[3]), comandos[4])
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
        Operacao(config, comandos)
        
if __name__ == "__main__":
    try:
        result = recebe_comandos(argv[1:])
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        print("\nAconteceu um erro, tente novamente.")
        print("Se o erro persistir, chame o técnico.")
		
        escreve_erros()
    finally:
        if not argv[1:] or argv[1] != "-o":
            input("\nDigite Enter para sair")
        elif argv[1] == "-o":
            try: # Dizer que terminou
                email = argv[2]
                dados = MongoDB.get_user(email)
                if dados:
                    dados["operando"] = False
                    MongoDB.modifica_usuario(dados, email)
                MongoDB.close()
            except Exception as e:
                print(e)
                input()
