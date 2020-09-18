import time, pprint, amanobot, json, os, sys
from datetime import timedelta
from bot import pegar_comando, escreve_erros
from amanobot.loop import MessageLoop
from amanobot.namedtuple import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from amanobot.delegate import (
    pave_event_space, per_chat_id, create_open)
from database import *
from controlador import Control

TOKEN = "737574969:AAHgaEmqn2jkzSW5shewX-U1jS8R8-VpK1s"
bot_name = "robô MM_007"

# Funções
def strDateHour(number):
    '''
    Converte números de 1 dígito para 2 dígitos:
        0:0 -> 00:00
        2/1/2000 -> 02/01/2000
    params:
        number = tipo int
    return:
        string do resultado
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
    lista_entradas = []
    if type(opcao) != list:
        lista = MongoDB.get_entradas(opcao)
    else:
        lista = opcao
    for linha in lista:
        timeframe = linha['timeframe']
        if timeframe == 0:
            timeframe = "padrão"
        lista_entradas.append(f'''
📊 Ativo: {linha["par"]}
📅 Dia: {"/".join(list(map(strDateHour, linha["data"])))}
⏱Hora: {":".join(list(map(strDateHour, linha["hora"])))}   
➡ Direção: {linha["ordem"].upper()}   
🕒 Timeframe: M{timeframe}
        ''')
    return lista_entradas

def get_adms():
    return [x[0] for x in [list(value.values()) for value in list(MongoDB.ADMS.find())]]

# São atributos gerais para todas as contas
# Pois o objeto Assistente é instanciado por usuário 
adms = get_adms()
entrada_01 = carregar_entradas(1)
entrada_02 = carregar_entradas(2)
entrada_03 = carregar_entradas(3)

os.name = "nt"
if os.name != "nt":
    print("Entrou")
    controlador = Control()
rodando = True

mapeamento_avancado = {
    "Tipo de paridade": ["tipo_par", False, tuple],
    "Mudar timeframe": ["tempo", False, tuple],
    "Mudar a correção": ["correcao", False, int],
    "Mudar o delay": ["delay", False, float]
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
        self.alteracoes_avancadas = {
            "adm": False,     # Adicionar novo ADM
            "licenca": False, # Renovar licença
            "aprovar": False, # Aprovar usuário
            "remover": False, # Tirar um usuário cadastrado
            "apagar": False,  # Tirar um usuário em cadastro
            "plano": False    # Pra escolher o plano
        }

        self.mapeamento = {
            "Tipo de conta": ["tipo_conta", False, tuple], 
            "Tipo de lista": ["tipo_lista", False, tuple],
            "Lista escolhida": ["num_lista", False, tuple],
            
            "Valor de entrada": ["valor", False, float],
            "Gerenciamento": ["tipo_gale", False, tuple], 
            "Payout mínimo": ["minimo", False, int], 
            
            "StopWin": ["goal", False, float],
            "StopLoss": ["stoploss", False, float],
            "Máximo de gales": ["max_gale", False, tuple],
            "Máximo de soros": ["max_soros", False, int],
            
            "Tipo de martingale": ["tipo_martin", False, tuple],
            "Percentual do martin": ["percent_martin", False, float],
            "Martingale na próxima": ["entrada_martin", False, tuple],
            "Soros": ["soros", False, bool], 
            "Percentual da soros": ["percent_soros", False, float],
            
            "Seguir tendência": ["tendencia", False, bool],
            "Tipo de tendência": ["tipo_tendencia", False, tuple],
            "Período da tendência": ["periodo_tendencia", False, tuple],
            "Desvio da tendência": ["desvio_tendencia", False, float],
            "Ativar notícias": ["noticias", False, bool],
            "Filtro horas": ['noticias_hora', False, int],
            "Filtro minutos": ['noticias_minuto', False, int],
            
            "Paridade": ["tipo_par", False, tuple],
            "Timeframe": ["tempo", False, tuple],
            "Correção": ["correcao", False, int],
            "Delay": ["delay", False, float],
            
            "Adicionar lista": ["lista", False, list]
        }

        self.informacoes = {
            "tipo_conta": "treino",
            "valor": 2,
            "minimo": 0,
            "goal": 100,
            "soros": False,
            "percent_soros": 0,
            "stoploss": 20,
            "percent_martin": 0,
            "max_gale": 2,
            "max_soros": 1,
            "tipo_gale": "martin",
            "tipo_martin": "seguro",
            "tendencia": False,
            "tipo_tendencia": "velas",
            "periodo_tendencia": 21,
            "desvio_tendencia": 0.1,
            "noticias": False,
            "noticias_hora": 0,
            "noticias_minuto": 0,
            "tipo_lista": "propria",
            "lista": [],
            "plano": "comum",
            "tipo_par": "auto",
            "delay": False,
            "correcao": 1,
            "tempo": 5
        }

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

        self.enviar_mensagem(f"Olá, eu sou seu assistente do {bot_name}.", delete = False,
            reply_markup = ReplyKeyboardMarkup(
                keyboard = [[KeyboardButton(text = "Entrar")]]))

    def enviar_mensagem(self, message, reply_markup = None, edit = False, delete = True, save = False):
        if edit:
            self.bot.editMessageText(self.message_id, message)
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

    def login(self, msg):
        '''
        Método para o login, verifica se o ID
        Está em análise ou já aprovado.
        '''
        if self.autenticacao:
            self.enviar_mensagem("Você já está logado.")
            return False

        self.enviar_mensagem("Carregado...")
        email = msg['text'].lower()

        if MongoDB.Users_collection.find_one({"email": email}): 
            # Verifica se está no banco de dados e entra na conta
            self.email = msg["text"].lower()
            self.informacoes.update(MongoDB.get_user(self.email))
            restante = self.informacoes['timestamp'] - time.time()
            if restante > 0:
                self.entrada = False
                self.autenticacao = True
                self.enviar_mensagem(
                    f"E-mail autenticado, seja bem-vindo Sr(a) {self.nome_usuario} sua licença expira em: {str(timedelta(seconds = restante)).replace('days', 'dias')}", 
                    save = True)
                self.comandos()
            else:
                self.enviar_mensagem("Sua licença expirou, peça para o administrador renovar.", save = True)
                self.close()
        elif (MongoDB.verifica_cadastro(email)):
            self.enviar_mensagem("Seu e-mail ainda está em análise...",
                save = True)
            self.close()
        else:
            # Caso o usuário não estiver na lista de espera ele adiciona
            MongoDB.adicionar_cadastro(email)
            self.enviar_mensagem(
                f"Seu e-mail foi colocado para analise. Espere a confirmação do administrador e mande seu e-mail novamente para logar.",
                save = True)
            self.close()

    def gerenciar(self):
        '''
        Comandos para administradores
        '''
        if self.id not in adms:
            self.enviar_mensagem("Usuário não tem permissão")
            return False

        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "Configurações avançadas" )],
            [KeyboardButton( text = "Administração" )],
            [KeyboardButton( text = "Parar bot" )],
            [KeyboardButton( text = "Voltar ao menu" )]
        ])

        self.enviar_mensagem("Configurações avançadas para admnistradores:",
            reply_markup = teclado)


    def submenu_avancado(self, msg):
        if self.id not in adms:
            return False

        verificador = False
        if msg['text'] == "Configurações avançadas":
            self.ver_avancadas()
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Adicionar entradas" ),
                KeyboardButton( text = "Tipo de paridade" )],
                [KeyboardButton( text = "Mudar a correção" ),
                KeyboardButton( text = "Mudar o delay" )],
                [KeyboardButton( text = "Mudar timeframe" ),
                KeyboardButton( text = "Gerenciar" )]
            ])
            verificador = True
        elif msg['text'] == "Administração":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Aprovar usuários" ),
                KeyboardButton( text = "Renovar licença" )],
                [KeyboardButton( text = "Tirar de cadastro" ),
                KeyboardButton( text = "Remover usuários" )],
                [KeyboardButton( text = "Adicionar administrador" )],
                [KeyboardButton( text = "Gerenciar" )]
            ])
            verificador = True
        if verificador:
            self.enviar_mensagem("Escolha a opção:",
                reply_markup = teclado)        
            return True
        return False

    def ver_avancadas(self):
        '''
        Método que mostra do jeito cru as configurações avançadas
        '''
        if self.id not in adms:
            self.enviar_mensagem("Usuário não tem permissão")
            return False
        default = MongoDB.get_avancadas()
        resultado = ""
        for key, value in default.items():
            if key not in ["_id"]:
                resultado += f"{key}: {value}\n"
        self.enviar_mensagem(resultado, save = True,
            reply_markup = ReplyKeyboardRemove())

    def adicionar_entrada(self, msg):
        '''
        Mudar caminho do arquivo de entradas
        '''
        if self.id in adms and msg['text'] == "Adicionar entradas":
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
        if self.id not in adms:
            return False
        if msg['text'] in ["entrada 01", "entrada 02", "entrada 03", "todas"]:
            self.add_entrada = ("todas" if msg['text'] == "todas" else 
                                int(msg['text'].split()[1].strip("0")))
            self.enviar_mensagem('''Mande a lista.
