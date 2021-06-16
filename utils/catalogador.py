from datetime import datetime, timedelta
from configparser import RawConfigParser
from utils.IQ import IQ_API
import time, re, amanobot

config = RawConfigParser()
config.read(".env")

BOTTOKEN = config.get("TELEGRAM", "token")

def pegar_comando_lista(texto):
    '''
    Recebe um texto e devolve:
    {
        "data": [dia, mes, ano],
        "hora": [hora, minuto]
        "par": paridade,
        "ordem": ordem,
        "timeframe": int
        "tipo": "lista"
    }
    No qual o conteúdo das listas são inteiros
    '''
    def timestamp(data, hora):
        return datetime(
            data[2], data[1], data[0], hora[0], hora[1]
        ).timestamp()
    try:
        data = re.search(r'\d{2}\W\d{2}\W\d{4}', texto)
        if data:
            data = [int(x) for x in re.split(r"\W", data[0])]
        else:
            hoje = datetime.datetime.now()
            data = [hoje.day, hoje.month, hoje.year]
        hora = re.search(r'\d{2}:\d{2}', texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]
        par = re.search(r'[A-Za-z]{6}(-OTC)?', 
            texto.upper().replace("/", ""))[0]
        ordem = re.search(r'CALL|PUT', texto.upper())[0].lower()
        timeframe = re.search(
            r'[MH][1-6]?[0-5]', texto.upper())
        if timeframe: 
            if "M" in timeframe[0].upper(): 
                timeframe = int(timeframe[0].strip("M"))
            else: 
                timeframe = int(timeframe[0].strip("H")) * 60
        else: timeframe = 0
    except Exception as e:
        print("Erro na catalogação", type(e), e)
        return {}

    return {
        "data": data,
        "hora": hora,
        "par": par,
        "ordem": ordem,
        "timeframe": timeframe,
        "tipo": "lista",
        "timestamp": timestamp(data, hora)
    }


