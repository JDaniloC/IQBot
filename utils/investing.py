def extrair_noticias():
    from datetime import datetime, timedelta
    from bs4 import BeautifulSoup
    import requests

    # Créditos: https://www.youtube.com/watch?v=xDTRcAR9u1U

    headers = requests.utils.default_headers()
    headers.update({
        'User-Agent': 
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0'
    })

    data = requests.get('http://br.investing.com/economic-calendar/', headers=headers)

    resultados = []

    if data.status_code == requests.codes.ok:
        info = BeautifulSoup(data.text, 'html.parser')

        blocos = ((info.find(
            'table', {'id': 'economicCalendarData'}
        )).find('tbody')).findAll('tr', {'class': 'js-event-item'})

        for blocos2 in blocos:
            impacto = str((blocos2.find(
                'td', {'class': 'sentiment'}
            )).get('data-img_key')).replace('bull', '')
            horario = str(blocos2.get('data-event-datetime')).replace('/', '-')
            paridade = (blocos2.find('td', {'class': 'left flagCur noWrap'})).text.strip()
            text = (blocos2.find('a')).text.strip()
            
            resultados.append({
                'horario': horario, 
                'par': paridade, 
                'impacto': impacto, 
                'text': text
            })

    for info in resultados:
        data, hora = info['horario'][:-3].split(" ")
        hora = [int(x) for x in hora.split(":")]
        info['horario'] = datetime.now().replace(
            hour = hora[0], minute = hora[1], second = 0)

    return resultados