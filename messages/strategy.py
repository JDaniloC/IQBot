def next_trade_hour_msg(hour: str) -> str:
    return f"⏰ Próxima entrada será às {hour} ⏰"

def canceled_trade_msg() -> str:
    return "⏰ A entrada foi cancelada: DOJI"

def bear_filter_msg(hits: int) -> str:
    return f"🔹 Filtro Bear {hits}: Analisando..."

def search_hits_msg(asset: str, hits: int) -> str:
    return f"🔹 Procurando por HIT {hits} em {asset}..."

def search_hitted_asset_msg() -> str:
    return "🔹 Procurando por um ativo com hit..."

def expected_direction_msg(direction: str) -> str:
    return f"Deveria dar: {direction}"

def without_trade_msg() -> str:
    return "Sem ciclo operável..."

def cannot_get_candles_msg() -> str:
    return "❌ Não consegui pegar as velas..."

def waiting_cataloguer_hour_msg() -> str:
    return "🔹 Esperando o tempo propício para catalogar..."

def without_cataloguer_result_msg() -> str:
    return "🔹 Catalogação: Nenhum atendeu os requisitos..."

def cataloguer_infos_msg(asset: str, strategy: str, 
    payout: float, assertively: float = "") -> str:
    if assertively:
        assertively = f"🎯 Assertividade: {assertively}% |"
    return f"""
🔹 {strategy} | Paridade: {asset} ♦️
{assertively} Payout: {payout}% ❇️"""

def waiting_next_minute_msg() -> str:
    return "🔹 Iniciando... Esperando próximo minuto..."

def show_direction_msg(direction: str) -> str:
    return f'Direção: {direction}'