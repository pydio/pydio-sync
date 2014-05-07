# Get needed open ports on the system and save it to a config file that will be used to
# sync the client/UI connection ports

def get_open_port(socket_name):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        save_config(socket_name, port)
        return port

def create_config_file():
    with open('pydio_port_config', 'w') as config_file:
        config_file.write("Pydio port config file \n")

def save_config(socket_name, port_to_save):
    with open('pydio_port_config', 'a') as config_file:
        config_file.write(socket_name + ':' + str(port_to_save) + "\n")