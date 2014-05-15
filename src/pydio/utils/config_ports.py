# Get needed open ports on the system and save it to a config file that will be used to
# sync the client/UI connection ports

class PortsDetector():

    def __init__(self, store_file):
        self.store = store_file

    def get_open_port(self, socket_name):
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("",0))
            s.listen(1)
            port = s.getsockname()[1]
            s.close()
            self.save_config(socket_name, port)
            return port

    def create_config_file(self):
        with open(self.store, 'w') as config_file:
            config_file.write("Pydio port config file \n")


    def save_config(self, socket_name, port_to_save):
        with open(self.store, 'a') as config_file:
            config_file.write(socket_name + ':' + str(port_to_save) + "\n")