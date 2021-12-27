"""A really simple test script"""
from mettaton import Mettaton
import time
import random

def main():
    d = Mettaton(["192.168.0.147:2376"], tls_params={
        "ca_cert": "/home/lymkwi/Programming/Gits/csgo-dockservers/certs/ca/ca.pem",
        "client_cert": ["/home/lymkwi/Programming/Gits/csgo-dockservers/certs/aries.limnas.ia/client/cert.pem", "/home/lymkwi/Programming/Gits/csgo-dockservers/certs/aries.limnas.ia/client/key.pem"]
        })

    host, ident = d.start_server("itzg/minecraft-server:latest", "mc-000", environment = {
        "TYPE": "FABRIC",
        "EULA": True,
        "SERVER_PORT": 25569,
        "SERVER_NAME": "ATTEMPT THREE",
        "MOTD": "This is the second run"
        }, port_config = {"25565": 25569})
    print(d.get_server_list())
    print(d.get_instance_list())
    time.sleep(5)
    print("Log output:")
    print(d.get_logs(ident, stream=True))
    print(d.get_status(ident))
    input()
    d.shutdown_server(ident)

    # Start a simple http server
if __name__ == "__main__":
    main()
