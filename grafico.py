# Básicos
from utils.IQ import IQ_API
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from tkinter import *
from tkinter import messagebox
from tkinter import ttk as t
from datetime import datetime
import time, threading

# Faz a união com tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg)

# Tendências
from talib import BBANDS
import numpy

class Tendencia(Frame):
    def __init__(self, janela, email, senha):
        '''
        Método construtor, que instancia variáveis
        '''
        super().__init__(janela, bg = "white")
        self.pack()
        self.janela = janela

        print("Logando...")
        self.api = IQ_API(email, senha)
        self.api.mudar_treino()
        self.rodando = BooleanVar(self, value = False)

        self.par = StringVar(self, value = "EURUSD")
        self.modalidade = StringVar(self, value = "digital")
        self.timeframe = IntVar(self, value = 300)
        self.maximo_exibidas = IntVar(self, value = 500)
        self.periodo = IntVar(self, value = 21)
        self.desvio = DoubleVar(self, value = 0.1)

        self.medias_moveis = BooleanVar(value = False)
        self.bollinger = BooleanVar(value = False)
        self.topos_fundos = {
            key: BooleanVar(value = False) for key in [
                "s3", "s2", "s1", "p",
                "r1", "r2", "r3"]
        }
        self.colorido = BooleanVar(value = False)

        self.superior, self.media_dados, self.inferior = [], [], []
        self.suporte_resistencia = {}
        self.operacoes = []

        estilo = t.Style()
        estilo.configure(
            "TLabel", background = 'white'
        )
        estilo.configure(
            "TRadiobutton", background = "white"
        )
        estilo.configure(
            "TCheckbutton", background = "white"
        )
        estilo.configure(
            "TScale", background = "white"
        )
        estilo.configure(
            "Tbutton", background = "white"
        )

        self.place_widgets()

    def definir_verificador(self, verificadores, local_verificadores):
        for key, value in verificadores.items():
            local_verificador = t.Label(local_verificadores)
            key = key.replace("s", "Suporte ") if len(key) == 2 else key
            key = key.replace("r", "Resistência ") if len(key) == 2 else key
            t.Label(local_verificador, text = key).pack()
            t.Checkbutton(local_verificador, variable = value).pack()
            local_verificador.pack(side = LEFT, padx = 10)

    def place_widgets(self):
        '''
        Coloca todos os widgets na tela
        '''

        cima = t.Label(self, background = "white")
        cima.pack()
        t.Label(cima, text = "Paridade").pack()
        self.entry_par = t.Entry(cima, textvariable = self.par)
        self.entry_par.pack()
        
        opcoes = {
            "Modalidade": [self.modalidade,
                ["digital", "binary"]],
            "Timeframe": [self.timeframe, 
                [5, 10, 15, 30, 60, 300]]
        }
        for key, value in opcoes.items():
            t.Label(cima, text = key).pack()
            local_opcoes = t.Label(cima)
            for opcao in value[1]:
                t.Radiobutton(
                    local_opcoes, variable = value[0], 
                    text = opcao, value = opcao).pack(side = LEFT, padx = 10)
            local_opcoes.pack()

        escalas = {
            "Quantidade de velas": (self.maximo_exibidas, 50, 1000),
            "Período": (self.periodo, 3, 21),
            "Desvio da tendência": (self.desvio, 0.1, 3)
        }

        for key, value in escalas.items():
            t.Label(cima, text = key).pack()
            t.Scale(
                cima, variable = value[0], 
                from_ = value[1], to = value[2], orient = HORIZONTAL, 
                length = 400).pack()
            t.Label(cima, textvariable = value[0]).pack()

        verificadores = {
            "Médias moveis": self.medias_moveis,
            "Bandas de bollinger": self.bollinger,
            "Cores": self.colorido
        }
        local_verificadores = t.Label(cima)
        self.definir_verificador(verificadores, local_verificadores)
        local_verificadores.pack()

        local_verificadores = t.Label(cima)
        self.definir_verificador(self.topos_fundos, local_verificadores)
        local_verificadores.pack()

        botoes = t.Label(cima)
        t.Button(
            botoes, text = "Plotar", command = self.plotar).pack(side = LEFT)
        t.Button(
            botoes, text = "Iniciar", command = self.iniciar).pack(side = LEFT)
        t.Button(
            botoes, text = "Parar", command = self.parar).pack(side = LEFT)
        botoes.pack()


        self.grafico = plt.figure()
        self.subgrafo = self.grafico.add_subplot(1, 1, 1)

        self.canvas = FigureCanvasTkAgg(self.grafico, master=janela)
        self.canvas.get_tk_widget().pack(
            side=TOP, fill=BOTH, expand=1)

        self.baixo = t.Label(self.janela)
        self.baixo.pack(pady = 10)
        t.Button(
            master = self.baixo, text = "Call", 
            command = self.call).pack(side = LEFT)
        t.Button(
            master = self.baixo, text = "Put", 
            command = self.put).pack(side = LEFT)

        self.mudar_estado("disabled")

    def iniciar(self):
        '''
        Plota e começa a calcular em tempo real
        '''
        self.plotar()
        self.entry_par.state(['disabled'])
        self.rodando.set(True)

    def parar(self):
        '''
        Para de calcular em tempo real
        '''
        self.rodando.set(False)
        self.entry_par.state(['!disabled'])
        self.mudar_estado("disable")

    def mudar_estado(self, opcao):
        '''
        Habulita/desabilita os botões de call/put
        '''
        for widget in self.baixo.winfo_children():
            if opcao != "disabled":
                widget.state(["!disabled"])
            else:
                widget.state(["disabled"])

    def busca_topos_fundos(self, par, timeframe):
        '''
        Pega as linhas de suporte e resistência e devolve
        um dicionário no estilo:
        {
            "s1": 0.8772134,
            "p": 0.86213412
            ...
        }
        '''
        if timeframe < 60:
            timeframe = 60
        indicadores = self.api.API.get_technical_indicators(par)
        if type(indicadores) == list:
            linhas = {
                indicator['name'].replace("Classic ", ""): indicator['value']
                for indicator in indicadores 
                if indicator['candle_size'] == timeframe and 
                "Classic" in indicator['name']
            }
        else:
            messagebox.showinfo("Aviso", "Indicadores não disponíveis para essa paridade")
            linhas = {}
        return linhas

    def plotar_topos_fundos(self, par, timeframe):
        '''
        Plota cada linha de suporte/resistencia que estiver habilitada
        '''
        for key, value in self.suporte_resistencia.items():
            if self.topos_fundos[key].get():
                self.subgrafo.plot(
                    [value for x in range(len(self.dados))],
                    "blue")

    def definir_tendencias(self, par, timeframe, periodo, maximo_exibidas):
        '''
        Pega as velas para análise e calcula a banda de bollinger
        '''
        self.para_analise = [
            x['close'] for x in self.api.API.get_candles(
            par, timeframe, maximo_exibidas + periodo,
            time.time())
        ]

        desvio = round(self.desvio.get(), 1)
        superior, meio, inferior = BBANDS(
            numpy.array(self.para_analise), timeperiod = periodo, 
            nbdevup = desvio, nbdevdn = desvio)
        maximo_exibidas = len(self.dados)
        self.superior = superior[-maximo_exibidas:]
        self.media_dados = meio[-maximo_exibidas:]
        self.inferior = inferior[-maximo_exibidas:]

    def plotar(self):
        '''
        Captura os dados de determinada paridade e plota
        '''
        
        par = self.par.get().strip()
        timeframe = self.timeframe.get()
        maximo_exibidas = int(self.maximo_exibidas.get())
        periodo = int(self.periodo.get())

        self.janela.title(f"Gráfico {par}")

        self.para_analise = [
            x['close'] for x in self.api.API.get_candles(
            par, timeframe, maximo_exibidas + periodo,
            time.time())
        ]
        self.dados = self.para_analise[-maximo_exibidas:]
        self.operacoes = []

        self.subgrafo.clear()
        self.subgrafo.plot(self.dados)
        self.mudar_estado("able")
        self.definir_tendencias(par, timeframe, periodo, maximo_exibidas)
        self.suporte_resistencia = self.busca_topos_fundos(par, timeframe)

        if self.bollinger.get() or self.medias_moveis.get():
            if self.bollinger.get():
                self.subgrafo.plot(self.superior)
                self.subgrafo.plot(self.inferior)
            if self.medias_moveis.get():
                self.subgrafo.plot(self.media_dados)

        if any([x.get() for x in self.topos_fundos.values()]):
            self.plotar_topos_fundos(par, timeframe)
        self.canvas.draw()

    def atualizar(self):
        '''
        Função que adiciona elementos no gráfico
        E remove caso chegar no seu limite
        No final ele limpa o gráfico e plota novamente
        '''
        if not self.rodando.get():
            return

        par = self.par.get().strip()
        timeframe = self.timeframe.get()
        maximo_exibidas = int(self.maximo_exibidas.get())
        periodo = int(self.periodo.get())

        medias_moveis = self.medias_moveis.get()
        bollinger = self.bollinger.get()
        colorido = self.colorido.get()

        vela = self.api.API.get_candles(
            par, timeframe, 2, time.time())[-1]["close"]

        segundo = datetime.now().second
        if segundo % timeframe == 0:
            self.dados.append(vela)
            
            if bollinger or medias_moveis:
                if len(self.superior) != 0:
                    desvio = round(self.desvio.get(), 1)
                    superior, meio, inferior = BBANDS(
                        numpy.array(self.dados[-(periodo + 5):]), 
                        timeperiod = periodo, nbdevup = desvio, 
                        nbdevdn = desvio)
                    self.superior = numpy.append(self.superior, superior[-1])
                    self.media_dados = numpy.append(self.media_dados, meio[-1])
                    self.inferior = numpy.append(self.inferior, inferior[-1])

                else:
                    # Define novas tendências
                    self.definir_tendencias(
                        par, timeframe, periodo, maximo_exibidas)
                                
                if len(self.media_dados) > maximo_exibidas:
                    self.media_dados = self.media_dados[1:]      
                    self.superior = self.superior[1:]      
                    self.inferior = self.inferior[1:] 
            if len(self.dados) >= maximo_exibidas:
                self.dados.pop(0) 
            remover = 0
            for op in self.operacoes:
                op['pos'] = (op['pos'][0] - 1, op['pos'][1])
                if op['pos'][0] == 0:
                    remover += 1
            self.operacoes = self.operacoes[remover:] 
        else:
            self.dados[-1] = vela

        self.subgrafo.clear()
        if colorido:
            for indice, value in enumerate(self.dados):
                if indice != 0:
                    color = "r" if self.dados[indice - 1] > value else "g"
                    if self.dados[indice - 1] == value: color = "gray"
                    self.subgrafo.plot(
                        [indice - 1, indice], 
                        [self.dados[indice - 1], value], color)
        else:
            self.subgrafo.plot(self.dados)
        if medias_moveis and len(self.media_dados) != 0:
            self.subgrafo.plot(self.media_dados)
        if bollinger and len(self.superior) != 0:
            self.subgrafo.plot(self.superior)
            self.subgrafo.plot(self.inferior)
        if any([x.get() for x in self.topos_fundos.values()]):
            self.plotar_topos_fundos(par, timeframe)
        
        for op in self.operacoes:
            self.subgrafo.plot(
                op['pos'][0], op['pos'][1], "g^" if op['dir'] == "call" else "rv")
            
        self.canvas.draw()

    def proximidade_supres(self, valor):
        '''
        Pega o suporte e resistência imediato de determinado valor
        '''
        if self.suporte_resistencia != {}:
            resistencia = self.suporte_resistencia['r1']
            suporte = self.suporte_resistencia['s1']
            for nome, linha in self.suporte_resistencia.items():
                if resistencia > linha > valor:
                    resistencia = linha
                elif suporte < linha < valor:
                    suporte = linha
            return (valor - suporte) / (resistencia - suporte) * 100
        return 50

    def devolve_tendencia(self):
        '''
        Devolve se o valor da tendência (positivo para alta e negativo para baixa)
        '''
        par = self.par.get()
        timeframe = self.timeframe.get() // 60
        if timeframe < 1: timeframe = 1
        velas = self.api.API.get_candles(
            par, timeframe * 60, 3, time.time())

        velas = [
            1 if x['close'] - x['open'] > 0 else 
            0 if x['close'] - x['open'] == 0 else 
            -1 for x in velas
        ]

        if velas[0] == velas[1] == velas[2]:
            return velas[0]

        diferenca = self.media_dados[-1] - self.media_dados[-int(self.periodo.get())]
        inclinacao = diferenca / int(self.periodo.get())
        return inclinacao
        
    def call(self):
        '''
        Verifica se o mercado está favorável para Call e executa
        '''
        dado = self.dados[-1]
        timeframe = self.timeframe.get() // 60
        if timeframe < 1: timeframe = 1

        proximidade = self.proximidade_supres(dado) < 80
        desvio_curto = self.desvio.get() < 1
        
        bollinger_band = True if not desvio_curto or (
            desvio_curto and self.superior[-1] < dado and proximidade
        ) else False

        if ((not self.medias_moveis.get() or 
            self.devolve_tendencia() > 0) and 
            (not self.bollinger.get() or bollinger_band)):
            threading.Thread(
                target = self.api.ordem, 
                args = (self.par.get(), "call"), 
                kwargs = {
                    "tipo": self.modalidade.get(),
                    "tempo": timeframe},
                daemon = True
            ).start()
            self.operacoes.append({
                "dir": "call",
                "pos": (len(self.dados) - 2, self.dados[-2])
                })
        else:
            messagebox.showwarning("Aviso", "Contra a tendência")

    def put(self):
        '''
        Verifica se o mercado está favorável para Put e executa
        '''
        dado = self.dados[-1]
        timeframe = self.timeframe.get() // 60
        if timeframe < 1: timeframe = 1

        proximidade = self.proximidade_supres(dado) > 20
        desvio_curto = self.desvio.get() < 1
        
        bollinger_band = True if not desvio_curto or (
            desvio_curto and self.inferior[-1] > dado and proximidade
        ) else False

        if ((not self.medias_moveis.get() 
            or self.devolve_tendencia() < 0) and 
            (not self.bollinger.get() or bollinger_band)):
            threading.Thread(
                target = self.api.ordem, 
                args = (self.par.get(), "put"), 
                kwargs = {
                    "tipo": self.modalidade.get(),
                    "tempo": timeframe},
                daemon = True
            ).start()
            self.operacoes.append({
                "dir": "put",
                "pos": (len(self.dados) - 2, self.dados[-2])
            })
        else:
            messagebox.showwarning("Aviso", "Contra a tendência")


def on_close():
    rodando = False
    janela.destroy()

rodando = True
janela = Tk()
janela['bg'] = "white"
janela.protocol("WM_DELETE_WINDOW", on_close)
program = Tendencia(
    janela, "daniloedaniel123@gmail.com", "Danilo123")

segundo_anterior = datetime.now()
while rodando:
    time.sleep(0.1)
    try:
        janela.update()
        janela.update_idletasks()
        if datetime.now().second != segundo_anterior.second:
            program.atualizar()
            segundo_anterior = datetime.now()
    except Exception as e:
        print(type(e), e)
        break
    print(str(segundo_anterior)[:-7], end = "\r")

exit()
