from admin.schema.users_schema import user as users_schema
from utils.estrategias import Estrategias
from utils.lista_taxa import ListaTaxa
from utils.operar import escreve_erros
from datetime import datetime
from sys import argv, exit
import re, logging, json

if argv[1:] and argv[1] == "-o":
    from admin.database import Mongo
    MongoDB = Mongo()

logging.disable(level = (logging.DEBUG))

LOCALAJUDA = "misc/ajuda.txt"
LOCALCONFIG = "config/config.txt"

print("\n[Comando para parar: Ctrl + C]\n")

def carregar_config(msg: str) -> dict:
    try:
        config = json.loads(msg)
        remove = ["_id", "email", "lista", "timestamp", 
            "num_lista", "plano", "operando", "tipo_lista"]
        
        for item in users_schema:
            if item not in remove and item in config:
                users_schema[item] = config[item]

        return config
    except Exception as e: 
        print(type(e), e)
        return {}

def salvar_config(config: dict) -> str:
    config = config.copy()
    remove = ["_id", "email", "lista", "timestamp", 
            "num_lista", "plano", "operando", "tipo_lista"]
        
    for item in remove:
        if item in config:
            del config[item]
    
    return json.dumps(config, ensure_ascii=False)
    
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
        "par": par,
        "data": data,
        "hora": hora,
        "ordem": ordem,
        "tipo": "lista",
        "timeframe": timeframe,
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
        timeframe = re.search(r'[MH][1-6]?[0-5]', texto.upper())
        if timeframe: 
            texto = re.sub(r'[MH][1-6]?[0-5]', r'', texto.upper())
            if "M" in timeframe[0].upper(): 
                timeframe = int(timeframe[0].strip("M"))
            else: 
                timeframe = int(timeframe[0].strip("H")) * 60
        else: timeframe = 0

        primeiro, segundo = re.split(r"[^\w.-]+", texto.strip())
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

def numerico(x):
    '''
    Verifica se a string pode ser convertida para float
    '''
    try:
        float(x)
        return True
    except:
        return False

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
            if config.get('tipo_lista', "Propria") == "Da casa":
                # Une com as informações gerais
                config.update(MongoDB.get_avancadas())
                # maximo = int(config.get('max_gale', 0))
                # if maximo < 1:
                #     maximo = 1
                # elif maximo > 3:
                #     maximo = 3
                entradas = MongoDB.get_entradas(1)
            else:
                entradas = config.get('lista', [])
            
            params = config, entradas, int(comandos[3])

            try:
                captura_erros(params, comandos[4] == "True")
            except Exception as e:
                escreve_erros(e)
        else: print("Nenhum comando passado")

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
