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
        super().__init__(janela)
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
                    "Martingale": "martin",
                    "Tendencia": "tendencia"
                },
                "numericos": {
                    "Máximo de martingales": "max_gale",
                    "Profit mínimo": "minimo",
                    "Correção de entrada": "correcao",
                    "Percentual do soros": "percent_soros",
                    "Percentual do martin": "percent_martin",
                    'Delay de resultado': "delay"
                },
                "alternativos": {
                    "Tipo de conta": "tipo_conta",
                    "Tipo de paridade": "tipo_par",
                    "tipo de martingale": "tipo_gale",
                    "Tempo": "tempo",
                }
            }

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
            Label(self, text = key).grid(row = pos)
            self.entradas[key] = Entry(self, width = 40)
            if key == "Senha":
                self.entradas["Senha"]["show"] = "*"
            self.entradas[key].grid(row = pos, column = 1, columnspan = 5)
            pos += 1
        Button(self, text = "Selecionar", command = self.mudar_entrada).grid(row = 2, column = 5)

        self.condicionais = {
            "OTC": BooleanVar(value = False), 
            "Soros": BooleanVar(value = False),
            "Martingale": BooleanVar(value = True),
            "Tendencia": BooleanVar(value = False)
        }
        for indice, nome in enumerate(self.condicionais.keys()):
            ttk.Checkbutton(self, text = nome, variable = self.condicionais[nome]).grid(
                row = pos, column = indice)
        pos += 1


        self.numericos = { 
            "Máximo de martingales": (1, 2, 1),
            "Profit mínimo": (0, 99, 1), 
            "Correção de entrada": (0, 120, 1), 
            "Percentual do soros": (0, 1000, 1), 
            "Percentual do martin": (0, 1000, 1),
            'Delay de resultado': (-1, 3, 0.1)
        }
        for key in self.numericos.keys():
            escala = Scale(
                self, label = key, from_=self.numericos[key][0], 
                to = self.numericos[key][1], orient = HORIZONTAL, 
                length = 400, resolution = self.numericos[key][2])
            self.numericos[key] = escala
            escala.grid(row = pos, columnspan = 6)
            pos += 1

        self.alternativos = {
            "Tipo de conta":["Treino", "Real"], 
            "Tipo de paridade":["Binaria", "Digital", "Auto"], 
            "tipo de martingale":["Seguro", "Simples", "Leve", "Agressivo", "Porcento"],
            "Tempo":["1", "5", "15"]
        }
        for key in self.alternativos.keys():
            Label(self, text = key).grid(row = pos, columnspan = 6)
            pos +=1
            variavel = StringVar()
            cont = 0
            for escolha in self.alternativos[key]:
                ttk.Radiobutton(self, text = escolha, variable = variavel, value = escolha).grid(row = pos, column = cont)
                if escolha == "Porcento":
                    Entry(self, width = 10, textvariable = variavel).grid(row = pos, column = cont + 1)
                cont += 1
            variavel.set(self.alternativos[key][0])
            self.alternativos[key] = variavel
            pos += 1
        
        Button(self, text = "Carregar", command = self.carregar).grid(row = pos, column = 0, columnspan = 4)
        Button(self, text = "Salvar", command = self.salvar).grid(row = pos, column = 1, columnspan = 4)
        Button(self, text = "Operar", command = self.operar).grid(row = pos, column = 2, columnspan = 4)
        
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
                messagebox.showwarning(
                    "ERRO", 
                    f"Preencha o campo {key}")
                return
            if key in ["Valor da entrada", "StopWin", "StopLoss"] and not self.numerico(value.get()):
                messagebox.showwarning(
                    "ERRO",
                    f"Campo de {key} deve ser númerico"
                )
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
            "profit_minimo": tudo["Profit mínimo"].get(),
            'tendencia': tudo['Tendencia'].get()
        }
        editor["WIN"] = {
            "goal": tudo["StopWin"].get(),
            "soros": tudo["Soros"].get(),
            "percent_soros": tudo["Percentual do soros"].get()
        }
        editor["LOSS"] = {
            "stoploss": tudo["StopLoss"].get(),
            "martin": tudo["Martingale"].get(),
            "percent_martin": tudo["Percentual do martin"].get(),
            "max_gale": tudo["Máximo de martingales"].get(),
            "tipo_gale": tudo["tipo de martingale"].get().lower().replace(",", ".")
        }
        editor['AJUSTES'] = {
            "correcao_entrada": tudo["Correção de entrada"].get(),
            "delay": tudo['Delay de resultado'].get()
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
        Método que faz os casts para operar
        '''
        dic["tipo_conta"] = dic["tipo_conta"].lower()
        dic["goal"] = float(dic["goal"].replace(",", "."))
        dic["stoploss"] = float(dic["stoploss"].replace(",", "."))
        dic["tipo_gale"] = dic["tipo_gale"].lower() if not self.numerico(dic['tipo_gale'].replace(",", ".")) else float(dic['tipo_gale'].replace(",", "."))
        dic["max_gale"] = int(dic["max_gale"])
        dic["valor"] = float(dic["valor"].replace(",", "."))
        dic["tipo_par"] = dic["tipo_par"].lower()
        dic["tempo"] = int(dic["tempo"])
        dic["minimo"] = int(dic["minimo"])
        dic["correcao"] = int(dic["correcao"])
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

    app = Config(janela)
    app.mainloop()
