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

		senha = self.config['senha']
		del self.config['senha']
		pprint(self.config)
		self.config['senha'] = senha

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
				self.ativar_noticias = (
					config["noticias_hora"] > 0 or 
					config["noticias_minuto"] > 0)

				empty = lambda x: x != []
				self.ciclos_gale = list(filter(empty, config["ciclos_gale"]))
				if len(self.ciclos_gale) == 0 and config["tipo_gale"] == "ciclos":
					self.mostrar_mensagem(
						"🌀 Nenhum ciclo detectado, mudando para martingale 🌀")
					config["tipo_gale"] = "martingale"
				self.ciclos_soros = list(filter(empty, config["ciclos_soros"]))
				if len(self.ciclos_soros) == 0:
					self.config['on_ciclos_soros'] = False

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
				self.fim_da_operacao = False
				if config['tendencia']:
					self.config['correcao'] += 3
				if self.ativar_noticias:
					self.atualizar_noticias()

				self.mostrar_mensagem(f"""
📝Revise as suas configurações:
👤 Conta: {config['tipo_conta'].upper()}
💰 Banca: $ {self.saldo_inicial}
💵 Valor da Entrada: $ {self.valor_inicial}
❇️ Stop Gain: $ {self.stopwin}
🚫 Stop Loss: $ {self.stoploss}
				""")

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
		else:
			payout, tipo = (self.payout_binaria(paridade) 
				if self.tipo != "digital" 
				else self.payout_digital(paridade)), self.tipo
		print(f"Payout de {paridade}: {tipo} {payout * 100}%")
		return tipo, payout

	def verificar_stop(self):
		'''
		Verifica se bateu no stopwin/loss
		Devolve um booleano
		'''
		with self.cadeado:
			if (-self.stoploss >= self.perda_total or 
				self.ganho_total >= self.stopwin) and not self.fim_da_operacao:
				self.fim_da_operacao = True
				mensagem = "🔰 Placar Final 🔰"
				if self.ganho_total >= self.stopwin:
					mensagem = "🤑 Stop WIN batido! 🤑"
				elif -self.stoploss >= self.perda_total:
					mensagem = "🥵 Stop LOSS batido! 🥵"
				placar = f"✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌"
				somatorio = sum(self.ganhos_perdas)
				assertividade = self.ganhos_perdas[0] / somatorio * 100 if somatorio > 0 else 0
				
				perda_total = self.perda_total
				if perda_total > 0: perda_total = 0
				self.mostrar_mensagem(f'''
{mensagem}
{placar.center(32, " ")}
💰 Saldo: $ {round(self.ganho_total, 2)} | $ {self.stopwin}
💲 Perca: $ {round(perda_total, 2)} | $ {-self.stoploss}
✴️ Assertividade: {round(assertividade, 2)}%
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

	def win_case(self, is_ciclo, in_soros, valor, lucro, gale_text = ""):
		if is_ciclo:
			self.config["ciclos"]['gales'] = 0
		gale_text, num_gales = "", 0

		if self.config["tipo_soros"] == "ciclos":
			ciclo_atual = self.config["ciclos"]["soros"]
			ciclos = self.ciclos_soros
			soros_atual = self.soros_atual + 1
			if ciclo_atual < len(ciclos):
				if soros_atual < len(ciclos[ciclo_atual]):
					self.valor = ciclos[ciclo_atual][soros_atual]
					gale_text = f"🔸 Soros no {ciclo_atual+1}° ciclo $ {valor} -> $ {self.valor}"
					self.soros_atual += 1
				else:
					gale_text = f"🔸 Soros: {ciclo_atual+1}° ciclo completo."
					self.config["ciclos"]["soros"] += 1
					self.soros_atual = 0
					self.valor = self.valor_inicial
			else:
				gale_text = "🔸 Soros: Voltando ao primeiro ciclo"
				self.config["ciclos"]["soros"] = 0
				self.soros_atual = 0
				self.valor = self.valor_inicial
		elif self.soros_atual < self.config['max_soros']:
			# Caso estiver em sorosgale
			fazer_soros = True
			if self.perda_atual > 0:
				self.perda_atual -= lucro
				if self.perda_atual < 0: 
					# Caso terminou o sorosgale
					fazer_soros = False
					self.perda_atual = 0
			if fazer_soros:
				novo = valor + lucro
				gale_text = f"🔸 Soros: $ {round(valor, 2)} para $ {round(novo, 2)}"
				self.valor = novo
				self.soros_atual += 1
		elif in_soros:
			self.soros_atual = 0
			self.valor = self.valor_inicial
			gale_text = f"🔸 Soros: $ {round(valor, 2)} para $ {self.valor_inicial}"
		elif self.gale_atual > 0:
			num_gales = self.gale_atual
			self.gale_atual = 0
			self.perda_atual -= abs(valor)
			self.valor = self.valor_inicial
			if self.perda_atual < 0: self.perda_atual = 0

		return gale_text, num_gales

	def operar(self, valor, paridade, ordem, tempo, 
		payout, tipo, estrategia = False):
		'''
		Faz a operação e a depender da configuração faz:
		Martingale/Sorosgale e calcula o ganhoTotal/perdaTotal
		'''
		num_gales = 0
		def mostra_resultado():
			perda_total = round(-self.perda_total, 2)
			if perda_total < 0:
				perda_total = 0
			perto_loss = f"🔻 Stop Móvel: $ {perda_total} | $ {self.stoploss}"
			somatorio = sum(self.ganhos_perdas)
			assertividade = (self.ganhos_perdas[0] / somatorio * 100 
				if somatorio > 0 else 0)
			threading.Thread(
				target = self.mostrar_mensagem,
				args = (f"""
💎 Saldo atual:  R$ {round(self.saldo_inicial + self.ganho_total, 2)}
✅ Vitórias: {self.ganhos_perdas[0]}
❌ Derrotas: {self.ganhos_perdas[1]}
💰 Lucro: {round(self.ganho_total, 2)}
{perto_loss if self.config['tipo_stop'] != 'fixo' else ''}
✴️ Assertividade: {round(assertividade, 2)}%""", )).start()

		def desconta_perda(resultado, lucro, 
			in_gale = "", entrada = None):
			with self.cadeado:
				inicial = self.saldo_inicial
				atual = round(self.saldo_inicial + self.ganho_total, 2)
				if entrada == None: entrada = valor
				mensagem = "⚪️"
				if resultado == "win":
					self.ganho_total += round(lucro, 2)
					self.ganhos_perdas[0] += 1
					mensagem = (num_gales * "🐔 ") + "✅"
					if self.config['tipo_stop'] == "fixo":
						self.perda_total += round(lucro, 2)
				else:
					if resultado == 'loose':
						if "♦️" in in_gale or in_gale == "":
							self.ganhos_perdas[1] += 1
							mensagem = "❌"
						else:
							mensagem = num_gales * "🐔"
						lucro = abs(lucro) * -1
					self.ganho_total -= round(abs(lucro), 2)
					self.perda_total -= round(abs(lucro), 2)

				threading.Thread(target = self.mostrar_mensagem,
						args = (self.format_dir(f"""
{paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
💠Valor: $ {round(entrada, 2)} 
💰Resultado: $ {round(lucro, 2)} {mensagem}   
{in_gale}"""), )).start()
		tipo_gale = self.config['tipo_gale']
		is_ciclos_gale = tipo_gale == 'ciclos'
		fazendo_soros = self.soros_atual > 0

		if (valor == self.valor_inicial or 
			self.config["ciclos"]["gales"] > 0):
			if is_ciclos_gale:
				ciclo_atual = self.config["ciclos"]['gales']
				if ciclo_atual >= len(self.ciclos_gale):
					ciclo_atual = 0
				valor = self.ciclos_gale[ciclo_atual][0]
			elif self.config["tipo_soros"] == "ciclos":
				ciclo_atual = self.config["ciclos"]["soros"]
				if ciclo_atual >= len(self.ciclos_soros):
					ciclo_atual = 0
				valor = self.ciclos_soros[ciclo_atual][0]
			if valor != self.valor_inicial:
				self.mostrar_mensagem(
					f"🔸 Operando no {ciclo_atual + 1}° Ciclo: R$ {round(valor, 2)}")

		resultado, lucro = None, 0
		for i in range(2):
			try:
				resultado, lucro = self.ordem(
					paridade, ordem, tempo, valor, tipo, 
					self.cadeado, self.config['delay'], 
					self.config["scalper"])
				break
			except Exception as e:
				self.mostrar_mensagem(
					f"Ocorreu um erro na operação:\n {type(e)}: {e}")
				self.conectar()
		if resultado == None:
			raise ConnectionAbortedError(
				"Não estou conseguindo fazer as operações.")
		
		texto_gale = ""
		if resultado == "win" and (self.config['max_soros'] > 0 or 
			(tipo_gale == "sorosgale" and self.perda_atual > 0) 
			or self.config["tipo_soros"] == "ciclos" 
			or (self.gale_atual > 0 and tipo_gale == "martingale")):
			texto_gale, num_gales = self.win_case(
				is_ciclos_gale, fazendo_soros, valor, lucro)
			
		if resultado == "loose": 
			tipo_martin = self.config['tipo_martin']
			if (is_ciclos_gale or 
				(tipo_gale in "martingale" and 
				self.config['vez_gale'] == "vela")):
				perda, num_gales, ciclo_atual = 0, 0, 0
				if is_ciclos_gale:
					num_gales += 1
					ciclo_atual = self.config["ciclos"]['gales']
					if ciclo_atual >= len(self.ciclos_gale):
						ciclo_atual = 0
					max_gale = len(self.ciclos_gale[ciclo_atual])
					tipo_martin = f"ciclo {ciclo_atual+1}"
				else:
					max_gale = self.max_gale
				
				while (max_gale > num_gales and resultado != "win"
					and self.stopwin > self.ganho_total):

					if resultado != "error":
						if resultado == "loose":
							lucro = abs(lucro) * -1
						
						label_gale = num_gales if is_ciclos_gale else num_gales + 1
						desconta_perda(resultado, lucro, 
							f"🔸 Iniciando {label_gale}° Martingale: {str(tipo_martin).capitalize()} 🔸", valor)
						mostra_resultado()
						perda += abs(lucro)
						lucro = valor * payout
						if tipo_gale == 'ciclos':
							valor = self.ciclos_gale[ciclo_atual][num_gales]
						else:
							valor = self.martingale(
								tipo_martin, payout, 
								perda, valor, lucro)
						valor = 2 if valor < 2 else valor # Caso der doji
					
					if self.perda_total <= -(self.stoploss):
						self.ganhos_perdas[1] += 1
						self.mostrar_mensagem(f"🥵 Stop Loss 🥵\n💲 Perca: R$ {round(self.perda_total, 2)}\n⚠️ Bot parado ⚠️")
						sys.exit(0)

					if estrategia == "MSF" and num_gales == 0:
						self.esperar_proximo_minuto()
					elif type(estrategia) == list:
						ordem = estrategia[num_gales]

					resultado, lucro = self.ordem(
						paridade, ordem, tempo, valor, tipo,
						self.cadeado, self.config['delay'])
					if resultado != "win":
						num_gales += 1
				if (resultado == "win" and 
					self.config['tipo_stop'] != "fixo"):
					self.perda_total += perda
				
				if is_ciclos_gale:
					num_gales -= 1
					if (resultado == "win" or
						ciclo_atual == len(self.ciclos_gale) - 1):
						texto_gale = "🔸 Voltando ao primeiro ciclo"
						if resultado != "win":
							texto_gale = "♦️" + texto_gale[1:]
						else:
							texto_gale, num_gales = self.win_case(
								is_ciclos_gale, fazendo_soros, 
								valor, lucro, texto_gale)
					elif resultado == "loose":
						self.config['ciclos']['gales'] += 1
						texto_gale = f"♦️ Avançando para o {ciclo_atual+2}° ciclo"
				
				if resultado == "equal" or lucro == 0:
					lucro = -perda

			elif tipo_gale == "martingale":
				if self.gale_atual < self.max_gale:
					texto_gale = f"🔸 {self.gale_atual + 1}° Martingale: {tipo_martin} para o próximo sinal"
					self.perda_atual += abs(valor)
					self.gale_atual += 1
					lucro = valor * payout
					self.valor = self.martingale(
						tipo_martin, payout, 
						self.perda_atual, valor, lucro)
					self.valor = 2 if self.valor < 2 else self.valor
				else:
					self.valor = self.valor_inicial
					self.gale_atual = 0

			elif tipo_gale == 'sorosgale':
				self.perda_atual += abs(valor)
				self.soros_atual = 0
				self.valor = self.perda_atual / 2
				self.valor = 2 if self.valor < 2 else self.valor
				texto_gale = f"🔸 Sorosgale: {valor} para {self.valor}"

			elif is_ciclos_gale:
				ciclo_atual = self.config["ciclos"]['gales']
				if ciclo_atual < len(self.ciclos_gale):
					if self.gale_atual < len(self.ciclos_gale[ciclo_atual]):
						self.valor = self.ciclos_gale[ciclo_atual][self.gale_atual]
						self.gale_atual += 1
					else:
						texto_gale = f"🔸 Gale {ciclo_atual}° completo."
						self.config["ciclos"]["gales"] += 1
						self.gale_atual = 1
						self.valor = self.valor_inicial
				else:
					texto_gale = f"♦️ Gale: Voltando ao primeiro ciclo"
					self.config["ciclos"]["gales"] = 0
					self.gale_atual = 1
					self.valor = self.valor_inicial

			if (((self.config['max_soros'] > 0 and fazendo_soros) or 
				self.config["tipo_soros"] == "ciclos") 
				and self.soros_atual > 0 and 
				resultado == "loose"):
				self.soros_atual = 0
				self.valor = self.valor_inicial
				self.config["ciclos"]["soros"] = 0
				if self.config["tipo_soros"] == "ciclos":
					self.valor = self.ciclos_soros[0][0]
				self.mostrar_mensagem(
					f"🔸 Soros: R$ {round(valor, 2)} para R$ {self.valor}")
			
		if resultado != "error":
			if resultado != "equal": 
				desconta_perda(resultado, lucro, texto_gale)      
			else:
				self.mostrar_mensagem(self.format_dir(f"""
{paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
	💰 $ {round(valor, 2)} | $ 0,00 💰"""))
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
				self.mostrar_mensagem(f" ⏰ {comando['par']} - {formatHour(horas)}:{formatHour(minutos)} passou da hora ⏰ ")
        
		for thread in self.espera:
			thread.join()

		time.sleep(1)
		self.verificar_stop()

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

		def proxima_entrada(min_list, estrategia, timeframe, isM1 = False):
			minutos = str(datetime.now().minute).zfill(2)
			for i in range(len(min_list)):
				if isM1:
					option = int(f"{minutos[0]}{min_list[i]}"
						) if estrategia != "DAKA" else min_list[i]
				else:
					option = min_list[i]
				
				if option > int(minutos):
					entrar = option
					break
				elif i == len(min_list) - 1:
					entrar = min_list[0]

			maisUm = timeframe * 60 if estrategia not in [
				"MHI2", "MHI3", "Vituxo"
			] else timeframe * 60 * 2 + 60 if (
				estrategia == "MHI2"
			) else timeframe * 60 * 3 + 60

			agora = datetime.fromtimestamp(
				datetime.utcnow().timestamp() - 10800).replace(
				minute = entrar, second = 0) + timedelta(seconds = maisUm)

			if agora.timestamp() - time.time() < 0:
				agora += timedelta(hours = 1)
			horario = agora.strftime(f'%H:%M')
			self.mostrar_mensagem(f"⏰ Próxima entrada será às {horario} ⏰")

		def entrada_estrategias_m1(estrategia, minutos, proxima = False):
			if estrategia == "DAKA":
				entrada = [3, 7, 11, 15, 19, 23, 
					27, 31, 35, 39, 43, 47, 51, 59]
			else:
				if minutos >= 10: minutos = int(str(minutos)[1])
			
			if estrategia == "R7":
				entrada = [5] # Quadrante de 10 velas
			elif estrategia in [
				"MSF", "HOPE", "Torres Gêmeas", 'Três Vizinhos']:
				entrada = [3, 8] # 5° vela
			elif estrategia in ["Três Mosqueteiros"]:
				entrada = [2, 7] # 4° vela
			elif estrategia in ["Melhor de 3"]:
				entrada = [1, 6] # 3° vela
			elif estrategia in ["Padrão 23"]:
				entrada = [0, 5] # 2° vela
			else:
				entrada = [4, 9] # 1° vela

			if proxima: proxima_entrada(entrada, estrategia, proxima, True)
			return minutos in entrada

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

		def entrada_estrategias_m5(estrategia, minutos, proxima = False):
			if estrategia in ["Três Mosqueteiros", "Triplicação"]:
				entrada = [9, 24, 39, 54]
			elif estrategia == "Milhão":
				entrada = [59]
			elif estrategia in ["Torres Gêmeas", "Five Flip"]:
				entrada = [24, 54]
			elif estrategia in ["Power", "GABA"]: 
				entrada = [14, 29, 44, 59]
			elif estrategia == 'Três Vizinhos':
				entrada = [19, 49]
			else:
				entrada = [29, 59]

			if proxima: proxima_entrada(entrada, estrategia, proxima)
			return minutos in entrada

		def velas_por_estrategia_m5(par, estrategia):
			if estrategia == "Last of five":
				velas = pegar_velas(par, 5, 5)
			elif estrategia in ["Três Mosqueteiros", "Triplicação"]:
				velas = pegar_velas(par, 2, 5)
			elif estrategia in ["Milhão"]:
				velas = pegar_velas(par, 6, 5)
			elif estrategia in ["Torres Gêmeas"]:
				velas = [pegar_velas(par, 6, 5)[0]]
			elif estrategia in ["Five Flip", 'Três Vizinhos']:
				velas = [pegar_velas(par, 1, 5)[0]]
			else:
				velas = pegar_velas(par, 3, 5)
			return velas

		def entrada_estrategias_m15(estrategia, minutos, proxima = False):
			if estrategia in ["MHI", "MHI2", "MHI3", 
				"Torres Gêmeas", "Hora do equilibrio", 
				"Turn Over"]:
				entrada = [59]
			elif estrategia == "Torres Gêmeas":
				entrada = [44]
			else:
				entrada = [29]

			if proxima: proxima_entrada(entrada, estrategia, proxima)
			return minutos in entrada

		def velas_por_estrategia_m15(par, estrategia):
			if estrategia == "Half hour":
				velas = [pegar_velas(par, 2, 15)[0]]
			elif estrategia == "Primeiros trocados":
				velas = pegar_velas(par, 2, 15)[0]
				velas = ["call"] if velas == "put" else ["put"]
			elif estrategia == "Turn Over":
				velas = pegar_velas(par, 1, 15)[0]
				velas = ["call"] if velas == "put" else ["put"]
			elif estrategia in ["MHI", "MHI2", "MHI3"]:
				velas = pegar_velas(par, 3, 15)
			elif estrategia == "Torres Gêmeas":
				velas = [pegar_velas(par, 4, 15)[0]]
			else:
				velas = pegar_velas(par, 4, 15)
			return velas
		
		def verifica_entrada(estrategia, timeframe, proxima = False):
			minutos = datetime.now().minute
			if proxima: proxima = timeframe

			if timeframe == 1:
				permitir = entrada_estrategias_m1(
					estrategia, minutos, proxima)
			elif timeframe == 5:
				permitir = entrada_estrategias_m5(
					estrategia, minutos, proxima)
			else:
				permitir = entrada_estrategias_m15(
					estrategia, minutos, proxima)
			return permitir

		def recebe_velas(paridade, estrategia, timeframe):
			if timeframe == 1:
				velas = velas_por_estrategia_m1(paridade, estrategia)
			elif timeframe == 5:
				velas = velas_por_estrategia_m5(paridade, estrategia)
			else:
				velas = velas_por_estrategia_m15(paridade, estrategia)
			self.mostrar_mensagem(" ".join(velas).replace("CALL", "🟢"
				).replace("PUT", "🔴").replace("DOJI", "⚪️"))
			return velas

		def pegar_catalogacao():
			porcentagem, paridade, estramilhao = self.catalogar_estrategia(
				self.config["autotime"], 
				self.config["autogale"])
			estrategia, tipo_milhao = estramilhao
			payout = 100 * self.recebe_payout(paridade, self.config["autotime"])[1]
			self.mostrar_mensagem(f"""
🔹 {estrategia} pela {tipo_milhao.capitalize()} | Paridade: {paridade} ♦️
🎯 Assertividade: {porcentagem}% | Payout: {payout}% ❇️""")
			return paridade, estrategia, tipo_milhao

		if self.config["auto"]:
			paridade, estrategia, tipo_milhao = pegar_catalogacao()
			timeframe = self.config["autotime"]
		else:
			tipo_milhao = self.config['tipo_milhao']
			paridade = self.config['paridade']
			estrategia = self.config['estrategia']
			timeframe = 5 if (estrategia in [
				"Power", "Last of five", 
				"Five Flip", "Triplicação"
			] or "M5" in estrategia) else 15 if (
			estrategia in [
				"Half hour", "Primeiros trocados", 
				"Hora do equilibrio"
			] or "M15" in estrategia) else 1
			estrategia = estrategia.replace("M5: ", "").replace("M15: ", "")
			payout = 100 * self.recebe_payout(paridade, self.config["autotime"])[1]
			self.mostrar_mensagem(f"""
🔹 {estrategia} pela {tipo_milhao.capitalize()} | Paridade: {paridade} ♦️
❇️ Payout: {payout}%""")

		verifica_entrada(estrategia, timeframe, True)
		while not self.verificar_stop():            
			if verifica_entrada(estrategia, timeframe):
				velas = recebe_velas(paridade, estrategia, timeframe)

				direcao = False
				if velas.count("DOJI") == 0 and not (
					estrategia == "Milhão" and timeframe == 5):
					if estrategia in ["MSF",  
						"Last of five", "GABA", "Power",
						"Milhão", "MHI", "MHI2", "MHI3",
						"Vituxo", "Hora do equilibrio"]:	
						direcao = velas.count('CALL') > velas.count('PUT')
						direcao = "call" if direcao else "put"
						if tipo_milhao == "Minoria" or estrategia in [
							"Hora do equilibrio", "MSF", "Power", "GABA"]:
							direcao = "put" if direcao == "call" else "call"
							if (estrategia == "Power" and 
								direcao.upper() != velas[1]):
								direcao = False
					elif timeframe == 5 and estrategia == "Três Mosqueteiros":
						if velas[0] != velas[1]: direcao = velas[0].lower()
					elif timeframe == 5 and estrategia == "Triplicação":
						if velas[0] == velas[1]: direcao = velas[0].lower()
					else:
						if estrategia != "HOPE" or velas[0] == velas[1]:
							direcao = velas[0].lower()
				elif (velas.count("DOJI") > 2 and 
					estrategia == "Milhão" and timeframe == 5):
					if velas.count("CALL") != velas.count("PUT"):
						direcao = velas.count('CALL') > velas.count('PUT')
						direcao = "call" if direcao else "put"
						if tipo_milhao == "Minoria": 
							direcao = "put" if direcao == "call" else "call"
				else:
					self.mostrar_mensagem("⏰ A entrada foi cancelada: DOJI")

				if direcao:
					self.mostrar_mensagem(self.format_dir(
						f'Direção: {direcao.upper()}'))
					
					if self.verificar_tendencia(
						paridade, direcao, timeframe):
						continue

					if (self.ativar_noticias and 
						not self.verificar_noticias(paridade)):
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
						if result != "win" and self.config["auto"]:
							paridade, estrategia, tipo_milhao = pegar_catalogacao()
					else:
						self.mostrar_mensagem(f"{paridade} não atende o payout mínimo {payout * 100}% < {self.config['minimo']}%")
				elif self.config["auto"]:
					paridade, estrategia, tipo_milhao = pegar_catalogacao()
				verifica_entrada(estrategia, timeframe, True)
			self.esperar_proximo_minuto()
		self.verificar_stop()
