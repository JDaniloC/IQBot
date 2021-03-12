# IQBot
A IQ Option bot for telegram using Gcloud and MongoDB service

## Getting started
Install Python 3.8 or higher

Make sure the requirements are installed:
``` python
pip install -r requirements.txt
```

To run the telegram app:
``` bash
python telegram.py
```
Make sure that have a .env file where:
``` env
[CLOUD]
project = gcloud-project-name
account = gcloud@account.gserviceaccount.com

[DATABASE]
autentication = mongodb+srv://mongoauth

[TELEGRAM]
token = 123456789:TELEGRAMTOKEN
```

Open the terminal and run:
``` bash
python bot.py 
```
Its will read the config.txt to load the user settings and the entradas.txt for call/put commands

## Commands

To see what the commands are, run:
``` bash
python bot.py -h
```
If no command was passed, it will try to read the settings and to execute the "entradas"

## User settings and errors

To see how manage your settings, open "ajuda.txt"

All errors will be placed in "errors.log"

## Important

API created by Lu-Yi-Hsun all rights reserved to him.
Github: https://github.com/Lu-Yi-Hsun/iqoptionapi

Using the variant of dsinmsdj:
Github: https://github.com/dsinmsdj/iqoptionapi

All instructions by IQ Coding youtube channel:
https://www.youtube.com/channel/UC51qSJBV60nneZXVNgM-bKQ/
