# Coloca aqui o caminho de cada arquivo de configuração
# Ou encha uma pasta de configurações e chame o técnico

$nomes = $(
    ..\config\config.txt
)

Foreach ($nome in $nomes) {
   Start-Process powershell python, ..\bot.py, -c, $nome
}