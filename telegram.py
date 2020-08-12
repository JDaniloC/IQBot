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

TOKEN = "1354635217:AAG1EbTt772cwPh008Ud3uBqyxyS28LXZao"
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
    if type(opcao) != []:
        lista = MongoDB.get_entradas(opcao)
    else:
        lista = opcao
    for linha in lista:
        lista_entradas.append(f'''
📊 Ativo: {linha["par"]}
📅 Dia: {"/".join(list(map(strDateHour, linha["data"])))}
⏱Hora: {":".join(list(map(strDateHour, linha["hora"])))}   
➡Direção: {linha["ordem"].upper()}   
        
        ''')
    return lista_entradas

def get_adms():
    return [x[0] for x in [list(value.values()) for value in list(MongoDB.ADMS.find())]]

# São atributos gerais para todas as contas
# Pois o objeto Assistente é instanciado por usuário 
adms = get_adms()
entrada_1gale = carregar_entradas(1)
entrada_2gale = carregar_entradas(2)
if os.name != "nt":
    controlador = Control()
rodando = True

mapeamento_avancado = {
    "Tipo de paridade": ["tipo_par", False, tuple],
    "Ativar OTC": ["otc", False, bool],
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

        self.add_entrada = "0"        
        self.iniciar_operacao = False
        self.parar_bot = False
        self.alteracoes_avancadas = {
            "adm": False,     # Adicionar novo ADM
            "licenca": False, # Renovar licença
            "aprovar": False, # Aprovar usuário
            "remover": False, # Tirar um usuário cadastrado
            "apagar": False   # Tirar um usuário em cadastro
        }

        self.mapeamento = {
            "Tipo de conta": ["tipo_conta", False, tuple], 
            "Valor de entrada": ["valor", False, float],
            "Payout mínimo": ["minimo", False, int], 
            "StopWin": ["goal", False, float],
            "Soros": ["soros", False, bool], 
            "Percentual da soros": [
                "percent_soros", False, float],
            "StopLoss": ["stoploss", False, float],
            "Gerenciamento": [
                "tipo_gale", False, tuple], 
            "Percentual do martin": [
                "percent_martin", False, float],
            "Máximo de gales": [
                "max_gale", False, tuple],
            "Tipo de martingale": [
                "tipo_martin", False, tuple],
            "Seguir tendência": [
                "tendencia", False, bool],
            "Tipo de tendência": [
                "tipo_tendencia", False, tuple],
            "Período da tendência": [
                "periodo_tendencia", False, tuple],
            "Desvio da tendência": [
                "desvio_tendencia", False, float],
            "Adicionar lista": ["lista", False, list],
            "Tipo de lista": ["tipo_lista", False, tuple]
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
            "tipo_gale": "martin",
            "tipo_martin": "seguro",
            "tendencia": False,
            "tipo_tendencia": "velas",
            "periodo_tendencia": 21,
            "desvio_tendencia": 0.1,
            "tipo_lista": "propria",
            "lista": [],
            "plano": "comum"
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

        self.sender.sendMessage(f"Olá, eu sou seu assistente do {bot_name}.", 
            reply_markup = ReplyKeyboardMarkup(
                keyboard = [[KeyboardButton(text = "Entrar")]]))

    def entrar(self):
        if not self.autenticacao:
            self.sender.sendMessage("Digite o seu e-mail para continuar:", 
                reply_markup = ReplyKeyboardRemove())
            self.entrada = True
        else:
            self.sender.sendMessage("Você já está logado")

    def login(self, msg):
        '''
        Método para o login, verifica se o ID
        Está em análise ou já aprovado.
        '''
        if self.autenticacao:
            self.sender.sendMessage("Você já está logado.")
            return False

        self.sender.sendMessage("Carregado...")
        email = msg['text'].lower()

        if MongoDB.Users_collection.find_one({"email": email}): 
            # Verifica se está no banco de dados e entra na conta
            self.email = msg["text"].lower()
            self.informacoes.update(MongoDB.get_user(self.email))
            restante = self.informacoes['timestamp'] - time.time()
            if restante > 0:
                self.entrada = False
                self.autenticacao = True
                self.sender.sendMessage(
                    f"E-mail autenticado, seja bem-vindo Sr(a) {self.nome_usuario} sua licença expira em: {str(timedelta(seconds = restante)).replace('days', 'dias')}")
                self.comandos()
            else:
                self.sender.sendMessage("Sua licença expirou, peça para o administrador renovar.")
                self.close()
        elif (MongoDB.verifica_cadastro(email)):
            self.sender.sendMessage("Seu e-mail ainda está em análise...")
            self.close()
        else:
            # Caso o usuário não estiver na lista de espera ele adiciona
            MongoDB.Users_em_aprovacao.insert_one(
                {"email":email})
            MongoDB.aprovar(email)
            self.sender.sendMessage("Usuário aprovado.")
            # self.sender.sendMessage(f"Seu e-mail foi colocado para analise. Espere a confirmação do administrador e mande seu e-mail novamente para logar.")
            self.close()

    def gerenciar(self):
        '''
        Comandos para administradores
        '''
        if self.id not in adms:
            self.sender.sendMessage("Usuário não tem permissão")
            return False

        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "Configurações avançadas" )],
            [KeyboardButton( text = "Administração" )],
            [KeyboardButton( text = "Parar bot" )],
            [KeyboardButton( text = "Voltar ao menu" )]
        ])

        self.sender.sendMessage("Configurações avançadas para admnistradores:",
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
                [KeyboardButton( text = "Ativar OTC" ),
                KeyboardButton( text = "Mudar timeframe" )],
                [KeyboardButton( text = "Mudar a correção" ),
                KeyboardButton( text = "Mudar o delay" )],
                [KeyboardButton( text = "Atualizar informações" )],
                [KeyboardButton( text = "Gerenciar" )]
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
            self.sender.sendMessage("Escolha a opção:",
                reply_markup = teclado)        
            return True
        return False

    def ver_avancadas(self):
        '''
        Método que mostra do jeito cru as configurações avançadas
        '''
        if self.id not in adms:
            self.sender.sendMessage("Usuário não tem permissão")
            return False
        default = MongoDB.get_avancadas()
        resultado = ""
        for key, value in default.items():
            if key not in ["_id", "arquivo"]:
                resultado += f"{key}: {value}\n"
        self.sender.sendMessage(resultado,
            reply_markup = ReplyKeyboardRemove())

    def adicionar_entrada(self, msg):
        '''
        Mudar caminho do arquivo de entradas
        '''
        if self.id not in adms:
            self.sender.sendMessage("Usuário não tem permissão")
            return False
       
        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "1 gale" )],
            [KeyboardButton( text = "2 gales" )],
            [KeyboardButton( text = "ambos" )]
        ])

        self.sender.sendMessage("Qual arquivo de entradas:",
            reply_markup = teclado)

    def habilitar_entradas(self, msg):
        '''
        Método que habilita a espera por uma nova lista
        '''
        if self.id not in adms:
            return False
        if msg['text'] in ["1 gale", "2 gales", "ambos"]:
            self.add_entrada = "ambos" if msg['text'] == "ambos" else msg['text'].split()[0]
            self.sender.sendMessage('''Mande a lista.
            Lembrando que na opção ambos é necessário colocar 1 gale/2 gales antes da lista especificando qual lista irá entrar.''',
                reply_markup = ReplyKeyboardRemove())            

    def pegar_entrada(self, entradas):
        '''
        Método que recebe as entradas e verifica se há um comando
        Devolve a lista de entradas que conseguiu extrair
        '''
        lista = []
        for linha in entradas:
            nova = pegar_comando(linha)
            if nova["data"] != [1, 1, 2000]:
                lista.append(nova)
        return lista

    def confirmar_entradas(self, msg):
        '''
        Método que recebe a mensagem de entradas, trata e salva.
        '''
        global entrada_1gale, entrada_2gale
        if self.id not in adms:
            return
        if self.add_entrada != "0":
            self.sender.sendMessage("Processando...")
            # Procura o início das velas
            if self.add_entrada == "ambos":
                para_verificar = {1:[], 2:[]}
                primeiro, segundo = False, False
                for linha in msg['text'].split("\n"):
                    if "1 gal" in linha:
                        primeiro, segundo = True, False
                    elif "2 gal" in linha:
                        primeiro, segundo = False, True
                    elif primeiro and linha not in ["", "\n"]:
                        para_verificar[1].append(linha)
                    elif segundo and linha not in ["", "\n"]:
                        para_verificar[2].append(linha)
                primeiro = self.pegar_entrada(para_verificar[1])
                segundo = self.pegar_entrada(para_verificar[2])
            elif self.add_entrada == "1":
                primeiro = self.pegar_entrada(
                    msg['text'].split("\n"))
            elif self.add_entrada == "2":
                segundo = self.pegar_entrada(
                    msg['text'].split("\n"))
            
            if self.add_entrada in ["ambos", "1"]:
                MongoDB.set_entradas(1, primeiro)
            if self.add_entrada in ["ambos", "2"]:
                MongoDB.set_entradas(2, segundo)
            
            entrada_1gale = carregar_entradas(1)
            entrada_2gale = carregar_entradas(2)
            
            self.add_entrada = "0"
            self.sender.sendMessage("Salvo")
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

            self.sender.sendMessage("O que deseja?", 
                reply_markup = teclado)
        else:
            self.sender.sendMessage("Usuário não autenticado")
    
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
            self.sender.sendMessage("Carregando...")

            if self.iniciar_operacao:
                self.sender.sendMessage("Iniciando operação, tenha paciência, isso pode demorar.",
                    reply_markup = ReplyKeyboardRemove())   
                self.iniciar_operacao = False
                self.informacoes["operando"] = True
                MongoDB.modifica_usuario(self.informacoes, self.email)
                
                if os.name == "nt": # No windows 
                    os.system(f"powershell start powershell python, bot.py, -o, {self.email}, {msg['text']}, {self.id}")
                else:
                    controlador.adicionar_pessoa(self.email, msg['text'], self.id)
                self.sender.sendMessage("Operação iniciada. Se em 5min eu não avisar que está conectado, reincie a operação.")
                self.comandos()
            else:
                temporario = MongoDB.get_user(self.email)

                if not temporario['operando']:
                    self.sender.sendMessage("Digite sua senha (não guardamos a sua senha, você terá que fazer isso todas as vezes): ", 
                    reply_markup = ReplyKeyboardRemove())
                    self.iniciar_operacao = True
                
                else:
                    self.sender.sendMessage("Você quer parar a operação ou ver o relatório?",
                        reply_markup = ReplyKeyboardMarkup(
                            keyboard = [
                                [KeyboardButton( text = "Ver relatório" )],
                                [KeyboardButton( text = "Parar operação" )]
                            ]
                        ))
            return True
        else:
            self.sender.sendMessage("Usuário não autenticado")
        return False

    def ver_relatorio(self, msg):
        self.sender.sendMessage("Pegando relatórios...")
        try:
            resultado = controlador.pegar_log(self.email)
            resultado = "\n".join(resultado.split("\n")[-50:])
            self.sender.sendMessage(resultado)
        except Exception as e:
            self.sender.sendMessage("Recebi esse erro:\n", e)
        self.comandos()

    def parar_operar(self, msg):
        '''
        Apenas para linux, dá kill na operação através do e-mail
        '''
        self.sender.sendMessage("Parando operação...")
        MongoDB.Users_collection.find_one_and_update({'email': self.email}, {'$set' : {'operando': False}})
        if os.name == "nt":
            pass
        else:
            controlador.parar_operacao(self.email)
        self.sender.sendMessage("Operação cancelada.")
        self.comandos()

    def ver_lista(self):
        '''
        Mostra as listas de sinais (casa|pessoal)
        Devolve um boolean se está autenticado
        '''
        if self.autenticacao:
            if self.informacoes['tipo_lista'] == "casa":
                self.sender.sendMessage("Entradas:", 
                    reply_markup = ReplyKeyboardRemove())
                
                self.sender.sendMessage("1 Gale:")
                self.sender.sendMessage(
                    "\n".join(entrada_1gale))
                
                self.sender.sendMessage("2 Gales:")
                self.sender.sendMessage(
                    "\n".join(entrada_2gale))
                self.comandos()
                return True
            else:
                self.sender.sendMessage("\n".join(
                    carregar_entradas(
                        self.informacoes['lista'])))
        else:
            self.sender.sendMessage("Usuário não autenticado")
        return False

    def ver_configuracoes(self):
        '''
        Mostra as configurações de usuário
        Devolve um boolean se está autenticado.
        '''
        if self.autenticacao:
            mensagem = ""
            for key, value in self.mapeamento.items():
                if value[0] not in ["lista", "tipo_lista", "plano"]:
                    mensagem += key + ": " + str(self.informacoes[value[0]]).replace("True", "Sim").replace("False", "Não") + "\n"
            self.sender.sendMessage(mensagem)
            self.comandos()
            return True
        else:
            self.sender.sendMessage("Usuário não autenticado")
        return False

    def editar_configuracoes(self):
        '''
        Menu de opções para editar as configurações
        Devolve um boolean se está autenticado
        '''
        if self.autenticacao:
            self.sender.sendMessage(
                "O que você deseja alterar?", 
                reply_markup = ReplyKeyboardMarkup( keyboard = [
                    [KeyboardButton( text = "Conta" ),
                    KeyboardButton( text = "Entrada" )],
                    [KeyboardButton( text = "Limites" ),
                    KeyboardButton( text = "Tendência" )],
                    [KeyboardButton( text = "Martingale e Soros" )],
                    [KeyboardButton( text = "Voltar ao menu" )]
            ], resize_keyboard = True))
            return True
        else:
            self.sender.sendMessage("Usuário não autenticado")
        return False

    def submenu_configuracoes(self, msg):
        verificador = False
        if msg['text'] == 'Conta':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de conta" )],
                [KeyboardButton( text = "Tipo de lista" )],
                [KeyboardButton( text = "Adicionar lista" )],
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
                [KeyboardButton( text = "Seguir tendência" )],
                [KeyboardButton( text = "Tipo de tendência" )],
                [KeyboardButton( text = "Período" ),
                KeyboardButton( text = "Desvio" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Limites':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "StopWin" )],
                [KeyboardButton( text = "StopLoss" )],
                [KeyboardButton( text = "Máximo de gales" )],
                [KeyboardButton( text = "Editar configurações" )]
                ])
            verificador = True
        elif msg['text'] == 'Martingale e Soros':
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Tipo de martingale" ),
                KeyboardButton( text = "Percentual do martin" )],
                [KeyboardButton( text = "Soros" ),
                KeyboardButton( text = "Percentual da soros" )],
                [KeyboardButton( text = "Editar configurações" )]])
            verificador = True
        if verificador:
            self.sender.sendMessage(
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
                elif value[2] == tuple:
                    opcoes = {
                        "tipo_conta": ["treino", "real"],
                        "max_gale": [1, 2],
                        "tempo": [1, 5, 15],
                        "tipo_par": ["binary", "digital", "auto"],
                        "tipo_lista": ["casa", "propria"],
                        "tipo_gale": [
                            "martin", "soros"],
                        "tipo_tendencia": [
                            "bollinger", "velas"],
                        "tipo_martin": [
                            "seguro", "leve", "agressivo",
                            "porcento", "individual"]
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
                elif value[0] == "tipo_lista" and self.informacoes['plano'] == "comum":
                    self.sender.sendMessage("Você não tem acesso a lista da casa, peça um upgrade na sua conta.")
                    return False
                else:
                    mensagem = "Digite a nova informação: "
                    teclado = ReplyKeyboardRemove()
                
                dicionario[text][1] = True
                self.sender.sendMessage(mensagem, 
                    reply_markup = teclado)
                return True
        return False

    def habilitar_avancadas(self, msg):
        '''
        Verifica se a mensagem está nas configurações avançadas
        Se estiver, devolve True caso contrário False
        '''
        global adms, entrada_1gale, entrada_2gale, rodando
        
        if self.id not in adms:
            return False
        if msg['text'] == 'Adicionar administrador':
            self.sender.sendMessage("Coloque o ID do telegram:",
                reply_markup = ReplyKeyboardRemove())
            self.alteracoes_avancadas['adm'] = True
        elif msg['text'] == "Atualizar informações":
            self.sender.sendMessage("Atualizando...")
            adms = get_adms()
            entrada_1gale = carregar_entradas(1)
            entrada_2gale = carregar_entradas(2)
            self.sender.sendMessage("Informações atualizadas.")
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
                self.sender.sendMessage("Escolha:",
                    reply_markup = ReplyKeyboardMarkup(keyboard = lista_usuarios))
                if msg['text'] == "Aprovar usuários":
                    self.alteracoes_avancadas['aprovar'] = True
                elif msg['text'] == "Tirar de cadastro":
                    self.alteracoes_avancadas['apagar'] = True
                elif msg['text'] == "Remover usuários":
                    self.alteracoes_avancadas['remover'] = True
                else:
                    self.alteracoes_avancadas['licenca'] = True
            else:
                self.sender.sendMessage("Nenhum usuário no banco")
        elif msg['text'] == "Parar bot":
            self.parar_bot = True
            self.sender.sendMessage("Tem certeza?",
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
            self.sender.sendMessage("Adminstrador adicionado.")
            self.alteracoes_avancadas["adm"] = False
            return True
        elif self.alteracoes_avancadas['aprovar']:
            MongoDB.aprovar(msg)
            self.sender.sendMessage("Usuário aprovado.")
            self.alteracoes_avancadas["aprovar"] = False
            return True
        elif self.alteracoes_avancadas['licenca']:
            MongoDB.renovar_licenca(msg)
            self.sender.sendMessage("Licença renovada")
            self.alteracoes_avancadas["licenca"] = False
            return True
        elif self.alteracoes_avancadas['remover']:
            MongoDB.remover_usuario(msg)
            self.sender.sendMessage("Usuário removido")
            self.alteracoes_avancadas["remover"] = False
            return True
        elif self.alteracoes_avancadas['apagar']:
            MongoDB.apagar_cadastro(msg)
            self.sender.sendMessage("Cadastro apagado")
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
                            self.sender.sendMessage("Deve ser um número! Tente novamente")
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
                        self.sender.sendMessage("Deve ser um número.")
                        return False
                elif novo == "individual":
                    self.sender.sendMessage(
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
            self.sender.sendMessage(f"Valor salvo.")
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
                self.sender.sendMessage("Alteração salva!")
                self.ver_configuracoes()
                self.editar_configuracoes()
                return True
        return False

    def desligar_bot(self):
        if os.name != "nt":
            self.sender.sendMessage("Deletando todas as instâncias...")
            usuarios = controlador.deletar_instancias()
            self.sender.sendMessage("Resetando o banco de dados...")
            for email in usuarios:
                MongoDB.Users_collection.find_one_and_update(
                    {'email': email}, {'$set' : {'operando': False}})
        self.sender.sendMessage("Desligando o bot...")
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
        elif msg['text'] == "Adicionar entradas":
            self.adicionar_entrada(msg) # [1] Entradas
        elif self.salvar_alteracoes_avancadas(msg):
            self.gerenciar() # [4] Avançadas (ADM)
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
        self.sender.sendMessage("Obrigado pela preferência, irei atender outras pessoas, qualquer coisa é só chamar.", reply_markup = ReplyKeyboardRemove())

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
