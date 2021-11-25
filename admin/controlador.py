import time, json, bottle, requests, threading
from configparser import RawConfigParser
from subprocess import check_output
from utils import ENV_NAME
from os import system 

config = RawConfigParser()
config.read(ENV_NAME)

SERVER_PORT = int(config.get("CONTROL", "port"))
project_name = config.get("CLOUD", "project")
account_name = config.get("CLOUD", "account")
regions = [
    "us-east1-b", "us-east4-c", "us-west1-b", 
    "us-west2-a", "us-west4-a", "us-central1-b",
]

class Instancia:
    def __init__(self, name, region):
        self.name = name
        self.people = []
        self.region = region
        
    def is_full(self):
        '''
        Devolve se a instância já tem 10 pessoas alocadas
        return: boolean
        '''
        return len(self.people) >= 10
    
    def on_instance(self, email):
        '''
        Devolve se o e-mail tá na instância
        return: boolean
        '''
        return email in self.people

    def get_people(self):
        '''
        Devolve a lista de pessoas
        return: list
        '''
        return self.people 

    def set_people(self, name):
        '''
        Adiciona uma nova pessoa à instância
        params:
            name: string com o e-mail da pessoa
        return: None
        '''
        self.people.append(name)

    temperature = property(get_people, set_people)

class Control:
    '''
    Como instalar o controlador

    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-293.0.0-linux-x86_64.tar.gz
    tar zxvf google-cloud-sdk-293.0.0-linux-x86_64.tar.gz google-cloud-sdk
    ./google-cloud-sdk/install.sh
    gcloud init
    gcloud components update
    ssh-keygen -q -t rsa -N '' -f ~/.ssh/google_compute_engine
    '''
    
    def __init__(self):
        self.instancias = []
        self.ao_vivo = []
        self.regiao = 0
        self.creating = False
        self.criar_instancia()

    def __procurar_email(self, email):
        '''
        Procura se o e-mail está em alguma instancia
        Caso contrário devolve None
        '''
        alvo = None
        for instancia in self.instancias:
            if instancia.on_instance(email):
                alvo = instancia
                break
        return alvo

    def __iniciar_bot(self, instancia, email, senha, 
        identificador, operar_lista, ao_vivo):
        '''
        Inicia o bot para determinado email/senha na instância
        params:
            instancia: objeto Instancia
            email: string com e-mail do usuario
            senha: string com a senha do usuario
        return: None
        '''
        if not instancia.on_instance(email):
            instancia.set_people(email)
        caminho_python = "/home/jdsc/.asdf/installs/python/3.8.0/bin/python iqbot/bot.py"
        if not ao_vivo:
            comando = f"{email} -L -Logfile {email}.log {caminho_python} -o"
        else:
            self.ao_vivo.append(email)
            comando = f"@{email} -L -Logfile @{email}.log {caminho_python} -a"

        try:
            check_output(f"gcloud compute ssh {instancia.name} --zone {instancia.region} --command='screen -ls | grep {email}'")
        except:
            self.parar_operacao(email)
            system(f"gcloud compute ssh {instancia.name} --zone {instancia.region} --command='screen -dmS {comando} {email} {senha} {identificador} {operar_lista}'")


    def adicionar_pessoa(self, email, senha, identificador, 
        operar_lista = False, ao_vivo = False) -> bool:
        '''
        Verifica se o e-mail está em alguma instância
        Caso não estiver verifica se a última instância 
        tem local para alocar o novo usuário
        Caso não tiver ele cria uma nova instância
        params:
            email: string com o e-mail do usuário
            senha: string com a senha do usuário
        return: None
        '''
        alvo = self.__procurar_email(email)
        if alvo == None:
            while self.creating:
                time.sleep(1)
            if self.instancias[-1].is_full():
                self.criar_instancia()
            alvo = self.instancias[-1]
        
        if not ao_vivo or email not in self.ao_vivo:
            self.__iniciar_bot(
                alvo, email, senha, identificador, 
                operar_lista, ao_vivo)
        return True

    def criar_instancia(self):
        '''
        Cria uma nova instância com o nome instancia{len(instancias)}
        E instala suas dependências.
        '''
        if len(self.instancias) != 0 and len(self.instancias) % 4 == 0:
            self.regiao += 1
            print(f"Região alterada para {regions[self.regiao]}")
        
        self.creating = True
        regiao = regions[self.regiao]
        name = "instancia" + str(len(self.instancias))
        print(f"Criando a VM de nome: {name}")

        system(f'yes "Y" | gcloud beta compute --project={project_name} instances create {name} --zone={regiao} --machine-type=e2-medium --subnet=default --network-tier=PREMIUM --maintenance-policy=MIGRATE --service-account={account_name} --scopes=https://www.googleapis.com/auth/cloud-platform --tags=http-server,https-server --image=padrao --image-project={project_name} --boot-disk-size=10GB --boot-disk-type=pd-standard --boot-disk-device-name={name} --no-shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring --reservation-affinity=any')
        status = -1
        while status != 0:
            status = system(f"gcloud compute ssh {name} --zone {regiao} --command='chmod 777 iqbot/setup.sh;./iqbot/setup.sh'")
            print("Status:", status)
            if status == 256:
                self.regiao += 1
                print(f"Região alterada para {regiao}.")
                return
        
        self.instancias.append(Instancia(name, regiao))
        self.creating = False

    def parar_operacao(self, email):
        '''
        Encontra a instancia que tem esse email
        E manda parar a operação
        '''
        alvo = self.__procurar_email(email)
        if alvo != None:
            system(f"gcloud compute ssh {alvo.name} --zone {alvo.region} --command='screen -X -S {email} quit'")
            return True
        return False

    def pegar_log(self, email):
        '''
        Devolve o arquivo de log gerado pelo bot
        '''
        alvo = self.__procurar_email(email)
        if alvo != None:
            resultado = check_output(f"gcloud compute ssh {alvo.name} --zone {alvo.region} --command='tail -n 50 {email}.log'", shell = True)
            return resultado.decode()
        return "Registro não encontrado."

    def deletar_instancias(self):
        '''
        Deleta todas as instâncias deixando apenas a original
        E devolve todos os usuários deletados
        '''
        usuarios = []
        for instancia in self.instancias:
            usuarios.extend(instancia.get_people())
            threading.Thread(system, args = (
                f'yes "Y" | gcloud compute instances delete --zone {instancia.region} {instancia.name}',), daemon = True).start()
        self.instancias = []
        self.ao_vivo = []
        self.regiao = 0
        self.creating = False
        return usuarios

    def mostrar_usuarios(self):
        '''
        Passa por todos os usuários e devolve um dicionário:
            {"nome_instancia": ["user1", "user2", ...]}
        '''
        usuarios = {}
        for instancia in self.instancias:
            usuarios[instancia.name] = instancia.get_people()
        return usuarios

    def enviar_comando(self, email, comando):
        '''
        Envia os comandos para as operações ao vivo
        '''
        if comando == "quit" and email in self.ao_vivo:
            self.ao_vivo.remove(email)
        alvo = self.__procurar_email(email)
        if alvo != None and email in self.ao_vivo:
            system(f"gcloud compute ssh {alvo.name} --zone {alvo.region} --command='screen -X -S @{email} stuff \"{comando}\n\"'")
        return "Modo ao vivo não ligado."

