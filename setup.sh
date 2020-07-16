#!/bin/bash
git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.7.8
echo . $HOME/.asdf/asdf.sh >> ~/.bashrc
echo . $HOME/.asdf/completions/asdf.bash >> ~/.bashrc
. $HOME/.asdf/asdf.sh
. $HOME/.asdf/completions/asdf.bash
sudo apt-get update; sudo apt-get -y install --no-install-recommends make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
asdf plugin-add python
asdf install python 3.8.0
asdf global python 3.8.0
pip install amanobot pymongo requests websocket-client==0.56 dnspython