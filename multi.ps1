$nomes = cat contas.txt

Foreach ($nome in $nomes) {
    start powershell python, bot.py, -c, $nome
}