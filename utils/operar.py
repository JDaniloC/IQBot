import threading, traceback, time, re, sys, amanobot
from utils.investing import extrair_noticias
from datetime import datetime, timedelta
from configparser import RawConfigParser
from utils.IQ import IQ_API
from pprint import pprint

config = RawConfigParser()
config.read(".env")

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
	def __init__(self, config, comandos = [], verboso = False, 
		operacao_lista = True, tentativas = 0):
		self.cadeado = threading.Lock()
		self.comandos = comandos
		self.verboso = verboso
		self.tentativas = tentativas
		self.config = config

		self.ganho_total = 0
		self.perda_total = 0
		self.perda_atual = 0 # Para sorosgale

		pprint(self.config)
		if self.tentativas < 3:
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
				self.ganhos_perdas = [0, 0]
				self.soros_atual = 0
				self.gale_atual = 0

				self.valor = config['valor']
				self.tempo = config['tempo']
				self.stopwin = config["stopwin"]
				self.stoploss = config["stoploss"]
				self.max_gale = config["max_gale"]
				self.ciclos_gale = config["ciclos_gale"]
				self.ciclos_soros = config["ciclos_soros"]
				self.ativar_noticias = (
					config["noticias_hora"] > 0 or 
					config["noticias_minuto"] > 0)

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
				if self.ativar_noticias:
					self.atualizar_noticias()

				if operacao_lista: 
					self.operar_lista()
				else: self.operar_estrategia()
			except KeyboardInterrupt:
				sys.exit(0)
			except Exception as e:
				if type(e) == ConnectionError:
					self.mostrar_mensagem("Não conseguiu se conectar na conta")
					self.tentativas = 3
				else:
					print("Aconteceu um erro na API, tentando novamente.")
				escreve_erros(e)
				
				try:
					print("Continuando as operações...")
					self.tentativas += 1
					self.__init__(
						self.config, self.comandos, self.verboso, 
						operacao_lista, self.tentativas)
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
					self.mostrar_mensagem(f"""Cancelando entrada devido notícia:
	{info['par']} {'⭐' * int(info['impacto'])}
{info['text'].center(60)}""")
					return False
		return True

	def recebe_payout(self, paridade, tempo = 1):
		'''
		Caso estiver em automático, verifica qual o maior
		payout, primeiro vendo se estão abertas.
		'''
		if self.tipo == "auto":
			try:
				payout_binaria = self.payout_binaria(paridade, tempo)
				payout_digital = self.payout_digital(paridade)
				if (payout_binaria and payout_digital 
					and payout_binaria < payout_digital):
					tipo, payout = "digital", payout_digital
				elif (payout_binaria and payout_digital 
					and payout_binaria > payout_digital):
					tipo, payout = "binary", payout_binaria
				elif payout_binaria: 
					tipo, payout = "binary", payout_binaria
				else:
					tipo, payout = "digital", payout_digital
			except:
				tipo, payout = "binary", 0.7
			print(f"Payout de {paridade}: {tipo} {payout * 100}%")
		else:
			payout, tipo = (self.payout_binaria(paridade) 
				if self.tipo != "digital" 
				else self.payout_digital(paridade)), self.tipo
		return tipo, payout

	def verificar_stop(self):
		'''
		Verifica se bateu no stopwin/loss
		Devolve um booleano
		'''
		with self.cadeado:
			if (-self.stoploss >= self.perda_total or 
				self.ganho_total >= self.stopwin):
				mensagem = "Fim da operação: \n"
				if self.ganho_total >= self.stopwin:
					mensagem += "🤑 Stop Gain 🤑"
				else:
					mensagem += "🥵 Stop Loss 🥵"
				placar = f"✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌"
				self.mostrar_mensagem(f'''{mensagem}
{placar.center(50, " ")}
	Stopwin: {self.stopwin}
	Total ganho: {round(self.ganho_total, 2)}
	Stoploss: {-self.stoploss}
	Total perdido: {round(self.perda_total, 2)}
	⚠️ Bot parado ⚠️''')
				return True
		return False

	def verificar_tendencia(self, paridade, direcao, timeframe):
		if (self.config['tendencia'] and not self.calcular_tendencia(
			self.config['tipo_tendencia'], paridade, direcao, 
			timeframe, self.config['periodo_tendencia'])):
			self.mostrar_mensagem(
				f"[❗️] {paridade}|{direcao.upper()} está contra a tendência. [❗️]")
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
{f'✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌'.center(30)}
{f'| Lucro: {perto_win} |'.center(30)}
{f'| Perda: {perto_loss} |'.center(30)}
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
			self.perda_atual > 0) or self.config["tipo_soros"] == "ciclos"):
			if self.config["tipo_soros"] == "ciclos":
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
		
		if resultado in ["loose", "equal"]:
			if ((self.config['max_soros'] > 0 and fazendo_soros)
				or self.config["tipo_soros"] == "ciclos") and self.soros_atual > 0:
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
						perda += abs(lucro)
						lucro = valor * payout
						if self.config['tipo_gale'] == 'ciclos':
							valor = self.ciclos_gale[ciclo_atual][num_gales]
						else:
							valor = self.martingale(
								self.config['tipo_martin'], 
								payout, perda, valor, lucro)
						valor = 1 if valor < 1 else valor # Caso der doji

					# self.esperar_anteriores(threading.currentThread().name)
					# threading.currentThread().setName(str(time.time()))

					if self.perda_total <= -(self.stoploss):
						self.ganhos_perdas[1] += 1
						self.mostrar_mensagem(
							f"🥵 Stop Loss 🥵\nR$ {round(self.perda_total, 2)}!\
							⚠️ Bot parado ⚠️")
						sys.exit(0)

					self.mostrar_mensagem(f"\n [{num_gales}° MARTINGALE] {self.config['tipo_martin']} na {paridade}|{ordem.upper()}")

					if estrategia == "MSF" and num_gales == 0:
						self.esperar_proximo_minuto()
					elif type(estrategia) == list:
						ordem = estrategia[num_gales]

					resultado, lucro = self.ordem(
                        paridade, ordem, tempo, valor, tipo, 
                        self.cadeado, self.config['delay'])
					if resultado not in ["error", "equal"]:
						num_gales += 1
						
				if resultado == "win" and self.config['tipo_stop'] != "fixo":
					self.perda_total += perda
				if self.config['tipo_gale'] == 'ciclos':
					if ciclo_atual == len(self.ciclos_gale) - 1:
						self.mostrar_mensagem(
							"[GALE] Voltando ao primeiro ciclo")
						self.config["ciclos"]['gales'] = 0
					else:
						self.config['ciclos']['gales'] += 1
						self.mostrar_mensagem(
							f"[GALE] Avançando para o {ciclo_atual+1}° ciclo")
				
			elif self.config['tipo_gale'] == "martingale":
				if self.gale_atual < self.max_gale:
					self.mostrar_mensagem(f"\n [{self.gale_atual + 1}° MARTINGALE] {self.config['tipo_martin']} on {paridade}|{ordem.upper()}")
					self.perda_atual += abs(valor)
					self.gale_atual += 1
					lucro = valor * payout
					self.valor = self.martingale(self.config['tipo_martin'], 
						payout, self.perda_atual, valor, lucro)
					self.valor = 2 if self.valor < 2 else self.valor
				else:
					self.valor = self.valor_inicial
					self.gale_atual = 0

			elif self.config['tipo_gale'] == 'sorosgale':
				mensagem = f"\n [SOROSGALE] na operação {paridade}|{ordem} {valor} -> "
				self.perda_atual += abs(valor)
				self.soros_atual = 0
				self.valor = self.perda_atual / 2
				self.valor = 2 if self.valor < 2 else self.valor
				self.mostrar_mensagem(mensagem + str(self.valor))

			elif self.config['tipo_gale'] == 'ciclos':
				ciclo_atual = self.config["ciclos"]['gales']
				if ciclo_atual < len(self.ciclos_gale):
					if self.gale_atual < len(self.ciclos_gale[ciclo_atual]):
						self.valor = self.ciclos_gale[ciclo_atual][self.gale_atual]
						self.gale_atual += 1
					else:
						self.mostrar_mensagem(
							f"[GALE] {ciclo_atual}° ciclo completo.")
						self.config["ciclos"]["gales"] += 1
						self.gale_atual = 0
						self.valor = self.valor_inicial
				else:
					self.mostrar_mensagem(
						"[GALE] Voltando ao primeiro ciclo")
					self.config["ciclos"]["gales"] = 0
					self.gale_atual = 0
					self.valor = self.valor_inicial

		if resultado != "error":
			if resultado != "equal": 
				desconta_perda(resultado, lucro)      
			time.sleep(3)          
			mostra_resultado()
		return resultado

	def operar_lista(self):
		'''
		1 - Percorre todos os comandos.
		2 - Pausa o script até a próxima hora:min
		3 - Calcula o payout da paridade
		4 - Cria uma thread para o método operar
		'''
		def formatHour(number):
			'''
			Converte números de 1 dígito para 2 dígitos:
				0:0 -> 00:00
				2/1/2000 -> 02/01/2000
			'''
			return str(number) if len(str(number)) != 1 else "0" + str(number)

		self.espera = []
		if self.verboso:
			mensagem = self.telegram.sendMessage(self.verboso, "Conectado com sucesso.")
			self.message_id = mensagem['message_id']
		
		# Taxas
		par_taxa = {}  
		for comando in self.comandos:
			if comando["tipo"] == "taxas":
				paridade = comando['par']
				if paridade not in par_taxa:
					par_taxa[paridade] = [comando['taxa']]
				else:
					par_taxa[paridade].append(comando['taxa'])
		
		for paridade, taxas in par_taxa.items():
			thread = threading.Thread(
				target = self.esperar_taxa, 
				name = f"{time.time()}", 
				args = (paridade, taxas),
				daemon = True)
			self.espera.append(thread)
			thread.start()

		# Lista
		self.comandos.sort(key = lambda x: x["timestamp"])
		for comando in self.comandos:
			if comando["tipo"] == "taxas": continue

			data = comando["data"]
			horas, minutos = comando["hora"]
			tempo = comando['timeframe'] if comando['timeframe'] != 0 else self.tempo
			segundos = 0

			if self.esperarAte(horas, minutos, segundos, data, 
                self.config['correcao'] + 1, self.mostrar_mensagem):

				par = comando['par']
				ordem = comando['ordem']
				valor = self.valor
				tipo, payout = self.recebe_payout(par, tempo)

				if self.verificar_tendencia(par, ordem, tempo):
					continue

				if (self.ativar_noticias and
					not self.verificar_noticias(par)):
						continue
				# self.esperar_anteriores()

				if self.verificar_stop():
					break
				
				if self.config["minimo"] / 100 <= payout:
					thread = threading.Thread(
						target = self.operar, 
						name = f"{time.time()}", 
						args = (valor, par, ordem, tempo, payout, tipo),
						daemon = True)
					self.espera.append(thread)
					thread.start()
					self.valor = self.valor_inicial
				else:
					self.mostrar_mensagem(f"{par} não atende o payout mínimo {payout * 100}% < {self.config['minimo']}%")
			else:
				momento = datetime.utcnow().timestamp() - 10800 # -3Horas
				self.mostrar_mensagem(
	f" - {datetime.fromtimestamp(momento).strftime('dia %d - %H:%M')} | {comando['par']} - {formatHour(horas)}:{formatHour(minutos)} passou da hora - ")
        
		for thread in self.espera:
			thread.join()

		time.sleep(1)
		self.mostrar_mensagem(
			f"\nFim da operação resultado final: R$ {round(self.ganho_total, 2)}\n")

	def esperar_taxa(self, par, taxas):
		'''
		1 - Verifica se a taxa atual ultrapassou alguma das especificadas
		2 - Cria uma thread para o método operar
		'''
		self.API.start_candles_stream(par, 60, 1)
		ultimo = {}
		while ultimo == {}:
			ultimo = self.API.get_realtime_candles(par, 60)
			ultimo = ultimo[list(ultimo.keys())[0]]['close']
			time.sleep(1)

		self.mostrar_mensagem(f"{par.upper()} esperando bater nas taxas:")
		self.mostrar_mensagem('\n'.join(list(map(str, taxas))))
		chegou_perto = 0
		while not self.verificar_stop() and taxas != []:
			velas = self.API.get_realtime_candles(par, 60)
			abertura = velas[list(velas.keys())[0]]['open']
			fechamento = velas[list(velas.keys())[0]]['close']

			for taxa in taxas:
				if (fechamento >= taxa and ultimo < taxa or 
					fechamento <= taxa and ultimo > taxa):

					direcao = "call" if abertura > fechamento else "put"
					tipo, payout = self.recebe_payout(par, self.tempo)

					if (self.ativar_noticias and
						not self.verificar_noticias(par)):
						continue

					if self.config["minimo"] / 100 <= payout:
						self.mostrar_mensagem(f"Taxas: {par} {taxa} ")
						thread = threading.Thread(
							target = self.operar, 
							name = f"{time.time()}", 
							args = (self.valor, par, direcao, 
								self.tempo, payout, tipo),
							daemon = True
						)
						self.espera.append(thread)
						thread.start()
					else:
						self.mostrar_mensagem(f"{par} {taxa} não atende o payout mínimo {payout} {self.config['minimo']}")

					taxas.remove(taxa)
				else:
					if (abs(taxa - fechamento) < 0.00001 and 
						chegou_perto != abs(taxa - fechamento)):
						chegou_perto = abs(taxa - fechamento)
						self.mostrar_mensagem(f"{par} perto da taxa {taxa}")
			ultimo = fechamento
			time.sleep(self.config['correcao'])
		self.API.stop_candles_stream(par, 60)

	def operar_estrategia(self):
		def pegar_velas(par, quantidade, timeframe = 1, modo = "colors"):
			velas = self.API.get_candles(
				par, 60 * timeframe, quantidade, time.time())
			if modo != "colors":
				return [x['close'] for x in velas]

			resultado = []
			if velas != None:
				for i in range(len(velas)):
					print(datetime.fromtimestamp(velas[i]['from']))
					resultado.append(('CALL' if velas[i]['open'] 
					< velas[i]['close'] else 'PUT' if velas[i]['open'] 
					> velas[i]['close'] else 'DOJI'))

			return resultado

		def entrada_estrategias_m1(estrategia, minutos):
			if estrategia == "DAKA":
				entrar = (minutos + 1) % 4 == 0
			else:
				if minutos >= 10: minutos = int(str(minutos)[1])
				if estrategia == "R7":
					entrar = minutos == 5 # Quadrante de 10 velas
				elif estrategia in [
					"MSF", "HOPE", "Torres Gêmeas", 'Três Vizinhos']:
					entrar = minutos == 3 or minutos == 8 # 5° vela
				elif estrategia in ["Três Mosqueteiros"]:
					entrar = minutos == 2 or minutos == 7 # 4° vela
				elif estrategia in ["Melhor de 3"]:
					entrar = minutos == 1 or minutos == 6 # 3° vela
				elif estrategia in ["Padrão 23"]:
					entrar = minutos == 0 or minutos == 5 # 2° vela
				else:
					entrar = minutos == 4 or minutos == 9 # 1° vela
			return entrar

		def velas_por_estrategia_m1(par, estrategia):
			if estrategia in ["MHI", "MHI2", "MHI3"]:
				velas = pegar_velas(par, 3)
			elif estrategia == "Padrão Impar":
				velas = [pegar_velas(par, 3)[0]]
			elif estrategia == "HOPE":
				velas = pegar_velas(par, 4)[::2]
			elif estrategia == "Torres Gêmeas":
				velas = [pegar_velas(par, 4)[0]]
			elif estrategia == "Melhor de 3":
				velas = pegar_velas(par, 6)[:-3]
			elif estrategia == "Milhão":
				velas = pegar_velas(par, 5)
			elif estrategia == "Vituxo":
				velas = pegar_velas(par, 5)[:3]
			elif estrategia == "C3":
				velas = pegar_velas(par, 5)[::2]
			elif estrategia in ["MSF", "R7"]:
				velas = [pegar_velas(par, 9)[0]]
			else:
				velas = pegar_velas(par, 1)
			return velas

		def entrada_estrategias_m5(estrategia, minutos):
			if estrategia == "Super 3":
				entrar = minutos == 14 or minutos == 44
			elif estrategia == "Três Mosqueteiros":
				entrar = minutos in [9, 24, 39, 54]
			elif estrategia in ["Torres Gêmeas", 
				"MHI", "MHI2", "MHI3", "Milhão"]:
				entrar = minutos == 59
			elif estrategia in ["Five Flip"]:
				entrar = minutos == 54
			elif estrategia == "Power": 
				entrar = minutos in [59, 14, 29, 44]
			else:
				entrar = minutos == 29 or minutos == 59
			return entrar

		def velas_por_estrategia_m5(par, estrategia):
			if estrategia == "Last of five":
				velas = pegar_velas(par, 5, 5)
			elif estrategia == "Três Mosqueteiros":
				velas = pegar_velas(par, 2, 5)
			elif estrategia in ["MHI", "MHI2", "MHI3"]:
				velas = pegar_velas(par, 3, 5)
			elif estrategia in ["Milhão"]:
				velas = pegar_velas(par, 6, 5)
			elif estrategia in ["Torres Gêmeas"]:
				velas = [pegar_velas(par, 5, 5)[0]]
			elif estrategia in ["Five Flip"]:
				velas = [pegar_velas(par, 1, 5)[0]]
			else:
				velas = pegar_velas(par, 3, 5)
			return velas

		def entrada_estrategias_m15(estrategia, minutos):
			if estrategia in [
				"Hora do equilibrio", "Turn Over"]:
				entrar = minutos == 59
			else:
				entrar = minutos == 29
			return entrar

		def velas_por_estrategia_m15(par, estrategia):
			if estrategia == "Half hour":
				velas = [pegar_velas(par, 2, 15)[0]]
			elif estrategia == "Primeiros trocados":
				velas = pegar_velas(par, 2, 15)[0]
				velas = ["call"] if velas == "put" else ["put"]
			elif estrategia == "Turn Over":
				velas = pegar_velas(par, 1, 15)[0]
				velas = ["call"] if velas == "put" else ["put"]
			else:
				velas = pegar_velas(par, 4, 15)
			return velas
		
		def verifica_entrada(estrategia, timeframe):
			minutos = datetime.now().minute
			if timeframe == 1:
				permitir = entrada_estrategias_m1(estrategia, minutos)
			elif timeframe == 5:
				permitir = entrada_estrategias_m5(estrategia, minutos)
			else:
				permitir = entrada_estrategias_m15(estrategia, minutos)
			return permitir

		def recebe_velas(paridade, estrategia, timeframe):
			self.mostrar_mensagem('Verificando cores...')
			if timeframe == 1:
				velas = velas_por_estrategia_m1(paridade, estrategia)
			elif timeframe == 5:
				velas = velas_por_estrategia_m5(paridade, estrategia)
			else:
				velas = velas_por_estrategia_m15(paridade, estrategia)
			self.mostrar_mensagem(" ".join(
				velas).replace("CALL", "🟢").replace("PUT", "🔴"))
			return velas

		def pegar_catalogacao():
			paridade, estramilhao = self.catalogar(
				self.config["autotime"], 
				self.config["autogale"])
			estrategia, tipo_milhao = estramilhao
			return paridade, estrategia, tipo_milhao

		if self.config["auto"]:
			paridade, estrategia, tipo_milhao = pegar_catalogacao()
			timeframe = self.config["autotime"]
		else:
			tipo_milhao = self.config['tipo_milhao']
			paridade = self.config['paridade']
			estrategia = self.config['estrategia']
			timeframe = 5 if (estrategia in [
				"Super 5", "Super 3", "Power",
				"Last of five", "Five Flip"
			] or "M5" in estrategia) else 15 if estrategia in [
			"Half hour", "Primeiros trocados", "Hora do equilibrio"
			] else 1
			estrategia = estrategia.replace("M5: ", "")

		self.mostrar_mensagem(f"Seguindo {estrategia} pela {tipo_milhao} em {paridade}")
		self.mostrar_mensagem("Esperando uma oportunidade")
		while not self.verificar_stop():            
			if verifica_entrada(estrategia, timeframe):
				velas = recebe_velas(paridade, estrategia, timeframe)

				direcao = False
				if velas.count("DOJI") == 0 and not (estrategia == "Milhão" and timeframe == 5):
					if estrategia in ["MSF", "Power",
						"Super 5", "Super 3", "Last of five",
						"Milhão", "MHI", "MHI2", "MHI3",
						"Vituxo", "Hora do equilibrio"]:	
						direcao = velas.count('CALL') > velas.count('PUT')
						direcao = "call" if direcao else "put"
						if tipo_milhao == "Minoria" or estrategia in [
							"Hora do equilibrio", "MSF", "Power"]:
							direcao = "put" if direcao == "call" else "call"
							if (estrategia == "Power" and 
								direcao.upper() != velas[1]):
								direcao = False
					elif timeframe == 5 and estrategia == "Três Mosqueteiros":
						if velas[0] != velas[1]: direcao = velas[0].lower()
					else:
						if estrategia != "HOPE" or velas[0] == velas[1]:
							direcao = velas[0].lower()
				elif velas.count("DOJI") > 2 and estrategia == "Milhão" and timeframe == 5:
					if velas.count("CALL") != velas.count("PUT"):
						direcao = velas.count('CALL') > velas.count('PUT')
						direcao = "call" if direcao else "put"
						if tipo_milhao == "Minoria": 
							direcao = "put" if direcao == "call" else "call"

				if direcao:
					self.mostrar_mensagem(f'Direção: {direcao.upper()}')
					if self.verificar_tendencia(paridade, direcao, timeframe):
						continue

					if estrategia == "MHI2":
						self.esperar_proximo_minuto(timeframe)
					elif estrategia in ["MHI3", "Vituxo"]:
						self.esperar_proximo_minuto(timeframe * 2)

					tipo, payout = self.recebe_payout(
						paridade, timeframe)
					gale = False
					if estrategia == "MSF": gale = "MSF"
					elif estrategia == "C3": gale = velas

					if self.config["minimo"] / 100 <= payout:
						result = self.operar(self.valor, paridade, direcao, 
							timeframe, payout, tipo, gale)
						if result == "loose" and self.config["auto"]:
							paridade, estrategia, tipo_milhao = pegar_catalogacao()
							self.mostrar_mensagem(f"Seguindo {estrategia} pela {tipo_milhao} em {paridade}")
					else:
						self.mostrar_mensagem(f"{paridade} não atende o payout mínimo {payout * 100}% < {self.config['minimo']}%")
			self.esperar_proximo_minuto()
		self.mostrar_mensagem(
	f"\nFim da operação resultado final: R$ {round(self.ganho_total, 2)}\n")
