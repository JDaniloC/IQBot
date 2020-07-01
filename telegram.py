import time, pprint, amanobot, json, os
from subprocess import call
from bot import pegar_comando
from amanobot.loop import MessageLoop
from amanobot.namedtuple import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from amanobot.delegate import (
    pave_event_space, per_chat_id, create_open)

def strDateHour(number):
    return str(number) if len(str(number)) != 1 else "0" + str(number)

def carregar_entradas(opcao):
    lista_entradas = []
    with open("config/entradas" + str(opcao) + ".txt") as file:
        lista = file.readlines()
        for linha in lista:
            parseado = pegar_comando(linha)
            lista_entradas.append(f'''
📊 Ativo: {parseado["par"]}
📅 Dia: {"/".join(list(map(strDateHour, parseado["data"])))}
⏱Hora: {":".join(list(map(strDateHour, parseado["hora"])))}   
➡Direção: {parseado["ordem"].upper()}   
            
            ''')
    return lista_entradas

with open("misc/dados.json", encoding = "utf-8") as file:
    dados = json.load(file)
    aprovados = dados["aprovados"]
    em_aprovacao = dados["em_aprovacao"]

with open("clients/default.json", encoding = "utf-8") as file:
    default = json.load(file) 

entrada_1gale = carregar_entradas(1)
entrada_2gale = carregar_entradas(2)

mapeamento_avancado = {
    "Mudar tipo de paridade": ["tipo_par", False, list],
    "Mudar configuração OTC": ["otc", False, bool],
    "Alterar timeframe": ["tempo", False, list],
    "Mudar a correção": ["correcao", False, int]
}

