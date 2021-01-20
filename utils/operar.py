import threading, traceback, time, re, sys, amanobot
from utils.investing import extrair_noticias
from datetime import datetime, timedelta
from configparser import RawConfigParser
from utils.IQ import IQ_API

config = RawConfigParser()
config.read(".env")

BOTNAME = config.get("TELEGRAM", "name")
BOTTOKEN = config.get("TELEGRAM", "token")
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
	def __init__(self, config, comandos = [], 
		maximo = 0, verboso = False):
		self.cadeado = threading.Lock()
		self.comandos = comandos
		self.verboso = verboso
		self.maximo = maximo
		self.config = config

		self.ganho_total = 0
		self.perda_total = 0
		self.perda_atual = 0 # Para sorosgale

		if self.maximo < 3:
			try:
				if self.verboso:
					self.telegram = amanobot.Bot(BOTTOKEN)

				print(f"Entrando na {config['email']}")
				super().__init__(
					config['email'], config['senha'], self.mostrar_mensagem)
				
				if config['tipo_conta'] == "treino":
					self.mudar_treino()
				else: self.mudar_real()

				if config['tipo_par'] == "auto":
					self.tipo = config['tipo_par']
				else:
					self.tipo = "digital" if (
						config['tipo_par'] == 'digital'
					) else "binary"

				# Para soros
				self.valor_inicial = config['valor']
				self.soros_atual = 0
				self.gale_atual = 0

				self.valor = config['valor']
				self.tempo = config['tempo']
				self.stopwin = config["stopwin"]
				self.stoploss = config["stoploss"]
				self.max_gale = config["max_gale"]
				self.ciclos_gale = config["ciclos_gale"]
				self.ciclos_soros = config["ciclos_soros"]
				self.ganhos_perdas = [0, 0]

				self.stopwin = 0.1 if (
					self.stopwin == 0
				) else self.stopwin
				self.stoploss = 0.1 if (
					self.stoploss == 0
				) else self.stoploss
				
				self.config['scalper'] = {
					"win": self.config['scalper_win'],
					"loss": self.config['scalper_loss']
				} if (self.config['scalper_win'] != 0 and 
					self.config['scalper_loss'] != 0) else False
				self.config["ciclos"] = {
					"gales": 0, "soros": 0
				}

				self.saldo_inicial = self.API.get_balance()
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
						self.config, self.comandos, self.maximo, self.verboso)
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
					self.telegram = amanobot.Bot(BOTTOKEN)
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
		if (self.ultima_atualizacao_noticia.day != agora.day):
			self.atualizar_noticias()
		for info in self.noticias:
			if agora > info['horario']: 
				diferenca = agora - info['horario']
			else: diferenca = info['horario'] - agora
			if diferenca < timedelta(
				hours = self.config['noticias_hora'], 
				minutes = self.config['noticias_minuto']):
				if info['par'] in paridade.upper() and (
					int(info['impacto']) >= self.config["toros"]):
					self.mostrar_mensagem(f"Cancelando entrada devido notícia: \
						{info['par']} {'⭐' * int(info['impacto'])}".center(60))
					self.mostrar_mensagem(f"{info['text']}".center(60))
					return False
		return True

	def operar(self, valor, paridade, ordem, tempo, 
		payout, tipo, estrategia = False):
		'''
		Faz a operação e a depender da configuração faz:
		Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
		'''
		num_gales = 0
		def mostra_resultado():
			perto_win = f"R$ {round(self.ganho_total, 2)} / {self.stopwin}"
			perto_loss = f"R$ {round(-self.perda_total, 2)} / {self.stoploss}"
			threading.Thread(
				target = self.mostrar_mensagem,
				args = (f"""
	Saldo inicial: R$ {self.saldo_inicial}
	Saldo atual: R$ {round(self.saldo_inicial + self.ganho_total, 2)}
	{f'✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌'.center(20)}
	{f'| Lucro: {perto_win} |'.center(10)}
	{f'| Perda: {perto_loss} |'.center(10)}
	""", )).start()

		def desconta_perda(resultado, lucro, gale = False):
			with self.cadeado:
				mensagem = "Doji"
				if resultado == "win":
					self.ganho_total += round(lucro, 2)
					self.ganhos_perdas[0] += 1
					mensagem = (num_gales * "🐔 ") + "✅"
					if self.config['tipo_stop'] == "fixo":
						self.perda_total += round(lucro, 2)
				else:
					if resultado == 'loose':
						if not gale:
							self.ganhos_perdas[1] += 1
						mensagem = "❌"
						lucro = abs(lucro) * -1
					self.ganho_total -= round(abs(lucro), 2)
					self.perda_total -= round(abs(lucro), 2)
				
				threading.Thread(target = self.mostrar_mensagem,
					args = (f"""
	{paridade.upper()} {ordem.upper()} M{tempo} 
	Resultado: {mensagem}
	Lucro: R$ {round(lucro, 2)}""", )).start()
		
		resultado, lucro = None, 0
		fazendo_soros = self.soros_atual > 0
		for i in range(2):
			try:
				resultado, lucro = self.ordem(
					paridade, ordem, tempo, valor, tipo, 
					self.cadeado, self.config['delay'], 
					self.config["scalper"])
				break
			except Exception as e:
				if "Connection is already closed." in str(e):
					self.mostrar_mensagem(
						"Sinal perdido, a IQ fechou a conexão, o bot irá reconectar.")
					raise ConnectionAbortedError("Reinicie o bot.")
				else:
					print(f"Ocorreu um erro na operação:\n {type(e)}: {e}")
				self.conectar()
		if resultado == None:
			raise ConnectionAbortedError("Reinicie o bot.")
		
		if resultado == "win" and (self.config['max_soros'] > 0 or 
			(self.config["tipo_gale"] == "sorosgale" and 
			self.perda_atual > 0) or self.config["on_ciclos_soros"]):
			if self.config["on_ciclos_soros"]:
				ciclo_atual = self.config["ciclos"]["soros"]
				if ciclo_atual < len(self.ciclos_soros):
					if self.soros_atual < len(self.ciclos_soros[ciclo_atual]):
						self.valor = self.ciclos_soros[ciclo_atual][self.soros_atual]
						self.mostrar_mensagem(
							f"[SOROS] ciclo {ciclo_atual+1} R$ {valor} -> R$ {self.valor}")
						self.soros_atual += 1
					else:
						self.mostrar_mensagem(f"[SOROS] {ciclo_atual+1}° ciclo completo.")
						self.config["ciclos"]["soros"] += 1
						self.soros_atual = 0
						self.valor = self.valor_inicial
				else:
					self.mostrar_mensagem("[SOROS] Voltando ao primeiro ciclo")
					self.config["ciclos"]["soros"] = 0
					self.soros_atual = 0
					self.valor = self.valor_inicial
			elif self.soros_atual < self.config['max_soros']:
				# Caso estiver em sorosgale
				verificador = True
				if self.perda_atual > 0:
					self.perda_atual -= lucro
					if self.perda_atual < 0: 
						# Caso terminou o sorosgale
						verificador = False
						self.perda_atual = 0

				if verificador:
					novo = valor + lucro
					self.mostrar_mensagem(
						f"\n [SOROS] : R$ {round(valor, 2)} -> R$ {round(novo, 2)}")
					self.valor = novo
					self.soros_atual += 1
			elif fazendo_soros:
				self.soros_atual = 0
				self.mostrar_mensagem(
					f" [SOROS] Preservando capital: R$ {round(valor, 2)} -> R$ {self.valor_inicial}")
				self.valor = self.valor_inicial
		
		if resultado == "loose" or resultado == "equal":
			if ((self.config['max_soros'] > 0 and fazendo_soros)
				or self.config['on_ciclos_soros']) and self.soros_atual > 0:
				self.soros_atual = 0
				self.mostrar_mensagem(
					f" [SOROS] Preservando capital: R$ {round(valor, 2)} -> R$ {self.valor_inicial}")
				self.valor = self.valor_inicial
			
			if (self.config['tipo_gale'] == "martingale" and 
				self.config['vez_gale'] == "vela") or (
				self.config['tipo_gale'] == 'ciclos'):
				perda, num_gales, ciclo_atual = 0, 0, 0
				if self.config['tipo_gale'] == 'ciclos':
					ciclo_atual = self.config["ciclos"]['gales']
					max_gale = len(self.ciclos_gale[ciclo_atual])
					self.config['tipo_martin'] = f"ciclo {ciclo_atual+1}"
				else:
					max_gale = self.max_gale
				while (max_gale > num_gales and lucro < 0
					and self.stopwin > self.ganho_total):
					
					if resultado not in ["error", "equal"]:
						desconta_perda(resultado, lucro, True)
						mostra_resultado()
		
					# self.esperar_anteriores(threading.currentThread().name)
					# threading.currentThread().setName(str(time.time()))

					if self.perda_total <= -(self.stoploss):
						self.ganhos_perdas[1] += 1
						self.mostrar_mensagem(
							f"🥵 Stop Loss 🥵\nR$ {round(self.perda_total, 2)}!\
							⚠️ {BOTNAME} parado ⚠️")
						sys.exit(0)

					print(f"\n [MARTINGALE] do tipo {self.config['tipo_martin']} na operação {par}|{ordem}")
						
					if resultado not in ["error", "equal"]:
						perda += abs(lucro)
						num_gales += 1

						lucro = valor * payout
						valor = self.martingale(self.config['tipo_martin'], 
							payout, perda, valor, lucro)
					
					valor = 1 if valor < 1 else valor # Caso der doji

					resultado, lucro = self.ordem(
						par, ordem, tempo, valor, tipo, 
						self.cadeado, self.config['delay'])
				
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

		if resultado != "error":
			if resultado != "equal": desconta_perda(resultado, lucro)      
			time.sleep(3)          
			mostra_resultado()

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
		
		if self.verboso:
			mensagem = self.telegram.sendMessage(self.verboso, "Conectado com sucesso.")
			self.message_id = mensagem['message_id']

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
					self.mostrar_mensagem(
						f"[❗️] {par}|{ordem} às {horas}:{minutos} entrou contra a tendência. [❗️]")
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
					self.mostrar_mensagem(f"[❗️] {par}|{ordem.upper()} payout: {payout * 100}% < {payout_desejado * 100}%. [❗️]")

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
		
		try:
			if self.tipo == "auto":
				for comando in self.comandos:
					par = comando["par"]
					self.API.unsubscribe_strike_list(par, self.config["tempo"])
		except:
			pass
		
		time.sleep(1)
		self.mostrar_mensagem(
			f"\nFim da operação resultado final: R$ {round(self.ganho_total, 2)}\n")

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
			if (-self.stoploss >= self.perda_total or 
				self.ganho_total >= self.stopwin):
				mensagem = "Fim da operação: "
				if self.ganho_total >= self.stopwin:
					mensagem += "🤑 Stop Gain 🤑"
				else:
					mensagem += "🥵 Stop Loss 🥵"
				self.mostrar_mensagem(f'''{mensagem}
		✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌
	Stopwin: {self.stopwin}
	Total ganho: {round(self.ganho_total, 2)}
	Stoploss: {-self.stoploss}
	Total perdido: {round(self.perda_total, 2)}
	⚠️ {BOTNAME} parado ⚠️''')
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
