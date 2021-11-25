from admin.controlador import *

controlador = Control()
server = socket(AF_INET, SOCK_DGRAM)
server.bind(('', SERVER_PORT))
print(f"Server preparado para receber. na porta {SERVER_PORT}")

try:
    while True:
        message, address = server.recvfrom(2048)
        command, args, kwargs = get_command_and_args(message)
        if command == "add":
            funcao = controlador.adicionar_pessoa
        elif command == "stop":
            funcao = controlador.parar_operacao
        elif command == "log":
            funcao = controlador.pegar_log
        elif command == "delete":
            funcao = controlador.deletar_instancias
        elif command == "list":
            funcao = controlador.mostrar_usuarios
        elif command == "send":
            funcao = controlador.enviar_comando
        else:
            funcao = lambda *args, **kwargs: "Comando não reconhecido"
        try:
            server.sendto(json.dumps({
                "result": funcao(*args, **kwargs),
            }).encode(), address)
        except Exception as e: print(type(e), e)
except KeyboardInterrupt:
    server.close()
    controlador.deletar_instancias()