class Catalogador(IQ_API): 

    def __init__(self, verboso = False):
        self.verboso = verboso

        super().__init__(
            "hiyivo1180@tmail7.com", "senha123", 
            self.mostrar_mensagem)
        self.mudar_treino()

    def mostrar_mensagem(self, mensagem):
        '''
        Mostra a mensagem no terminal e no listbox.
        '''
        # print(mensagem)
        if self.verboso:
            try:
                self.telegram.sendMessage(self.verboso, mensagem)
            except Exception as e:
                try:
                    self.telegram = amanobot.Bot(BOTTOKEN)
                    self.telegram.sendMessage(self.verboso, mensagem)
                except Exception as e:
                    print("O erro:", type(e), e)

    def catalogar(self, timeframe, dias, porcentagem, martingale):
        def cataloga(par, dias, timeframe):
            data = []
            datas_testadas = []
            time_ = time.time()
            sair = False
            while sair == False:
                velas = self.API.get_candles(
                    par, (timeframe * 60), 1000, time_)
                velas.reverse()
                
                for x in velas:	
                    if datetime.fromtimestamp(x['from']).strftime('%Y-%m-%d') not in datas_testadas: 
                        datas_testadas.append(datetime.fromtimestamp(x['from']).strftime('%Y-%m-%d'))
                        
                    if len(datas_testadas) <= dias:
                        x.update({'cor': 'verde' if x['open'] < x['close'] else 'vermelha' if x['open'] > x['close'] else 'doji'})
                        data.append(x)
                    else:
                        sair = True
                        break

                if len(velas) > 0:
                    time_ = int(velas[-1]['from'] - 1)   

            analise = {}
            for velas in data:
                horario = datetime.fromtimestamp(velas['from']).strftime('%H:%M')
                if horario not in analise : analise.update({horario: {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0, 'dir': ''}})	
                analise[horario][velas['cor']] += 1
                
                try:
                    analise[horario]['%'] = round(100 * (analise[horario]['verde'] / (analise[horario]['verde'] + analise[horario]['vermelha'] + analise[horario]['doji'])))
                except:
                    pass
            
            for horario in analise:
                if analise[horario]['%'] > 50 : analise[horario]['dir'] = 'CALL'
                if analise[horario]['%'] < 50 : analise[horario]['%'],analise[horario]['dir'] = 100 - analise[horario]['%'],'PUT '
                
            
            return analise  
        P = self.API.get_all_open_time()

        catalogacao = {}
        for par in P['digital']:
            if P['digital'][par]['open'] == True:
                timer = int(time.time())
                self.mostrar_mensagem(' CATALOGANDO - ' + par + '.. ')
                
                catalogacao.update({par: cataloga(par, dias, timeframe)})	
                
                for par in catalogacao:
                    for horario in sorted(catalogacao[par]):	
                        mg_time = horario
                        soma = {'verde': catalogacao[par][horario]['verde'], 'vermelha': catalogacao[par][horario]['vermelha'], 'doji': catalogacao[par][horario]['doji']}
                        
                        for i in range(martingale):

                            catalogacao[par][horario].update({'mg'+str(i+1): {'verde': 0, 'vermelha': 0, 'doji': 0, '%': 0} })

                            mg_time = str(datetime.strptime((datetime.now()).strftime('%Y-%m-%d ') + str(mg_time), '%Y-%m-%d %H:%M') + timedelta(minutes=timeframe))[11:-3]
                            
                            if mg_time in catalogacao[par]:
                                catalogacao[par][horario]['mg'+str(i+1)]['verde'] += catalogacao[par][mg_time]['verde'] + soma['verde']
                                catalogacao[par][horario]['mg'+str(i+1)]['vermelha'] += catalogacao[par][mg_time]['vermelha'] + soma['vermelha']
                                catalogacao[par][horario]['mg'+str(i+1)]['doji'] += catalogacao[par][mg_time]['doji'] + soma['doji']
                                
                                catalogacao[par][horario]['mg'+str(i+1)]['%'] = round(100 * (catalogacao[par][horario]['mg'+str(i+1)]['verde' if catalogacao[par][horario]['dir'] == 'CALL' else 'vermelha'] / (catalogacao[par][horario]['mg'+str(i+1)]['verde'] + catalogacao[par][horario]['mg'+str(i+1)]['vermelha'] + catalogacao[par][horario]['mg'+str(i+1)]['doji']) ) )
                                
                                soma['verde'] += catalogacao[par][mg_time]['verde']
                                soma['vermelha'] += catalogacao[par][mg_time]['vermelha']
                                soma['doji'] += catalogacao[par][mg_time]['doji']
                            else:						
                                catalogacao[par][horario]['mg'+str(i+1)]['%'] = 'N/A'
                
                self.mostrar_mensagem('finalizado em ' + str(int(time.time()) - timer) + ' segundos')
        
        resultado = []
        texto_entradas, conta_texto = "", 0
        for par in catalogacao:
            for horario in sorted(catalogacao[par]):
                ok = False		
                if catalogacao[par][horario]['%'] >= porcentagem:
                    ok = True
                else:
                    for i in range(int(martingale)):
                        porcentagem_sinal = catalogacao[par][horario]['mg'+str(i+1)]['%']
                        if porcentagem_sinal != "N/A" and porcentagem_sinal >= porcentagem:
                            ok = True
                            break
                
                if ok == True:                    
                    texto_entrada = f"{datetime.now().strftime('%d/%m/%Y')} {horario} {par} {catalogacao[par][horario]['dir'].strip()} M{timeframe}\n"
                    entrada = pegar_comando_lista(texto_entrada)
                    if entrada != {}:
                        resultado.append(entrada)
                        texto_entradas += texto_entrada + "\n"
                        conta_texto += 1
                        if conta_texto % 50 == 0:
                            self.mostrar_mensagem(texto_entradas)	
                            texto_entradas = ""
        self.mostrar_mensagem(texto_entradas)	        
        self.mostrar_mensagem("Catalogação finalizada")	
        return resultado