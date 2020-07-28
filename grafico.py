# Básicos
from utils.IQ import IQ_API
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from tkinter import *
from tkinter import messagebox
from tkinter import ttk as t
import time, threading, sys
from datetime import datetime

# Faz a união com tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.backend_bases import key_press_handler

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
        self.timeframe = IntVar(self, value = 60)
        self.maximo_exibidas = IntVar(self, value = 100)
        self.periodo = IntVar(self, value = 20)
        self.desvio = DoubleVar(self, value = 2)

        self.medias_moveis = BooleanVar(value = False)
        self.bollinger = BooleanVar(value = False)
        self.colorido = BooleanVar(value = False)

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

    def place_widgets(self):
        '''
        Coloca todos os widgets na tela
        '''

        cima = t.Label(self, background = "white")
        cima.pack()
        t.Label(cima, text = "Paridade").pack()
        t.Entry(cima, textvariable = self.par).pack()
        
        opcoes = {
            "Modalidade": [self.modalidade,
                ["digital", "binária"]],
            "Timeframe": [self.timeframe, 
                [5, 10, 15, 30, 60]]
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
            "Período": (self.periodo, 3, 20),
            "Desvio da tendência": (self.desvio, 0.1, 2)
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
        for key, value in verificadores.items():
            local_verificador = t.Label(local_verificadores)
            t.Label(local_verificador, text = key).pack()
            t.Checkbutton(local_verificador, variable = value).pack()
            local_verificador.pack(side = LEFT, padx = 10)
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

    def mudar_estado(self, opcao):
        for widget in self.baixo.winfo_children():
            if opcao != "disabled":
                widget.state(["!disabled"])
            else:
                widget.state(["disabled"])

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

        self.subgrafo.clear()
        self.subgrafo.plot(self.dados)
        self.mudar_estado("able")

        if self.bollinger.get() or self.medias_moveis.get():
            desvio = round(self.desvio.get(), 1)
            superior, meio, inferior = BBANDS(
                numpy.array(self.para_analise), timeperiod = periodo, 
                matype = 2, nbdevup = desvio, nbdevdn = desvio)
            self.superior = superior[-maximo_exibidas:]
            self.media_dados = meio[-maximo_exibidas:]
            self.inferior = inferior[-maximo_exibidas:]

            if self.bollinger.get():
                self.subgrafo.plot(self.superior)
                self.subgrafo.plot(self.inferior)
            if self.medias_moveis.get():
                self.subgrafo.plot(self.media_dados)
        else:
            self.superior = self.dados[:]
            self.media_dados = self.dados[:]
            self.inferior = self.dados[:]
        
        self.canvas.draw()

    def iniciar(self):
        '''
        Plota e começa a calcular em tempo real
        '''
        self.plotar()
        self.rodando.set(True)

    def parar(self):
        '''
        Para de calcular em tempo real
        '''
        self.rodando.set(False)
        self.mudar_estado("disable")

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
                desvio = round(self.desvio.get(), 1)
                superior, meio, inferior = BBANDS(
                    numpy.array(self.dados[-(periodo + 5):]), timeperiod = periodo,
                    matype = 2, nbdevup = desvio, nbdevdn = desvio)
                self.superior = numpy.append(self.superior, superior[-1])
                self.media_dados = numpy.append(self.media_dados, meio[-1])
                self.inferior = numpy.append(self.inferior, inferior[-1])

            if len(self.dados) >= maximo_exibidas:
                self.dados.pop(0)
            if len(self.media_dados) > maximo_exibidas:
                self.media_dados = self.media_dados[1:]      
                self.superior = self.superior[1:]      
                self.inferior = self.inferior[1:]      
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
        if medias_moveis:
            self.subgrafo.plot(self.media_dados)
        if bollinger:
            self.subgrafo.plot(self.superior)
            self.subgrafo.plot(self.inferior)
        self.canvas.draw()

    def call(self):
        '''
        Verifica se o mercado está favorável para Call e executa
        '''
        # Call automático quando bater bollinger
        par = self.par.get()
        periodo = int(self.periodo.get())
        modalidade = self.modalidade.get()

        valor = self.media_dados[-1] - self.media_dados[-periodo]
        if valor > 0:
            threading.Thread(
                target = self.api.ordem, 
                args = (par, "call"), 
                kwargs = {"tipo": modalidade}
            ).start()
        else:
            messagebox.showwarning("Aviso", "Contra a tendência")

    def put(self):
        '''
        Verifica se o mercado está favorável para Put e executa
        '''
        par = self.par.get()
        periodo = int(self.periodo.get())
        modalidade = self.modalidade.get()

        valor = self.media_dados[-1] - self.media_dados[-periodo]
        if valor < 0:
            threading.Thread(
                target = self.api.ordem, 
                args = (par, "put"), 
                kwargs = {"tipo": modalidade}
            ).start()
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
        print(e)
        break
    print(str(segundo_anterior)[:-7], end = "\r")
# janela.mainloop()

exit()
