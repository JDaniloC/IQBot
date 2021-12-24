def connection_error_msg() -> str:
    return "❌ Não conseguiu se conectar, reveja a senha ❌"

def connection_success_msg() -> str:
    return "✅ Conectado com sucesso ✅"

def connection_trying_msg() -> str:
    return "⏱ Tentando se conectar ⏱"

def demo_account_msg() -> str:
    return "- Usando a conta treino -"

def real_account_msg() -> str:
    return "- Usando a conta real -"

def without_payout_msg() -> str:
    return "❌ Algo deu errado, se conectando novamente. ❌"

def restart_bot_msg() -> str:
    return "❌❌ Reinicie o bot ❌❌"

def cannot_get_payout_msg(asset: str) -> str:
    return f" [❗️] Não consegui pegar o payout de {asset} [❗️]"

def closed_asset_msg() -> str:
    return "❌ Ativo fechado nesta modalidade/timeframe."

def invalid_asset_msg() -> str:
    return "❌ Paridade não encontrada na digital pela IQ." 

def trade_error_msg() -> str:
    return "❌ Não conseguiu operar..."

def pre_stop_loss_msg() -> str:
    return "❌ Pré-stoploss: Fim da operação ❌"

def pre_stop_win_msg() -> str:
    return "✅ Pré-stopwin: Fim da operação ✅"

def switch_trade_type_msg(_type: str) -> str:
    return f"❌ Erro na operação, tentando operar na {_type}."

def payout_not_found_msg() -> str:
    return "Payout não devolvido."

def payout_below_minimum_msg(_type: str, reason: str) -> str:
    return f"Payout na {_type} está abaixo do aceitável: {reason}"

def trade_realized_msg() -> str:
    return "Operação realizada"

def digital_loop_error_msg() -> str:
    return "❌ Não consegui pegar o resultado..."

def connect_cataloguer_msg() -> str:
    return "🔹 Tentando se conectar ao catalogador..."

def connect_cataloguer_failed_msg() -> str:
    return "❌ Não consegui me conectar ao catalogador! Mudando para o antigo..."

def abort_cataloguer_msg() -> str:
    return "❌ Ocorreu um problema no catalogador..."

def cataloguer_error_msg(reason: str) -> str:
    return f"Motivo de estar sem resultados: {reason}"

