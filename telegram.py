import time, pprint, amanobot, os, sys, json
from configparser import RawConfigParser
from datetime import timedelta, datetime

from amanobot.loop import MessageLoop
from amanobot.namedtuple import (
    ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove, InlineKeyboardMarkup, 
    InlineKeyboardButton)
from amanobot.delegate import (
    pave_event_space, per_chat_id, create_open)

from bot import pegar_comando, escreve_erros
from utils.catalogador import Catalogador
from utils.checador import checa_sinais
from controlador import Control
from database import Mongo


config = RawConfigParser()
config.read(".env")
MongoDB = Mongo()

TOKEN = config.get("TELEGRAM", "token")
BOTNAME = MongoDB.infos["nome"]

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
        if linha["tipo"] == "taxas": 
            lista_entradas.append(f"""
📊 Ativo: {linha['par']}
📈 Taxa: {linha['taxa']}""")
            continue
        direcao = linha["ordem"].lower()
        timeframe = linha['timeframe']
        if timeframe == 0:
            timeframe = "Padrão"
        else:
            timeframe = f"M{linha['timeframe']}"
        lista_entradas.append(f'''
📊 Ativo: {linha["par"]}
📅 Dia: {"/".join(list(map(strDateHour, linha["data"])))}
⏱ Hora: {":".join(list(map(strDateHour, linha["hora"])))}   
{'⬆' if direcao == "call" else '⬇'} Direção: {direcao.upper()} 
⏰ Período: {timeframe}
        ''')
    return lista_entradas

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
    "Mudar a correção": ["correcao", False, int],
    "Catalogar: Timeframe": ["cat_time", False, int],
    "Catalogar: Dias": ["cat_days", False, int],
    "Catalogar: Porcentagem": ["cat_perct", False, int],
    "Catalogar: Martingale": ["cat_mg", False, int],
}

