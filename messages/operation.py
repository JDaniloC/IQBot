def login_account_msg(email: str) -> str:
    return f"📝 Entrando na {email}"

def none_cycles_msg() -> str:
    return "🌀 Nenhum ciclo detectado, mudando para martingale 🌀"

def operation_end_msg() -> str:
    return "🔰 Placar Final 🔰"

def stop_win_msg() -> str:
    return "🤑 Stop WIN batido! 🤑"

def stop_loss_msg() -> str:
    return "🥵 Stop LOSS batido! 🥵"

def stop_msg(final_msg:str, scoreboard: str, 
    total_earn: float, stop_win: float,
    total_lost: float, stop_loss: float,
    assertively: float) -> str:
    return f"""{final_msg}
{scoreboard}
💰 Saldo: $ {total_earn} | $ {stop_win}
💲 Perca: $ {total_lost} | $ {stop_loss}
✴️ Assertividade: {assertively}%
        ⚠️ Bot parado ⚠️"""

def tendency_msg(asset: str, direcao: str) -> str:
    return f"[❗️] {asset}|{direcao} está contra a tendência. [❗️]"

def posgale_msg():
    return "[❗️] Cancelando entrada devido gale na última operação. [❗️]"

def payout_msg(asset: str, current: float, minimun: float) -> str:
    return f"{asset} não atende o payout mínimo {current}% < {minimun}%"

def payout_failed(paridade: str) -> str:
    f"[❗️] Não consegui pegar o payout {paridade}!"

def news_msg(asset: str, impact: str) -> str:
    return f"Cancelando entrada devido notícia: {asset} {impact}"

def soros_cycles_complete_msg(cycle: int, value: float, original_value:float) -> str:
    return f"""🔸 CicloSoros: {cycle}° ciclo completo:
        Variação de $ {value} -> $ {original_value}"""

def soros_cycles_back_to_first_msg() -> str:
    return "🔸 CicloSoros: Voltando ao primeiro ciclo."

def soros_gale_end_msg() -> str:
    return "🔸 Fim do sorosgale!"

def do_soros_msg(old_value: float, new_value: float) -> str:
    return f"🔸 Soros: $ {old_value} para $ {new_value}"

def soros_end_msg(old_value: float, new_value: float) -> str:
    return f"🔸 Soros: Voltando $ {old_value} -> $ {new_value}"

def flex_stop_msg(current_lost: float, stop_loss: float) -> str:
    return f"🔻 Stop Móvel: $ {current_lost} | $ {stop_loss}"

def trade_msg(current_balance: float, wins_count: int, loss_count: int, 
    gain_total: float, assertively: float, flex_stop: str) -> str:
    return f"""
💎 Saldo atual:  R$ {current_balance}
✅ Vitórias: {wins_count}
❌ Derrotas: {loss_count}
💰 Lucro: {gain_total}
{flex_stop}
✴️ Assertividade: {assertively}%"""

def update_value_msg(asset: str, _type: str, timeframe: int, 
    direction: str, value: float, result_value: float, 
    result_msg: str, gale_msg: str) -> str:
    return f"""
{asset}|{_type} M{timeframe} {direction}
💠 Valor: $ {value} 
💰 Resultado: $ {result_value} {result_msg}   
{gale_msg}"""

def cycle_trade_msg(current_cycle: int, cycle_type: str, value: float) -> str:
    return f"🔸 Operando no {current_cycle}° ciclo de {cycle_type}: R$ {value}"

def report_trade_error_msg(error_type: str, error:str) -> str:
    return f"Ocorreu um erro na operação:\n {error_type}: {error}"

def do_gale_msg(gale_number: int, gale_type: str) -> str:
    return f"🔸 Iniciando {gale_number}° Martingale: {gale_type} 🔸"

def gale_error_msg() -> str:
    return "❌ Não consigo fazer o gale..."

def gale_cycles_come_to_first_msg() -> str:
    return "🔸 Voltando ao primeiro ciclo"

def gale_cycles_next_msg(next_cycle: int) -> str:
    return f"♦️ Avançando para o {next_cycle}° ciclo"

def martingale_next_trade_msg(current_gale: int, martin_type: str) -> str:
    return f"🔸 {current_gale}° Martingale: {martin_type} para o próximo sinal"

def soros_gale_new_value_msg(old_value: float, new_value: float) -> str:
    return f"🔸 Sorosgale: {old_value} para {new_value}"

def soros_gale_come_to_first_msg() -> str:
    return "♦️ Sorosgale: Voltando ao valor inicial"

def gale_cycles_next_trade(current_gale: int) -> str:
    return f"🔸 Próxima entrada no {current_gale}° gale."
