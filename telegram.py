import time, pprint, amanobot, os, sys
from configparser import RawConfigParser
from datetime import timedelta, datetime

from amanobot.text import apply_entities_as_markdown
from amanobot.loop import MessageLoop
from amanobot.namedtuple import (
    ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove, InlineKeyboardMarkup, 
    InlineKeyboardButton)
from amanobot.delegate import (pave_event_space,
    per_callback_query_origin, per_chat_id, create_open)

from bot import (pegar_comando, escreve_erros, 
    carregar_config, salvar_config)
from utils.catalogador import Catalogador
from utils.checador import checa_sinais
from admin.controlador import Control
from admin.database import Mongo

account_list = {}
config = RawConfigParser()
config.read(".env")
MongoDB = Mongo()

TOKEN = config.get("TELEGRAM", "token")

# Funções
def strDateHour(number:int) -> str:
    '''
    Converte números de 1 dígito para 2 dígitos:
        0:0 -> 00:00
        2/1/2000 -> 02/01/2000
    '''
    return str(number) if len(str(number)) != 1 else "0" + str(number)

def carregar_entradas(opcao):
    '''
    Abre o arquivo de entradas e organiza de forma legível
    Params:
        opcao = 1 ou 2, para entrar no arquivo de entradas1/entradas2.txt
    return:
        lista de strings dessas entradas
    '''
    if type(opcao) != list:
        lista = MongoDB.get_entradas(opcao)
    else:
        lista = opcao
    lista.sort(key = lambda x: x["timestamp"])

    lista_entradas = []
    for linha in lista:
        timeframe = linha['timeframe']
        if timeframe == 0:
            timeframe = "Padrão"
        else:
            timeframe = f"M{linha['timeframe']}"

        if linha["tipo"] == "taxas": 
            lista_entradas.append(f"""
📊 Ativo: {linha['par']}
📈 Taxa: {linha['taxa']}
⏰ Período: {timeframe}
            """)
            continue
        direcao = linha["ordem"].lower()
        lista_entradas.append(f'''
📊 Ativo: {linha["par"]}
📅 Dia: {"/".join(list(map(strDateHour, linha["data"])))}
⏱ Hora: {":".join(list(map(strDateHour, linha["hora"])))}   
{'⬆' if direcao == "call" else '⬇'} Direção: {direcao.upper()} 
⏰ Período: {timeframe}
        ''')
    return lista_entradas

def exibir_configuracoes(mapeamento, infos, modalidade):
    headers = {
        "Tipo de conta": "🧾 Geral 🌐",
        "Tipo de gerenciamento": "🧮 Gerenciamento 🖍",
        "Tipo de martingale": "⚠️ Martingale e Soros ✅",
        "Filtro de tendência": "📈 Tendência e Notícias 📡",
        "Estratégias: Automático": "✳️ Opções de estratégias ⚙️",
        "Tipo de paridade": "🔩 Outras Opções ⚙️",
        "Paridade": "✳️ Estratégias ❇️",
    }
    mensagem, current_header = "", ""
    for key, value in mapeamento.items():
        if value[0] not in ["lista", "num_lista"]:
            if key in headers:
                current_header = headers[key]
                if modalidade == "Todas" or current_header == modalidade:
                    mensagem += f"\n{headers[key]}\n"
            valor = str(infos.get(value[0], 'Não configurado'))
            valor = valor.replace('True', 'Sim').replace('False', 'Não')
            if modalidade == "Todas" or current_header == modalidade:
                mensagem += f"*{key}*: {valor}\n"

    return mensagem

# São atributos gerais para todas as contas
# Pois o objeto Assistente é instanciado por usuário 
ADMS = MongoDB.get_adms()
entrada_01 = carregar_entradas(1)
entrada_02 = carregar_entradas(2)
entrada_03 = carregar_entradas(3)
cache_catalogador = ()

if os.name != "nt":
    controlador = Control()
rodando = True

mapeamento_avancado = {
    "Tipo de paridade": ["tipo_par", False, tuple],
    "Mudar timeframe": ["tempo", False, tuple],
    "Antecipar entrada": ["correcao", False, int],
    "Catalogar: Timeframe": ["cat_time", False, int],
    "Catalogar: Dias": ["cat_days", False, int],
    "Catalogar: Porcentagem": ["cat_perct", False, int],
    "Catalogar: Martingale": ["cat_mg", False, int],
    "Catalogar: Limite": ["cat_max", False, int],
    "Catalogar: Hora início": ["cat_start", False, str],
    "Catalogar: Hora final": ["cat_end", False, str]
}