@bottle.post("/add/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.adicionar_pessoa(*args, **kwargs)
    return { "resultado": resultado }

@bottle.post("/stop/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.parar_operacao(*args, **kwargs)
    return { "resultado": resultado }

@bottle.post("/log/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.pegar_log(*args, **kwargs)
    return { "resultado": resultado }

@bottle.post("/delete/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.deletar_instancias(*args, **kwargs)
    return { "resultado": resultado }

@bottle.post("/list/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.mostrar_usuarios(*args, **kwargs)
    return { "resultado": resultado }

@bottle.post("/send/")
def adicionar_pessoa():
    data = json.loads(bottle.request.body.read())
    args, kwargs = data["args"], data["kwargs"]
    resultado = controlador.enviar_comando(*args, **kwargs)
    return { "resultado": resultado }

class Client:
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = SERVER_PORT
        self.url = f"http://{self.host}:{self.port}"
    
    def send(self, command: str, args: list, kwargs: dict):
        response = requests.post(f"{self.url}/{command}/", 
            json = { "args": args, "kwargs": kwargs }
        )
        return response.json()["resultado"]

    def adicionar_pessoa(self, *args, **kwargs):
        return self.send("add", args, kwargs)
    
    def parar_operacao(self, *args, **kwargs):
        return self.send("stop", args, kwargs)
    
    def pegar_log(self, *args, **kwargs):
        return self.send("log", args, kwargs)
    
    def deletar_instancias(self, *args, **kwargs):
        return self.send("delete", args, kwargs)
    
    def mostrar_usuarios(self, *args, **kwargs):
        return self.send("list", args, kwargs)

if __name__ == "__main__":
    controlador = Control()
    print(f"Server preparado para receber. na porta {SERVER_PORT}")
    bottle.run(host = "localhost", port = SERVER_PORT, debug = True)
