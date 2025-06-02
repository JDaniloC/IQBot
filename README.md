# 🤖 IQBot - Bot de Trading Automatizado para Telegram

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org)

Um bot avançado para trading automatizado na IQ Option integrado ao Telegram, com suporte a múltiplas estratégias, gerenciamento de risco e análise técnica.

## 🚀 Funcionalidades Principais

### 📊 Trading Automatizado
- **Múltiplas Estratégias**: Suporte a estratégias automáticas e manuais
- **Análise Técnica**: Integração com indicadores técnicos via TA-Lib
- **Timeframes Variados**: Operações em 1, 5 e 15 minutos
- **Paridades Múltiplas**: Suporte a opções binárias e digitais

### 🛡️ Gerenciamento de Risco
- **Stop Win/Loss**: Controle automático de lucros e perdas
- **Martingale Inteligente**: Sistema de recuperação com múltiplas modalidades
- **Scalper**: Proteção contra perdas consecutivas
- **Filtros de Tendência**: Análise de tendência para evitar entradas contra o mercado

### 🔧 Configurações Avançadas
- **Interface Telegram**: Configuração completa via bot do Telegram
- **Múltiplas Contas**: Suporte a contas demo e real
- **Catalogação de Sinais**: Sistema de análise e catalogação automática
- **Filtro de Notícias**: Evita operações durante eventos de alto impacto

### 🌐 Integração Cloud
- **Google Cloud**: Suporte para execução em nuvem
- **MongoDB**: Banco de dados para persistência de configurações
- **Multi-usuário**: Sistema de administração para múltiplos usuários

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Conta na IQ Option
- Bot do Telegram (opcional, para interface)
- MongoDB (para persistência de dados)
- Google Cloud (opcional, para execução em nuvem)

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/JDaniloC/IQBot.git
cd IQBot
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Configure o TA-Lib (Linux/Mac)
```bash
chmod +x talib.sh
./talib.sh
```

### 4. Execute o script de configuração
```bash
chmod +x setup.sh
./setup.sh
```

## ⚙️ Configuração

### Arquivo .env
Crie um arquivo `.env` na raiz do projeto:

```env
[CLOUD]
project = seu-projeto-gcloud
account = sua-conta@gserviceaccount.com

[DATABASE]
authentication = mongodb+srv://sua-string-de-conexao

[TELEGRAM]
token = 123456789:SEU_TOKEN_DO_TELEGRAM
```

### Configuração via Telegram
1. Inicie o bot: `python telegram.py`
2. Envie `/start` para o bot
3. Configure suas preferências através do menu interativo

### Configuração Manual
Edite o arquivo `config/config.txt` com suas preferências:

```ini
[CONTA]
email = seu@email.com
senha = suasenha
tipo_conta = treino

[ENTRADAS]
tipo_par = auto
valor = 2.00
tempo = 1
profit_minimo = 80

[WIN]
stopwin = 50.00
max_soros = 2
scalper_win = 3

[LOSS]
stoploss = 30.00
martin = True
max_gale = 2
tipo_gale = seguro

[ESTRATEGIA]
auto = True
autotime = 1
autogale = 1
```

## 🚀 Como Usar

### Modo Básico
```bash
python bot.py
```

### Modo Online (Multi-usuário)
```bash
python bot.py -o email@exemplo.com senha 1 True
```

### Interface Telegram
```bash
python telegram.py
```

### Comandos Disponíveis
```bash
python bot.py -h  # Ver todos os comandos disponíveis
```

## 📊 Estratégias Disponíveis

### Automáticas
- **Auto Trade**: Seleção automática baseada em performance
- **Catalogação**: Análise histórica para otimização
- **Filtros Inteligentes**: Múltiplos filtros de qualidade

### Manuais
- **Lista Personalizada**: Importação de sinais externos
- **Estratégias Fixas**: Configuração manual de parâmetros
- **Timeframes Específicos**: Operações em horários determinados

## 🛠️ Funcionalidades Avançadas

### Gerenciamento de Martingale
- **Seguro**: Incremento conservador
- **Simples**: Dobrar o valor
- **Leve**: Incremento moderado
- **Agressivo**: Incremento alto
- **Personalizado**: Valor definido pelo usuário

### Filtros de Qualidade
- **Tendência**: Análise SMA para direção do mercado
- **Notícias**: Evita operações durante eventos importantes
- **Payout Mínimo**: Garante rentabilidade mínima
- **Horário**: Restrições de horário de operação

### Sistema de Soros
- **Ciclos Configuráveis**: Múltiplos ciclos de recuperação
- **Tipos Variados**: Diferentes modalidades de soros
- **Limite Inteligente**: Proteção contra perdas excessivas

## 📈 Monitoramento e Relatórios

### Logs Detalhados
- **Operações**: Histórico completo de trades
- **Erros**: Log de erros para debugging
- **Performance**: Métricas de desempenho

### Relatórios
- **Assertividade**: Taxa de acerto por estratégia
- **Lucro/Prejuízo**: Balanço financeiro
- **Estatísticas**: Análises detalhadas de performance

## 🔒 Segurança

- **Validação de Entrada**: Verificação de todos os parâmetros
- **Limite de Tentativas**: Proteção contra ataques
- **Criptografia**: Dados sensíveis protegidos
- **Auditoria**: Log de todas as ações

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## ⚠️ Disclaimer

**AVISO IMPORTANTE**: Trading de opções binárias envolve riscos significativos. Este bot é fornecido apenas para fins educacionais e de pesquisa. O uso deste software é por sua conta e risco. Os desenvolvedores não se responsabilizam por perdas financeiras.

## 🙏 Créditos

- **API IQ Option**: Baseada no trabalho de [Lu-Yi-Hsun](https://github.com/Lu-Yi-Hsun/iqoptionapi)
- **Variante Utilizada**: [dsinmsdj](https://github.com/dsinmsdj/iqoptionapi)
- **Tutoriais**: [IQ Coding YouTube Channel](https://www.youtube.com/channel/UC51qSJBV60nneZXVNgM-bKQ/)

## 📞 Suporte

Para suporte e dúvidas:
- 📧 Email: [Criar issue no GitHub](https://github.com/JDaniloC/IQBot/issues)
- 💬 Telegram: Através do bot oficial
- 📖 Documentação: Arquivo `misc/ajuda.txt`

---

**Desenvolvido com ❤️ para a comunidade de trading**