# O bot
class Assistente(amanobot.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(Assistente, self).__init__(*args, **kwargs)
        self.autenticacao = False
        self.nome_usuario = ""
        self.email = ""

        self.entrada = False

        self.add_entrada = "-"        
        self.iniciar_operacao = False
        self.parar_bot = False
        self.operar_lista = True
        self.alteracoes_avancadas = {
            "adm_in": False,  # Adicionar novo ADM
            "adm_out": False,  # Remover um ADM
            "licenca": False, # Renovar licença
            "aprovar": False, # Aprovar usuário
            "remover": False, # Tirar um usuário cadastrado
            "apagar": False,  # Tirar um usuário em cadastro
            "plano": False    # Pra escolher o plano
        }

        self.mapeamento = {
            "Adicionar lista": ["lista", False, list],
            "Tipo de conta": ["tipo_conta", False, tuple], 
            "Tipo de lista": ["tipo_lista", False, tuple],
            "Lista escolhida": ["num_lista", False, tuple],
            "Valor de entrada": ["valor", False, float],
            "Tipo de gale": ["tipo_gale", False, tuple], 
            "Tipo de Stoploss": ["tipo_stop", False, tuple], 
            # "Scalper Loss": ["scalper_loss", False, int],
            # "Scalper Win": ["scalper_win", False, int],
            "Payout mínimo": ["minimo", False, int], 
            "StopLoss": ["stoploss", False, float],
            "StopWin": ["stopwin", False, float],

            "Tipo de martingale": ["tipo_martin", False, tuple],
            "Martingale na próxima": ["vez_gale", False, tuple],
            # "Ciclos de soros": ["ciclos_soros", False, str],
            # "Ciclos de gales": ["ciclos_gale", False, str],
            "Máximo de soros": ["max_soros", False, int],
            "Máximo de gales": ["max_gale", False, int],
            "Tipo soros": ["tipo_soros", False, tuple],

            "Seguir tendência": ["tendencia", False, bool],
            "Notícias: toros": ["toros", False, tuple],
            "Notícias: horas": ['noticias_hora', False, int],
            "Notícias: minutos": ['noticias_minuto', False, int],
            "Tipo de tendência": ["tipo_tendencia", False, tuple],
            "Período da tendência": ["periodo_tendencia", False, int],

            # "Paridade": ["paridade", False, str],
            # "Estratégia": ["estrategia", False, tuple],
            # "Tipo milhão": ["tipo_milhao", False, tuple],
            # "Auto VIP: Timeframe": ["autotime", False, tuple],
            # "Auto VIP: Gales": ["autogale", False, tuple],

            "Tipo par": ["tipo_par", False, tuple],
            "Timeframe": ["tempo", False, tuple],
            "Correção": ["correcao", False, int],
            "Delay": ["delay", False, float],
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
           f"Olá, eu sou seu assistente do {BOTNAME}.",
            delete = False, reply_markup = ReplyKeyboardMarkup(
                keyboard = [[KeyboardButton(text = "Entrar")]]))

    def enviar_mensagem(self, message, reply_markup = None, edit = False, delete = True, save = False):
        if edit:
            self.bot.editMessageText(self.message_id, message)
            if reply_markup:
                mensagem = self.sender.sendMessage("Escolha: ",
                    reply_markup = reply_markup)  
                self.bot.deleteMessage((self.chat_id, mensagem['message_id']))
        else:
            if delete and not save:
                self.bot.deleteMessage(self.message_id)
     
            mensagem = self.sender.sendMessage(message,
                reply_markup = reply_markup)
            if not save:
                self.message_id = (self.chat_id, mensagem['message_id'])

    def entrar(self):
        if not self.autenticacao:
            self.enviar_mensagem("Digite o seu e-mail para continuar:", 
                reply_markup = ReplyKeyboardRemove())
            self.entrada = True
        else:
            self.enviar_mensagem("Você já está logado")
            self.comandos()

    def login(self, msg):
        '''
        Método para o login, verifica se o ID
        Está em análise ou já aprovado.
        '''
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
                restante = str(
                    timedelta(seconds = restante)
                ).replace('days', 'dias')
                self.enviar_mensagem(
                    f"E-mail autenticado, seja bem-vindo Sr(a) {self.nome_usuario} sua licença expira em: {restante[:-10]}.",
                    save = True)
                self.comandos()
            else:
                self.enviar_mensagem("Sua licença expirou, peça para o administrador renovar.", save = True)
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

    def gerenciar(self):
        '''
        Comandos para administradores
        '''
        if self.id not in ADMS:
            self.enviar_mensagem("Usuário não tem permissão")
            return False

        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "Configurações avançadas" ),
             KeyboardButton( text = "Administração" )],
            [KeyboardButton( text = "Catalogação"),
             KeyboardButton( text = "Desligar VPS" )],
            [KeyboardButton( text = "Voltar ao menu" )]
        ])

        self.enviar_mensagem("Configurações avançadas para admnistradores:",
            reply_markup = teclado)


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
                [KeyboardButton( text = "Mudar a correção" ),
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
            """
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Catalogar: Timeframe" ),
                 KeyboardButton( text = "Catalogar: Dias" )],
                [KeyboardButton( text = "Catalogar: Porcentagem" ),
                 KeyboardButton( text = "Catalogar: Martingale" )],
                [KeyboardButton( text = "Gerenciar" )]
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
        default = MongoDB.get_avancadas()
        resultado = ""
        for key, value in default.items():
            if key not in ["_id"]:
                resultado += f"{key}: {value}\n"
        return resultado

    def adicionar_entrada(self, msg):
        '''
        Mudar caminho do arquivo de entradas
        '''
        if self.id in ADMS and msg['text'] == "Adicionar entradas":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "entrada 01" )],
                [KeyboardButton( text = "entrada 02" )],
                [KeyboardButton( text = "entrada 03" )],
                [KeyboardButton( text = "todas" )]
            ])

            self.enviar_mensagem("Qual arquivo de entradas:",
                reply_markup = teclado)
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
            self.gerenciar()

    def comandos(self):
        '''
        Menu principal quando já está logado.
        '''
        if self.autenticacao:
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Operar Lista" ),
                 KeyboardButton( text = "Adicionar lista" )],
                [KeyboardButton( text = "Catalogar sinais"),
                 KeyboardButton( text = "Verificar lista")],
                #  [KeyboardButton( text = "Operar Estratégias" ),
                #   KeyboardButton( text = "Operar Auto VIP")],
                [KeyboardButton( text = "Editar configurações" ),
                 KeyboardButton( text = "Ver lista de sinais" )],
                [KeyboardButton( text = "Parar Bot" ),
                 KeyboardButton( text = "Sair da conta" )]
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
        if texto == "Operar Lista":
            self.operar_lista = True
            return self.operar(msg)
        elif texto == "Operar Estratégias":
            self.informacoes["auto"] = False
            self.operar_lista = False
            return self.operar(msg)
        elif texto == "Operar Auto VIP":
            self.informacoes["auto"] = True
            self.operar_lista = False
            return self.operar(msg)
        elif texto == "Catalogar sinais":
            self.enviar_mensagem("Carregando...")
            sinais = MongoDB.get_entradas(3)
            conf = MongoDB.get_avancadas()
            conf_catalogador = (
                conf["cat_time"], conf["cat_days"], 
                conf["cat_perct"], conf["cat_mg"])
            if len(sinais) == 0 or (len(sinais) > 0 and 
                (datetime.now() - datetime.fromtimestamp(
                    sinais[0]["timestamp"])).days > 0 or 
                cache_catalogador != conf_catalogador):
                self.catalogar_sinais()
            self.informacoes["lista"] = MongoDB.get_entradas(3)
            self.enviar_mensagem(
                "Sinais catalogados adicionados à sua lista.", save = True)
            self.comandos()
            return True
        elif texto == "Ver configurações":
            self.enviar_mensagem(
                self.ver_configuracoes(), save = True)
            return True
        elif texto == "Editar configurações":
            return self.editar_configuracoes()
        elif texto == "Ver lista de sinais":
            return self.ver_lista()
        elif texto == "Sair da conta":
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
                                    text = "Ver relatório da operação" )],
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
        self.enviar_mensagem("Pegando relatórios...")
        try:
            if os.name != "nt":
                resultado = controlador.pegar_log(self.email)
                resultado = "\n".join(resultado.split("\n")[-50:])
            else: resultado = "Não disponível"
            self.enviar_mensagem(resultado, save = True)
        except Exception as e:
            self.enviar_mensagem(f"Recebi esse erro:\n{e}", save = True)
        self.comandos()

    def parar_operar(self, msg):
        '''
        Apenas para linux, dá kill na operação através do e-mail
        '''
        self.enviar_mensagem("Parando operação...")
        MongoDB.parar_operacao(self.email)
        if os.name != "nt":
            controlador.parar_operacao(self.email)
        self.enviar_mensagem("Operação cancelada.")
        self.comandos()

    def ver_lista(self):
        '''
        Mostra as listas de sinais (casa|pessoal)
        Devolve um boolean se está autenticado
        '''
        global entrada_01, entrada_02, entrada_03
        if self.autenticacao:
            def enviar_lista(label, lista):
                msg = "\n".join(lista)
                if len(msg) >  4000:
                    mensagens = [msg[x:x+4000] 
                        for x in range(0, len(msg), 4000)]
                else:
                    mensagens = [msg]
                for msg in mensagens:
                    self.enviar_mensagem(f"{label}:\n" +
                        msg, save = True)
            
            if self.informacoes['tipo_lista'] == "casa":
                self.enviar_mensagem("Entradas:", 
                    reply_markup = ReplyKeyboardRemove())
                
                enviar_lista("Lista 01", entrada_01)
                enviar_lista("Lista 02", entrada_02)
                enviar_lista("Lista 03", entrada_03)
            else:
                if self.informacoes['lista'] != []:
                    enviar_lista("Lista própria", carregar_entradas(
                            self.informacoes['lista']))
                else:
                    self.enviar_mensagem(
                        "Nenhuma lista registrada. Para adicionar: Conta > Adicionar lista.")
            self.comandos()
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def ver_configuracoes(self):
        '''
        Mostra as configurações de usuário
        Devolve um boolean se está autenticado.
        '''
        if self.autenticacao:
            
            headers = {
                "Tipo de conta": "Conta e listas",
                "Tipo de gale": "Gerenciamento",
                "Tipo de martingale": "Martingale e Soros",
                "Seguir tendência": "Tendência e notícias",
                "Tipo par": "Ajustes",
                "Paridade": "Auto Trade"
            }
            mensagem = ""
            for key, value in self.mapeamento.items():
                if value[0] not in ["lista", "tipo_lista", "num_lista"]:
                    if key in headers:
                        mensagem += f"\n⚙️ {headers[key]} ⚙️\n"
                    mensagem += f"{key}: {str(self.informacoes[value[0]]).replace('True', 'Sim').replace('False', 'Não')}\n"
            return mensagem
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def editar_configuracoes(self):
        '''
        Menu de opções para editar as configurações
        Devolve um boolean se está autenticado
        '''
        if self.autenticacao:
            self.enviar_mensagem(
                self.ver_configuracoes(), 
                reply_markup = ReplyKeyboardMarkup( keyboard = [
                    [KeyboardButton( text = "Conta e listas" ),
                     KeyboardButton( text = "Ajustes" )],
                    [KeyboardButton( text = "Gerenciamento" ),
                     KeyboardButton( text = "Martingale e Soros" )],
                    [KeyboardButton( text = "Tendência e notícias" )],
                    #  KeyboardButton( text = "Estratégias")],
                    [KeyboardButton( text = "Ver configurações" ), 
                     KeyboardButton( text = "Voltar ao menu" )]
            ], resize_keyboard = True))
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def submenu_configuracoes(self, msg):
        verificador, teclado = False, []
        if msg['text'] == 'Conta e listas':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de conta" ),
                 KeyboardButton( text = "Valor de entrada" )],
                [KeyboardButton( text = "Adicionar lista" ),
                 KeyboardButton( text = "Verificar lista")],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        elif msg['text'] == 'Gerenciamento':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de Stoploss" ),
                 KeyboardButton( text = "Tipo de gale" )],
                [KeyboardButton( text = "StopWin" ),
                 KeyboardButton( text = "StopLoss" )],
                # [KeyboardButton( text = "Scalper Win"),
                #  KeyboardButton( text = "Scalper Loss")],
                [KeyboardButton( text = "Payout mínimo" ),
                 KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Martingale e Soros':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de martingale" ),
                 KeyboardButton( text = "Martingale na próxima" )],
                [KeyboardButton( text = "Máximo de gales" ),
                 KeyboardButton( text = "Máximo de soros" )],
                # [KeyboardButton( text = "Ciclos de soros" ),
                #  KeyboardButton( text = "Ciclos de gales" )],
                # [KeyboardButton( text = "Tipo soros" ),
                 [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        elif msg['text'] == 'Tendência e notícias':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Notícias: toros"),
                 KeyboardButton( text = "Seguir tendência" )],
                [KeyboardButton( text = "Notícias: horas" ),
                 KeyboardButton( text = "Notícias: minutos" )],
                [KeyboardButton( text = "Tipo de tendência" ),
                 KeyboardButton( text = "Período da tendência" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == "Ajustes":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo par" ),
                 KeyboardButton( text = "Timeframe" )],
                [KeyboardButton( text = "Correção" ),
                 KeyboardButton( text = "Delay" )],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        elif msg['text'] == "Estratégias":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Paridade" ),
                 KeyboardButton( text = "Estratégia" ),
                 KeyboardButton( text = "Tipo milhão" )],
                [KeyboardButton( text = "Auto VIP: Gales" ),
                 KeyboardButton( text = "Auto VIP: Timeframe")],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        if verificador:
            self.enviar_mensagem("Qual das opções?", reply_markup = teclado)
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
            elif (value[0] == "tipo_lista" and 
                self.informacoes['plano'] == "teste"):
                self.enviar_mensagem(
                    "Você não tem acesso a lista da casa, peça um upgrade na sua conta.", save = True)
                return True
            elif value[2] == tuple:
                opcoes = {
                    "toros": [0, 1, 2, 3], "num_lista": [1, 2, 3],
                    "tempo": [1, 5, 15, 30], "autogale": [0, 1, 2],
                    "autotime": [1, 5, 15], "vez_gale": ["vela", "sinal"],
                    "tipo_par": ["binary", "digital", "auto"],
                    "tipo_lista": ["casa", "propria"],
                    "tipo_conta": ["treino", "real"],
                    "tipo_soros": ["normal", "ciclos"],
                    "tipo_stop": ["movel", "fixo"],
                    "tipo_milhao": ["Minoria", "Maioria"],
                    "tipo_gale": [
                        "martingale", "sorosgale", "nenhum"],  
                        # "ciclos",
                    "tipo_tendencia": [
                        "medias móveis simples", "velas"],
                    "tipo_martin": [
                        "seguro", "leve", "agressivo", "individual"],
                    "estrategia": ["Milhão", "MHI", "MHI2", 
                        "MHI3", 'C3', "MSF", "HOPE", "R7", 
                        "Vituxo", "Três Mosqueteiros",
                        "Padrão Impar", 'Três Vizinhos', 
                        'Torres Gêmeas', "Last of five",
                        "DAKA", "Padrão 23", "Power", 
                        "Melhor de 3", "Triplicação", 
                        "M5: Três Mosqueteiros", "GABA", 
                        "M5: Três Vizinhos", "Five Flip",
                        "M5: MHI", "M5: MHI2", "M5: MHI3", 
                        "M5: Torres Gêmeas", "M5: Milhão", 
                        "Primeiros trocados", "Half hour", 
                        "Hora do equilibrio", "Turn Over",
                        "M15: Torres Gêmeas", "M15: MHI",
                        "M15: MHI2", "M15: MHI3"]
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
                if value[2] == str and value[0] != "paridade":
                    mensagem = "Pegue os ciclos no site: https://argente123.github.io/Ciclos/"
                elif value[2] == list:
                    mensagem = """Envie a lista no formato:
    01/01/2000 13:00 EURUSD-OTC PUT M1
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
        global ADMS, BOTNAME, rodando, \
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
            BOTNAME = MongoDB.infos["nome"]
            ADMS = MongoDB.get_adms()
            entrada_01 = carregar_entradas(1)
            entrada_02 = carregar_entradas(2)
            entrada_03 = carregar_entradas(3)
            self.enviar_mensagem("Informações atualizadas.")
            self.gerenciar()
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
        resultados = checa_sinais(
            self.informacoes['lista'], 
            self.informacoes["tempo"])
        resultado = "\n".join(resultados)
        if len(resultado) > 4000:
            mensagens  = [resultado[x:x+4000] 
                for x in range(0, len(resultado), 4000)]
        else: mensagens = [resultado]

        for msg in mensagens:
            self.enviar_mensagem(msg, save = True)

    def catalogar_sinais(self):
        '''
        Cataloga os sinais e adiciona a lista 3
        '''
        global entrada_03, cache_catalogador
        catalogador = Catalogador(self.chat_id)
        conf = MongoDB.get_avancadas()
        cache_catalogador = (
            conf["cat_time"], conf["cat_days"], 
            conf["cat_perct"], conf["cat_mg"])
        lista = catalogador.catalogar(*cache_catalogador)

        if lista != []:
            MongoDB.set_entradas(3, lista)
            entrada_03 = carregar_entradas(3)
        else:
            self.enviar_mensagem(
                "Nenhum sinal encontrado...")

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
            self.enviar_mensagem("Adminstrador adicionado.")
            self.alteracoes_avancadas["adm_in"] = False
            return True
        elif self.alteracoes_avancadas['adm_out']:
            MongoDB.remover_adm(int(msg))
            ADMS = MongoDB.get_adms()
            self.enviar_mensagem("Adminstrador removido.")
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
            MongoDB.aprovar(
                self.alteracoes_avancadas['plano'], msg)
            self.enviar_mensagem("Usuário aprovado.")
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
        Mapea o dicionário para ver se há um valor verdadeiro
        Se houver verifica se o novo valor está correto
        Devolve um bool, usado para confirmar_alteracao/avancado
        '''
        def numerization(valor, func):
            try:
                return func(valor.strip().replace(",", "."))
            except: return False

        for key, value in dicionario.items():
            if value[1]:
                if value[2] in [int, float]:
                    novo = numerization(novo, value[2])
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
                    except Exception as e:
                        dicionario[key][1] = False
                        self.enviar_mensagem("Deve ser um número.", save = True)
                        return True
                elif value[2] == str and value[0] != "paridade":
                    try:
                        # novo = list(map(lambda x: list(
                        #     map(float, x.strip().split(","))), 
                        # novo.strip().split("\n"))) 
                        if novo != "0" and not numerization(novo, float):
                            novo = json.loads(novo)
                        else:
                            raise ValueError("JSON != int!")    
                    except Exception as e:
                        print(e)
                        self.enviar_mensagem(
                            "Não entendi, tente novamente: https://argente123.github.io/Ciclos/")
                        return True
                elif novo == "individual":
                    self.enviar_mensagem(
                        "Digite o fator do martingale:\nEx: 2.5", 
                        reply_markup = ReplyKeyboardRemove())
                    return True
                elif value[0] == "tipo_martin" and novo not in [
                    "seguro", "leve", "agressivo"]:
                    novo = float(novo.strip().replace(",", "."))
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
            self.gerenciar()
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
                self.enviar_mensagem("Alteração salva!")
                self.editar_configuracoes()
                return True
            return result
        return False

    def listar_usuarios(self):
        if os.name != "nt":
            instancias = controlador.mostrar_usuarios()
            for instancia, usuarios in instancias.items():
                self.enviar_mensagem(instancia, save = True)
                for usuario in usuarios:
                    self.enviar_mensagem(usuario, save = True)
        
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

    def on_chat_message(self, msg):
        '''
        Método que é chamado sempre que é digitado alguma coisa
        '''
        
        if self.entrada:
            self.login(msg)         # [0] Login
        elif self.iniciar_operacao:
            self.operar(msg)        # [3] Opções
        elif self.salvar_alteracoes_avancadas(msg) in [True, None]:
            if not self.alteracoes_avancadas['plano']:
                self.gerenciar()    # [4] Avançadas (ADM)
        elif "Parar Bot" in msg['text']:
            self.parar_operar(msg)  # [4] Opções
        elif msg['text'] == "Ver relatório da operação":
            self.ver_relatorio(msg) # [4] Opções
        elif msg['text'].capitalize() in ["Entrar", "/start"]:
            self.entrar()           # [1] Login
        elif msg['text'].capitalize() == 'Gerenciar':
            self.gerenciar()        # [1] Avançadas
        elif msg['text'].capitalize() in ["Voltar ao menu", "Menu"]:
            if not self.autenticacao: self.entrar()
            else: self.comandos()   # [1] Opções
        elif self.submenu_comandos(msg):
            pass                    # [2] Opções
        elif self.submenu_configuracoes(msg):
            pass                    # [1] Alterações
        elif self.adicionar_entrada(msg):
            pass                    # [1] Entradas
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
        elif self.parar_bot:
            if msg['text'] == "Sim":
                self.desligar_bot()
            else:
                self.parar_bot = False
                self.enviar_mensagem(
                    "Deixando o bot ligado", save = True)
                self.gerenciar()
        elif msg['text'].capitalize() == "Listar users":
            self.listar_usuarios()
        else:
            self.entrar()
        
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
    if iteration == total: 
        print()

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
