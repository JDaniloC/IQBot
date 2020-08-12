import configparser
from bot import abrir_arquivo, configuracoes, Operacao
from tkinter import *
from tkinter import messagebox
from tkinter import ttk
from tkinter.filedialog import askopenfilename

DEFAULTFILE = "./config/config.txt"

class Config(Frame):
    '''
    Objeto para facilitar a configuração
    '''
    def __init__(self, janela):
        super().__init__(janela, bg = "white")
        self.cima = ttk.Label(self)

        self.lado_esquerdo = ttk.Label(self.cima)
        self.lado_direito = ttk.Label(self.cima)
        self.baixo = ttk.Label(self)

        self.lado_esquerdo.pack(side = LEFT)
        self.lado_direito.pack(side = RIGHT)
        self.cima.pack(side = TOP)
        self.baixo.pack(side = BOTTOM)

        self.janela = janela
        self.pack(fill=X, padx=5, pady=5)
        
        # Um mapeamento para facilitar
        self.traducao = {
                "entries":
                {
                    "E-mail": "email",
                    "Senha": "senha",
                    "Arquivo de entradas": "arquivo",
                    "Valor da entrada": "valor",
                    "StopWin": "goal",
                    "StopLoss": "stoploss"
                },
                "booleans": {
                    "OTC": "otc",
                    "Soros": "soros",
                    "Tendencia": "tendencia"
                },
                "numericos": {
                    "Máximo de martingales": "max_gale",
                    "Profit mínimo": "minimo",
                    "Correção de entrada": "correcao",
                    "Percentual do soros": "percent_soros",
                    "Percentual do martin": "percent_martin",
                    'Delay de resultado': "delay",
                    "Período da tendência": "periodo_tendencia",
                    "Desvio da tendência": "desvio_tendencia"
                },
                "alternativos": {
                    "Tipo de conta": "tipo_conta",
                    "Tipo de paridade": "tipo_par",
                    "Gerenciamento": "tipo_gale",
                    "Tipo de martingale": "tipo_martin",
                    "Tempo": "tempo",
                    "Tipo de tendência": "tipo_tendencia"
                }
            }

        estilo = ttk.Style()
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

        self.widgets()

    def widgets(self):
        '''
        Coloca os widgets no Frame, e no fim
        roda o método carregar.
        '''
        
        self.entradas = {
            "E-mail": None, 
            "Senha": None, 
            "Arquivo de entradas": None, 
            "Valor da entrada": None, 
            "StopWin": None, 
            "StopLoss": None 
        }
        pos = 0

        for key in self.entradas.keys():
            ttk.Label(self.lado_esquerdo, text = key).grid(row = pos)
            self.entradas[key] = ttk.Entry(self.lado_esquerdo, width = 40)
            if key == "Senha":
                self.entradas["Senha"]["show"] = "*"
            elif key == "Arquivo de entradas":
                self.entradas["Arquivo de entradas"].config(
                    width = 30)
            self.entradas[key].grid(
                row = pos, column = 1, columnspan = 6, sticky = "w")
            pos += 1
        ttk.Button(self.lado_esquerdo, text = "Selecionar", command = self.mudar_entrada
            ).grid(row = 2, column = 2, columnspan = 6, sticky = "e")

        self.condicionais = {
            "OTC": BooleanVar(value = False), 
            "Soros": BooleanVar(value = False),
            "Tendencia": BooleanVar(value = False),
            "Ativar delay": BooleanVar(value = False)
        }
        for indice, nome in enumerate(self.condicionais.keys()):
            ttk.Checkbutton(
                self.lado_esquerdo, text = nome, variable = self.condicionais[nome]
                ).grid(row = pos, column = indice)
        pos += 1


        self.numericos = { 
            "Máximo de martingales": (1, 2, 1),
            "Profit mínimo": (0, 99, 1), 
            "Correção de entrada": (0, 120, 1), 
            "Percentual do soros": (0, 1000, 1), 
            "Percentual do martin": (0, 1000, 1),
            'Delay de resultado': (-1, 3, 0.1),
            'Período da tendência': (1, 21, 1),
            'Desvio da tendência': (0.1, 3, 0.1)
        }
        for key in self.numericos.keys():
            escala = Scale(self.lado_direito, label = key, 
                from_=self.numericos[key][0], 
                to = self.numericos[key][1], orient = HORIZONTAL, 
                length = 400, resolution = self.numericos[key][2],
                bg = "white", troughcolor='#73B5FA')
            self.numericos[key] = escala
            escala.grid(row = pos, columnspan = 6)
            pos += 1

        self.alternativos = {
            "Tipo de conta":["Treino", "Real"], 
            "Tipo de paridade":["Binaria", "Digital", "Auto"], 
            "Gerenciamento": ["martin", "soros"],
            "Tipo de martingale":["Seguro", "Simples", "Leve", "Agressivo", "Porcento"],
            "Tempo":["1", "5", "15"],
            "Tipo de tendência":["bollinger", "velas"]
        }
        for key in self.alternativos.keys():
            ttk.Label(self.lado_esquerdo, text = key
                ).grid(row = pos, columnspan = 4, pady = 10)
            pos +=1
            variavel = StringVar()
            cont = 1 if len(self.alternativos[key]) == 2 else 0
            for escolha in self.alternativos[key]:
                ttk.Radiobutton(
                    self.lado_esquerdo, text = escolha, 
                    variable = variavel, value = escolha
                    ).grid(
                        row = pos, column = cont)
                if escolha == "Porcento":
                    ttk.Entry(self.lado_esquerdo, width = 10, textvariable = variavel
                        ).grid(row = pos, column = 3)
                cont += 1
                if cont == 4: # Pra ir para baixo
                    cont = 0
                    pos += 1
            variavel.set(self.alternativos[key][0])
            self.alternativos[key] = variavel
            pos += 1
        
        ttk.Button(self.baixo, text = "Carregar", command = self.carregar
            ).grid(row = pos, column = 0)
        ttk.Button(self.baixo, text = "Salvar", command = self.salvar
            ).grid(row = pos, column = 1)
        ttk.Button(self.baixo, text = "Operar", command = self.operar
            ).grid(row = pos, column = 2)
        
        self.carregar(DEFAULTFILE)

    def carregar(self, nome = None):
        '''
        Método que carrega o arquivo do disco na interface
        Vai até onde pode.
        '''
        try:
            if nome == None: nome = askopenfilename()
            info = configuracoes(nome)
            for key in self.traducao["entries"]:
                self.entradas[key].delete(0, 'end')
                self.entradas[key].insert(
                    END, info[self.traducao["entries"][key]]
                )
            for key in self.traducao["booleans"]:
                self.condicionais[key].set(
                    bool(info[self.traducao["booleans"][key]])
                )
            for key in self.traducao["numericos"]:
                if self.numericos[key] == "delay" and self.numerico(
                    info[self.traducao["numericos"][key]]):
                        self.numericos[key].set(0)
                        self.condicionais['Ativar delay'].set(False)
                else:
                    if self.numericos[key] == "delay":
                        self.condicionais['Ativar delay'].set(True)
                    self.numericos[key].set(
                    float(info[self.traducao["numericos"][key]])
                    )
            for key in self.traducao["alternativos"]:
                self.alternativos[key].set(
                    info[self.traducao["alternativos"][key]].capitalize() if 
                    key != "Tempo" else 
                    info[self.traducao["alternativos"][key]]
                )
        except:
            pass

    def salvar(self):
        '''
        Método que pega as informações da interface e guarda no arquivo
        '''
        for key, value in self.entradas.items():
            if value.get() == "":
                messagebox.showwarning("ERRO", 
                    f"Preencha o campo {key}")
                return
            if key in ["Valor da entrada", "StopWin", "StopLoss"
                ] and not self.numerico(value.get()):
                messagebox.showwarning("ERRO",
                    f"Campo de {key} deve ser númerico")
                return
        
        tudo = {}
        tudo.update(self.entradas)
        tudo.update(self.condicionais)
        tudo.update(self.numericos)
        tudo.update(self.alternativos)

        editor = configparser.ConfigParser()
        
        editor["CONTA"] = {
            "email": tudo["E-mail"].get(),
            "senha": tudo["Senha"].get(),
            "tipo": tudo["Tipo de conta"].get()
        }
        editor["ENTRADAS"] = {
            "arquivo": tudo["Arquivo de entradas"].get(),
            "tipo_par": tudo["Tipo de paridade"].get(),
            "otc": tudo["OTC"].get(),
            "valor": tudo["Valor da entrada"].get(),
            "tempo": tudo["Tempo"].get(),
            "profit_minimo": tudo["Profit mínimo"].get()
        }
        editor["WIN"] = {
            "goal": tudo["StopWin"].get(),
            "soros": tudo["Soros"].get(),
            "percent_soros": tudo["Percentual do soros"].get()
        }
        editor["LOSS"] = {
            "stoploss": tudo["StopLoss"].get(),
            "tipo_gale": tudo["Gerenciamento"].get(),
            "percent_martin": tudo["Percentual do martin"].get(),
            "max_gale": tudo["Máximo de martingales"].get(),
            "tipo_martin": tudo["Tipo de martingale"].get(
                ).lower().replace(",", ".")
        }
        editor['AJUSTES'] = {
            "correcao_entrada": tudo["Correção de entrada"].get(),
            "delay": tudo['Delay de resultado'].get()
        }
        if not self.condicionais['Ativar delay'].get():
            editor['AJUSTES']['delay'] = "False"
        editor['TENDENCIA'] = {
            "tendencia": tudo["Tendencia"].get(),
            "tipo_tendencia": tudo["Tipo de tendência"].get(),
            "periodo_tendencia": tudo["Período da tendência"].get(),
            "desvio_tendencia": tudo['Desvio da tendência'].get()
        }
        with open(askopenfilename(), "w") as arquivo:
            editor.write(arquivo)
        
        messagebox.showinfo("Resultado", "Arquivo salvo!")
    
    def operar(self):
        '''
        Método que usa as informações da interface para operar
        '''
        tudo = {}
        tudo.update(self.entradas)
        tudo.update(self.condicionais)
        tudo.update(self.numericos)
        tudo.update(self.alternativos)

        resultado = {}
        for tipo in self.traducao:
            for key, value in self.traducao[tipo].items():
                resultado[value] = tudo[key].get()
        
        self.janela.destroy()
        resultado = self.parsear(resultado)
        comandos = abrir_arquivo(resultado["arquivo"])
        try:
            Operacao(resultado, comandos)
        except:
            print("Ocorreu um erro, entrando novamente.")
            Operacao(resultado, comandos)

    def parsear(self, dic):
        '''
        Ajusta as entradas de widgets do tipo entry, radiobutton
        '''
        dic["tipo_conta"] = dic["tipo_conta"].lower()
        dic["goal"] = float(dic["goal"].replace(",", "."))
        dic["stoploss"] = float(dic["stoploss"].replace(",", "."))
        dic["tipo_martin"] = dic["tipo_martin"].lower() if not self.numerico(
            dic['tipo_martin'].replace(",", ".")
            ) else float(dic['tipo_martin'].replace(",", "."))
        dic["valor"] = float(dic["valor"].replace(",", "."))
        dic["tipo_par"] = dic["tipo_par"].lower()
        dic["tempo"] = int(dic["tempo"])
        # dic["max_gale"] = int(dic["max_gale"])
        # dic["minimo"] = int(dic["minimo"])
        # dic["correcao"] = int(dic["correcao"])
        # dic["periodo_tendencia"] = int(dic["periodo_tendencia"])
        # dic["desvio_tendencia"] = float(dic["desvio_tendencia"])
        return dic

    def numerico(self, x):
        '''
        Verifica se a string pode ser convertida para float
        '''
        try:
            float(x)
            return True
        except:
            return False

    def mudar_entrada(self):
        '''
        Método que seleciona o arquivo de entradas
        '''
        self.entradas["Arquivo de entradas"].delete(0, 'end')
        self.entradas["Arquivo de entradas"].insert(END, askopenfilename())

if __name__ == "__main__":
    janela = Tk()
    janela.title("Configurações")
    janela['bg'] = "white"
    
    app = Config(janela)
    app.mainloop()
