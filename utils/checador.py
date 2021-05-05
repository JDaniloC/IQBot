from datetime import datetime
from utils.IQ import IQ_API
import time

class IQ_BOT(IQ_API): 
    def __init__(self, email, senha):
        super().__init__(email, senha)
        self.mudar_treino()
        self.agendamento = self.API.get_all_init_v2()
        self.identificadores = self.API.get_all_ACTIVES_OPCODE()

    def ver_resultado(self, entrada, timeframe):
        data = entrada['data']
        hora = entrada['hora']
        paridade = entrada['par']
        direcao = entrada['ordem'].lower()

        timestamp = datetime(
            data[2], data[1], data[0], hora[0], hora[1]
        ).timestamp()
        
        format_hour = lambda x: "0" + str(x) if len(str(x)) == 1 else str(x)
        identificador = f'{paridade} {":".join(map(format_hour, hora))} '

        if not self.ver_condicao(paridade, timestamp):
            return identificador + "🔐"

        resultado = self.pegar_cores(
            paridade, timestamp + ((timeframe * 60) * 2), timeframe)

        gales = 0
        win = False
        while gales < 3 and not win:
            win = resultado[gales] == 1 if direcao == "call" else resultado[gales] == -1
            if not win:
                gales += 1
        
        if gales == 3:
            resultado = identificador + "❌"
        elif gales > 0:
            resultado = identificador + (f"🐔" * gales + "✅")
        else:
            resultado = identificador + ("✅")
        
        return resultado

    def mandar_resultado(self, paridade):
        timeframe = 300
        direcao = "acima"
        print(datetime.now())
        time.sleep(timeframe * 3)

        print(datetime.now())
        velas = self.API.get_candles(paridade, timeframe, 3, time.time())
        for vela in velas:
            print(datetime.fromtimestamp(vela['at']/1000000000))
        velas = [
            1 if x['close'] - x['open'] > 0 else 
            0 if x['close'] - x['open'] == 0 else 
            -1 for x in velas
        ]
        print(velas)

        win = False
        gales = 0
        while gales < 2 and not win:
            win = velas[gales] == 1 if direcao == "acima" else velas[gales] == -1
            if not win:
                gales += 1
        
        resposta = f"""
        📊 Par: {paridade}
        {'⬆' if direcao.lower() == "acima" else '⬇'} Direção: {direcao}
        ⏰ Tempo: {timeframe // 60}
        Resultado: {(gales * 'G') + '✅' if win else '❌'}
        """

        print(resposta)

    def pegar_cores(self, paridade, timestamp, timeframe):
        velas = self.pegar_velas(paridade, timeframe * 60, 3, timestamp)
        # for vela in velas:
        #     print(datetime.fromtimestamp(vela['at']/1000000000))
        return [
            1 if x['close'] - x['open'] > 0 else 
            0 if x['close'] - x['open'] == 0 else 
            -1 for x in velas
        ] 
        
    def ver_condicao(self, paridade, horario, tipo = "turbo"):
        '''
        Verifica se a paridade está aberta naquele determinado horário
        param:
            paridade = EURUSD..
            horario = timestamp
            tipo = binary ou turbo (M1)
        '''
        ID = self.identificadores[paridade]
        try:
            agenda = self.agendamento[tipo]['actives'][str(ID)]['schedule']
        except:
            return True
        for abertura, fechamento in agenda:
            if abertura > horario:
                return False
            elif abertura <= horario:
                if fechamento > horario:
                    return True

def checa_sinais(sinais, timeframe_padrao):
    api = IQ_BOT("hiyivo1180@tmail7.com", "senha123")
    resultado = []
    for entrada in sinais:
        timeframe = entrada["timeframe"]
        if timeframe == 0: timeframe = timeframe_padrao
        resultado.append(api.ver_resultado(entrada, timeframe))
    return resultado