class Assistente(amanobot.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(Assistente, self).__init__(*args, **kwargs)
        self.nome_usuario = ""
        self.email = ""
        self.add_entrada = "0"
        self.entrada = False
        self.cadastro = False
        self.autenticacao = False
        self.iniciar_operacao = False

        self.mapeamento = {
            "Tipo de conta": ["tipo_conta", False, list], 
            "Valor de entrada": ["valor", False, float],
            "Payout mínimo": ["minimo", False, int], # 0 - 100
            "StopWin": ["goal", False, float],
            "Soros": ["soros", False, bool], 
            "Percentual da soros": ["percent_soros", False, int],
            "StopLoss": ["stoploss", False, float],
            "Martingale": ["martin", False, bool], 
            "Percentual do martin": ["percent_martin", False, int],
            "Máximo de gales": ["max_gale", False, list],
            "Tipo de martingale": ["tipo_gale", False, list]
        }

        self.informacoes = {
            "tipo_conta": "treino",
            "valor": 2,
            "minimo": 0,
            "goal": 100,
            "soros": False,
            "percent_soros": 0,
            "stoploss": 20,
            "martin": True,
            "percent_martin": 0,
            "max_gale": 2,
            "tipo_gale": "seguro"
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

        self.sender.sendMessage("Olá, eu sou seu assistente do robô MM_007.", 
            reply_markup = ReplyKeyboardMarkup(
                keyboard = [[KeyboardButton(text = "Entrar")]]
        ))

    def login(self, msg):
        '''
        Método para o login, verifica se o ID
        Está em análise ou já aprovado.
        '''
        if self.autenticacao:
            self.sender.sendMessage("Você já está logado.")
            return False

        self.entrada = False

        if msg['text'] in aprovados:
            self.email = msg["text"]
            self.autenticacao = True
            with open("clients/" + self.email + ".json") as file:
                self.informacoes = json.load(file)
            self.sender.sendMessage(
                f"E-mail autenticado, seja bem-vindo Sr(a) {self.nome_usuario}")
            self.comandos()

        elif msg['text'] in em_aprovacao.values() or self.id in em_aprovacao:
            self.sender.sendMessage(f"Digite a senha:")
            self.cadastro = True
        else:
            em_aprovacao[self.id] = msg['text'] 
            pprint.pprint(em_aprovacao)
            self.sender.sendMessage(f"Seu e-mail foi colocado para analise. Peça a senha para o administrador. Se você já tiver a senha digite 'Sim'.")
            self.entrada = True

    def cadastrar(self, msg):
        '''
        Método para verificar a senha de cadastro
        '''
        if self.autenticacao:
            self.sender.sendMessage("Você já está cadastrado")
            return False

        if msg['text'] == str(self.id):
            email = em_aprovacao[self.id]
            del em_aprovacao[self.id]
            aprovados[email] = False

            resposta = "E-mail cadastrado! Continue o cadastro para operar."
            self.cadastro = False
            self.autenticacao = True
            self.email = email
            self.editar_configuracoes()
        else:
            resposta = "Código errado, tente novamente."
        
        self.sender.sendMessage(resposta)
        return True

    def comandos(self):
        '''
        Menu principal quando já está logado.
        '''
        if self.autenticacao:
            teclado = ReplyKeyboardMarkup(keyboard = [
                [KeyboardButton( text = "Operar" )],
                [KeyboardButton( text = "Ver configurações" )],
                [KeyboardButton( text = "Editar configurações" )],
                [KeyboardButton( text = "Ver lista de sinais" )]
            ])

            self.sender.sendMessage("O que deseja?", 
                reply_markup = teclado)
        else:
            self.sender.sendMessage("Usuário não autenticado")

    def gerenciar(self):
        '''
        Comandos para administradores
        '''
        if self.id not in [756287805, 915778450]:
            self.sender.sendMessage("Usuário não tem permissão")
            return False

        teclado = ReplyKeyboardMarkup(keyboard = [
            [KeyboardButton( text = "Ver configuração atual" )],
            [KeyboardButton( text = "Adicionar entradas" )],
            [KeyboardButton( text = "Mudar tipo de paridade" )],
            [KeyboardButton( text = "Mudar configuração OTC" )],
            [KeyboardButton( text = "Alterar timeframe" )],
            [KeyboardButton( text = "Mudar a correção" )],
            [KeyboardButton( text = "Voltar ao menu" )]
        ])

        self.sender.sendMessage("Configurações avançadas para admnistradores:",
            reply_markup = teclado)

    def ver_avancadas(self):
        '''
        Método que mostra do jeito cru as configurações avançadas
        '''
        if self.id not in [756287805, 915778450]:
            self.sender.sendMessage("Usuário não tem permissão")
            return False
        for key, value in default.items():
            self.sender.sendMessage(key + ": " + str(value),
            reply_markup = ReplyKeyboardRemove())

    def adicionar_entrada(self, msg):
        '''
        Mudar caminho do arquivo de entradas
        '''
        if self.id not in [756287805, 915778450]:
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
        if self.id not in [756287805, 915778450]:
            return False
        if msg['text'] in ["1 gale", "2 gales", "ambos"]:
            self.add_entrada = "ambos" if msg['text'] == "ambos" else msg['text'].split()[0]
            self.sender.sendMessage('''Mande a lista.
            Lembrando que na opção ambos é necessário colocar 1 gale/2 gales antes da lista especificando qual lista irá entrar.''',
                reply_markup = ReplyKeyboardRemove())            

    def pegar_entrada(self, entradas):
        lista = []
        for linha in entradas:
            nova = pegar_comando(linha)
            if nova["data"] != [1, 1, 2000]:
                lista.append(nova)
        return lista

    def guarda_entrada(self, lista, opcao):
        with open("config/entradas" + str(opcao) + ".txt", "w") as file:
            for entrada in lista:
                result = [
                    "/".join(map(strDateHour, entrada['data'])),
                    ":".join(map(strDateHour, entrada['hora'])),
                    entrada['par'],
                    entrada['ordem']
                ]
                
                file.write(",".join(result) + "\n")

    def confirmar_entradas(self, msg):
        if self.id not in [756287805, 915778450]:
            return False
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
                primeiro = self.pegar_entrada(msg['text'].split("\n"))
            elif self.add_entrada == "2":
                segundo = self.pegar_entrada(msg['text'].split("\n"))
            if self.add_entrada in ["ambos", "1"]:
                self.guarda_entrada(primeiro, 1)
            if self.add_entrada in ["ambos", "2"]:
                self.guarda_entrada(segundo, 2)
            self.add_entrada = "0"
            self.sender.sendMessage("Salvo")
            entrada_1gale = carregar_entradas(1)
            entrada_2gale = carregar_entradas(2)
            self.gerenciar()

    def operar(self, msg):
        '''
        Opção que inicia a operação, no qual salva as informações
        do usuário e abre um novo processo com o bot
        '''
        if self.autenticacao:
            if self.iniciar_operacao:
                aprovados[self.email] = True
                self.iniciar_operacao = False
                
                with open("clients/" + self.email + ".json", "w") as file:
                    json.dump(self.informacoes, file)
                
                if os.name == "nt": # No windows
                    call([
                        "powershell", "start", "powershell",
                        "python, bot.py, -o, " + 
                        self.email + ", " + msg['text']
                    ])
                else:
                    call([
                        "screen", "-dm", "python3", 
                        "bot.py", "-o", self.email, msg['text']
                    ])
                self.sender.sendMessage("Operação iniciada")
            elif not aprovados[self.email]:
                self.sender.sendMessage("Digite sua senha (não guardamos a sua senha, você terá que fazer isso todas as vezes): ", 
                reply_markup = ReplyKeyboardRemove())
                self.iniciar_operacao = True
            else:
                self.sender.sendMessage("Sua conta já está em operação.")
        else:
            self.sender.sendMessage("Usuário não autenticado")

    def ver_configuracoes(self):
        '''
        Mostra as configurações atuais
        '''
        if self.autenticacao:
            mensagem = ""
            for key, value in self.mapeamento.items():
                mensagem += key + ": " + str(self.informacoes[value[0]]).replace("True", "Sim").replace("False", "Não") + "\n"
            self.sender.sendMessage(mensagem)
        else:
            self.sender.sendMessage("Usuário não autenticado")

    def editar_configuracoes(self):
        '''
        Menu de opções para editar as configurações
        '''
        if self.autenticacao:
            self.sender.sendMessage(
                "O que você deveja alterar?", reply_markup = ReplyKeyboardMarkup(
                    keyboard = [
                        [KeyboardButton( text = "Tipo de conta" )],
                        [KeyboardButton( text = "Valor de entrada" )],
                        [KeyboardButton( text = "Payout mínimo" )],
                        [KeyboardButton( text = "StopWin" )],
                        [KeyboardButton( text = "StopLoss" )],
                        [KeyboardButton( text = "Soros" )],
                        [KeyboardButton( text = "Percentual da soros" )],
                        [KeyboardButton( text = "Martingale" )],
                        [KeyboardButton( text = "Percentual do martin" )],
                        [KeyboardButton( text = "Máximo de gales" )],
                        [KeyboardButton( text = "Tipo de martingale" )],
                        [KeyboardButton( text = "Voltar ao menu" )]
            ]))
        else:
            self.sender.sendMessage("Usuário não autenticado")

    def mapear(self, dicionario, text):
        '''
        Faz o mapeamento de botões para os métodos habilitar
        '''
        for key, value in dicionario.items():
            if text == key:
                dicionario[text][1] = True
                mensagem = "Escolha uma das opções abaixo:"
                if value[2] == bool:
                    teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = "Sim" )],
                                [KeyboardButton( text = "Não" )]])
                elif value[2] == list:
                    if value[0] == "tipo_conta":
                        teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = "treino" )],
                                [KeyboardButton( text = "real" )]])
                    elif value[0] == "max_gale":
                        teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = 1 )],
                                [KeyboardButton( text = 2 )]])
                    elif value[0] == "tempo":
                        teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = 1 )],
                                [KeyboardButton( text = 5 )],
                                [KeyboardButton( text = 15 )]])
                    elif value[0] == "tipo_par":
                        teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = "binary" )],
                                [KeyboardButton( text = "digital" )],
                                [KeyboardButton( text = "auto" )]])
                    else:
                        teclado = ReplyKeyboardMarkup( keyboard = [
                                [KeyboardButton( text = "seguro" )],
                                [KeyboardButton( text = "leve" )],
                                [KeyboardButton( text = "agressivo" )],
                                [KeyboardButton( text = "porcento" )]])
                else:
                    mensagem = "Digite a nova informação: "
                    teclado = ReplyKeyboardRemove()
                
                self.sender.sendMessage(mensagem, 
                    reply_markup = teclado)
                return True
        return False

    def habilitar_avancadas(self, msg):
        '''
        Verifica se a mensagem está nas configurações avançadas
        Se estiver, devolve True caso contrário False
        '''
        if self.id not in [756287805, 915778450]:
            return False
        return self.mapear(mapeamento_avancado, msg['text'])

    def habilitar_alteracao(self, msg):
        '''
        Habilita a alteração da informação e pergunta qual a nova
        Devolvendo um bool se completou a habilitação
        '''
        if not self.autenticacao:
            return False
        return self.mapear(self.mapeamento, msg['text'])

    def confirmar_mapeamento(self, dicionario, novo):
        '''
        Mapea o dicionário para ver se há um valor verdadeiro
        Se houver verifica se o novo valor está correto
        Devolve um bool, usado para confirmar_alteracao/avancado
        '''
        for key, value in dicionario.items():
            if value[1]:
                if value[2] not in [list, bool]:
                    try:
                        novo = value[2](novo.strip().replace(",", "."))
                    except Exception as e:
                        print(e)
                        self.sender.sendMessage("Deve ser um número! Tente novamente")
                        return False
                elif value[2] == bool:
                    novo = bool(novo.strip() == "Sim")
                dicionario[key][1] = False
                return value[0], novo
        return False

    def confirmar_alteracao_avancada(self, msg):
        if not self.id in [756287805, 915778450]:
            return False
        result = self.confirmar_mapeamento(mapeamento_avancado, msg['text'])
        if result:
            key, value = result
            default[key] = value
            with open("clients/default.json", "w") as file:
                json.dump(default, file, indent = 2)
            self.sender.sendMessage(f"Valor salvo.")
            self.ver_avancadas()
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
                key, value = result
                self.informacoes[key] = value
                self.sender.sendMessage("Alteração salva!")
                self.ver_configuracoes()
                return True
        return False
            
    def ver_lista(self):
        if self.autenticacao:
            self.sender.sendMessage("Listas atuais:", 
                reply_markup = ReplyKeyboardRemove())
            self.sender.sendMessage("1 Gale:")
            for entrada in entrada_1gale:
                self.sender.sendMessage(entrada)
            self.sender.sendMessage("\n2 Gales:")
            for entrada in entrada_2gale:
                self.sender.sendMessage(entrada)
            self.sender.sendMessage("Fim das listas")
            self.comandos()
        else:
            self.sender.sendMessage("Usuário não autenticado")

    def on_chat_message(self, msg):
        '''
        Método que é chamado sempre que é digitado alguma coisa
        '''
        if self.entrada:
            self.login(msg)
        elif self.cadastro:
            self.cadastrar(msg)
        elif self.iniciar_operacao:
            self.operar(msg)
        elif msg['text'] == "Entrar":
            if not self.autenticacao:
                self.sender.sendMessage("Digite o seu e-mail para continuar:", 
                    reply_markup = ReplyKeyboardRemove())
                self.entrada = True
            else:
                self.sender.sendMessage("Você já está logado")
        elif msg['text'] == 'Gerenciar':
            self.gerenciar()
        elif msg['text'] == "Voltar ao menu":
            self.comandos()
        elif msg['text'] == "Ver configurações":
            self.ver_configuracoes()
        elif msg['text'] == "Editar configurações":
            self.editar_configuracoes()
        elif msg['text'] == "Operar":
            self.operar(msg)
        elif msg['text'] == "Ver lista de sinais":
            self.ver_lista()
        elif msg['text'] == "Ver configuração atual":
            self.ver_avancadas()
            self.gerenciar()
        elif msg['text'] == "Adicionar entradas":
            self.adicionar_entrada(msg)
        elif self.confirmar_alteracao(msg):
            self.editar_configuracoes()
        elif self.habilitar_alteracao(msg):
            pass
        elif self.confirmar_alteracao_avancada(msg):
            self.gerenciar()
        elif self.habilitar_avancadas(msg):
            pass
        elif self.confirmar_entradas(msg):
            self.gerenciar()
        elif self.habilitar_entradas(msg):
            pass
        
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
            with open("clients/" + self.email + ".json", "w") as file:
                json.dump(self.informacoes, file, indent = 2)

        print(f"Usuário {self.nome_usuario} saiu.\n")
        self.sender.sendMessage("Obrigado pela preferência, irei atender outras pessoas, qualquer coisa é só chamar.", reply_markup = ReplyKeyboardRemove())

TOKEN = "1230540493:AAE3sDtChTvq1SlhqGDJhnIPfM2Qlgrr4_g"

bot = amanobot.DelegatorBot(TOKEN, [
    pave_event_space()(
        per_chat_id(), create_open, Assistente, timeout = 60),
])

try:
    MessageLoop(bot).run_as_thread()
    print("Esperando comandos...")
    while 1:
        time.sleep(3)
except KeyboardInterrupt:
    pass
finally:
    with open("misc/dados.json", "w", encoding = "utf-8") as file:
        dados = {
            "aprovados": {key: False for key in aprovados},
            "em_aprovacao": em_aprovacao
        }
        dados = json.dump(dados, file, indent = 2)
    print("Bot desligado")