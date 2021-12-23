wget https://sonik.dl.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz
tar -xzf ./ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
cd ..

# https://gitlab.com/JDaniloC/iqbot/-/commit/8d711da0a0f5025fa0d0129c034f35802faac296