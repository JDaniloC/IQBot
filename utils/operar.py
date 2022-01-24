import threading, traceback, time, sys, amanobot
from utils.investing import extrair_noticias
from datetime import datetime, timedelta
from configparser import RawConfigParser
from utils.IQ import IQ_API
from random import randint
from utils import ENV_NAME
from pprint import pprint

config = RawConfigParser()
config.read(ENV_NAME)

BOTTOKEN = config.get("TELEGRAM", "token")
LICENSOR_EMAIL = config.get("LICENSOR", "email")
LICENSOR_PASSWORD = config.get("LICENSOR", "password")
LOCALERROR = "errors.log"
LOCALLOG = ""

def escreve_erros():
	with open(LOCALERROR, "a") as file:
		traceback.print_exc(file = file)

def escreve_log(email, mensagem):
	with open(LOCALLOG + email + ".txt", "a", encoding = "utf-8") as file:
		file.write(mensagem + "\n")

def is_in_list(estrategia, lista):
    for item in lista:
        if item.lower() in estrategia.lower():
            return True
    return False

class Operacao(IQ_API): 
	def __init__(self, config, comandos = [], verboso = False, 
		tipo_operacao = "lista", tentativas = 0):
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
		self.config.update({
			"senha": senha,
			"licensor_email": LICENSOR_EMAIL,
			"licensor_password": LICENSOR_PASSWORD,
		})

		if self.tentativas < 3:
			try:
				if self.verboso:
					self.telegram = amanobot.Bot(BOTTOKEN)

				print(f"Entrando na {config['email']}")
				super().__init__(config['email'], config['senha'])
				
				if config['tipo_conta'] == "treino":
					self.mudar_treino()
				else: self.mudar_real()

				if config['tipo_par'] == "auto":
					self.tipo = config['tipo_par']
				else:
					self.tipo = "digital" if (
						config['tipo_par'] == 'digital'
					) else "binary"

				self.saldo_inicial = self.API.get_balance()
				if tipo_operacao == "3por1":
					config["valor"] = max(round(self.saldo_inicial * 0.03), 2)
					config["stopwin"] = max(round(self.saldo_inicial * 0.055), 2)
					config["stoploss"] = max(round(self.saldo_inicial * 0.10), 2)
					config["noticias_hora"] = 1
					config["poshit"] = True
					config["minimo"] = 70
					config["assert"] = 95
					config["auto"] = True
					config["toros"] = 3

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
					config.get("noticias_hora", 0) > 0 or 
					config.get("noticias_minuto", 0) > 0)

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
				
				if tipo_operacao == "lista": 
					self.operar_lista()
				elif tipo_operacao in ["estrategia", "3por1"]: 
					self.operar_estrategia()
				elif tipo_operacao == "chinesa": 
					self.operar_chinesa()
				elif tipo_operacao == "donchian": 
					self.operar_donchian()
				elif tipo_operacao == "chart":
					self.operar_value_chart()
				else:
					self.operar_berman()

			except KeyboardInterrupt:
				sys.exit(0)
			except Exception as e:
				if type(e) == ConnectionError:
					self.mostrar_mensagem("Não conseguiu se conectar na conta")
					self.tentativas = 3
				escreve_erros()
				
				try:
					print("Continuando as operações...")
					self.tentativas += 1
					self.__init__(self.config, self.comandos, 
						self.verboso, tipo_operacao, self.tentativas)
				except: escreve_erros()
		else:
			self.mostrar_mensagem("Ultrapassou o máximo de tentativas.")

	def mostrar_mensagem(self, mensagem):
		'''
		O método mostra a mensagem em tela
		Se self.verboso então envia para o telegram
		'''
		if mensagem == "": return
		
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
		Devolve um boolean
		'''
		with self.cadeado:
			if (-self.stoploss >= self.perda_total or 
				self.ganho_total >= self.stopwin) or self.fim_da_operacao:
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
				if self.fim_da_operacao:
					self.mostrar_mensagem(f'''
{mensagem}
{placar.center(32, " ")}
💰 Saldo: $ {round(self.ganho_total, 2)} | $ {self.stopwin}
💲 Perca: $ {round(perda_total, 2)} | $ {-self.stoploss}
✴️ Assertividade: {round(assertividade, 2)}%
					⚠️ Bot parado ⚠️''')
					self.fim_da_operacao = False
				self.fim_da_operacao = True
				return True
		return False

	def verificar_tendencia(self, paridade, direcao, timeframe):
		if (self.config['tendencia'] and not self.calcular_tendencia(
			paridade, direcao, timeframe, self.config['periodo_tendencia'])):
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
		if is_ciclo: self.gale_atual = 1
		gale_text, num_gales = "", 0
		self.config["ciclos"]['gales'] = 0

		if self.config["tipo_soros"] == "ciclos":
			self.gale_atual = 0
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
		elif (self.soros_atual < self.config['max_soros'] or 
			(self.config["tipo_gale"] == "sorosgale" 
				and self.perda_atual > 0)):
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
				# inicial = self.saldo_inicial
				# atual = round(self.saldo_inicial + self.ganho_total, 2)

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
		delay = self.config.get('delay', False)
		for _ in range(2):
			try:
				resultado, lucro, tipo = self.ordem(paridade, 
					ordem, tempo, valor, tipo, delay)
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

					resultado, lucro, tipo = self.ordem(paridade, ordem, 
						tempo, valor, tipo, self.config['delay'])
					if resultado != "win":
						num_gales += 1
				if (resultado == "win" and 
					self.config['tipo_stop'] != "fixo"):
					self.perda_total += perda
				
				if is_ciclos_gale:
					num_gales -= 1
					if (resultado == "win" or
						ciclo_atual == len(self.ciclos_gale) - 1):
						self.config["ciclos"]['gales'] = 0
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
					self.perda_atual = 0
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
		else:
			result_method = 'histórico' if delay == False else 'taxa'
			self.mostrar_mensagem(self.format_dir(f"""
A IQ Option não devolveu o resultado por {result_method}!
{paridade.upper()}|{tipo.capitalize()} M{tempo} {ordem.upper()}
	💰 $ {round(valor, 2)} | $ 0,00 💰"""))
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
				valor = (comando['taxa'], comando['timeframe'])
				if paridade not in par_taxa:
					par_taxa[paridade] = [valor]
				else:
					par_taxa[paridade].append(valor)
		
		taxa_time = lambda x: f"{x[0]} M{x[1]}".replace(
			"M0", f"M{self.config.get('tempo', 1)}")
		mensagem = ""
		for paridade, taxas in par_taxa.items():
			mensagem += f"{paridade.upper()} esperando bater nas taxas:\n" + \
				'\n'.join(list(map(taxa_time, taxas))) + "\n\n"
			thread = threading.Thread(
				target = self.esperar_taxa, 
				name = f"{time.time()}", 
				args = (paridade, taxas),
				daemon = True)
			self.espera.append(thread)
			thread.start()

		linhas = mensagem.split("\n")
		for i in range(0, len(linhas), 50):
			self.mostrar_mensagem("\n".join(linhas[i:i+50]))

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

		while not self.verificar_stop() and taxas != []:
			velas = self.API.get_realtime_candles(par, 60)
			try:
				abertura = velas[list(velas.keys())[0]]['open']
				fechamento = velas[list(velas.keys())[0]]['close']
			except:
				traceback.print_exc()
				time.sleep(1)
				continue

			
			for index, (taxa, timeframe) in enumerate(taxas.copy()):
				timeframe = self.tempo if timeframe == 0 else timeframe
				if (fechamento >= taxa and ultimo < taxa or 
					fechamento <= taxa and ultimo > taxa):

					direcao = "call" if abertura > fechamento else "put"
					tipo, payout = self.recebe_payout(par, timeframe)

					if (self.ativar_noticias and
						not self.verificar_noticias(par)):
						continue

					if self.config["minimo"] / 100 <= payout:
						self.mostrar_mensagem(f"Taxas: {par} {taxa} ")

						if self.config.get("taxas_vela", "retração") != "retração":
							self.esperar_proximo_minuto(seconds = 59)
							velas = self.API.get_candles(par, 
								60 * timeframe, 1, time.time())
							direcao = velas[0]["close"] - velas[0]["open"]
							direcao = "call" if direcao < 0 else "put"

						if tipo == "binary" and timeframe == 5:
							atual = datetime.utcnow()
							if ((atual.minute % 5 == 4 and atual.second < 30) 
								or atual.minute % 5 < 4): 
								timeframe = 5 - (atual.minute % 5)

						thread = threading.Thread(
							target = self.operar, 
							name = f"{time.time()}", 
							args = (self.valor, par, direcao, 
								timeframe, payout, tipo),
							daemon = True)
						self.espera.append(thread)
						thread.start()
					else:
						self.mostrar_mensagem(f"{par} {taxa} não atende o payout mínimo {payout} {self.config['minimo']}")

					try: taxas.pop(index)
					except: traceback.print_exc()
			ultimo = fechamento
			time.sleep(self.config['correcao'])
		self.API.stop_candles_stream(par, 60)

	def operar_estrategia(self):
		def pegar_velas(par, quantidade, timeframe = 1, 
				modo = "colors", start = None, velas = []):
			if velas == []:
				if start is None: start = time.time()
				velas = self.API.get_candles(
					par, 60 * timeframe, quantidade, start)
				if modo == "pure": return velas
			else: velas = velas[-quantidade:]
			
			if modo != "colors":
				return [x['close'] for x in velas]

			resultado = []
			if velas != None and velas != []:
				for i in range(len(velas)):
					print(datetime.fromtimestamp(velas[i]['from']))
					resultado.append(('CALL' if velas[i]['open'] 
					< velas[i]['close'] else 'PUT' if velas[i]['open'] 
					> velas[i]['close'] else 'DOJI'))

			return resultado

		def proxima_entrada(min_list, estrategia, timeframe, isM1 = False):
			minutos = str((datetime.now() + timedelta(minutes = 1)).minute).zfill(2)

			is_the_last = False
			for i in range(len(min_list)):
				if isM1:
					option = int(f"{minutos[0]}{min_list[i]}"
						) if estrategia != "daka" else min_list[i]
				else:
					option = min_list[i]
				
				if option > int(minutos):
					entrar = option
					break
				elif i == len(min_list) - 1:
					entrar = min_list[0] if (
						not isM1 or estrategia == "daka"
					) else int(f"{minutos[0]}{min_list[0]}")
					is_the_last = True

			maisUm = timeframe * 60 if estrategia not in [
				"mhi2", "mhi3", "vituxo"
			] else timeframe * 60 * 2 + 60 if (
				estrategia == "mhi2"
			) else timeframe * 60 * 3 + 60

			agora = datetime.fromtimestamp(
				datetime.utcnow().timestamp() - 10800).replace(
				minute = entrar, second = 0) + timedelta(seconds = maisUm)

			if agora.timestamp() - time.time() < 0 and is_the_last:
				if isM1: agora += timedelta(minutes = 10)
				else: agora += timedelta(hours = 1)
			horario = agora.strftime(f'%H:%M')
			self.mostrar_mensagem(f"⏰ Próxima entrada será às {horario} ⏰")

		def entrada_estrategias_m1(estrategia, minutos, proxima = False):
			if estrategia == "daka":
				entrada = [x for x in range(0, 60, 4)]
			else:
				if minutos >= 10: minutos = int(str(minutos)[1])
			
				if estrategia in ['padrão 3x1', 'quinto elemento',
					"msf", "hope", "torres gêmeas", 'três vizinhos']:
					entrada = [3, 8] # 5° vela
				elif estrategia in ["três mosqueteiros"]:
					entrada = [2, 7] # 4° vela
				elif is_in_list(estrategia, ["melhor de 3", "vituxo"]):
					entrada = [1, 6] # 3° vela
				elif is_in_list(estrategia, ["padrão 23"]):
					entrada = [0, 5] # 2° vela
				elif estrategia == "seven flip":
					entrada = [6]
				elif estrategia == "r7":
					entrada = [5]
				else:
					entrada = [4, 9] # 1° vela

			if proxima: proxima_entrada(entrada, estrategia, proxima, True)
			return minutos in entrada

		def velas_por_estrategia_m1(par, estrategia, preset = []):
			if "impar" in estrategia:
				velas = [pegar_velas(par, 3, velas = preset)[0]]
			elif estrategia == "hope":
				velas = pegar_velas(par, 4, velas = preset)[::2]
			elif estrategia == "torres gêmeas":
				velas = [pegar_velas(par, 4, velas = preset)[0]]
			elif estrategia == "melhor de 3":
				velas = pegar_velas(par, 6, velas = preset)[:3]
			elif "milhão" in estrategia:
				velas = pegar_velas(par, 5, velas = preset)
			elif estrategia == "vituxo":
				velas = pegar_velas(par, 7, velas = preset)[:3]
			elif estrategia == "c3":
				velas = pegar_velas(par, 5, velas = preset)[::2]
			elif estrategia == "msf":
				velas = [pegar_velas(par, 9, velas = preset)[0]]
			elif estrategia == "r7":
				velas = [pegar_velas(par, 7, velas = preset)[0]]
			elif 'seven' in estrategia:
				velas = [pegar_velas(par, 7, velas = preset)[-1]]
			elif is_in_list(estrategia, ['padrão 3x1']):
				velas = pegar_velas(par, 4, velas = preset)[:3]
			elif is_in_list(estrategia, ["mhi"]):
				velas = pegar_velas(par, 3, velas = preset)
			else:
				velas = pegar_velas(par, 1, velas = preset)
			return velas

		def entrada_estrategias_m5(estrategia, minutos, proxima = False):
			if estrategia in ["três mosqueteiros", 
            "triplicação", "não triplicação"]:
				entrada = [9, 24, 39, 54]
			elif estrategia in ["torres gêmeas", "five flip"]:
				entrada = [24, 54]
			elif estrategia in ["power", "gaba"]: 
				entrada = [14, 29, 44, 59]
			elif is_in_list(estrategia, ['três vizinhos']):
				entrada = [19, 49]
			else:
				entrada = [29, 59]

			if proxima: proxima_entrada(entrada, estrategia, proxima)
			return minutos in entrada

		def velas_por_estrategia_m5(par, estrategia, preset = []):
			if "last of five" in estrategia:
				velas = pegar_velas(par, 5, 5, velas = preset)
			elif estrategia in ["três mosqueteiros", 
				"triplicação", "não triplicação"]:
				velas = pegar_velas(par, 2, 5, velas = preset)
			elif "milhão" in estrategia:
				velas = pegar_velas(par, 6, 5, velas = preset)
			elif estrategia in ["torres gêmeas"]:
				velas = [pegar_velas(par, 6, 5, velas = preset)[0]]
			elif estrategia in ["five flip", 'três vizinhos']:
				velas = [pegar_velas(par, 1, 5, velas = preset)[0]]
			else:
				velas = pegar_velas(par, 3, 5, velas = preset)
			return velas

		def entrada_estrategias_m15(estrategia, minutos, proxima = False):
			if is_in_list(estrategia, ["torres gêmeas",  
				"mhi", "milhão", "turn over"]):
				entrada = [59]
			elif estrategia == "torres gêmeas":
				entrada = [44]
			else:
				entrada = [29]

			if proxima: proxima_entrada(entrada, estrategia, proxima)
			return minutos in entrada

		def velas_por_estrategia_m15(par, estrategia, preset = []):
			if estrategia == "half hour":
				velas = [pegar_velas(par, 2, 15, velas = preset)[0]]
			elif estrategia == "primeiros trocados":
				velas = pegar_velas(par, 2, 15, velas = preset)[0]
				velas = ["call"] if velas.lower() == "put" else ["put"]
			elif estrategia == "turn over":
				velas = pegar_velas(par, 1, 15, velas = preset)[0]
				velas = ["call"] if velas.lower() == "put" else ["put"]
			elif "mhi" in estrategia:
				velas = pegar_velas(par, 3, 15, velas = preset)
			elif estrategia == "torres gêmeas":
				velas = [pegar_velas(par, 4, 15, velas = preset)[0]]
			else:
				velas = pegar_velas(par, 4, 15, velas = preset)
			return velas
		
		def verifica_entrada(estrategia, timeframe, 
			minutos = None, proxima = False):
			if minutos is None:
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

		def recebe_velas(paridade, estrategia, timeframe, preset = []):
			if timeframe == 1:
				velas = velas_por_estrategia_m1(paridade, estrategia, preset)
			elif timeframe == 5:
				velas = velas_por_estrategia_m5(paridade, estrategia, preset)
			else:
				velas = velas_por_estrategia_m15(paridade, estrategia, preset)
			if len(velas) > 0 and type(velas[0]) == str:
				self.mostrar_mensagem(self.format_candles(" ".join(velas)))
			return velas

		def pegar_catalogacao():
			percent = False
			poshit = self.config.get("poshit", False)
			hits = self.config.get("hits", 1)
			_assert = self.config.get("assert", 0)
			while not self.verificar_stop() and not percent:
				percent, paridade, strategy = self.catalogar_estrategia(
					self.config["autotime"], self.config["autogale"],
					poshit, hits, _assert)
				if not percent:
					self.mostrar_mensagem("🔹 Catalogação: Sem resultados...")
					self.esperar_proximo_minuto()
			if self.verificar_stop(): sys.exit(0)

			estrategia, tipo_milhao = strategy
			payout = 100 * self.recebe_payout(paridade, self.config["autotime"])[1]
			self.mostrar_mensagem(f"""
🔹 {estrategia} pela {tipo_milhao.capitalize()} | Paridade: {paridade} ♦️
🎯 Assertividade: {percent}% | Payout: {payout}% ❇️""")
			return paridade.upper(), estrategia.lower(), tipo_milhao.lower()

		def determina_direcao(paridade, estrategia, timeframe, preset = []):
			velas = recebe_velas(paridade, estrategia, timeframe, preset)
			
			direcao = False
			if len(velas) > 0 and velas.count("DOJI") == 0 and not (
				estrategia == "milhão" and timeframe == 5):
				if is_in_list(estrategia, ["msf", "five flip",
					'padrão 3x1', "last of five", "gaba", 
					"power", "milhão", "mhi", "flip",
					"vituxo", "hora do equilibrio"]):	
					direcao = velas.count('CALL') > velas.count('PUT')
					direcao = "call" if direcao else "put"
					if tipo_milhao == "minoria" or is_in_list(estrategia, 
						["hora do equilibrio", "msf", "power", 
						"gaba", "five flip", 'padrão 3x1']):
						direcao = "put" if direcao == "call" else "call"
						if (estrategia == "power" and 
							direcao.upper() != velas[1]):
							direcao = False
				elif timeframe == 5 and estrategia == "três mosqueteiros":
					if velas[0] != velas[1]: direcao = velas[0].lower()
				elif timeframe == 5 and estrategia == "triplicação":
					if velas[0] == velas[1]: direcao = velas[0].lower()
				else:
					if estrategia != "hope" or velas[0] == velas[1]:
						direcao = velas[0].lower()
			elif (velas.count("DOJI") > 2 and 
				estrategia == "milhão" and timeframe == 5):
				if velas.count("CALL") != velas.count("PUT"):
					direcao = velas.count('CALL') > velas.count('PUT')
					direcao = "call" if direcao else "put"
					if tipo_milhao == "minoria": 
						direcao = "put" if direcao == "call" else "call"
			else:
				self.mostrar_mensagem("⏰ A entrada foi cancelada: Sem ciclo")
			return velas, direcao

		def esperar_poshit(paridade, estrategia, timeframe, hits = 3):
			'''
			Espera ocorrer um hit, de acordo com o especificado.
			'''
			self.mostrar_mensagem(f"🔹 Procurando por HIT em {paridade}...")
			while not self.verificar_stop():
				horario = (datetime.now() - timedelta(minutes = timeframe * hits)) 
				entrada = verifica_entrada(estrategia, timeframe, horario.minute) 

				if entrada:
					velas = pegar_velas(paridade, 10, timeframe, 
						"pure", start = horario.timestamp())
					velas, direcao = determina_direcao(
						paridade, estrategia, timeframe, velas)

					if direcao:
						ultimas = pegar_velas(paridade, hits, timeframe)
						self.mostrar_velas(self.format_candles(
                            f"Deveria dar: {direcao}"), ultimas)
						is_equal = lambda x: x.lower() != direcao.lower()
						if all(map(is_equal, ultimas)):
							return velas, direcao
				self.esperar_proximo_minuto()
			return [], False

		if self.config["auto"]:
			paridade, estrategia, tipo_milhao = pegar_catalogacao()
			timeframe = self.config["autotime"]
		else:
			tipo_milhao = self.config.get('tipo_milhao', "minoria").lower()
			paridade = self.config['paridade'].upper()
			estrategia = self.config['estrategia'].lower()
			timeframe = 5 if (estrategia in [
				"power", "last of five", 
				"five flip", "triplicação"
			] or "m5" in estrategia) else 15 if (
			estrategia in [
				"half hour", "primeiros trocados", 
				"hora do equilibrio", "turn over"
			] or "m15" in estrategia) else 1
			estrategia = estrategia.replace("m5: ", "").replace("m15: ", "")
			payout = 100 * self.recebe_payout(paridade, self.config["autotime"])[1]
			self.mostrar_mensagem(f"""
🔹 {estrategia.upper()} pela {tipo_milhao.capitalize()} | Paridade: {paridade} ♦️
❇️ Payout: {payout}%""")

		poshit = self.config.get("poshit", False)
		if not self.config["auto"] and poshit:
			esperar_poshit(paridade, estrategia, timeframe)

		verifica_entrada(estrategia, timeframe, proxima = True)
		while not self.verificar_stop():            
			if verifica_entrada(estrategia, timeframe):
				velas, direcao = determina_direcao(
					paridade, estrategia, timeframe)

				if direcao:
					self.mostrar_mensagem(self.format_dir(
						f'Direção: {direcao.upper()}'))
					
					if self.verificar_tendencia(
						paridade, direcao, timeframe):
						continue

					if (self.ativar_noticias and 
						not self.verificar_noticias(paridade)):
						continue
					
					if estrategia == "mhi2":
						self.esperar_proximo_minuto(timeframe)
					elif is_in_list(estrategia, ["mhi3", "vituxo"]):
						self.esperar_proximo_minuto(timeframe * 2)
						if timeframe > 1: time.sleep(60)

					tipo, payout = self.recebe_payout(paridade, timeframe)
					gale = False
					if estrategia == "msf": gale = "msf"
					elif estrategia == "c3": gale = velas

					if self.config["minimo"] / 100 <= payout:
						self.operar(self.valor, paridade, direcao, 
							timeframe, payout, tipo, gale)
						if self.config["auto"]:
							paridade, estrategia, tipo_milhao = pegar_catalogacao()
						elif poshit:
							esperar_poshit(paridade, estrategia, timeframe)
					else:
						self.mostrar_mensagem(f"{paridade} não atende o payout mínimo {payout * 100}% < {self.config['minimo']}%")
				elif self.config["auto"]:
					paridade, estrategia, tipo_milhao = pegar_catalogacao()
				elif poshit:
					esperar_poshit(paridade, estrategia, timeframe)
				verifica_entrada(estrategia, timeframe, proxima = True)
			self.esperar_proximo_minuto()
		self.verificar_stop()

	def operar_chinesa(self):
		last_update, paridades = self.update_abertas()
		SSMA_1 = self.config.get("chinesa_1", 3)
		SSMA_2 = self.config.get("chinesa_2", 50)
		MOAVDE = self.config.get("chinesa_mad", 20)

		self.mostrar_mensagem(f"""🔸 Operando Estratégia Chinesa 🔸
		⏰ Timeframe: M{self.tempo}
		📊 SSMA curto: {SSMA_1}
		📊 SSMA longo: {SSMA_2}
		📊 Moving Average Deviation: {MOAVDE}
		""")
		while not self.verificar_stop():
			for paridade in paridades:
				dataframe = self.get_dataframe_candles(
					paridade, self.tempo, MOAVDE * 10)
				if len(dataframe) == 0: continue

				dev_direction = self.moving_average_deviation(dataframe, MOAVDE)
				indicator_ssma_3_line = self.get_SSMA(dataframe, SSMA_1)
				indicator_ssma_50_line = self.get_SSMA(dataframe, SSMA_2)
				
				was_collision, col_direction = self.indicator_lines_colision(
					indicator_ssma_3_line, indicator_ssma_50_line)
				is_confluence = dev_direction == col_direction

				if was_collision and is_confluence:
					tipo, payout = self.recebe_payout(paridade, self.tempo)
					payout_minimo = self.config.get("minimo", 0) / 100
					
					if (self.ativar_noticias and not 
						self.verificar_noticias(paridade)):
						continue

					if payout_minimo <= payout:
						self.operar(self.valor, paridade, 
							dev_direction, self.tempo, payout, tipo)
						if self.verificar_stop():
							time.sleep(1)
							break

				time.sleep(0.1)
			time.sleep(5)

			if (time.time() - last_update) > 600:
				last_update, paridades = self.update_abertas()

	def operar_berman(self):
		last_update, paridades = self.update_abertas()
		BBANDS_PERIOD = self.config.get("berman_bbands", 20)
		EMA_PERIOD = self.config.get("berman_ema", 100)

		self.mostrar_mensagem(f"""🔸 Operando Estratégia Berman 🔸
		⏰ Timeframe: M{self.tempo}
		📊 Período do bollinger bands: {BBANDS_PERIOD}
		📊 período da EMA: {EMA_PERIOD}
		""")

		while not self.verificar_stop():
			for paridade in paridades:
				taxa_atual, up, low, emma = self.berman_strategy(
					paridade, EMA_PERIOD, BBANDS_PERIOD)

				if (taxa_atual >= up and emma > up) or (
					taxa_atual <= low and emma < low):
					tipo, payout = self.recebe_payout(paridade, self.tempo)
					payout_minimo = self.config.get("minimo", 0) / 100
					direcao = 'put' if taxa_atual >= up else 'call'

					if (self.ativar_noticias and not 
						self.verificar_noticias(paridade)):
						continue
					
					if payout_minimo <= payout:
						self.operar(self.valor, paridade, 
							direcao, self.tempo, payout, tipo)
						time.sleep(60)
				time.sleep(0.1)
			time.sleep(5)

			if (time.time() - last_update) > 600:
				last_update, paridades = self.update_abertas()
		
		time.sleep(1)
		self.verificar_stop()

	def print_hour(self, message: str):
		hour = datetime.fromtimestamp(
			datetime.utcnow().timestamp() - 10800
		).strftime(f'%H:%M')
		print(f"{hour} {message}")

	def operar_donchian(self):
		self.mostrar_mensagem("🔸 Operando Donchian + Fractal 🔸")
		last_update, paridades = self.update_abertas()
		self.tempo = 3

		while not self.verificar_stop():
			for paridade in paridades:
				try:
					velas = self.API.get_candles(
						paridade, 60, 21, time.time())
				except:
					time.sleep(0.1)
					continue

				if len(velas) == 0: 
					time.sleep(0.1)
					continue

				taxas_min = []
				taxas_max = []
				
				for candles in velas:
					taxas_min.append(round(candles['min'], 6))
					taxas_max.append(round(candles['max'], 6))
				
				if len(taxas_min) == 1 or len(taxas_max) == 1:
					time.sleep(0.1)
					continue
				
				# Donchian
				maior = sorted(taxas_max, reverse=True)[0]
				menor = sorted(taxas_min)[0]
				
				# Fractal
				fractal = None
				ultima = velas[-1]
				penultima = velas[-2]
				antipenultima = velas[-3]
				if (penultima['max'] > antipenultima['max'] 
					and penultima['max'] > ultima['max']):
					fractal = 'CALL'
				elif (penultima['min'] < antipenultima['min'] 
					and penultima['min'] < ultima['min']):
					fractal = 'PUT'
					
				# Ultimas 3 velas respeitam os limites do Donchian
				limite_acima = False if (
					ultima['max'] > maior or 
					penultima['max'] > maior or 
					antipenultima['max'] > maior
				) else True
				limite_abaixo = False if (
					ultima['min'] < menor or 
					penultima['min'] < menor or 
					antipenultima['min'] < menor
				) else True
				
				if fractal is not None:
					is_max = round(penultima['max'], 6) >= maior
					is_min = round(penultima['min'], 6) <= menor
					if (fractal == 'CALL' and is_max and limite_acima) or (
						fractal == 'PUT' and is_min and limite_abaixo
					):
						_, payout = self.recebe_payout(paridade, self.tempo)
						payout_minimo = self.config.get("minimo", 0) / 100
						direcao = "CALL" if fractal == "PUT" else "PUT"

						if (self.ativar_noticias and not 
							self.verificar_noticias(paridade)):
							continue
						
						if payout_minimo <= payout:
							resultado = self.operar(self.valor, 
								paridade, direcao, 3, payout, "binary")
							self.print_hour(f"Fim da operação:", resultado)
							time.sleep(60)
							if self.verificar_stop():
								time.sleep(1)
								break
						
				time.sleep(0.1)
			time.sleep(5)
			if (time.time() - last_update) > 600:
				last_update, paridades = self.update_abertas()
		
	def operar_value_chart(self):		
		TIMEFRAME = self.tempo * 60
		CANDLE_AMOUNT = self.config.get("vchart_candles", 7)
		SUPERIOR_LINE = self.config.get("vchart_high", 10)
		INFERIOR_LINE = self.config.get("vchart_low", -10)
		PERCENT_OFFSET = self.config.get("vchart_pct", 100)

		if CANDLE_AMOUNT == 0: CANDLE_AMOUNT = 1
		if PERCENT_OFFSET < 0: PERCENT_OFFSET = 0
		if INFERIOR_LINE > 0: -INFERIOR_LINE

		if INFERIOR_LINE > SUPERIOR_LINE:
			SUPERIOR_LINE, INFERIOR_LINE = INFERIOR_LINE, SUPERIOR_LINE
		elif INFERIOR_LINE == SUPERIOR_LINE:
			INFERIOR_LINE -= 1
			SUPERIOR_LINE += 1

		self.mostrar_mensagem(f"""🔸 Price Action no value chart 🔸
		⏰ Timeframe: M{self.tempo}
		📈 Linha superior: {SUPERIOR_LINE}
		📉 Linha inferior: {INFERIOR_LINE}
		📊 Quantidade de velas: {CANDLE_AMOUNT}
		📊 Porcentagem de entrada: {PERCENT_OFFSET}%
		""")
		
		last_update, paridades = self.update_abertas()

		for paridade in paridades:
			self.API.start_candles_stream(paridade, TIMEFRAME, CANDLE_AMOUNT)

		while not self.verificar_stop():
			for paridade in paridades:
				candles = self.API.get_realtime_candles(
					paridade, TIMEFRAME).copy()
				if len(candles) <= 1: 
					time.sleep(0.1)
					continue

				open = list(reversed([ candles[x]['open'] for x in candles ]))
				close = list(reversed([ candles[x]['close'] for x in candles ]))
				high = list(reversed([ candles[x]['max'] for x in candles ]))
				low = list(reversed([ candles[x]['min'] for x in candles ]))
				
				left_range = self.candle_chart_range(CANDLE_AMOUNT, high, low, close)
				
				average = [(high[x] + low[x]) / 2 for x in range(len(high))]
				average_sma = self.list_sma(average, CANDLE_AMOUNT)
				v_close = (close[0] - average_sma) / left_range
				direction = "CALL" if open[0] > close[0] else "PUT"

				try:
					inferior = round((v_close / SUPERIOR_LINE) * 100, 2)
					superior = round((v_close / INFERIOR_LINE) * 100, 2)		
				except:
					inferior, superior = 0, 0

				if inferior >= PERCENT_OFFSET and direction == "PUT":
					direcao = "PUT"
				elif superior >= PERCENT_OFFSET and direction == "CALL":
					direcao = "CALL"
				else: 
					direcao = ""

				if direcao:
					tipo, payout = self.recebe_payout(paridade, self.tempo)
					payout_minimo = self.config.get("minimo", 0) / 100

					if (self.ativar_noticias and not 
						self.verificar_noticias(paridade)):
						continue
					
					if payout_minimo <= payout:
						resultado = self.operar(self.valor, paridade, 
							direcao, self.tempo, payout, tipo)
						self.print_hour(f"Fim da operação:", resultado)
						time.sleep(60)
						
						if self.verificar_stop():
							time.sleep(1)
							break

				time.sleep(0.1)
			time.sleep(5)
			if (time.time() - last_update) > 600:
				last_update, paridades = self.update_abertas()
			
		