Caso a opção for todas, então não esqueça de especificar acima de cada lista: [0x]
Onde x seria 1, 2, 3 a depender da lista''',
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
        if self.id not in adms:
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
                processa_entradas(self.add_entrada, msg['text'].split("\n"))
            
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
                [KeyboardButton( text = "Operação" )],
                [KeyboardButton( text = "Ver configurações" )],
                [KeyboardButton( text = "Editar configurações" )],
                [KeyboardButton( text = "Ver lista de sinais" )]
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
        if texto == "Operação":
            return self.operar(msg)
        elif texto == "Ver configurações":
            return self.ver_configuracoes()
        elif texto == "Editar configurações":
            return self.editar_configuracoes()
        elif texto == "Ver lista de sinais":
            return self.ver_lista()
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
                    edit = True, reply_markup = ReplyKeyboardRemove())   
                self.iniciar_operacao = False
                self.informacoes["operando"] = True
                MongoDB.modifica_usuario(self.informacoes, self.email)
                
                if os.name == "nt": # No windows 
                    os.system(f"powershell start powershell python, bot.py, -o, {self.email}, {msg['text']}, {self.id}")
                else:
                    controlador.adicionar_pessoa(self.email, msg['text'], self.id)
                self.enviar_mensagem("Operação iniciada. Se em 5min eu não avisar que está conectado, reincie a operação.",
                    edit = True)
                self.comandos()
            else:
                temporario = MongoDB.get_user(self.email)

                if not temporario['operando']:
                    self.enviar_mensagem("Digite sua senha (não guardamos a sua senha, você terá que fazer isso todas as vezes): ", 
                        edit = True, reply_markup = ReplyKeyboardRemove())
                    self.iniciar_operacao = True
                
                else:
                    self.enviar_mensagem("Você quer parar a operação ou ver o relatório?",
                        edit = True, reply_markup = ReplyKeyboardMarkup(
                            keyboard = [
                                [KeyboardButton( text = "Ver relatório" )],
                                [KeyboardButton( text = "Parar operação" )]
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
            resultado = controlador.pegar_log(self.email)
            resultado = "\n".join(resultado.split("\n")[-50:])
            self.enviar_mensagem(resultado, edit = True)
        except Exception as e:
            self.enviar_mensagem("Recebi esse erro:\n" + str(e), edit = True)
        self.comandos()

    def parar_operar(self, msg):
        '''
        Apenas para linux, dá kill na operação através do e-mail
        '''
        self.enviar_mensagem("Parando operação...")
        MongoDB.Users_collection.find_one_and_update({'email': self.email}, {'$set' : {'operando': False}})
        if os.name == "nt":
            pass
        else:
            controlador.parar_operacao(self.email)
        self.enviar_mensagem("Operação cancelada.", edit = True)
        self.comandos()

    def ver_lista(self):
        '''
        Mostra as listas de sinais (casa|pessoal)
        Devolve um boolean se está autenticado
        '''
        if self.autenticacao:
            if self.informacoes['tipo_lista'] == "casa":
                self.enviar_mensagem("Entradas:", 
                    reply_markup = ReplyKeyboardRemove())
                
                self.enviar_mensagem("Lista 01:" +
                    "\n".join(entrada_01), save = True)
                
                self.enviar_mensagem("Lista 02:" +
                    "\n".join(entrada_02), save = True)
                
                self.enviar_mensagem("Lista 03:" +
                    "\n".join(entrada_03), save = True)
                self.comandos()
                return True
            else:
                if self.informacoes != []:
                    self.enviar_mensagem("\n".join(
                        carregar_entradas(
                            self.informacoes['lista'])))
                else:
                    self.enviar_mensagem(
                        "Nenhuma lista registrada. Adicione em Conta > Adicionar lista")
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
                "Valor de entrada": "Entrada",
                "StopWin": "Limites",
                "Tipo de martingale": "Martingale e Soros",
                "Seguir tendência": "Tendência",
                "Paridade": "Ajustes"
            }
            mensagem = ""
            for key, value in self.mapeamento.items():
                if value[0] not in ["lista"]:
                    if key in headers:
                        mensagem += f"\n⚙️ {headers[key]} ⚙️\n"
                    mensagem += f"{key}: {str(self.informacoes[value[0]]).replace('True', 'Sim').replace('False', 'Não')}\n"
            self.enviar_mensagem(mensagem)
            return True
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
                "O que você deseja alterar?", 
                reply_markup = ReplyKeyboardMarkup( keyboard = [
                    [KeyboardButton( text = "Conta e listas" ),
                    KeyboardButton( text = "Entrada" )],
                    [KeyboardButton( text = "Limites" ),
                    KeyboardButton( text = "Tendência" )],
                    [KeyboardButton( text = "Martingale e Soros" ),
                    KeyboardButton( text = "Ajustes" )],
                    [KeyboardButton( text = "Voltar ao menu" )]
            ], resize_keyboard = True))
            return True
        else:
            self.enviar_mensagem("Usuário não autenticado")
        return False

    def submenu_configuracoes(self, msg):
        verificador = False
        if msg['text'] == 'Conta e listas':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de conta" ),
                KeyboardButton( text = "Adicionar lista" )],
                [KeyboardButton( text = "Tipo de lista" ),
                KeyboardButton( text = "Lista escolhida" )],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        elif msg['text'] == 'Entrada':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Valor de entrada" )],
                [KeyboardButton( text = "Gerenciamento" )],
                [KeyboardButton( text = "Payout mínimo" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Tendência':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Seguir tendência" ),
                KeyboardButton( text = "Ativar notícias" )],
                [KeyboardButton( text = "Filtro horas" ),
                KeyboardButton( text = "Filtro minutos" )],
                [KeyboardButton( text = "Tipo de tendência" ),
                KeyboardButton( text = "Período" ),
                KeyboardButton( text = "Desvio" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Limites':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "StopWin" ),
                KeyboardButton( text = "StopLoss" )],
                [KeyboardButton( text = "Máximo de gales" ),
                KeyboardButton( text = "Máximo de soros" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Martingale e Soros':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Martingale na próxima" )],
                [KeyboardButton( text = "Tipo de martingale" ),
                KeyboardButton( text = "Percentual do martin" )],
                [KeyboardButton( text = "Soros" ),
                KeyboardButton( text = "Percentual da soros" )],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        elif msg['text'] == "Ajustes":
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Paridade" ),
                KeyboardButton( text = "Timeframe" )],
                [KeyboardButton( text = "Correção" ),
                KeyboardButton( text = "Delay" )],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        if verificador:
            self.enviar_mensagem(
                "Qual das opções?", 
                reply_markup = teclado)
            return True
        return False

    def mapear(self, dicionario, text):
        '''
        Faz o mapeamento de botões para os métodos habilitar
        '''
        for key, value in dicionario.items():
            if text == key:
                mensagem = "Escolha uma das opções abaixo:"
                if value[2] == bool:
                    teclado = ReplyKeyboardMarkup( 
                        keyboard = [
                        [KeyboardButton( text = "Sim" ),
                        KeyboardButton( text = "Não" )]])
                elif (self.informacoes['plano'] == "comum" and 
                      value[0] == "tipo_lista"):
                    self.enviar_mensagem("Você não tem acesso a lista da casa, peça um upgrade na sua conta.")
                    return False
                elif value[2] == tuple:
                    opcoes = {
                        "tipo_conta": ["treino", "real"],
                        "max_gale": [0, 1, 2],
                        "tempo": [1, 5, 15],
                        "num_lista": [1, 2, 3],
                        "tipo_par": ["binary", "digital", "auto"],
                        "tipo_lista": ["casa", "propria"],
                        "tipo_gale": [
                            "martin", "soros", "nenhum"],
                        "tipo_tendencia": [
                            "medias móveis", "velas"],
                        "tipo_martin": [
                            "seguro", "leve", "agressivo",
                            "porcento", "individual"],
                        "entrada_martin": ["vela", "sinal"]
                    }
                    if value[0] in ["tipo_martin", "tipo_par"]:
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
                    mensagem = "Digite a nova informação: "
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
        global adms, entrada_01, entrada_02, entrada_03, rodando
        
        if self.id not in adms:
            return False
        if msg['text'] == 'Adicionar administrador':
            self.enviar_mensagem("Coloque o ID do telegram:",
                reply_markup = ReplyKeyboardRemove())
            self.alteracoes_avancadas['adm'] = True
        elif msg['text'] == "Atualizar informações":
            self.enviar_mensagem("Atualizando...")
            adms = get_adms()
            entrada_01 = carregar_entradas(1)
            entrada_02 = carregar_entradas(2)
            entrada_03 = carregar_entradas(3)
            self.enviar_mensagem("Informações atualizadas.")
        elif msg['text'] in [
            "Aprovar usuários", "Renovar licença", 
            "Tirar de cadastro", "Remover usuários"]:
            # Captura todos os usuários
            if msg['text'] in ["Aprovar usuários", "Tirar de cadastro"]:
                users = MongoDB.Users_em_aprovacao.find()
            else:
                users = MongoDB.Users_collection.find()
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
            else:
                self.enviar_mensagem("Nenhum usuário no banco")
        elif msg['text'] == "Parar bot":
            self.parar_bot = True
            self.enviar_mensagem("Tem certeza?",
                reply_markup = ReplyKeyboardMarkup(keyboard = [
                    [KeyboardButton( text = "Sim" ),
                    KeyboardButton( text = "Não" )]]))
        else:
            return self.mapear(mapeamento_avancado, msg['text'])
        return True

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
        global adms
        if self.id not in adms:
            return False
        msg = msg['text']
        if self.alteracoes_avancadas['adm']:
            MongoDB.adiciona_adm(int(msg))
            adms = get_adms()
            self.enviar_mensagem("Adminstrador adicionado.")
            self.alteracoes_avancadas["adm"] = False
            return True
        elif self.alteracoes_avancadas['plano'] == True:
            self.enviar_mensagem("Escolha o tipo de plano",
                reply_markup = ReplyKeyboardMarkup(keyboard = [
                    [KeyboardButton( text = "comum" ),
                    KeyboardButton( text = "premium" )]]))
            self.alteracoes_avancadas['plano'] = msg
            return False
        elif self.alteracoes_avancadas['aprovar']:
            MongoDB.aprovar(
                self.alteracoes_avancadas['plano'], msg)
            self.enviar_mensagem("Usuário aprovado.")
            self.alteracoes_avancadas["aprovar"] = False
            return True
        elif self.alteracoes_avancadas['licenca']:
            MongoDB.renovar_licenca(
                self.alteracoes_avancadas['plano'], msg)
            self.enviar_mensagem("Licença renovada")
            self.alteracoes_avancadas["licenca"] = False
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
        for key, value in dicionario.items():
            if value[1]:
                if value[2] in [int, float]:
                    try:
                        novo = value[2](
                            novo.strip().replace(",", ".").replace("%", ""))
                    except Exception as e:
                        if value[0] == "delay":
                            novo = False
                        else:
                            print(e)
                            self.enviar_mensagem("Deve ser um número! Tente novamente")
                            return False
                elif value[2] == list:
                    novo = self.pegar_entrada(novo.split("\n"))
                elif value[2] == bool:
                    novo = bool(novo.strip() == "Sim")
                elif value[0] in ["tempo", "max_gale"]:
                    try:
                        novo = int(novo)
                    except Exception as e:
                        dicionario[key][1] = False
                        self.enviar_mensagem("Deve ser um número.")
                        return False
                elif novo == "individual":
                    self.enviar_mensagem(
                        "Digite o fator do martingale:\nEx: 2.5", 
                        reply_markup = ReplyKeyboardRemove())
                    return False
                elif value[0] == "tipo_martin" and novo not in [
                    "seguro", "leve", "agressivo", "porcento"]:
                    novo = float(novo.strip().replace(",", "."))
                dicionario[key][1] = False
                return value[0], novo
        return False

    def confirmar_alteracao_avancada(self, msg):
        '''
        Método que altera as informações avançadas
        '''
        if self.id not in adms:
            return False
        result = self.confirmar_mapeamento(mapeamento_avancado, msg['text'])
        if result:
            info, valor = result
            MongoDB.modifica_avancadas(info, valor)
            self.enviar_mensagem(f"Valor salvo.")
            self.ver_avancadas()
            self.gerenciar()
            return True
        return False

    def confirmar_alteracao(self, msg):
        '''
        Altera a informação no dicionário e avisa se deu certo
        Devolvendo um bool se completou a alteração
        '''
        if self.autenticacao:
            result = self.confirmar_mapeamento(self.mapeamento, msg['text'])
            if result:
                info, valor = result
                self.informacoes[info] = valor
                self.enviar_mensagem("Alteração salva!")
                self.editar_configuracoes()
                self.ver_configuracoes()
                return True
        return False

    def desligar_bot(self):
        global rodando
        if os.name != "nt":
            self.enviar_mensagem("Deletando todas as instâncias...")
            usuarios = controlador.deletar_instancias()
            self.enviar_mensagem("Resetando o banco de dados...")
            for email in usuarios:
                MongoDB.Users_collection.find_one_and_update(
                    {'email': email}, {'$set' : {'operando': False}})
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
        elif msg['text'] == "Parar operação":
            self.parar_operar(msg)  # [4] Opções
        elif msg['text'] == "Ver relatório":
            self.ver_relatorio(msg) # [4] Opções
        elif msg['text'] == "Entrar":
            self.entrar()           # [1] Login
        elif msg['text'] == 'Gerenciar':
            self.gerenciar()        # [1] Avançadas
        elif msg['text'] == "Voltar ao menu":
            if not self.autenticacao: self.entrar()
            else: self.comandos()   # [1] Opções
        elif self.submenu_comandos(msg):
            pass                    # [2] Opções
        elif self.submenu_configuracoes(msg):
            pass                    # [1] Alterações
        elif self.adicionar_entrada(msg):
            pass                    # [1] Entradas
        elif self.salvar_alteracoes_avancadas(msg):
            self.gerenciar()        # [4] Avançadas (ADM)
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
        if self.id in adms:
            for key in mapeamento_avancado:
                mapeamento_avancado[key][1] = False

        print(f"Usuário {self.nome_usuario} saiu.\n")
        self.enviar_mensagem(
            "Obrigado pela preferência, irei atender outras pessoas, qualquer coisa é só chamar.", 
            reply_markup = ReplyKeyboardRemove())

def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
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
            per_chat_id(), create_open, Assistente, timeout = 60),
    ])

    try:
        MessageLoop(bot).run_as_thread()
        print("\nEsperando comandos...")
        while rodando:
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    except Exception as e:	
        escreve_erros(e)
        problema = True

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
