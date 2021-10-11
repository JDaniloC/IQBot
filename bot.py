from utils.estrategias import Estrategias
from utils.operar import escreve_erros
from utils.lista_taxa import ListaTaxa
from datetime import datetime
from sys import argv, exit
import re, logging

if argv[1:] and argv[1] == "-o":
    from database import Mongo
    MongoDB = Mongo()

logging.disable(level = (logging.DEBUG))

ASSET_REGEX = r'[A-Za-z]{6}(-OTC)?'
DATE_REGEX = r'\d{2}\W\d{2}\W\d{4}'
TIME_REGEX = r'[MH][1-6]?[0-5]'
HOUR_REGEX = r'\d{2}:\d{2}'
DIR_REGEX = r'CALL|PUT'

def numerico(x):
    '''
    Verifica se a string pode ser convertida para float
    '''
    try:
        float(x)
        return True
    except:
        return False

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
    
    texto = texto.upper().replace("/", "")
    try:
        data = re.search(DATE_REGEX, texto)
        if data:
            data = [int(x) for x in re.split(r"\W", data[0])]
        else:
            hoje = datetime_brazil()
            data = [hoje.day, hoje.month, hoje.year]
        
        hora = re.search(HOUR_REGEX, texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]

        par = re.search(ASSET_REGEX, texto)[0]
        ordem = re.search(DIR_REGEX, texto)[0].lower()
        has_timeframe = re.search(TIME_REGEX, texto)
        if has_timeframe: 
            if "M" in has_timeframe[0]: 
                timeframe = int(has_timeframe[0].strip("M"))
            else: 
                timeframe = int(has_timeframe[0].strip("H")) * 60
        else: timeframe = 0
    except:
        return {}

    return {
        "par": par,
        "data": data,
        "hora": hora,
        "ordem": ordem,
        "tipo": "lista",
        "timeframe": timeframe,
        "timestamp": timestamp(data, hora)
    }

def pegar_comando_taxas(original_text: str) -> dict:
    '''
    Recebe um texto e devolve:
    {
        par: str,       # Paridade eg. EURUSD-OTC
        taxa: int,      # A taxa eg. 1.12345
        ordem: str,     # "" ou "PUT"|"CALL"
        tipo: "taxas",  # Para ser identificado pelo bot
        timeframe: int, # 0 ou um número se houver
        timestamp: timestamp
    }
    '''
    texto = original_text.strip().upper()
    paridade, taxa, direction, timeframe = "", 0, "", 0
    try:
        has_timeframe = re.search(TIME_REGEX, texto)
        if has_timeframe: 
            texto = re.sub(TIME_REGEX, r'', texto).strip()
            if "M" in has_timeframe[0]: 
                timeframe = int(has_timeframe[0].strip("M"))
            else: 
                timeframe = int(has_timeframe[0].strip("H")) * 60
        
        partitions = re.split(r"[^\w.-]", texto)
        for text_part in partitions: 
            possible_asset = text_part.replace("/", "")
            has_asset = re.search(ASSET_REGEX, possible_asset)
            has_direction = re.search(DIR_REGEX, text_part)
            if has_asset:
                paridade = has_asset[0]
            elif numerico(text_part): 
                taxa = float(text_part)
            elif has_direction:
                direction = has_direction[0].lower()
                    
        if paridade == "" or taxa == 0:
            raise ValueError("Faltando a paridade ou taxa!")
        
    except Exception as e:
        print(type(e), e, original_text)
        return {}
        
    return {
        "par": paridade, 
        "taxa": taxa, 
        "tipo": "taxas",
        "ordem": direction,
        "timeframe": timeframe,
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

def captura_erros(params, operar_lista, tentativas = 0):      
    if operar_lista: bot = ListaTaxa(*params)
    else: bot = Estrategias(*params)
    
    if not bot.entrou:
        return

    try:
        bot.operar()
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        if type(e) == ConnectionError:
            bot.mostrar_mensagem("Não consegui se conectar na conta")
            tentativas = 2
        escreve_erros(e)
        
        if tentativas == 1: 
            return

        captura_erros(params, operar_lista, tentativas + 1)

def recebe_comandos(comandos):
    '''
    Recebe os comandos do terminal e computa algum resultado
    Se nenhum comando for passado:
        1 - Carrega as informações
        2 - Segue a operação do entradas.txt
    '''
    if comandos != []:
        if comandos[0] in ['-o', 'online'] and len(comandos[1:]) > 3:
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

            try:
                captura_erros(params, comandos[4] == "True")
            except Exception as e:
                escreve_erros(e)

        else:
            print('''[COMANDOS]
        Ajuda: -h
        Testar a leitura do arquivo/configuração: -t
        Rodar o bot a partir de uma configuração: -c nomeDoArquivo
        Verificar tipos de martingale: -m
        Para telegram: -o email senha
            ''')
    else:
        print("Nenhum comando passado.")
        
if __name__ == "__main__":
    try:
        result = recebe_comandos(argv[1:])
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
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
