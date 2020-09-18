from utils.investing import extrair_noticias
import threading, traceback, time, re, sys
from datetime import datetime, timedelta
from utils.IQ import IQ_API
from pprint import pprint

LOCALERROR = "errors.log"
LOCALLOG = ""

def escreve_erros(erro):
	linhas = " -> ".join(re.findall(r'line \d+', str(traceback.extract_tb(erro.__traceback__))))
	with open(LOCALERROR, "a") as file:
		file.write(f"{type(erro)} - {erro}:\n{linhas}\n")

def escreve_log(email, mensagem):
	with open(LOCALLOG + email + ".txt", "a", encoding = "utf-8") as file:
		file.write(mensagem + "\n")

class Operacao(IQ_API): 
	logo = ('''
	   ******                                               
	***********                                             
   ************                                             
	 ***********                                            
			 *****       .,,,,,,,,,,,,,,,,,                 
				*****,,,,,/(((((((#(((((,,,,,,              
				  ,*****/(((,,,,,,,,,((((#(,*,,             
				 ,,,,*****,,,.*//,,,,,,,((((.,,,*           
			   ,,*((((,*****,///(/((/,,,,((((,,,,*          
			  ,,,(((,,,,//,,*,,,,/(((,,,,#(((,,,,*/         
			 ,,,((((,,,////,,.,..////,,,/(((*,,,***         
   @@@@@##   .,,//@@@@@//////(//(//..*@@@@@/,,,,,*. ((@@@@  
   @&@@@@##  ,,,/@@@@@@/,,(///(/,,,,,*@@@@@@/,,,,, ((@@@@@  
   @&*@@@@## ,,,@@*&@@@/,,,,,,,,,,/(//@@,@@@@/,,  ((@&*@@@  
   @&**@@@@##,,@@*.@@@@/((//(((((((((*@@,,&@@@/  ((@@**@@@  
   @&/* @@@@##@@*.,&@@@/(((((((*,,*,,*@@..,&@@@@/(@  **@@@  
   @&/*  @@@@@@*   &@@@/,,,,,,,,,,,..*@@.  ,%@@@@@   **@@@  
   @&/*   @@@@*    %@@@/......&(.....,@@    .#@@@    **@@@  
   @&/,    @@*     %@@@      @*@      @@      /@      *@@@  
														   
''')

	welcome = ('''                                                          
  ___       _        _                      _         _         
 / __| ___ (_)__ _  | |__  ___ _ __ _____ _(_)_ _  __| |___     
 \__ \/ -_)| / _` | | '_ \/ -_) '  \___\ V / | ' \/ _` / _ \    
 |___/\___|/ \__,_| |_.__/\___|_|_|_|   \_/|_|_||_\__,_\___/    
		 |__/                                                   
			 ___     _           __  __   __  __   __   __ ____ 
  __ _ ___  | _ \___| |__  ___  |  \/  | |  \/  | /  \ /  \__  |
 / _` / _ \ |   / _ \ '_ \/ _ \ | |\/| |_| |\/| || () | () |/ / 
 \__,_\___/ |_|_\___/_.__/\___/ |_|  |_(_)_|  |_|_\__/ \__//_/  
											   |___|           
''')

	def __init__(self, config, comandos, 
		maximo = 0, verboso = False):
		self.maximo = maximo
		self.cadeado = threading.Lock()

		self.config = config
		self.comandos = comandos
		self.ganho_total = 0
		self.perda_total = 0
		self.perda_atual = 0 # Para sorosgale
		self.verboso = verboso

		if self.maximo < 3:
			try:
				print(self.logo, flush = True)
				print(self.welcome, flush = True)

				if self.verboso:
					import amanobot
					self.telegram = amanobot.Bot("1354635217:AAG1EbTt772cwPh008Ud3uBqyxyS28LXZao")

				print(f"Entrando na {config['email']}")
				super().__init__(config['email'], config['senha'])

				if config['tipo_conta'] == "treino":
					self.mudar_treino()
				else:
					self.mudar_real()

				if config['tipo_par'] == "auto":
					self.tipo = config['tipo_par']
				else:
					self.tipo = "digital" if config['tipo_par'] == 'digital' else "binary"

				# Para soros
				self.valor_inicial = config['valor']
				self.soros_atual = 0
				self.gale_atual = 0

				self.valor = config['valor']
				self.tempo = config['tempo']
				self.max_gale = config["max_gale"]
				self.ganhos_perdas = [0, 0]
				if config['tendencia']:
					self.config['correcao'] += 3
				if config['noticias']:
					self.atualizar_noticias()

				self.computar()
			except KeyboardInterrupt:
				sys.exit(0)
			except Exception as e:
				if type(e) == ConnectionError:
					self.mostrar_mensagem("Não conseguiu se conectar na conta")
		
					self.maximo = 3
				else:
					print("Aconteceu um erro na API, tentando novamente.")
				escreve_erros(e)
				
				try:
					print("Continuando as operações...")
					self.maximo += 1
					self.__init__(
						self.config, self.comandos, self.maximo)
				except:
					print("Deu erro novamente! Finalizando o programa.")
					escreve_erros(e)
		else:
			self.mostrar_mensagem("Ultrapassou o máximo de tentativas.")

	def mostrar_mensagem(self, mensagem):
		'''
		Mostra a mensagem em tela
		Se self.verboso tenta enviar para o telegram
		'''
		print(mensagem)
		if self.verboso:
			try:
				self.telegram.sendMessage(self.verboso, mensagem)
			except Exception as e:
				try:
					import amanobot
					self.telegram = amanobot.Bot(
						"1354635217:AAG1EbTt772cwPh008Ud3uBqyxyS28LXZao")
					self.telegram.sendMessage(self.verboso, mensagem)
				except Exception as e:
					print(type(e), e)

	def atualizar_noticias(self):
		'''
		Atualiza a última atualização de notícias realizada
		E substitui as notícias antigas.
		'''
		self.ultima_atualizacao_noticia = datetime.now()
		self.noticias = extrair_noticias()

	def verificar_noticias(self, paridade):
		'''
		Verifica se há alguma notícia no período especificado pelo:
			config['noticia_hora'], config['noticia_minuto']
		'''
		agora = datetime.utcfromtimestamp(datetime.utcnow().timestamp() - 10800) # -3Horas
		if (self.ultima_atualizacao_noticia.day != 
			agora.day):
			self.atualizar_noticias()
		for info in self.noticias:
			if agora > info['horario']: 
				diferenca = agora - info['horario']
			else: diferenca = info['horario'] - agora
			if diferenca < timedelta(
				hours = self.config['noticias_hora'], 
				minutes = self.config['noticias_minuto']):
				if info['par'] in paridade.upper():
					self.mostrar_mensagem(
						f"Cancelando entrada devido notícia: {info['par']} {'⭐' * int(info['impacto'])}".center(60))
					self.mostrar_mensagem(
						f"{info['text']}".center(60))
					return False
		return True

	def operar(self, valor, par, ordem, tempo, payout, tipo):
		'''
		Faz a operação e a depender da configuração faz:
		Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
		'''
		def mostra_resultado():
			perto_win = round(
				self.ganho_total/self.config['goal'] * 100, 2)
			perto_loss = round(
				-self.perda_total/self.config['stoploss'] * 100, 2)
			threading.Thread(
				target = self.mostrar_mensagem,
				args = (f"""
{par} {ordem.upper()} R$ {round(self.ganho_total, 2)}
	✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌
| {perto_win}% perto do objetivo |
| {perto_loss}% perto do stoploss |""", )).start()

		def desconta_perda(resultado, lucro):
			with self.cadeado:
				if resultado == "win":
					self.ganho_total += round(lucro, 2)
					self.ganhos_perdas[0] += 1
				else:
					if resultado == "loose":
						self.ganhos_perdas[1] += 1
					self.ganho_total -= round(abs(lucro), 2)
					self.perda_total -= round(abs(lucro), 2)

		resultado = None
		for i in range(2):
			try:
				resultado, lucro = self.ordem(
					par, ordem, tempo, valor, tipo, 
					self.cadeado, self.config['delay'])
				break
			except Exception as e:
				print(f"Ocorreu um erro na operação:\n {type(e)}: {e}")
				self.conectar()
		if resultado == None:
			raise ConnectionAbortedError(
				"Não estou conseguindo fazer as operações, reinicie o bot.")
		
		if resultado == "win" and (
			self.config['soros'] or self.perda_atual > 0):
			if (not self.config['tipo_gale'] == "martin" and 
				self.soros_atual < self.config['max_soros']):
				with self.cadeado:
					# Caso estiver em sorosgale
					verificador = True
					if self.perda_atual > 0:
						self.perda_atual -= lucro
						if self.perda_atual < 0: 
							# Caso terminou o sorosgale
							verificador = False
							self.perda_atual = 0

					if verificador:
						novo = (valor + lucro if self.config["percent_soros"] == 0 
							else valor + valor * self.config["percent_soros"] / 100)
						print(f"\n [SOROS] : {round(valor, 2)} -> {round(novo, 2)}")
						self.valor = novo
						self.soros_atual += 1
			elif self.config['tipo_gale'] == "martin":
				self.gale_atual = 0
				self.perda_atual -= lucro
				self.perda_total += lucro
				if self.perda_atual < 0: self.perda_atual = 0
				if self.perda_total > 0: self.perda_total = 0
				self.valor = self.valor_inicial
			else:
				self.soros_atual = 0
				print(f" [SOROS] Preservando capital: R$ {valor} -> R$ {self.valor_inicial}")
				self.valor = self.valor_inicial
		
		if resultado == "loose":
			if self.config['soros'] and self.soros_atual > 0:
				self.soros_atual = 0
				print(f" [SOROS] Preservando capital: R$ {valor} -> R$ {self.valor_inicial}")
				self.valor = self.valor_inicial
			
			if (self.config['tipo_gale'] == "martin" and 
				self.config['entrada_martin'] == "vela"):
				perda = 0
				num_gales = 0
				while (self.config['goal'] > self.ganho_total and (
					self.max_gale > num_gales and resultado == 'loose')):
					desconta_perda(resultado, lucro)
					mostra_resultado()
		
					# self.esperar_anteriores(threading.currentThread().name)
					# threading.currentThread().setName(str(time.time()))

					if self.perda_total <= -(self.config['stoploss']):
						self.mostrar_mensagem(
							f"BATEU NO STOPLOSS: R$ {round(self.perda_total, 2)}!")
						sys.exit(0)

					perda += abs(lucro)

					print(f"\n [MARTINGALE] do tipo {self.config['tipo_martin']} na operação {par}|{ordem}")
						
					lucro = (valor * payout if self.config["tipo_martin"] != "porcento" 
							else self.config["percent_martin"] / 100)
					valor = self.martingale(self.config['tipo_martin'], 
						payout, perda, valor, lucro)
					
					valor = 1 if valor < 1 else valor # Caso der doji

					resultado, lucro = self.ordem(
						par, ordem, tempo, valor, tipo, 
						self.cadeado, self.config['delay'])
				
					num_gales += 1
				if resultado == "win":
					self.perda_total += perda
			elif self.config['tipo_gale'] == "martin":
				print(f"\n [MARTINGALE] do tipo {self.config['tipo_martin']} na operação {par}|{ordem}")
				self.perda_atual += abs(valor)
				self.gale_atual += 1
				lucro = (valor * payout if 
						self.config["tipo_martin"] != "porcento" else 
						self.config["percent_martin"] / 100)
				with self.cadeado:
					self.valor = self.martingale(self.config['tipo_martin'], 
						payout, self.perda_atual, valor, lucro)
				self.valor = 1 if self.valor < 1 else self.valor 

			elif self.config['tipo_gale'] == 'soros':
				print(f"\n [SOROSGALE] na operação {par}|{ordem} {valor} -> ", end = "")
				self.perda_atual += abs(valor)
				self.soros_atual = 0
				self.valor = self.perda_atual / 2
				self.valor = 1 if self.valor < 1 else self.valor
				print(self.valor)

		if resultado not in ["error", "equal"]:
			desconta_perda(resultado, lucro)                
			mostra_resultado()

		elif resultado == "error":
			print(f"\nErro na operação às {str(datetime.utcnow())[:-7]}")

	def computar(self):
		'''
		1 - Percorre todos os comandos.
		2 - Pausa o script até a próxima hora:min
		3 - Calcula o payout da paridade
		4 - Cria uma thread para o método operar
		'''
		self.espera = []

		if self.tipo == "auto":
			ultima_vez = time.time()
			paridades = []
			for par in self.comandos:
				paridade = par['par']
				paridades.append(paridade)
			self.payouts = self.abertas(paridades)

			def atualizar_profits(comando):
				'''
				Atualiza os payouts do comando em diante.
				'''
				paridades = []
				for par in self.comandos[self.comandos.index(comando):]:
					paridade = par['par']
					paridades.append(paridade)
				novo = self.abertas(paridades)
				if novo == None:
					raise ConnectionAbortedError(
				"Não estou conseguindo pegar as paridades. Reinicie o bot")
				self.payouts.update(novo)

		self.mostrar_mensagem("Conectado com sucesso.")
		for comando in self.comandos:
			
			data = comando["data"]
			horas, minutos = comando["hora"]
			tempo = comando['timeframe'] if comando['timeframe'] != 0 else self.tempo
			segundos = 0
			if self.esperarAte(
				horas, minutos, segundos, data, 
				self.config['correcao'] + 1, True):

				par = comando['par']
				ordem = comando['ordem']
				valor = self.valor

				if self.tipo == "auto":
					maior = self.maior_payout(par, tempo)
					if maior: tipo, payout = maior
					else: tipo, payout = "binary", 0.7
				else:
					payout = (self.payout_binaria(par) / 100 if 
							  self.tipo == "binary" else 
							  self.payout_digital(par) / 100)
					tipo = self.tipo

				if self.config['tendencia'] and not self.calcular_tendencia(
					self.config['tipo_tendencia'], par, ordem, tempo, 
					self.config['periodo_tendencia'], self.config['desvio_tendencia']):
					self.mostrar_mensagem(f"[ ❗️] {par}|{ordem} às {horas}:{minutos} entrou contra a tendência. [ ❗️]")
					continue

				if (self.config['noticias'] and
					not self.verificar_noticias(par)):
						continue
				# self.esperar_anteriores()

				if self.verificar_stop():
					break
				
				payout_desejado = self.config["minimo"] / 100
				if payout_desejado <= payout:
					thread = threading.Thread(
						target = self.operar, 
						name = f"{time.time()}", 
						args = (
						valor, par, ordem, tempo, payout, tipo))
					self.espera.append(thread)
					thread.start()
				else:
					self.mostrar_mensagem(f"[ ❗️] {par}|{ordem.upper()} payout: {payout * 100}% < {payout_desejado * 100}%. [ ❗️]")

				if self.tipo == "auto":
					if time.time() - ultima_vez > 900:
						threading.Thread(
						target = atualizar_profits,
						args = (comando,)
						).start()
			else:
				momento = datetime.utcnow().timestamp() - 10800 # -3Horas
				print(f" - {datetime.fromtimestamp(momento).strftime('dia %d - %H:%M')} | {comando['par']} - {horas}:{minutos} passou da hora - ")
		for thread in self.espera:
			thread.join()

		self.mostrar_mensagem(
			f"\nFim da operação resultado final: R$ {round(self.ganho_total, 2)}\n")
		
		try:
			if self.tipo == "auto":
				for comando in self.comandos:
					par = comando["par"]
					self.API.unsubscribe_strike_list(par, self.config["tempo"])
		except:
			pass
	
	def maior_payout(self, par, tempo):
		'''
		Caso estiver em automático, verifica qual o maior
		payout, primeiro vendo se estão abertas.
		'''
		tipo_binaria = "turbo" if tempo <= 5 else "binary"
		if ((self.payouts["binary"][tipo_binaria][par][0] and 
			self.payouts["digital"][par][0])
			and 
			(self.payouts["binary"][tipo_binaria][par][1] < 
			self.payouts["digital"][par][1])):
			tipo = "digital"
			payout = self.payouts["digital"][par][1]
		elif self.payouts["binary"][tipo_binaria][par][0]:
			tipo = "binary"
			payout = self.payouts["binary"][tipo_binaria][par][1]
		elif self.payouts["digital"][par][0]:
			tipo = "digital"
			payout = self.payouts["digital"][par][1]
		else:
			return False
		return tipo, payout

	def verificar_stop(self):
		'''
		Verifica se bateu no stopwin/loss
		Devolve um booleano
		'''
		with self.cadeado:
			if (-self.config['stoploss'] >= self.perda_total or 
				self.ganho_total >= self.config['goal']):
				self.mostrar_mensagem(f'''{"- " * 20}
	Stopwin: {self.config['goal']}
	Total ganho: {round(self.ganho_total, 2)}
	Stoploss: {-self.config['stoploss']}
	Total perdido: {round(self.perda_total, 2)}''')
				return True
		return False

	def esperar_anteriores(self, atual = 0):
		'''
		Espera as operações anteriores acabar para poder liberar a próxima
		'''
		esperar_anteriores = True

		while esperar_anteriores:
			esperar_anteriores = False
			ativos = [
				datetime.fromtimestamp(float(x.name)) for x in threading.enumerate() if self.istime(x.name) and x.name != atual]
			for timing in ativos:
				momento_atual = datetime.fromtimestamp(time.time())
				anteriores = (atual == 0 or datetime.fromtimestamp(float(atual)) > timing)

				perto_de_terminar = (self.tempo * 60 + 30 >= 
								 (momento_atual - timing).seconds >= 
								 self.tempo * 60 - 30)
				if anteriores and perto_de_terminar:
					time.sleep(1)
					print("Esperando as operações anteriores acabar...")
					esperar_anteriores = True
					break

	def istime(self, string):
		'''
		Verifica se é numérico (timestamp)
		'''
		try:
			float(string)
			return True
		except:
			return False