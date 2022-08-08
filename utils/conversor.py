from datetime import datetime
import re

ASSET_REGEX = r'[A-Za-z]{6}(-OTC)?'
DATE_REGEX = r'\d{2}\W\d{2}\W\d{4}'
TIME_REGEX = r'[MH][1-6]?[0-5]'
HOUR_REGEX = r'\d{2}:\d{2}'
DIR_REGEX = r'CALL|PUT'

def datetime_brazil():
    return datetime.fromtimestamp(
        datetime.utcnow().timestamp() - 10800)

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
    
    texto = texto.upper()
    try:
        data = re.search(DATE_REGEX, texto)
        if data:
            data = [int(x) for x in re.split(r"\W", data[0])]
        else:
            hoje = datetime_brazil()
            data = [hoje.day, hoje.month, hoje.year]
        
        hora = re.search(HOUR_REGEX, texto)[0]
        hora = [int(x) for x in re.split(r'\W', hora)]

        par = re.search(ASSET_REGEX, texto)[0]
        ordem = re.search(DIR_REGEX, texto)[0].lower()
        has_timeframe = re.search(TIME_REGEX, texto)
        if has_timeframe: 
            if "M" in has_timeframe[0]: 
                timeframe = int(has_timeframe[0].strip("M"))
            else: 
                timeframe = int(has_timeframe[0].strip("H")) * 60
        else: timeframe = 0
    except:
        return {}

    return {
        "par": par,
        "data": data,
        "hora": hora,
        "ordem": ordem,
        "tipo": "lista",
        "timeframe": timeframe,
        "timestamp": timestamp(data, hora)
    }

def numerico(x):
    '''
    Verifica se a string pode ser convertida para float
    '''
    try:
        float(x.replace(",", "."))
        return True
    except: return False

def pegar_comando_taxas(original_text: str) -> dict:
    '''
    Recebe um texto e devolve:
    {
        par: str,       # Paridade eg. EURUSD-OTC
        taxa: int,      # A taxa eg. 1.12345
        ordem: str,     # "" ou "PUT"|"CALL"
        tipo: "taxas",  # Para ser identificado pelo bot
        timeframe: int, # 0 ou um número se houver
        timestamp: timestamp
    }
    '''
    texto = original_text.strip().upper()
    paridade, taxa, direction, timeframe = "", 0, "", 0
    try:
        has_timeframe = re.search(TIME_REGEX, texto)
        if has_timeframe: 
            texto = re.sub(TIME_REGEX, r'', texto).strip()
            if "M" in has_timeframe[0]: 
                timeframe = int(has_timeframe[0].strip("M"))
            else: 
                timeframe = int(has_timeframe[0].strip("H")) * 60
        
        partitions = re.split(r"[^\w.-]", texto)
        for text_part in partitions: 
            possible_asset = text_part.replace("/", "")
            has_asset = re.search(ASSET_REGEX, possible_asset)
            has_direction = re.search(DIR_REGEX, text_part)
            if has_asset:
                paridade = has_asset[0]
            elif numerico(text_part): 
                taxa = float(text_part)
            elif has_direction:
                direction = has_direction[0].lower()
                    
        if paridade == "" or taxa == 0:
            raise ValueError("Faltando a paridade ou taxa!")
        
    except Exception as e:
        print(type(e), e, original_text)
        return {}
        
    return {
        "par": paridade, 
        "taxa": taxa, 
        "tipo": "taxas",
        "ordem": direction,
        "timeframe": timeframe,
        "timestamp": datetime_brazil()
    }

def convert_lines_to_list(message: list, remove_timestamp: bool = True):
    '''
    Usa a função pegar_comando em cada comando
    E devolve uma lista de cada um deles
    '''
    comandos = []
    for entrada in message:
        if entrada not in ['', '\n']:
            comando = pegar_comando_lista(entrada)
            if comando == {}:
                comando = pegar_comando_taxas(entrada)
            if comando != {}:
                comandos.append(comando)
    comandos.sort(key = lambda x: x["timestamp"])
    if remove_timestamp:
        for entrada in comandos:
            del entrada["timestamp"]
    return comandos

def strDateHour(number:int) -> str:
    '''
    Converte números de 1 dígito para 2 dígitos:
        0:0 -> 00:00
        2/1/2000 -> 02/01/2000
    '''
    return str(number) if len(str(number)) != 1 else "0" + str(number)

def convert_list_to_text(lista):
    '''
    Transform a list of dicts into a string
    '''
    lista_entradas = []
    if len(lista) > 0 and "timestamp" in lista[0]:
        lista.sort(key = lambda x: x["timestamp"])

    lista_entradas = []
    for linha in lista:
        timeframe = linha['timeframe']
        if timeframe == 0:
            timeframe = "Padrão"
        else:
            timeframe = f"M{linha['timeframe']}"
        direcao = linha["ordem"].upper()
        direcao_sign = '⬆' if direcao == "CALL" else '⬇'

        if linha["tipo"] == "taxas": 
            lista_entradas.append(f"""
📊 Ativo: {linha['par']}
📈 Taxa: {linha['taxa']}
⏰ Período: {timeframe}
{f'{direcao_sign} Direção {direcao}' if direcao != "" else ""}
            """)
            continue

        lista_entradas.append(f'''
📊 Ativo: {linha["par"]}
📅 Dia: {"/".join(list(map(strDateHour, linha["data"])))}
⏱ Hora: {":".join(list(map(strDateHour, linha["hora"])))}   
{direcao_sign} Direção: {direcao} 
⏰ Período: {timeframe}
        ''')
    return lista_entradas