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
	arquivo = open(LOCALERROR, "a", encoding = "utf-8", errors = "??")
	print(type(erro), erro, file = arquivo)
	traceback.print_exc(file = arquivo)

def escreve_log(email, mensagem):
	print(mensagem + "\n", 
		file = open(LOCALLOG + email + ".txt", 
		"a", encoding = "utf-8", errors = "??"))

class Operacao(IQ_API): 
	def __init__(self, config, comandos = [], chat_id = False):
		self.cadeado = threading.Lock()
		self.chat_id = chat_id
		self.comandos = comandos
		self.config = config
		self.operacoes_ativas = {}	

		# Mostra a configuração sem a senha
		senha = self.config['senha']
		del self.config['senha']
		# pprint(self.config)
		self.config['senha'] = senha

		self.mostrar_mensagem(f"Entrando na {config['email']}")
		super().__init__(config['email'], config['senha'])

		self.resetar_status()
		self.salvar_variaveis(config)

		self.mostrar_mensagem(f"""
📝Revise as suas configurações:
👤 Conta: {config['tipo_conta'].upper()}
💰 Banca: $ {self.saldo_inicial}
💵 Valor da Entrada: $ {self.valor_inicial}
❇️ Stop Gain: $ {self.stopwin}
🚫 Stop Loss: $ {self.stoploss}
🐔 Tipo de gale: {config["tipo_gale"]}
		""")
		
	def salvar_variaveis(self, config):
		self.config.update(config)

		if config['tipo_conta'] == "treino":
			self.mudar_treino()
		else: self.mudar_real()

		if config['tipo_par'] == "auto":
			self.tipo = config['tipo_par']
		else:
			self.tipo = "digital" if (
				config['tipo_par'] == 'digital'
			) else "binary"

		self.stopwin = config["stopwin"]
		self.stoploss = config["stoploss"]
		self.max_gale = config["max_gale"]
		self.valor_inicial = config["valor"]
		
		empty = lambda x: x != []      
		self.ciclos_gale = list(
			filter(empty, config["ciclos_gale"]))
		if len(self.ciclos_gale) == 0 and config["tipo_gale"] == "ciclos":
			self.mostrar_mensagem(
				"🌀 Nenhum ciclo detectado, mudando para martingale 🌀")
			self.config["tipo_gale"] = "martingale"
		
		self.ciclos_soros = list(
			filter(empty, config["ciclos_soros"]))
		if len(self.ciclos_soros) == 0:
			self.config['tipo_soros'] = "normal"
		elif any(map(lambda x: len(x) > 1, self.ciclos_soros)
			) and self.config['tipo_soros'] == 'ciclos':
			self.config['tipo_gale'] = "ciclosoros"

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
		
		if config['tendencia']:
			self.config['correcao'] = self.config.get('correcao', 0) + 3
		self.ativar_noticias = (
			config.get("noticias_pre", 0) > 0 or 
			config.get("noticias_pos", 0) > 0)
		if self.ativar_noticias:
			self.atualizar_noticias()

		if self.chat_id != "":
			self.telegram = amanobot.Bot(BOTTOKEN)

	def resetar_status(self):
		self.saldo_inicial = self.API.get_balance()
		self.valor = self.config["valor"]
		self.fim_da_operacao = False
		self.ganhos_perdas = [0, 0]      
		self.ocorreu_gale = False
		self.perda_atual = 0 # Para sorosgale
		self.ganho_total = 0
		self.perda_total = 0
		self.soros_atual = 0
		self.gale_atual = 0
		self.config["ciclos"] = {
			"gales": 0, "soros": 0
		}

	def mostrar_mensagem(self, mensagem, logs = False):
		'''
		Mostra a mensagem na interface e no terminal/arquivo.
		'''
		print(mensagem)
		if logs: return

		if self.chat_id:
			try:
				self.telegram.sendMessage(self.chat_id, mensagem)
			except Exception as e:
				try:
					self.telegram = amanobot.Bot(BOTTOKEN)
					self.telegram.sendMessage(self.chat_id, mensagem)
				except Exception as e:
					print("mostrar_mensagem()", type(e), e)

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
		agora = datetime.fromtimestamp(
			datetime.utcnow().timestamp() - 10800) # -3Horas
		if (self.ultima_atualizacao_noticia.day != agora.day):
			self.atualizar_noticias()
		for info in self.noticias:
			if agora > info['horario']: 
				diferenca = agora - info['horario']
				cancelar = timedelta(minutes = self.config['noticias_pre']) > diferenca
			else: 
				diferenca = info['horario'] - agora
				cancelar = timedelta(minutes = self.config['noticias_pos']) > diferenca

			if cancelar:
				if info['par'] in paridade.upper() and (
					int(info['impacto']) >= self.config["toros"]):
					self.mostrar_mensagem(
						f"Cancelando entrada devido notícia: {info['par']} {'⭐' * int(info['impacto'])}".center(60))
					self.mostrar_mensagem(f"{info['text']}".center(60))
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
		self.mostrar_mensagem(
			f"Payout de {paridade}: {tipo} {payout * 100}%", True)
		return tipo, payout

	def verificar_stop(self, parar = False):
		'''
		Verifica se bateu no stopwin/loss
		Devolve um booleano
		'''
		if (-self.stoploss >= self.perda_total or 
			self.ganho_total >= self.stopwin or parar):

			mensagem = "🔰 Placar Final 🔰"
			if self.ganho_total >= self.stopwin:
				mensagem = "🤑 Stop WIN batido! 🤑"
			elif -self.stoploss >= self.perda_total:
				mensagem = "🥵 Stop LOSS batido! 🥵"
			placar = f"✅ {self.ganhos_perdas[0]} | {self.ganhos_perdas[1]} ❌"
			somatorio = sum(self.ganhos_perdas)
			assertividade = self.ganhos_perdas[0] / somatorio * 100 if somatorio > 0 else 0
			
			perca = round(self.perda_total, 2)
			if perca > 0: perca = 0
			if not self.fim_da_operacao:
				self.mostrar_mensagem(f'''{mensagem}
	{placar.center(32, " ")}
	💰 Saldo: $ {round(self.ganho_total, 2)} | $ {self.stopwin}
	💲 Perca: $ {perca} | $ {-self.stoploss}
	✴️ Assertividade: {round(assertividade, 2)}%
					⚠️ Bot parado ⚠️''')
				self.fim_da_operacao = True
			return True
		return False

	def verificar_tendencia(self, paridade, direcao, timeframe):
		if (self.config['tendencia'] and not self.calcular_tendencia(
			self.config['tipo_tendencia'], paridade, direcao, 
			timeframe, self.config['periodo_tendencia'])):
			self.mostrar_mensagem(f"[❗️] {paridade}|{direcao.upper()} está contra a tendência. [❗️]")
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

	def win_case(self, in_soros, valor, lucro, gale_text = ""):
		tipo_gale = self.config["tipo_gale"]
		if tipo_gale == "ciclos":
			self.config["ciclos"]['gales'] = 0
			self.gale_atual = 1
		elif tipo_gale == "ciclosoros":
			self.gale_atual = 0

		num_gales = 0
		if self.config["tipo_soros"] == "ciclos":
			ciclo_atual = self.config["ciclos"]["soros"] + 1
			ciclos = self.ciclos_soros
			if ciclo_atual < len(ciclos):
				self.valor = ciclos[ciclo_atual][0]
				self.config["ciclos"]["soros"] += 1
				gale_text = f"🔸 Soros: {ciclo_atual+1}° ciclo completo: \nVariação de $ {valor} -> $ {self.valor}"
			else:
				gale_text = "🔸 Soros: Voltando ao primeiro ciclo"
				self.config["ciclos"]["soros"] = 0
				self.valor = self.valor_inicial
		elif (self.soros_atual < self.config['max_soros'] or 
			(tipo_gale == "sorosgale" and self.perda_atual > 0)):
			# Caso estiver em sorosgale
			fazer_soros = True
			if self.perda_atual > 0:
				self.perda_atual -= lucro
				if self.perda_atual < 0: 
					# Caso terminou o sorosgale
					fazer_soros = False
					self.perda_atual = 0
					self.valor = self.valor_inicial
					gale_text = "🔸 Fim do sorosgale!"
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
			self.mostrar_mensagem(f"""
💎 Saldo atual:  R$ {round(self.saldo_inicial + self.ganho_total, 2)}
✅ Vitórias: {self.ganhos_perdas[0]}
❌ Derrotas: {self.ganhos_perdas[1]}
💰 Lucro: {round(self.ganho_total, 2)}
{perto_loss if self.config['tipo_stop'] != 'fixo' else ''}
✴️ Assertividade: {round(assertividade, 2)}%""")

		def desconta_perda(resultado, lucro, 
			in_gale = "", entrada = None):
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
			
			self.mostrar_mensagem(self.format_dir(f"""
{paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
💠Valor: $ {round(entrada, 2)} 
💰Resultado: $ {round(lucro, 2)} {mensagem}   
{in_gale}"""))

		tipo_gale = self.config['tipo_gale']
		is_ciclos_gale = tipo_gale in ['ciclos', 'ciclosoros']
		fazendo_soros = self.soros_atual > 0

		ciclo_atual = self.config['ciclos']['gales']
		if valor == self.valor_inicial or ciclo_atual > 0:
			if (self.config["tipo_soros"] == "ciclos" 
				and ciclo_atual == 0) or tipo_gale == "ciclosoros":
				ciclo_atual = self.config["ciclos"]["soros"]
				if ciclo_atual >= len(self.ciclos_soros):
					ciclo_atual = 0
				valor = self.ciclos_soros[ciclo_atual][0]
				modalidade = "soros"
			elif tipo_gale == "ciclos":
				if ciclo_atual >= len(self.ciclos_gale):
					ciclo_atual = 0
				valor = self.ciclos_gale[ciclo_atual][0]
				modalidade = "gale"
			
			if valor != self.valor_inicial:
				self.mostrar_mensagem(f"🔸 Operando no {ciclo_atual + 1}° ciclo de {modalidade}: R$ {round(valor, 2)}")

		resultado, lucro = None, 0
		for i in range(2):
			try:
				resultado, lucro, tipo = self.ordem(
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
			or (self.gale_atual > 0 and tipo_gale == "martingale")
			or (is_ciclos_gale and (self.gale_atual > 1 or 
				self.config["ciclos"]["gales"] > 0))):
			texto_gale, num_gales = self.win_case(
				fazendo_soros, valor, lucro)
			
		if resultado == "loose": 
			self.ocorreu_gale = True
			tipo_martin = self.config['tipo_martin']
			if (self.config['vez_gale'] == "vela" and (
				is_ciclos_gale or tipo_gale == "martingale")):
				perda, num_gales, ciclo_atual, errors = 0, 0, 0, 0
				if is_ciclos_gale:
					if tipo_gale == 'ciclos':
						ciclo_atual = self.config["ciclos"]['gales']
						max_gale = len(self.ciclos_gale[ciclo_atual])
						if ciclo_atual >= len(self.ciclos_gale):
							ciclo_atual = 0
					else:
						ciclo_atual = self.config['ciclos']['soros']
						max_gale = len(self.ciclos_soros[ciclo_atual])
						if ciclo_atual >= len(self.ciclos_soros):
							ciclo_atual = 0
					tipo_martin = f"ciclo {ciclo_atual+1}"
					num_gales += 1
				else:
					max_gale = self.max_gale
				
				while (max_gale > num_gales and resultado == "loose"
					and self.stopwin > self.ganho_total):

					if resultado not in ["error", "equal"]:
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
						elif tipo_gale == "ciclosoros":
							valor = self.ciclos_soros[ciclo_atual][num_gales]
						else:
							if tipo_martin == "percent":
								lucro = self.config['martin_pct'] / 100
							self.mostrar_mensagem(
					f"Fazendo martingale {tipo_martin} {payout}% R$ {perda} R$ {valor} R$ {lucro}", True)
							valor = self.martingale(
								tipo_martin, payout, perda, valor, lucro)
						valor = 2 if valor < 2 else valor # Caso der doji

					if self.verificar_stop():
						self.ganhos_perdas[1] += 1
						sys.exit(0)

					if ((estrategia == "msf" and num_gales == 0) 
						or estrategia == "padrão impar"):
						self.esperar_proximo_minuto()
					elif type(estrategia) == list:
						ordem = estrategia[num_gales]

					resultado, lucro, tipo = self.ordem(
						paridade, ordem, tempo, valor, tipo,
						self.cadeado, self.config['delay'])
					if resultado == "loose":
						num_gales += 1
					elif resultado == "error":
						errors += 1
						if errors == 2:
							self.mostrar_mensagem("Não consigo fazer o gale...")
							break
					
				if (resultado == "win" and 
					self.config['tipo_stop'] != "fixo"):
					self.perda_total += perda
				
				if is_ciclos_gale:
					num_gales -= 1
					if (resultado == "win" or (tipo_gale == "ciclos"
						and ciclo_atual == len(self.ciclos_gale) - 1)):
						texto_gale = "🔸 Voltando ao primeiro ciclo"
						if resultado != "win":
							texto_gale = "♦️" + texto_gale[1:]
							self.config['ciclos']['gales'] = 0
							num_gales += 1
						else:
							texto_gale, num_gales = self.win_case(
								fazendo_soros, valor, lucro, texto_gale)
					elif resultado == "loose":
						if tipo_gale == "ciclos":
							self.config['ciclos']['gales'] += 1
							texto_gale = f"♦️ Avançando para o {ciclo_atual+2}° ciclo"
						else:
							self.config['ciclos']['soros'] = 0
							texto_gale = f"♦️ Voltando ao primeiro ciclo"
						self.valor = self.valor_inicial
						num_gales += 1

				if resultado == "equal" or lucro == 0:
					lucro = -perda

			elif tipo_gale == "martingale":
				if self.gale_atual < self.max_gale:
					texto_gale = f"🔸 {self.gale_atual + 1}° Martingale: {tipo_martin} para o próximo sinal"
					self.perda_atual += abs(valor)
					self.gale_atual += 1
					lucro_esperado = valor * payout
					if tipo_martin == "percent":
						lucro_esperado = self.config['martin_pct'] / 100
					self.valor = self.martingale(
						tipo_martin, payout, self.perda_atual, 
						valor, lucro_esperado)
					self.valor = 2 if self.valor < 2 else self.valor
				else:
					self.valor = self.valor_inicial
					self.gale_atual = 0

			elif tipo_gale == 'sorosgale':
				if self.gale_atual < self.max_gale:
					self.soros_atual = 0
					self.gale_atual += 1
					self.perda_atual += abs(valor)
					self.valor = self.perda_atual / 2
					self.valor = 2 if self.valor < 2 else round(self.valor, 2)
					texto_gale = f"🔸 Sorosgale: {round(valor, 2)} para {self.valor}"
				else:
					self.gale_atual = 0
					self.perda_atual = 0
					self.soros_atual = 0
					self.valor = self.valor_inicial
					texto_gale = f"♦️ Sorosgale: Voltando ao valor inicial"

			elif is_ciclos_gale:
				ciclo_atual = self.config["ciclos"]['gales'] if (
					tipo_gale == "ciclos"
				) else self.config["ciclos"]["soros"]

				ciclo_gale = self.ciclos_gale if (
					tipo_gale == "ciclos" ) else self.ciclos_soros

				if ciclo_atual < len(ciclo_gale):
					if self.gale_atual < len(ciclo_gale[ciclo_atual]):
						self.valor = ciclo_gale[ciclo_atual][self.gale_atual]
						self.gale_atual += 1
					else:
						texto_gale = f"🔸 Gale {ciclo_atual}° completo."
						ciclo_atual += 1
						self.gale_atual = 1
						self.valor = self.valor_inicial
				else:
					texto_gale = f"♦️ Gale: Voltando ao primeiro ciclo"
					ciclo_atual = 0
					self.gale_atual = 1
					self.valor = self.valor_inicial

				if tipo_gale == "ciclos":
					self.config["ciclos"]["gales"] = ciclo_atual
				else:
					self.config["ciclos"]["soros"] = ciclo_atual

			if (resultado == "loose" and (
				(self.config['max_soros'] > 0 and fazendo_soros 
				) or self.config["ciclos"]["soros"] > 0)):
				self.soros_atual = 0
				self.config["ciclos"]["soros"] = 0
				
				if self.config["tipo_soros"] == "ciclos":
					self.valor = self.ciclos_soros[0][0]
				if texto_gale == "":
					self.valor = self.valor_inicial
					texto_gale = f"♦️ Soros: R$ {round(valor, 2)} para R$ {self.valor}"

		if resultado != "error":
			if resultado != "equal": 
				desconta_perda(resultado, lucro, texto_gale)      
			else:
				self.mostrar_mensagem(self.format_dir(f"""
	⚪️ {paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
	💰 $ {round(valor, 2)} | $ 0,00 💰"""))
			time.sleep(3)          
			mostra_resultado()

		return resultado
