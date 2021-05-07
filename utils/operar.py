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
	def __init__(self, config, comandos = [], 
		verboso = False, tentativas = 0):
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
					self.config['tipo_soros'] = "normal"

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
				self.ocorreu_gale = False
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
						self.config, self.comandos, 
						self.verboso, self.tentativas)
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

	def realizar_trade(self, valor, paridade, ordem, tempo, 
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
			self.ocorreu_gale = True
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
							self.config['ciclos']['gales'] = 0
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