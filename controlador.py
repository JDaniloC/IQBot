from os import system 

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
    
    def adicionar_pessoa(self, email, senha):
        '''
        Verifica se a última instância tem local para alocar
        Caso não tiver ele cria uma nova instância
        params:
            email: string com o e-mail do usuário
            senha: string com a senha do usuário
        return:
            None
        '''
        if self.instancias[-1].is_full():
            self.criar_instancia()
        self.iniciar_bot(self.instancias[-1], email, senha)

    def criar_instancia(self):
        '''
        Cria uma nova instância com o nome instancia{len(instancias)}
        E instala suas dependências.
        '''
        name = "instancia" + str(len(self.instancias))
        system(f'yes "Y" | gcloud beta compute --project=durable-matter-281714 instances create {name} --zone=us-central1-a --machine-type=e2-highcpu-2 --subnet=default --network-tier=PREMIUM --maintenance-policy=MIGRATE --service-account=46980103503-compute@developer.gserviceaccount.com --scopes=https://www.googleapis.com/auth/cloud-platform --tags=http-server,https-server --image=padrao --image-project=durable-matter-281714 --boot-disk-size=10GB --boot-disk-type=pd-standard --boot-disk-device-name={name} --no-shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring --reservation-affinity=any')
        system(f"gcloud compute ssh {name} --zone us-central1-a")
        system("cd iqbot")
        system("chmod 777 setup.sh")
        system("./setup.sh")
        system("exit")
        
        self.instancias.append(Instancia(name))

    def iniciar_bot(self, instancia, email, senha):
        '''
        Inicia o bot para determinado email/senha na instância
        params:
            email: string com e-mail do usuario
            senha: string com a senha do usuario
        return:
            None
        '''
        instancia.set_people(email)
        system(f"gcloud compute ssh {instancia.name} --zone us-central1-a")
        system("cd iqbot")
        system(f"screen -S {email} -dm python3 bot.py -o {email} {senha}")
        system("exit")
    
    def deletar_instancias(self):
        '''
        Deleta todas as instâncias deixando apenas a original
        '''
        for instancia in self.instancias:
            system(f'yes "Y" | gcloud compute instances delete {instancia.name}')
        self.instancias = []
        self.criar_instancia()
        