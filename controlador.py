from os import system 
from subprocess import check_output

project_name = "robotic-incline-285016"
account = "976842081628-compute@developer.gserviceaccount.com"

class Instancia:
    def __init__(self, name):
        self.name = name
        self.people = []
        
    def is_full(self):
        '''
        Devolve se a instância já tem 5 pessoas alocadas
        return: boolean
        '''
        return len(self.people) >= 5
    
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
        self.criar_instancia()
    
    def procura_email(self, email):
        alvo = None
        for instancia in self.instancias:
            if instancia.on_instance(email):
                alvo = instancia
                break
        return alvo

    def adicionar_pessoa(self, email, senha, identificador):
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
        alvo = self.procura_email(email)
        if alvo == None:
            if self.instancias[-1].is_full():
                self.criar_instancia()
            alvo = self.instancias[-1]
            
        self.iniciar_bot(alvo, email, senha, identificador)

    def criar_instancia(self):
        '''
        Cria uma nova instância com o nome instancia{len(instancias)}
        E instala suas dependências.
        '''
        name = "instancia" + str(len(self.instancias))
        system(f'yes "Y" | gcloud beta compute --project={project_name} instances create {name} --zone=us-central1-a --machine-type=e2-highcpu-2 --subnet=default --network-tier=PREMIUM --maintenance-policy=MIGRATE --service-account={account} --scopes=https://www.googleapis.com/auth/cloud-platform --tags=http-server,https-server --image=padrao --image-project={project_name} --boot-disk-size=10GB --boot-disk-type=pd-standard --boot-disk-device-name={name} --no-shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring --reservation-affinity=any')
        status = -1
        while status != 0:
            status = system(f"gcloud compute ssh {name} --zone us-central1-a --command='chmod 777 iqbot/setup.sh;./iqbot/setup.sh'")
        
        self.instancias.append(Instancia(name))

    def iniciar_bot(self, instancia, email, senha, identificador):
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
        system(f"gcloud compute ssh {instancia.name} --zone us-central1-a --command='screen -dmS {email} -L -Logfile {email}.log /home/jdsc/.asdf/installs/python/3.8.0/bin/python iqbot/bot.py -o {email} {senha} {identificador}'")

   
    def parar_operacao(self, email):
        '''
        Encontra a instancia que tem esse email
        E manda parar a operaçao
        '''
        alvo = self.procura_email(email)
        if alvo != None:
            system(f"gcloud compute ssh {alvo.name} --zone us-central1-a --command='screen -X -S {email} quit'")

    def pegar_log(self, email):
        alvo = self.procura_email(email)
        if alvo != None:
            resultado = check_output(f"gcloud compute ssh {alvo.name} --command='cat {email}.log'", shell = True)
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
            system(f'yes "Y" | gcloud compute instances delete {instancia.name}')
        self.instancias = []
        return usuarios