# O bot
class Assistente(amanobot.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(Assistente, self).__init__(*args, **kwargs)
        self.autenticacao = False
        self.nome_usuario = ""
        self.email = ""

        self.entrada = False

        self.ultimo_comando = ""
        self.add_entrada = "-"        
        self.parar_bot = False
        self.operar_lista = True
        self.esperar_config = False
        self.iniciar_operacao = False
        self.alteracoes_avancadas = {
            "adm_in": False,  # Adicionar novo ADM
            "adm_out": False, # Remover um ADM
            "licenca": False, # Renovar licença
            "aprovar": False, # Aprovar usuário
            "remover": False, # Tirar um usuário cadastrado
            "apagar": False,  # Tirar um usuário em cadastro
            "plano": False    # Pra escolher o plano
        }

        self.mapeamento = {
            "Tipo de conta": ["tipo_conta", False, tuple], 
            "Valor de entrada": ["valor", False, float],
            "StopWin": ["stopwin", False, float],
            "StopLoss": ["stoploss", False, float],
            "Pre-stop Win": ["prestopwin", False, int],
            "Pre-stop Loss": ["prestoploss", False, bool],
            "Payout mínimo": ["minimo", False, int], 

            "Tipo de gerenciamento": ["tipo_gale", False, tuple], 
            "Tipo de Stoploss": ["tipo_stop", False, tuple], 
            "Scalper Loss": ["scalper_loss", False, int],
            "Scalper Win": ["scalper_win", False, int],
            "Martingale porcentagem": ["martin_pct", False, int],

            "Tipo de martingale": ["tipo_martin", False, tuple],
            "Martingale na próxima": ["vez_gale", False, tuple],
            "Ciclos de soros": ["ciclos_soros", False, str],
            "Ciclos de gales": ["ciclos_gale", False, str],
            "Máximo de soros": ["max_soros", False, int],
            "Máximo de gales": ["max_gale", False, int],
            "Tipo soros": ["tipo_soros", False, tuple],

            "Filtro de tendência": ["tendencia", False, bool],
            "Período da tendência": ["periodo_tendencia", False, int],
            "Notícias - antes": ['noticias_pre', False, int],
            "Notícias - depois": ['noticias_pos', False, int],
            "Notícias - toros": ["toros", False, tuple],

            "Paridade": ["paridade", False, str],
            "Pós hit": ["poshit", False, bool],
            "Filtros": ["posgale", False, tuple],
            "Estratégia": ["estrategia", False, tuple],
            "Máximo de trades": ["max_trades", False, int],
            "Estratégias - gales": ["autogale", False, tuple],
            "Estratégias - timeframe": ["autotime", False, tuple],

            "Estratégias: Automático": ["auto", False, bool],
            "Estratégias: Catalogador": ["catalogador", False, tuple],
            "Min ciclos válidos": ["autocycles", False, int],
            "Assertividade mínima": ["assert", False, int],
            "Mínimo de hits": ["hits", False, tuple],

            "Tipo de paridade": ["tipo_par", False, tuple],
            "Timeframe lista/taxa": ["tempo", False, tuple],
            "Antecipar resultado": ["delay", False, float],
            "Antecipar entrada": ["correcao", False, int],
            "Adicionar lista": ["lista", False, list],
            "Tipo de lista": ["tipo_lista", False, tuple],
            "Lista escolhida": ["num_lista", False, tuple],
            "Taxas: próxima vela": ["taxas_vela", False, tuple],
        }

        self.informacoes = {}

    def open(self, msg, id):
        '''
        O primeiro método chamado ao receber a primeira mensagem
        '''
        pprint.pprint(msg)
        try:
            self.nome_usuario = msg['from']['first_name']
            if "last_name" in msg['from']:
                self.nome_usuario += " " + msg['from']['last_name']
        except:
            self.nome_usuario = msg['chat']['username']
        print(f"Usuário {self.nome_usuario} começou conversa.\n")
        
        teclado = InlineKeyboardMarkup(inline_keyboard = [
            [InlineKeyboardButton(
                text = MongoDB.infos["campo1"]["titulo"],
                url = MongoDB.infos["campo1"]["link"]
            ),
            InlineKeyboardButton(
                text = MongoDB.infos["campo2"]["titulo"],
                url = MongoDB.infos["campo2"]["link"]
            )]
        ])
        
        self.sender.sendMessage(
            "Não se esqueça dos links importantes", reply_markup = teclado)

        self.enviar_mensagem(
           f"Olá, eu sou seu assistente.",
            delete = False, reply_markup = ReplyKeyboardMarkup(
                keyboard = [[KeyboardButton(text = "Entrar")]]))

        if self.id in account_list:
            print(account_list[self.id]['email'])
            self.entrada = True
            self.login({ "text": account_list[self.id]["email"] })

    def enviar_mensagem(self, message, reply_markup = None, 
        edit = False, delete = True, save = False):
        if edit:
            self.bot.editMessageText(self.message_id, message)
            if reply_markup:
                message = self.sender.sendMessage("Escolha: ",
                    reply_markup = reply_markup)  
                self.bot.deleteMessage((self.chat_id, message['message_id']))
        else:
            if delete and not save:
                try:
                    self.bot.deleteMessage(self.message_id)
                except: pass
     
            message = self.sender.sendMessage(message,
                reply_markup = reply_markup, parse_mode = "Markdown")
            if not save:
                self.message_id = (self.chat_id, message['message_id'])
        return message

    def entrar(self, msg):
        is_in_list = lambda x: x in msg["text"].lower()
        if not any(map(is_in_list, ["entrar", "/start"])):
            return False
        if not self.autenticacao:
            self.enviar_mensagem("Digite o seu e-mail para continuar:", 
                reply_markup = ReplyKeyboardRemove())
            self.entrada = True
        else:
            self.comandos()
        return True

    def login(self, msg):
        '''
        Método para o login, verifica se o ID
        Está em análise ou já aprovado.
        '''
        if not self.entrada: return False
        if self.autenticacao:
            self.enviar_mensagem("Você já está logado.")
            self.comandos()
            return False

        self.enviar_mensagem("Carregado...")
        email = msg['text'].lower()

        usuario = MongoDB.get_user(email)
        if usuario: 
            # Verifica se está no banco de dados e entra na conta
            self.email, self.informacoes = email, usuario
            restante = self.informacoes['timestamp'] - time.time()
            if restante > 0:
                self.entrada = False
                self.autenticacao = True
                account_list[self.id] = {
                    "email": self.email, 
                    "mapping": self.mapeamento,
                    "informacoes": self.informacoes 
                }
                restante = str(
                    timedelta(seconds = restante)
                ).replace('days', 'dias')
                self.sender.sendMessage(f"E-mail autenticado, seja bem-vindo Sr(a) {self.nome_usuario} sua licença expira em: {restante[:-10]}.", 
                reply_markup = InlineKeyboardMarkup(inline_keyboard = [[InlineKeyboardButton( 
                    text = "Ver configurações gerais", callback_data = "show" )]
                ]), parse_mode = "Markdown")
                self.comandos()
            else:
                self.enviar_mensagem(
                    "Sua licença expirou, peça para o administrador renovar.", save = True)
                self.close()
        elif (MongoDB.verifica_cadastro(email)):
            self.enviar_mensagem("Seu e-mail ainda está em análise...", save = True)
            self.close()
        else:
            # Caso o usuário não estiver na lista de espera ele adiciona
            if len(email) > 10 and "@" in email and "." in email:
                MongoDB.adicionar_cadastro(email)
                self.enviar_mensagem(
                    f"Seu e-mail foi colocado para analise. \
                    \nEspere a confirmação do administrador e mande seu e-mail novamente para logar.",
                    save = True)
            else:
                self.enviar_mensagem("Não é um e-mail válido!", save = True)
            self.close()
        return True

    def gerenciar(self, msg):
        '''
        Comandos para administradores
        '''
        if not 'gerenciar' in msg['text'].lower(): 
            return False
        if self.id not in ADMS:
            self.enviar_mensagem("Usuário não tem permissão")
            return False

        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "Configurações avançadas" ),
             KeyboardButton( text = "Administração" )],
            [KeyboardButton( text = "Catalogação"),
             KeyboardButton( text = "Adicionar entradas")],
            [KeyboardButton( text = "Desligar VPS" ),
             KeyboardButton( text = "Voltar ao menu" )]
        ])

        self.enviar_mensagem("Configurações avançadas para administradores:",
            reply_markup = teclado)
        return True

    def submenu_avancado(self, msg):
        if self.id not in ADMS:
            return False
        
        mensagem, teclado = "", []
        verificador = False
        if msg['text'] == "Configurações avançadas":
            mensagem = self.ver_avancadas()
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de paridade" ),
                 KeyboardButton( text = "Mudar timeframe" )],
                [KeyboardButton( text = "Antecipar entrada" ),
                 KeyboardButton( text = "Mudar o delay" )],
                [KeyboardButton( text = "Gerenciar" )]
            ])
            verificador = True
        elif msg['text'] == "Administração":
            mensagem = "Escolha a opção:"
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Aprovar usuários" ),
                 KeyboardButton( text = "Renovar licença" )],
                [KeyboardButton( text = "Tirar de cadastro" ),
                 KeyboardButton( text = "Remover usuários" )],
                [KeyboardButton( text = "Adicionar administrador" ),
                 KeyboardButton( text = "Remover administrador")],
                [KeyboardButton( text = "Atualizar informações"),
                 KeyboardButton( text = "Gerenciar" )]
            ])
            verificador = True
        elif msg['text'] == "Catalogação":
            mensagem = """Opções:
            Timeframe: velas de M(1/5/15/30)
            Dias: analisar últimos 1-30 dias
            Porcentagem: mínimo 0-100%
            Martingale: até 0-2 gales
            Limite: máximo de sinais
            Hora início: Hora útil inicial (00:00)
            Hora final: hora útil final (23:59)
            """
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Catalogar: Timeframe" ),
                 KeyboardButton( text = "Catalogar: Dias" )],
                [KeyboardButton( text = "Catalogar: Porcentagem" ),
                 KeyboardButton( text = "Catalogar: Martingale" )],
                [KeyboardButton( text = "Catalogar: Hora início" ),
                 KeyboardButton( text = "Catalogar: Hora final" )],
                [KeyboardButton( text = "Catalogar: Limite" ),
                 KeyboardButton( text = "Gerenciar" )]
            ])
            verificador = True
        if verificador:
            self.enviar_mensagem(mensagem,
                reply_markup = teclado)        
            return True
        return False

    def ver_avancadas(self):
        '''
        Método que mostra do jeito cru as configurações avançadas
        '''
        if self.id not in ADMS:
            self.enviar_mensagem("Usuário não tem permissão")
            return False
        def traduz_key(key):
            tradutor = {
                "tipo_par": "Tipo de modalidade",
                "tempo": "Timeframe",
                "correcao": "Antecipar entrada",
                "delay": "Antecipar resultado",
                "cat_perct": "Catalogação - Porcentagem",
                "cat_days": "Catalogação - Dias",
                "cat_mg": "Catalogação - Gales",
                "cat_time": "Catalogação - Timeframe",
                "cat_max": "Catalogação - Limite",
                "cat_start": "Catalogação - Hora início",
                "cat_end": "Catalogação - Hora final"
            }
            return tradutor.get(key)

        default = MongoDB.get_avancadas()
        resultado = ""
        for key, value in default.items():
            if key not in ["_id"]:
                resultado += f"{traduz_key(key)}: {value}\n"
        return resultado

    def adicionar_entrada(self, msg):
        '''
        Mudar caminho do arquivo de entradas
        '''
        if self.id in ADMS and msg['text'].lower() == "adicionar entradas":
            # teclado = ReplyKeyboardMarkup(keyboard = [
            #     [KeyboardButton( text = "entrada 01" )],
            #     [KeyboardButton( text = "entrada 02" )],
            #     [KeyboardButton( text = "entrada 03" )],
            #     [KeyboardButton( text = "todas" )]
            # ])
            self.habilitar_entradas({"text": "entrada 01"})
            # self.enviar_mensagem("Qual arquivo de entradas:",
            #     reply_markup = teclado)
            return True
        return False

    def habilitar_entradas(self, msg):
        '''
        Método que habilita a espera por uma nova lista
        '''
        if self.id not in ADMS:
            self.enviar_mensagem("Usuário não tem permissão")
            return False
        if msg['text'] in ["entrada 01", "entrada 02", "entrada 03", "todas"]:
            self.add_entrada = ("todas" if msg['text'] == "todas" else 
                                int(msg['text'].split()[1].strip("0")))
            self.enviar_mensagem('''Envie a lista no formato:
    01/01/2000 13:00 EURUSD-OTC PUT M1
Não importa a ordem das informações, e sim o formato de cada componente.
Se você escolheu adicionar "todas", então especifique as entradas assim:
[01]
01/01/2000 13:00 EURUSD-OTC PUT M1

[02]
EURJPY 31/12/2000 CALL M5 02:30
...''',
        reply_markup = ReplyKeyboardRemove())
            return True
    
    def pegar_entrada(self, entradas):
        '''
        Método que recebe as entradas e verifica se há um comando
        Devolve a lista de entradas que conseguiu extrair
        '''
        lista = []
        for linha in entradas:
            nova = pegar_comando(linha)
            if nova != {}:
                lista.append(nova)
        return lista

    def confirmar_entradas(self, msg):
        '''
        Método que recebe a mensagem de entradas, trata e salva.
        '''
        global entrada_01, entrada_02, entrada_03
        if self.id not in ADMS:
            return
                 
        if self.add_entrada != "-":
            
            def processa_entradas(escolha, texto):
                MongoDB.set_entradas(escolha, 
                    self.pegar_entrada(texto))
                
            self.enviar_mensagem("Processando...")
            # Procura o início das velas
            if self.add_entrada == "todas":
                para_verificar = {1:[], 2:[], 3:[]}
                key = 1
                for linha in msg['text'].split("\n"):
                    if   "[01]" in linha: key = 1
                    elif "[02]" in linha: key = 2
                    elif "[03]" in linha: key = 3
                    elif key and linha not in ["", "\n"]:
                        para_verificar[key].append(linha)
                processa_entradas(1, para_verificar[1])
                processa_entradas(2, para_verificar[2])
                processa_entradas(3, para_verificar[3])
            else:
                processa_entradas(
                    self.add_entrada, msg['text'].split("\n"))
            
            entrada_01 = carregar_entradas(1)
            entrada_02 = carregar_entradas(2)
            entrada_03 = carregar_entradas(3)
            
            self.add_entrada = "-"
            self.enviar_mensagem("Salvo")
            self.gerenciar({"text": "gerenciar"})

    def comandos(self):
        '''
        Menu principal quando já está logado.
        '''
        if self.autenticacao:
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "▶️ Operar Lista/Taxas 📝" ),
                 KeyboardButton( text = "▶️ Operar Estratégias ✳️" )],
                [KeyboardButton( text = "🗂 Catalogar Sinais 📝" ),
                 KeyboardButton( text = "☑️ Verificar Lista 📝" )],
                [KeyboardButton( text = "⚙️ Editar configurações ⚙️" ),
                 KeyboardButton( text = "🔍 Ver lista de Sinais 📝" )],
                [KeyboardButton( text = "⏹ Parar Bot 🤖" ),
                 KeyboardButton( text = "🚪 Sair da Conta ⏏️" )]
            ])

            self.enviar_mensagem("O que deseja?", 
                reply_markup = teclado)
        else:
            self.enviar_mensagem("Usuário não autenticado")
    
    def submenu_comandos(self, msg):
        '''
        Verifica se a pessoa clicou em alguma opção
        do menu principal, devolvendo um boolean
        '''
        texto = msg['text']
        if texto == "▶️ Operar Lista/Taxas 📝":
            self.operar_lista = True
            return self.operar(msg)
        elif texto == "▶️ Operar Estratégias ✳️":
            self.operar_lista = False
            return self.operar(msg)
        elif texto == "🗂 Catalogar Sinais 📝":
            return self.adicionar_catalogados()
        elif texto == "☑️ Verificar Lista 📝":
            return self.verificar_sinais()
        elif texto == "Ver configurações":
            self.enviar_mensagem(
                self.ver_configuracoes(), save = True)
            return True
        elif texto == "⚙️ Editar configurações ⚙️":
            return self.editar_configuracoes()
        elif texto == "🔍 Ver lista de Sinais 📝":
            return self.ver_lista()
        elif texto == "🚪 Sair da Conta ⏏️":
            del account_list[self.id]
            self.close()
            return True
        return False
    
    def operar(self, msg):
        '''
        Opção que inicia a operação.
        E então salva as informações atuais
        Devolve um boolean se autenticado
        '''
        if self.autenticacao:
            self.enviar_mensagem("Carregando...")

            if self.iniciar_operacao:
                self.enviar_mensagem("Iniciando operação, tenha paciência, isso pode demorar.",
                    reply_markup = ReplyKeyboardRemove())   
                self.iniciar_operacao = False
                self.informacoes["operando"] = True
                MongoDB.modifica_usuario(
                    self.informacoes, self.email)
                
                if os.name == "nt": # No windows 
                    os.system(f"powershell start powershell python, bot.py, -o, {self.email}, {msg['text']}, {self.chat_id}, {self.operar_lista}")
                else:
                    controlador.adicionar_pessoa(
                        self.email, msg['text'], self.id, self.operar_lista)
                self.enviar_mensagem("Operação iniciada. Se em 5min eu não avisar que está conectado, reincie a operação.")
                self.comandos()
            else:
                temporario = MongoDB.get_user(self.email)

                if not temporario['operando']:
                    self.enviar_mensagem("Digite sua senha (não guardamos a sua senha, você terá que fazer isso todas as vezes): ", reply_markup = ReplyKeyboardRemove())
                    self.iniciar_operacao = True
                
                else:
                    self.enviar_mensagem("Você quer parar a operação ou ver o relatório?",
                        reply_markup = ReplyKeyboardMarkup(
                            keyboard = [
                                [KeyboardButton( 
                                    text = "🔍 Ver relatório da operação" )],
                                [KeyboardButton( 
                                    text = "Parar Bot/Clique se não foi iniciada" )]
                            ]
                        ))
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def ver_relatorio(self, msg):
        '''
        Devolve as últimas 50 linhas do arquivo de operação
        '''
        is_in_list = lambda x: x in msg["text"].lower()
        if not any(map(is_in_list, ["relatório", "relatorio"])):
            return False
        try:
            self.enviar_mensagem("Pegando relatórios...")
            if os.name != "nt":
                resultado = controlador.pegar_log(self.email)
                resultado = "\n".join(resultado.split("\n")[-50:])
            else: resultado = "Não disponível"
            self.enviar_mensagem(resultado, save = True)
        except Exception as e:
            self.enviar_mensagem(f"Recebi esse erro:\n{e}", save = True)
        self.comandos()
        return True

    def parar_operar(self, msg):
        '''
        Apenas para linux, dá kill na operação através do e-mail
        '''
        if not "parar bot".lower() in msg['text'].lower():
            return False
        self.enviar_mensagem("Parando operação...")
        MongoDB.parar_operacao(self.email)
        if os.name != "nt":
            controlador.parar_operacao(self.email)
        self.enviar_mensagem("Operação cancelada.")
        self.comandos()
        return True

    def ver_lista(self):
        '''
        Mostra as listas de sinais (casa|pessoal)
        Devolve um boolean se está autenticado
        '''
        global entrada_01, entrada_02, entrada_03
        if self.autenticacao:
            def enviar_lista(label, lista):
                msg = "".join(lista)
                if len(msg) >  4000:
                    mensagens = [msg[x:x+4000] 
                        for x in range(0, len(msg), 4000)]
                else:
                    mensagens = [msg]
                for msg in mensagens:
                    self.enviar_mensagem(f"{label}:\n" +
                        msg, save = True)
            
            if self.informacoes['lista'] != []:
                enviar_lista("Lista própria", carregar_entradas(
                        self.informacoes['lista']))
            else:
                self.enviar_mensagem(
                    "Nenhuma lista registrada. Para adicionar: Conta > Adicionar lista.\
                    Ou considere clicar em 🗂 Catalogar Sinais 📝.", 
                    save = True)
            self.comandos()
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def ver_configuracoes(self, modalidade = "Todas"):
        '''
        Mostra as configurações de usuário
        Devolve um boolean se está autenticado.
        '''
        if self.autenticacao:
            return exibir_configuracoes(
                self.mapeamento, self.informacoes, modalidade)
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def editar_configuracoes(self):
        '''
        Menu de opções para editar as configurações
        Devolve um boolean se está autenticado
        '''
        if self.autenticacao:
            result = self.enviar_mensagem(
                self.ver_configuracoes(), 
                reply_markup = ReplyKeyboardMarkup( keyboard = [
                    [KeyboardButton( text = "🧾 Geral 🌐" ),
                     KeyboardButton( text = "📈 Tendência e Notícias 📡" )],
                    [KeyboardButton( text = "🧮 Gerenciamento 🖍" ),
                     KeyboardButton( text = "⚠️ Martingale e Soros ✅" )],
                    [KeyboardButton( text = "✳️ Estratégias ❇️"),
                     KeyboardButton( text = "✳️ Opções de estratégias ⚙️")],
                    [KeyboardButton( text = "🔩 Outras Opções ⚙️" ),
                     KeyboardButton( text = "↪️ Voltar ao menu ⏪" )]
            ], resize_keyboard = True))
            apply_entities_as_markdown(result['text'], [])
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def submenu_configuracoes(self, msg):
        verificador, teclado = False, []
        if msg['text'] == '🧾 Geral 🌐':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de conta" ),
                 KeyboardButton( text = "Valor de entrada" )],
                [KeyboardButton( text = "StopWin" ),
                 KeyboardButton( text = "StopLoss" )],
                [KeyboardButton( text = "Pre-stop Win" ),
                 KeyboardButton( text = "Pre-stop Loss" )],
                [KeyboardButton( text = "Payout mínimo" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == '🧮 Gerenciamento 🖍':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de gerenciamento" ),
                 KeyboardButton( text = "Tipo de Stoploss" )],
                [KeyboardButton( text = "Scalper Win" ),
                 KeyboardButton( text = "Scalper Loss" )],
                [KeyboardButton( text = "Martingale porcentagem" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == '⚠️ Martingale e Soros ✅':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de martingale" ),
                 KeyboardButton( text = "Martingale na próxima" )],
                [KeyboardButton( text = "Ciclos de soros" ),
                 KeyboardButton( text = "Ciclos de gales" )],
                [KeyboardButton( text = "Máximo de gales" ),
                 KeyboardButton( text = "Máximo de soros" )],
                [KeyboardButton( text = "Tipo soros" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == '📈 Tendência e Notícias 📡':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Filtro de tendência" ),
                 KeyboardButton( text = "Período da tendência" )],
                [KeyboardButton( text = "Notícias - antes" ),
                 KeyboardButton( text = "Notícias - depois" )],
                [KeyboardButton( text = "Notícias - toros" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == "✳️ Estratégias ❇️":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Paridade" ),
                 KeyboardButton( text = "Estratégia" ),
                 KeyboardButton( text = "Pós hit" )],
                [KeyboardButton( text = "Estratégias - gales" ),
                 KeyboardButton( text = "Estratégias - timeframe"),
                 KeyboardButton( text = "Filtros" )],
                [KeyboardButton( text = "Máximo de trades" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == "✳️ Opções de estratégias ⚙️":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Estratégias: Automático" ),
                 KeyboardButton( text = "Estratégias: Catalogador" )],
                [KeyboardButton( text = "Min ciclos válidos" ),
                 KeyboardButton( text = "Assertividade mínima" )],
                [KeyboardButton( text = "Mínimo de hits" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        elif msg['text'] == "🔩 Outras Opções ⚙️":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de paridade" ),
                 KeyboardButton( text = "Timeframe lista/taxa" )],
                [KeyboardButton( text = "Antecipar resultado" ),
                 KeyboardButton( text = "Antecipar entrada" )],
                [KeyboardButton( text = "Adicionar lista" ),
                 KeyboardButton( text = "Tipo de lista" )], 
                [KeyboardButton( text = "Taxas: próxima vela" ),
                 KeyboardButton( text = "⚙️ Editar configurações ⚙️" )]])
            verificador = True
        
        if verificador:
            self.ultimo_comando = msg
            result = self.enviar_mensagem(self.ver_configuracoes(msg['text']), 
                reply_markup = teclado)
            apply_entities_as_markdown(result['text'], [])
            return True
        return False

    def mapear(self, dicionario, text):
        '''
        Faz o mapeamento de botões para os métodos habilitar
        '''
        if text in dicionario:
            value = dicionario[text]
            mensagem = "Escolha uma das opções abaixo:"
            if value[2] == bool:
                teclado = ReplyKeyboardMarkup( 
                    keyboard = [
                    [KeyboardButton( text = "Sim" ),
                    KeyboardButton( text = "Não" )]])
            elif value[2] == tuple:
                opcoes = {
                    "toros": [0, 1, 2, 3], "num_lista": [1, 2, 3],
                    "tempo": [1, 5, 15, 30], "autogale": [0, 1, 2], 
                    "posgale": ["Nenhum", "Bear 1", "Bear 2"],
                    "autotime": [1, 5, 15], "vez_gale": ["vela", "sinal"],
                    "tipo_par": ["binary", "digital", "auto"],
                    "tipo_lista": ["Própria", "Da casa"],
                    "tipo_conta": ["treino", "real"],
                    "tipo_soros": ["normal", "ciclos"],
                    "tipo_stop": ["movel", "fixo"], "hits": [1, 2, 3], 
                    "taxas_vela": ["atual", "próxima"],
                    "catalogador": ["velho", "novo"], "tipo_gale": [
                        "martingale", "sorosgale", "ciclos", "nenhum"],  
                    "tipo_martin": ["seguro", "leve", 
                        "porcento", "agressivo", "individual"],
                    "estrategia": ['c3', 'daka','five flip',
                        'five flip + não triplicação', 'five flip + torres gêmeas',
                        'gaba','half hour','hope','last of five','melhor de 3',
                        'mhi + padrão impar','mhi maioria','mhi minoria','vituxo'
                        'mhi2 + r7','mhi2 maioria','mhi2 minoria','mhi3 + seven flip',
                        'mhi3 maioria','mhi3 minoria','milhão maioria','milhão minoria',
                        'msf','não triplicação','padrão 23','padrão 3x1','padrão impar',
                        'power','primeiros trocados','quinto elemento','r7','seven flip',
                        'torres gêmeas','torres gêmeas + padrão 3x1','triplicação',
                        'triplicação + torres gêmeas','três mosqueteiros','três vizinhos',
                        'três vizinhos + torres gêmeas','turn over','turn over + mhi']
                }
                if value[0] in ["tipo_gale", "tempo",
                    "tipo_martin", "tipo_par", "estrategia"]:
                    # Um abaixo do outro
                    teclado = ReplyKeyboardMarkup( 
                    keyboard = [
                        [KeyboardButton( text = x )] 
                        for x in opcoes[value[0]]])
                else:
                    # Um do lado do outro
                    teclado = teclado = ReplyKeyboardMarkup( 
                    keyboard = [
                        [KeyboardButton( text = x )
                        for x in opcoes[value[0]]]])
            else:
                mensagem = f"Digite a nova informação para {text}: "
                if value[0] in ["ciclos_soros", "ciclos_gale"]:
                    mensagem = """As linhas são os ciclos e colunas são gales:
    1,2,3 (ciclo 1 com 2 gales)
    4,5    (ciclo 2 com 1 gale)
    6       (ciclo 3 sem gale)"""
                elif value[0] in ["cat_start", "cat_end"]:
                    mensagem = "Formato 00:00 até 23:59, erros serão desconsiderados"
                elif value[2] == list:
                    mensagem = """Formato sugerido:
    Lista: 01/01/2000 13:00 EURUSD-OTC PUT M1
    Taxas: EURUSD 1.12345 M5
Se o timeframe não for especificado, irá usar o padrão
Não importa a ordem das informações, e sim o formato de cada componente."""
                teclado = ReplyKeyboardRemove()
            
            dicionario[text][1] = True
            self.enviar_mensagem(mensagem, 
                reply_markup = teclado)
            return True
        return False

    def habilitar_avancadas(self, msg):
        '''
        Verifica se a mensagem está nas configurações avançadas
        Se estiver, devolve True caso contrário False
        '''
        global ADMS, rodando, \
            entrada_01, entrada_02, entrada_03
        
        if self.id not in ADMS:
            return False
        if msg['text'] == 'Adicionar administrador':
            self.enviar_mensagem("Coloque o ID do telegram:",
                reply_markup = ReplyKeyboardRemove())
            self.alteracoes_avancadas['adm_in'] = True
            return True
        elif msg['text'] == "Remover administrador":
            teclado = [[KeyboardButton(text = _id)] 
                for _id in ADMS]
            self.enviar_mensagem(
                "Coloque o ID que deseja remover:",
                reply_markup = ReplyKeyboardMarkup(
                    keyboard = teclado))
            self.alteracoes_avancadas['adm_out'] = True
            return True
        elif msg['text'] == "Atualizar informações":
            self.enviar_mensagem("Atualizando...")
            MongoDB.atualizar_infos()
            ADMS = MongoDB.get_adms()
            entrada_01 = carregar_entradas(1)
            entrada_02 = carregar_entradas(2)
            entrada_03 = carregar_entradas(3)
            self.enviar_mensagem("Informações atualizadas.")
            self.gerenciar({"msg": "gerenciar"})
        elif msg['text'] in [
            "Aprovar usuários", "Renovar licença", 
            "Tirar de cadastro", "Remover usuários"]:
            self.enviar_mensagem("Carregando banco de dados...")
            # Captura todos os usuários
            if msg['text'] in ["Aprovar usuários", "Tirar de cadastro"]:
                users = MongoDB.usuarios_em_cadastro()
            else:
                users = MongoDB.usuarios_cadastrados()
            # Faz um botão para cada e-mail
            lista_usuarios = [] 
            for user in users:
                email = user['email']
                lista_usuarios.append([KeyboardButton(text = email)])
            if len(lista_usuarios) > 0:
                self.enviar_mensagem("Escolha:",
                    reply_markup = ReplyKeyboardMarkup(keyboard = lista_usuarios))
                if msg['text'] == "Aprovar usuários":
                    self.alteracoes_avancadas['aprovar'] = True
                    self.alteracoes_avancadas['plano'] = True
                elif msg['text'] == "Tirar de cadastro":
                    self.alteracoes_avancadas['apagar'] = True
                elif msg['text'] == "Remover usuários":
                    self.alteracoes_avancadas['remover'] = True
                else:
                    self.alteracoes_avancadas['licenca'] = True
                    self.alteracoes_avancadas['plano'] = True
                return True
            else:
                self.enviar_mensagem("Nenhum usuário no banco", save = True)
        elif msg['text'] == "Catalogar":
            self.catalogar_sinais()
        elif msg['text'] == "Desligar VPS":
            self.parar_bot = True
            self.enviar_mensagem("Tem certeza? Isso irá desligar a VPS\n\
                Cancelando as operações dos clientes\n\
                Até o suporte ligar novamente",
                reply_markup = ReplyKeyboardMarkup(keyboard = [
                    [KeyboardButton( text = "Sim" ),
                    KeyboardButton( text = "Não" )]]))
        else:
            return self.mapear(mapeamento_avancado, msg['text'])
        return True

    def verificar_sinais(self):
        '''
        Verifica os sinais da lista própria
        '''
        self.enviar_mensagem("Carregando...")
        resultados = checa_sinais(
            self.informacoes['lista'], 
            self.informacoes["tempo"])
        resultado = "\n".join(resultados)
        if len(resultado) > 4000:
            mensagens  = [resultado[x:x+4000] 
                for x in range(0, len(resultado), 4000)]
        else: mensagens = [resultado]

        for msg in mensagens:
            if msg != "":
                self.enviar_mensagem(msg, save = True)
        self.comandos()
        return True
    
    def adicionar_catalogados(self):
        ''' 
        Verifica se os sinais são atuais ou foi modificado 
        '''
        self.enviar_mensagem("Carregando...")
        lista_da_casa = self.informacoes["tipo_lista"] == "Da casa"
        if lista_da_casa:
            sinais = MongoDB.get_entradas(1)
            conf_alterada = False
        else:
            sinais = MongoDB.get_entradas(3)
            conf = MongoDB.get_avancadas()
            conf_catalogador = (conf["cat_time"], 
                conf["cat_days"], conf["cat_perct"], 
                conf["cat_mg"], conf["cat_max"],
                conf["cat_start"], conf["cat_end"])
            conf_alterada = cache_catalogador != conf_catalogador

        sinais_antigos = (len(sinais) > 0 and 
            (datetime.now() - datetime.fromtimestamp(
                sinais[0]["timestamp"])).days > 0)
        
        if len(sinais) == 0 or sinais_antigos or (
            not lista_da_casa and conf_alterada):
            if self.id not in ADMS:
                self.enviar_mensagem(
                    "Peça para o administrador catalogar os sinais de hoje!", 
                    save = True)
                return True
            if not lista_da_casa:
                self.catalogar_sinais()
            else: 
                self.enviar_mensagem("Atualize a lista!", save = True)
                return True
        
        if lista_da_casa:
            nova_lista = MongoDB.get_entradas(1)
        else:
            nova_lista = MongoDB.get_entradas(3)
        self.informacoes["lista"] = nova_lista
        self.enviar_mensagem(
            "Sinais catalogados adicionados à sua lista.", save = True)
        self.comandos()
        return True

    def catalogar_sinais(self):
        '''
        Cataloga os sinais e adiciona a lista 3
        '''
        global entrada_03, cache_catalogador
        self.enviar_mensagem("Carregando...")
        catalogador = Catalogador(self.chat_id)
        conf = MongoDB.get_avancadas()
        cache_catalogador = (conf["cat_time"], 
            conf["cat_days"], conf["cat_perct"], 
            conf["cat_mg"], conf["cat_max"],
            conf["cat_start"], conf["cat_end"])
        lista = catalogador.catalogar(*cache_catalogador)

        if lista != []:
            MongoDB.set_entradas(3, lista)
            entrada_03 = carregar_entradas(3)
        else:
            self.enviar_mensagem(
                "Nenhum sinal encontrado...", save = True)

    def habilitar_alteracao(self, msg):
        '''
        Habilita a alteração da informação e pergunta qual a nova
        Devolvendo um bool se completou a habilitação
        '''
        if not self.autenticacao:
            return False
        return self.mapear(self.mapeamento, msg['text'])

    def salvar_alteracoes_avancadas(self, msg):
        '''
        Verifica se está requisitando alguma alteração avançada
        Se sim, faz a operação no banco de dados e desabilita
        Devolve um boolean caso positivo.
        '''
        global ADMS
        if self.id not in ADMS:
            return False
        msg = msg['text']
        if self.alteracoes_avancadas['adm_in']:
            MongoDB.adiciona_adm(int(msg))
            ADMS = MongoDB.get_adms()
            self.enviar_mensagem("Administrador adicionado.")
            self.alteracoes_avancadas["adm_in"] = False
            return True
        elif self.alteracoes_avancadas['adm_out']:
            MongoDB.remover_adm(int(msg))
            ADMS = MongoDB.get_adms()
            self.enviar_mensagem("Administrador removido.")
            self.alteracoes_avancadas["adm_out"] = False
            return True
        elif self.alteracoes_avancadas['plano'] == True:
            self.enviar_mensagem("Escolha o tipo de plano",
                reply_markup = ReplyKeyboardMarkup(keyboard = [
                    [KeyboardButton( text = "teste" ),
                    KeyboardButton( text = "semanal" )],
                    [KeyboardButton( text = "mensal" ),
                    KeyboardButton( text = "trimestral" )],
                    [KeyboardButton( text = "anual" )]]))
            self.alteracoes_avancadas['plano'] = msg
            return None
        elif self.alteracoes_avancadas['aprovar']:
            aprovado = MongoDB.aprovar(
                self.alteracoes_avancadas['plano'], msg)
            if aprovado:
                self.enviar_mensagem("Usuário aprovado.")
            else:
                self.enviar_mensagem(
                    "Você já atingiu o limite de usuários. \
                        Sua VPS já não suporta.", save = True)
            self.alteracoes_avancadas["aprovar"] = False
            self.alteracoes_avancadas['plano'] = False
            return True
        elif self.alteracoes_avancadas['licenca']:
            MongoDB.renovar_licenca(
                self.alteracoes_avancadas['plano'], msg)
            self.enviar_mensagem("Licença renovada")
            self.alteracoes_avancadas["licenca"] = False
            self.alteracoes_avancadas['plano'] = False
            return True
        elif self.alteracoes_avancadas['remover']:
            MongoDB.remover_usuario(msg)
            self.enviar_mensagem("Usuário removido")
            self.alteracoes_avancadas["remover"] = False
            return True
        elif self.alteracoes_avancadas['apagar']:
            MongoDB.apagar_cadastro(msg)
            self.enviar_mensagem("Cadastro apagado")
            self.alteracoes_avancadas["apagar"] = False
            return True
        return False

    def confirmar_mapeamento(self, dicionario, novo):
        '''
        Faz a mapeação do dicionário para ver se há um valor verdadeiro
        Se houver verifica se o novo valor está correto
        Devolve um bool, usado para confirmar_alteração/avançado
        '''
        def numeration(valor, func):
            try:
                return func(valor.strip().replace(",", "."))
            except: return False

        for key, value in dicionario.items():
            if value[1]:
                if value[2] in [int, float]:
                    novo = numeration(novo, value[2])
                    if novo != 0 and not novo:
                        if value[0] == "delay":
                            novo = False
                        else:
                            self.enviar_mensagem("Deve ser um número! Tente novamente", save = True)
                            return True
                elif value[2] == list:
                    novo = self.pegar_entrada(novo.split("\n"))
                elif value[2] == bool:
                    novo = bool(novo.strip() == "Sim")
                elif value[0] in ["tempo", "toros",
                    "num_lista", "autogale", "autotime"]:
                    try:
                        novo = int(novo)
                    except:
                        dicionario[key][1] = False
                        self.enviar_mensagem("Deve ser um número.", save = True)
                        return True
                elif value[0] in ["ciclos_soros", "ciclos_gale"]:
                    try:
                        novo = list(map(lambda x: list(
                            map(float, x.strip().split(","))), 
                            novo.strip().split("\n"))) 
                    except:
                        self.enviar_mensagem("Não entendi, tente novamente!")
                        return True
                elif novo == "individual":
                    self.enviar_mensagem(
                        "Digite o fator do martingale:\nEx: 2.5", 
                        reply_markup = ReplyKeyboardRemove())
                    return True
                elif value[0] == "tipo_martin" and numeration(novo, float):
                    novo = numeration(novo, float)
                dicionario[key][1] = False
                return value[0], novo
        return False

    def confirmar_alteracao_avancada(self, msg):
        '''
        Método que altera as informações avançadas
        '''
        if self.id not in ADMS:
            return False
        result = self.confirmar_mapeamento(mapeamento_avancado, msg['text'])
        if result and type(result) == tuple:
            info, valor = result
            MongoDB.modifica_avancadas(info, valor)
            self.enviar_mensagem(f"Valor salvo.")
            self.gerenciar({"text": "gerenciar"})
            return True
        return result

    def confirmar_alteracao(self, msg):
        '''
        Altera a informação no dicionário e avisa se deu certo
        Devolvendo um bool se completou a alteração
        '''
        if self.autenticacao:
            result = self.confirmar_mapeamento(self.mapeamento, msg['text'])
            if result and type(result) == tuple:
                info, valor = result
                self.informacoes[info] = valor
                account_list[self.id]["informacoes"] = self.informacoes 
                self.enviar_mensagem("Alteração salva!")
                self.submenu_configuracoes(self.ultimo_comando)
                return True
            return result
        return False

    def carregar_config(self, msg):
        if not self.autenticacao:
            return False
        
        if msg['text'].lower() == 'carregar config':
            self.esperar_config = True
            self.enviar_mensagem("Envie a configuração:")
            return True
        elif msg['text'].lower() == "salvar config":
            config = salvar_config(self.informacoes)
            self.enviar_mensagem(config, save = True)
            return True
        elif self.esperar_config:
            config = carregar_config(msg['text'])
            if config != {}:
                self.informacoes.update(config)
                account_list[self.id]["informacoes"] = self.informacoes 
                self.enviar_mensagem("Alteração salva!")
            else: self.enviar_mensagem("Não foi possível carregar config")
            self.comandos()
            self.esperar_config = False
            return True
        return False

    def listar_usuarios(self, msg):
        is_in_list = lambda x: x in msg["text"].lower()
        if not any(map(is_in_list, ["listar users", 
            "listar usuários", "listar usuarios"])):
            return False
        if os.name != "nt":
            instancias = controlador.mostrar_usuarios()
            for instancia, usuarios in instancias.items():
                self.enviar_mensagem(instancia, save = True)
                for usuario in usuarios:
                    self.enviar_mensagem(usuario, save = True)
        return True
        
    def desligar_bot(self):
        global rodando
        if os.name != "nt":
            self.enviar_mensagem("Deletando todas as instâncias...")
            usuarios = controlador.deletar_instancias()
            self.enviar_mensagem("Resetando o banco de dados...")
            MongoDB.modificar_banco_users("off")
            for email in usuarios:
                print(email)
        self.enviar_mensagem("Desligando o bot...")
        rodando = False
        self.close()
        sys.exit(0)

    def cancelar(self, msg):
        if not "cancelar" in msg['text'].lower():
            return False
        self.alteracoes_avancadas = {
            key: False for key in self.alteracoes_avancadas.keys()}
        self.mapeamento = {
            key: [value[0], False, value[2]]
            for key, value in self.mapeamento.items()}
        self.iniciar_operacao = False
        self.parar_bot = False
        self.comandos()
        return True

    def confirmar_desligar_bot(self, msg):
        if not self.parar_bot: return False
        if msg['text'] == "Sim":
            self.desligar_bot()
        else:
            self.parar_bot = False
            self.enviar_mensagem(
                "Deixando o bot ligado", save = True)
            self.gerenciar({"text": "gerenciar"})
        return True

    def voltar(self, msg):
        is_in_list = lambda x: x in msg["text"].lower()
        if any(map(is_in_list, ["voltar ao menu", "menu"])):
            if not self.autenticacao: self.entrar()
            else: self.comandos()
            return True
        elif any(map(is_in_list, ["voltar", "menu anterior"])):
            if self.autenticacao: self.comandos()
            return True
        return False

    def on_chat_message(self, msg):
        '''
        Método que é chamado sempre que é digitado alguma coisa
        '''
        if self.cancelar(msg):
            pass # [0] Geral
        elif self.login(msg):
            pass # [1] Login
        elif self.iniciar_operacao:
            self.operar(msg)        # [3] Opções
        elif self.salvar_alteracoes_avancadas(msg) in [True, None]:
            if not self.alteracoes_avancadas['plano']:
                self.gerenciar({"text": "gerenciar"})    # [4] Avançadas (ADM)
        elif self.entrar(msg):
            pass # [0] Login
        elif self.voltar(msg):
            pass # [0] Voltar
        elif self.ver_relatorio(msg):
            pass # [4] Opções
        elif self.parar_operar(msg):
            pass # [4] Operação 
        elif self.gerenciar(msg):
            pass # [0] Avançadas|Entradas
        elif self.submenu_comandos(msg):
            pass # [2] Opções
        elif self.submenu_configuracoes(msg):
            pass # [1] Alterações
        elif self.adicionar_entrada(msg):
            pass # [1] Entradas
        elif self.confirmar_alteracao(msg):
            pass # [3] Alterações
        elif self.habilitar_alteracao(msg):
            pass # [2] Alterações
        elif self.confirmar_alteracao_avancada(msg):
            pass # [4] Avançadas (Inf)
        elif self.habilitar_avancadas(msg):
            pass # [3] Avançadas
        elif self.submenu_avancado(msg):
            pass # [2] Avançadas
        elif self.confirmar_entradas(msg):
            pass # [3] Entradas
        elif self.habilitar_entradas(msg):
            pass # [2] Entradas
        elif self.confirmar_desligar_bot(msg):
            pass # [0] Desligar
        elif self.listar_usuarios(msg):
            pass # [0] Usuários
        elif self.carregar_config(msg):
            pass # [0] Configurações
        else: self.entrar({"text": "entrar"})
        
    def on__idle(self, event):
        '''
        Método que acontece quando está em espera
        '''
        print("Esperando outra pessoa...")
        return super().on__idle(event)

    def on_close(self, msg):
        '''
        Método que é chamado quando acaba uma conversa
        '''
        if self.autenticacao:
            MongoDB.modifica_usuario(self.informacoes, self.email)
        if self.id in ADMS:
            for key in mapeamento_avancado:
                mapeamento_avancado[key][1] = False

        print(f"Usuário {self.nome_usuario} saiu.\n")
        self.enviar_mensagem(MongoDB.infos["despedida"], 
            reply_markup = ReplyKeyboardRemove())

def printProgressBar (iteration, total, prefix = '', suffix = '', 
    decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    TAKEN FROM https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: print()

class Settings(amanobot.helper.CallbackQueryOriginHandler):
    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self._answer = ""

    def _get_settings(self, id, modalidade = "Todas"):
        if id in account_list:
            account = account_list[id]
            return True, exibir_configuracoes(account["mapping"], 
                account["informacoes"], modalidade)
        return False, "Você não está logado!"

    def on_callback_query(self, msg):
        _, from_id, query_data = amanobot.glance(
            msg, flavor='callback_query')

        if query_data == "show":
            authenticated, answer = self._get_settings(from_id)
        else:
            authenticated, answer = self._get_settings(from_id, query_data)

        keyboard = None
        if answer != self._answer and answer != "":
            self._answer = answer

            if authenticated: 
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text= "🧾 Geral 🌐", 
                        callback_data = "🧾 Geral 🌐"),
                    InlineKeyboardButton(text= "🧮 Gerenciamento 🖍", 
                        callback_data = "🧮 Gerenciamento 🖍")
                ], [
                    InlineKeyboardButton(text= "⚠️ Martingale e Soros ✅", 
                        callback_data = "⚠️ Martingale e Soros ✅"),
                    InlineKeyboardButton(text= "📈 Tendência e Notícias 📡", 
                        callback_data = "📈 Tendência e Notícias 📡"),
                ], [
                    InlineKeyboardButton(text= "🔩 Outras Opções ⚙️", 
                        callback_data = "🔩 Outras Opções ⚙️"),
                    InlineKeyboardButton(text= "✳️ Estratégias ❇️", 
                        callback_data = "✳️ Estratégias ❇️"),
                    InlineKeyboardButton(text= "✳️ Opções de estratégias ⚙️", 
                        callback_data = "✳️ Opções de estratégias ⚙️")
                ]])
            
            try: 
                result = self.editor.editMessageText(self._answer, 
                    reply_markup = keyboard, parse_mode = "Markdown")
                apply_entities_as_markdown(result['text'], [])
            except: pass

    def on__idle(self, event):
        time.sleep(5)
        self.editor.deleteMessage()
        try: self.close()
        except: pass

if __name__ == "__main__":
    print("Carregando...")
    printProgressBar(0, 20, prefix = 'Progress:', suffix = 'Complete', length = 30)
    for i in range(20):
        time.sleep(0.1)
        printProgressBar(i + 1, 20, prefix = 'Progress:', suffix = 'Complete', length = 50)

    problema = False
    bot = amanobot.DelegatorBot(TOKEN, [
        pave_event_space()(
            per_chat_id(), create_open, Assistente, timeout = 180),
        pave_event_space()(
            per_callback_query_origin(), create_open, Settings, timeout = 60),
    ])

    try:
        MessageLoop(bot).run_as_thread()
        print("\nEsperando comandos...")
        while rodando:
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    except ConnectionResetError:
        problema = True
    except Exception as e:	
        escreve_erros(e)
        problema = True

    MongoDB.close()

    if problema:
        print("\nAconteceu um erro, tentando se reconectar...")
        if os.name == "nt":
            os.system("powershell start powershell python, telegram.py")
        else:
            os.system("nohup python3 telegram.py &")
    else:
        if os.name != "nt":
            print("Deletando instâncias...")
            controlador.deletar_instancias()
    print("Bot desligado")
