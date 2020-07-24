from utils.IQ import IQ_API
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from tkinter import *
from tkinter import messagebox

# Faz a união com tkinter
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.backend_bases import key_press_handler

from talib import WMA
import pandas as pd
import numpy
from pprint import pprint

import time, threading
from datetime import datetime

def media(lista):
    return sum(lista) / len(lista)

api = IQ_API("daniloedaniel123@gmail.com", "Danilo123")
api.mudar_treino()

par = "EURUSD"
timeframe = 5
maximo_exibidas = 100
periodo = 20

grafico = plt.figure()
subgrafo = grafico.add_subplot(1, 1, 1)
dados = [x['close'] for x in api.API.get_candles(
    par, timeframe, maximo_exibidas, time.time())
] # Aqui é a lista onde vai entrar os dados
# Faz uma média dos dados
para_analise = [x['close'] for x in api.API.get_candles(
    par, timeframe, maximo_exibidas + periodo, time.time())
]

media_dados = WMA(numpy.array(para_analise), timeperiod = periodo)
media_dados = media_dados[-maximo_exibidas:]

subgrafo.plot(dados)

def atualizar(contador = 0):
    '''
	Função que adiciona elementos no gráfico
	E remove caso chegar no seu limite
	No final ele limpa o gráfico e plota novamente
	Param:
		contador: Aumenta de 1 em 1 conforme o tempo 
	'''
    global media_dados

    # PARTE MAIS IMPORTANTE: jogue aqui o dado
    vela = api.API.get_candles(par, timeframe, 2, time.time())[-1]["close"]

    segundo = datetime.now().second
    if segundo % 5 == 0:
        dados.append(vela)
        novo = WMA(numpy.array(dados[-25:]), timeperiod = periodo)
        media_dados = numpy.append(media_dados, novo[-1])

        if len(dados) >= maximo_exibidas:
            dados.pop(0)
        if len(media_dados) > maximo_exibidas:
            media_dados = media_dados[1:]
        
    else:
        dados[-1] = vela

    subgrafo.clear()
    for indice, value in enumerate(dados):
        if indice != 0:
            subgrafo.plot(
                [indice - 1, indice],
                [media_dados[indice - 1], media_dados[indice]],
                "black"
            )
            color = "r" if dados[indice - 1] > value else "g"
            if dados[indice - 1] == value: color = "gray"
            subgrafo.plot(
                [indice - 1, indice], 
                [dados[indice - 1], value], color)
    

janela = Tk()
janela.title(f"Gráfico {par}")

canvas = FigureCanvasTkAgg(grafico, master=janela)
canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)

def call():
    if media_dados[-1] > media_dados[-2]:
        threading.Thread(
            target = api.ordem, args = (par, "call"), kwargs = {"tipo": "digital"}
        ).start()
    else:
        messagebox.showwarning("Aviso", "Contra a tendência")

def put():
    if media_dados[-1] < media_dados[-2]:
        threading.Thread(
            target = api.ordem, args = (par, "put"), kwargs = {"tipo": "digital"}
        ).start()
    else:
        messagebox.showwarning("Aviso", "Contra a tendência")

def _quit():
    janela.quit()
    janela.destroy()

intervalo =  600 # 7000 De quanto em quanto tempo vai entrar na função
animacao = animation.FuncAnimation(
    grafico, atualizar, interval = intervalo)

baixo = Label(janela)
baixo.pack()
Button(master=baixo, text="Call", command=call).pack(side = LEFT)
Button(master=baixo, text="Put", command=put).pack(side = LEFT)
Button(master=baixo, text="Quit", command=_quit).pack(side= LEFT)

janela.mainloop()

print("Chegou ao fim.")