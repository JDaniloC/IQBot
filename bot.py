from utils.conversor import convert_lines_to_list, convert_list_to_text
from admin.schema.users_schema import user as users_schema
from utils.estrategias import Estrategias
from utils.lista_taxa import ListaTaxa
from utils.operar import escreve_erros
from sys import argv, exit
import logging, json

if argv[1:] and argv[1] == "-o":
    from admin.database import Mongo
    MongoDB = Mongo()

logging.disable(level = (logging.DEBUG))

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
            config = MongoDB.usuario_cadastrado(comandos[1])
            config['senha'] = comandos[2]
  
            # Define o arquivo de entradas a partir do gale máximo/própria
            if config.get('tipo_lista', "Propria") == "Da casa":
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
        escreve_erros(e)
    finally:
        if not argv[1:] or argv[1] != "-o":
            input("\nDigite Enter para sair")
        elif argv[1] == "-o":
            try: # Dizer que terminou
                email = argv[2]
                MongoDB.modifica_usuario(email, {
                    "operando": False })
                MongoDB.close()
            except Exception as e:
                print(e)
                input()
