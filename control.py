from admin.controlador import *
import bottle, json

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

if __name__ == "__main__":
    controlador = Control()
    print(f"Server preparado para receber. na porta {SERVER_PORT}")
    bottle.run(host = "localhost", port = SERVER_PORT, debug = True)

