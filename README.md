# IQBot
Script that simplify the IQ Option API to braziliams

## Download
Click the "download" button.

## Getting started
Install Python 3.7 or higher

Make sure the websocket is installed:
``` python
pip install websocket-client==0.5.6
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
