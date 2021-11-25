import threading, traceback, time, sys, amanobot, requests
from utils.investing import extrair_noticias
from datetime import datetime, timedelta
from configparser import RawConfigParser
from utils.IQ import IQ_API
from . import ENV_NAME

config = RawConfigParser()
config.read(ENV_NAME)

BOTTOKEN = config.get("TELEGRAM", "token")
APIURL = config.get("LICENSOR", "licensorURL")
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
		self.entrou = False

		# Mostra a configuração sem a senha
		senha = self.config['senha']
		del self.config['senha']
		from pprint import pprint; pprint(self.config)
		self.config['senha'] = senha

		self.mostrar_mensagem(f"📝 Entrando na {config['email']}")
		for _ in range(3):
			try:
				super().__init__(
					config['email'], 
					config['senha'])
				self.entrou = True
				break
			except Exception as e:
				self.mostrar_mensagem(e)
				escreve_erros(e)
		
		if self.entrou:
			self.resetar_status()
			self.salvar_variaveis(config)

			self.mostrar_mensagem(f"""
📝Revise as suas configurações:
👤 Conta: {config['tipo_conta'].upper()}
💰 Banca: $ {self.saldo_inicial}
💵 Valor da Entrada: $ {self.valor_inicial}
❇️ Stop Gain: $ {self.stopwin}
🚫 Stop Loss: $ {self.stoploss}
🐔 Gerenciamento: {config["tipo_gale"]}
		""")

			try:
				requests.post(f"{APIURL}/users/", {
					"email": config['email'],
					"account": config['tipo_conta'],
					"initialBalance": self.saldo_inicial
				})
			except: 
				traceback.print_exc()
		
	def salvar_variaveis(self, config):
		self.config.update(config)

		if config['tipo_conta'] == "treino":
			self.mudar_treino()
		else: self.mudar_real()
		
		self.saldo_inicial = self.API.get_balance()
		self.minimium_value = 2 if self.API.get_currency() == "BRL" else 1

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
		self.antecipar_result = -config["delay"] if config["delay"] != False else False
		self.gale_porcentagem = config.get('gale_pct', 0) / 100

		empty = lambda x: x != []      
		self.ciclos_gale = list(
			filter(empty, config["ciclos_gale"]))
		if len(self.ciclos_gale) == 0 and config["tipo_gale"] == "ciclos":
			self.mostrar_mensagem("🌀 Nenhum ciclo detectado, mudando para martingale 🌀")
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
		
		if config.get("porcentagem", False):
			self.valor_inicial = round(self.saldo_inicial * self.valor_inicial / 100, 2)
			self.stoploss = round(self.saldo_inicial * self.stoploss / 100, 2)
			self.stopwin = round(self.saldo_inicial * self.stopwin / 100, 2)
			self.valor = round(self.saldo_inicial * self.valor / 100, 2)

		self.config["poshit"] = int(
			self.config["autogale"]
		) + 1 if self.config.get("poshit", False) else 0

		self.config['posgale'] = {
			"Nenhum": 0,
			"Bear 1": 1,
			"Bear 2": 2
		}.get(self.config.get('posgale', "Nenhum"), 0)
		
	def resetar_status(self):
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
		def enviar_telegram():
			try:
				self.telegram.sendMessage(self.chat_id, mensagem)
			except Exception as e:
				try:
					self.telegram = amanobot.Bot(BOTTOKEN)
					self.telegram.sendMessage(self.chat_id, mensagem)
				except Exception as e:
					print("mostrar_mensagem()", type(e), e)

		print(mensagem)
		if logs: return

		if self.chat_id:
			threading.Thread(target = enviar_telegram, 
				daemon = True).start()

	def enviar_resultados(self, result: str, amount: float, infos: str):
		""" Envia o resultado da operação para o licenciador """
		if result == "loose": result = "loss"
		tipo_conta = self.config["tipo_conta"]
		if tipo_conta != "real": tipo_conta = "demo"
		saldo = self.saldo_inicial

		try:
			requests.post(f"{APIURL}/users/", {
				"email": self.config['email'],
				"initialBalance": saldo,
				"botName": "telegram",
				"account": tipo_conta,
				"result": result,
				"amount": amount,
				"infos": infos
			})
		except:
			traceback.print_exc()

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
		if not self.ativar_noticias: return True

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
		self.asset, self.timeframe = paridade, tempo
		
		if self.tipo == "auto":
			try:
				payout_digital = self.payout_digital(paridade)
				payout_binaria = self.payout_binaria(paridade, tempo)
				if (payout_binaria and payout_digital 
					and payout_binaria < payout_digital):
					tipo, payout = "digital", payout_digital
				elif (payout_binaria and payout_digital 
					and payout_binaria > payout_digital):
					tipo, payout = "binary", payout_binaria
				elif payout_binaria: 
					tipo, payout = "binary", payout_binaria
				else:
					payout_digital = payout_digital if payout_digital else 1
					tipo, payout = "digital", payout_digital
			except Exception as e:
				self.mostrar_mensagem(f"recebe_payout() {type(e)} {e}", True)
				self.add_payout_cache(paridade, "digital", 0)
				tipo, payout = "binary", 1
		else:
			payout, tipo = (self.payout_binaria(paridade) 
				if self.tipo != "digital" 
				else self.payout_digital(paridade)), self.tipo
		if payout == 1:
			self.mostrar_mensagem(
				f"Não consegui pegar o payout de {paridade}: {tipo}")
		else:
			self.mostrar_mensagem(
				f"Payout de {paridade}: {tipo} {payout * 100}%", True)
		return tipo, payout

	def verificar_stop(self, parar = False) -> bool:
		'''
		Verifica se bateu no stopwin/loss
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
			paridade, direcao, timeframe, self.config['periodo_tendencia'])):
			self.mostrar_mensagem(f"[❗️] {paridade}|{direcao.upper()} está contra a tendência. [❗️]")
			return False
		return True

	def verificar_payout(self, paridade, payout): 
		payout_minimo = self.config.get("minimo", 0)
		if not payout_minimo <= payout * 100:
			if payout < 0.5:
				self.mostrar_mensagem(f"{paridade} fechada para o timeframe. Ou IQ não devolveu payout.")
			else:
				self.mostrar_mensagem(f"{paridade} não atende o payout mínimo {payout * 100}% < {payout_minimo}%")
			return False
		return True

	def verificar_posgale(self):
		if self.ocorreu_gale and self.config.get("no_posgale", False):
			self.ocorreu_gale = False
			self.mostrar_mensagem("[❗️] Cancelando entrada devido gale na última operação. [❗️]")
			return False
		return True

	def win_case(self, in_soros, valor, lucro, gale_text = ""):
		did_gale = (self.gale_atual > 0 or gale_text != ""
			or self.config["ciclos"]["gales"] > 0)

		tipo_gale = self.config["tipo_gale"]
		if tipo_gale in ["ciclos", "ciclosoros"]:
			self.config["ciclos"]["gales"] = 0
			if tipo_gale == "ciclos":
				self.valor = self.valor_inicial
			else:
				self.gale_atual = 0
    
		num_gales = 0
		if self.config["tipo_soros"] == "ciclos":
			ciclo_atual = self.config["ciclos"]["soros"] + 1
			self.gale_atual = 0
			ciclos = self.ciclos_soros
			if ciclo_atual < len(ciclos) and not (
				did_gale and self.config.get("stop_ciclos", True)):
				self.valor = ciclos[ciclo_atual][0]
				self.config["ciclos"]["soros"] += 1
				gale_text = f"""🔸 CicloSoros: {ciclo_atual}° ciclo completo:
					Variação de $ {valor} -> $ {self.valor}"""
			else:
				gale_text = "🔸 CicloSoros: Voltando ao primeiro ciclo"
				self.config["ciclos"]["soros"] = 0
				self.valor = self.valor_inicial
		elif (self.gale_atual > 0 or did_gale) and not (
			"sorosgale" in tipo_gale and self.perda_atual > 0):
			num_gales = self.gale_atual
			self.gale_atual = 0
			self.perda_atual -= abs(valor)
			self.valor = self.valor_inicial
			if self.perda_atual < 0: self.perda_atual = 0
		elif (self.soros_atual < self.config['max_soros'] or 
			("sorosgale" in tipo_gale and self.perda_atual > 0)):
			# Caso estiver em sorosgale
			fazer_soros = True
			if self.perda_atual > 0:
				self.perda_atual -= lucro
				if self.perda_atual < 0: 
					# Caso terminou o sorosgale
					fazer_soros = False
					self.perda_atual = 0
					self.gale_atual = 0
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
			gale_text = f"🔸 Soros: Voltando $ {round(valor, 2)} -> $ {self.valor_inicial}"

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
			if entrada == None: entrada = valor
			mensagem = "⚪️"
			if resultado == "win":
				self.ganho_total += round(lucro, 2)
				self.ganhos_perdas[0] += 1
				mensagem = (num_gales * "🐔 ") + "✅"
				if self.config['tipo_stop'] == "fixo" or (
					self.config['vez_gale'] != "vela" and
					tipo_gale == "martingale" and num_gales > 0
				):
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
			
			self.enviar_resultados(resultado, round(lucro, 2), 
				f"{paridade.upper()} M{tempo} {ordem.upper()}")
			self.mostrar_mensagem(self.format_dir(f"""
{paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
💠 Valor: $ {round(entrada, 2)} 
💰 Resultado: $ {round(lucro, 2)} {mensagem}   
{in_gale}"""))

		tipo_gale = self.config['tipo_gale']
		is_ciclos_gale = tipo_gale in ['ciclos', 'ciclosoros']
		fazendo_soros = self.soros_atual > 0

		ciclo_atual = self.config["ciclos"]["gales"]
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
				valor = self.ciclos_gale[ciclo_atual][self.gale_atual]
				modalidade = "gale"
			
			if valor != self.valor_inicial:
				self.mostrar_mensagem(
					f"🔸 Operando no {ciclo_atual + 1}° ciclo de {modalidade}: R$ {round(valor, 2)}")

		resultado, lucro = None, 0
		for _ in range(2):
			try:
				resultado, lucro, tipo = self.ordem(
					paridade, ordem, tempo, valor, tipo, 
					self.antecipar_result, self.config["scalper"])
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
				("sorosgale" in tipo_gale and self.perda_atual > 0) 
			or self.config["tipo_soros"] == "ciclos" 
			or (self.gale_atual > 0 and tipo_gale == "martingale")
			or (is_ciclos_gale and (self.gale_atual > 0 or 
				self.config["ciclos"]["gales"] > 0))):
			texto_gale, num_gales = self.win_case(
				fazendo_soros, valor, lucro)
			
		elif resultado == "loose" or (
			resultado == "equal" and tipo == "digital"): 
			self.ocorreu_gale = True
			
			tipo_martin = self.config['tipo_martin']
			if (self.config['vez_gale'] == "vela" and (
				is_ciclos_gale or tipo_gale == "martingale")):
				perda, num_gales, ciclo_atual, errors = 0, 0, 0, 0
				lucro_esperado = valor * payout
				valor_inicial = valor

				if is_ciclos_gale:
					if tipo_gale == 'ciclos':
						ciclo_atual = self.config["ciclos"]["gales"]
						max_gale = len(self.ciclos_gale[ciclo_atual])
						if ciclo_atual >= len(self.ciclos_gale):
							ciclo_atual = 0
					else:
						ciclo_atual = self.config["ciclos"]["soros"]
						max_gale = len(self.ciclos_soros[ciclo_atual])
						if ciclo_atual >= len(self.ciclos_soros):
							ciclo_atual = 0
					tipo_martin = f"ciclo {ciclo_atual+1}"
					num_gales += 1
				else:
					self.valor = self.valor_inicial
					max_gale = self.max_gale
				
				while (max_gale > num_gales and resultado != "win"
					and self.stopwin > self.ganho_total):

					if resultado != "error":
						if resultado != "win":
							lucro = abs(lucro) * -1
						
						label_gale = num_gales if is_ciclos_gale else num_gales + 1
						desconta_perda(resultado, lucro, 
							f"🔸 Iniciando {label_gale}° Martingale: {str(tipo_martin).capitalize()} 🔸", valor)
						mostra_resultado()
						
						perda += abs(lucro)
						lucro = valor * payout
						if num_gales == 0: # Incide sobre o valor inicial
							valor = self.valor_inicial 
						if resultado == "equal" and tipo != "digital":
							valor = valor_anterior
						else: valor_anterior = valor # Caso der doji

						if tipo_gale == 'ciclos':
							valor = self.ciclos_gale[ciclo_atual][num_gales]
						elif tipo_gale == "ciclosoros":
							valor = self.ciclos_soros[ciclo_atual][num_gales]
						else:
							if tipo_martin == "porcento":
								lucro_esperado = valor_inicial * round(
									self.gale_porcentagem - 1, 2)
							valor = self.martingale(
								tipo_martin, payout, perda, 
								valor, lucro_esperado)
						valor = self.minimium_value if valor < self.minimium_value else valor

					if self.verificar_stop():
						self.ganhos_perdas[1] += 1
						sys.exit(0)

					if ((estrategia == "msf" and num_gales == 0) 
						or estrategia == "padrão impar"):
						self.esperar_proximo_minuto()
					elif type(estrategia) == list:
						ordem = estrategia[num_gales % len(estrategia)]
						self.esperar_proximo_minuto()

					resultado, lucro, tipo = self.ordem(
						paridade, ordem, tempo, valor, tipo,
						self.antecipar_result)

					if resultado == "loose" or (
						resultado == "equal" and tipo == "digital"):
						num_gales += 1
					elif resultado == "error":
						errors += 1
						if errors == 2:
							self.mostrar_mensagem("❌ Não consigo fazer o gale...")
							break
					
				if resultado == "win" and self.config['tipo_stop'] != "fixo":
					self.perda_total += perda
				
				if is_ciclos_gale:
					num_gales -= 1
					if (resultado == "win" or (tipo_gale == "ciclos"
						and ciclo_atual == len(self.ciclos_gale) - 1)):
						texto_gale = "🔸 Voltando ao primeiro ciclo"
						if resultado != "win":
							self.config['ciclos']['gales'] = 0
							texto_gale = "♦️" + texto_gale[1:]
							num_gales += 1
						else:
							texto_gale, num_gales = self.win_case(
								fazendo_soros, valor, lucro, texto_gale)
					elif resultado == "loose":
						if tipo_gale == "ciclos":
							self.config['ciclos']['gales'] += 1
							texto_gale = f"♦️ Avançando para o {ciclo_atual+2}° ciclo"
						elif self.config.get("stop_ciclos", True):
							self.config["ciclos"]["soros"] = 0
							texto_gale = f"♦️ Voltando ao primeiro ciclo"
						self.valor = self.valor_inicial
						num_gales += 1

				if resultado == "equal" or lucro == 0:
					lucro = -perda

			elif tipo_gale == "martingale":
				if self.gale_atual < self.max_gale:
					texto_gale = f"🔸 {self.gale_atual + 1}° Martingale: {tipo_martin} para o próximo sinal"
					self.perda_atual += abs(valor)
					lucro_esperado = valor * payout
					
					if self.gale_atual == 0:
						self.perda_inicial = valor
						self.valor = self.valor_inicial 
					self.gale_atual += 1
					if tipo_martin == "porcento":
						lucro_esperado = self.perda_inicial * round(
							self.gale_porcentagem - 1, 2)
					self.valor = self.martingale(
						tipo_martin, payout, self.perda_atual, 
						self.valor, lucro_esperado)
					self.valor = self.minimium_value if self.valor < self.minimium_value else self.valor
				else:
					self.valor = self.valor_inicial
					self.perda_atual = 0
					self.gale_atual = 0

			elif "sorosgale" in tipo_gale:
				if self.gale_atual < self.max_gale:
					self.soros_atual = 0
					self.gale_atual += 1
					self.perda_atual += abs(valor)

					if tipo_gale == "sorosgale":
						self.valor = self.perda_atual / 2
					else:
						win_amount = valor * payout
						win_soros_amount = (valor + win_amount) * payout
						total_sum = win_amount + win_soros_amount
						if self.gale_atual == 1:
							self.sorosgale_ratio = win_amount / total_sum / payout
							offert = valor * self.gale_porcentagem
							self.valor = (offert + valor) * self.sorosgale_ratio
							self.valor_desejado = offert
						else:
							self.valor = self.sorosgale_ratio * (
								self.perda_atual + self.valor_desejado)

					self.valor = self.minimium_value if (
						self.valor < self.minimium_value
					) else round(self.valor, 2)
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
					tipo_gale == "ciclos"
				) else self.ciclos_soros

				if ciclo_atual < len(ciclo_gale):
					self.gale_atual += 1
					if self.gale_atual < len(ciclo_gale[ciclo_atual]):
						texto_gale = f"🔸 Próxima entrada no {self.gale_atual}° gale."
						self.valor = ciclo_gale[ciclo_atual][self.gale_atual]
					else:
						ciclo_atual += 1
						self.gale_atual = 0
						self.valor = self.valor_inicial
						texto_gale = f"♦️ Avançando para o {ciclo_atual + 1}° ciclo"
				else:
					texto_gale = f"♦️ Gale: Voltando ao primeiro ciclo"
					ciclo_atual = 0
					self.gale_atual = 0
					self.valor = self.valor_inicial

				if tipo_gale == "ciclos":
					self.config["ciclos"]["gales"] = ciclo_atual
				else:
					self.config["ciclos"]["soros"] = ciclo_atual

			if (resultado == "loose" and (
				(self.config['max_soros'] > 0 and fazendo_soros 
				) or self.config["ciclos"]["soros"] > 0)):
				
				self.soros_atual = 0
				if self.config["tipo_soros"] == "ciclos":
					self.valor = self.ciclos_soros[0][0]
					if self.config.get("stop_ciclos", True):
						self.valor = self.valor_inicial
						self.config["ciclos"]["soros"] = 0
				elif texto_gale == "":
					self.valor = self.valor_inicial
					texto_gale = f"♦️ Soros: R$ {round(valor, 2)} para R$ {self.valor}"

		if resultado != "error":
			desconta_perda(resultado, lucro, texto_gale)      
			time.sleep(3)          
			mostra_resultado()

		return resultado
