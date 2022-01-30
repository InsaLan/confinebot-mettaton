"""A really simple test script"""
from mettaton import Mettaton
import time
import random
import threading
import queue

def health_watch(stream):
    while True:
        s = None
        try:
            s = stream.get_nowait()
        except queue.Empty:
            time.sleep(1)
            continue
        if s is None:
            break
        print("MESSAGE", s)

def main():
    # A connection through TCP with SSL certificates :
    #d = Mettaton(["tcp://127.0.0.1:2376"], tls_params={
    #    "ca_cert": "certs/ca/ca.pem",
    #    "client_cert": ["certs/my_host/client/cert.pem", "certs/my_host/client/key.pem"]
    #    })

    # A connection through the usual socket
    d = Mettaton(["unix:///var/run/docker.sock"])

    mc_nbr = random.randrange(0, 1000)
    host, ident = d.start_server("itzg/minecraft-server:latest", f"mc-{mc_nbr:04d}", environment = {
        "TYPE": "FABRIC",
        "EULA": True,
        "SERVER_PORT": 25565,
        "SERVER_NAME": "A simple minecraft server",
        "MOTD": "This is an attempt at deploying a minecraft server"
        }, port_config = {"25565/udp": 25569, "25565/tcp": 25569})
    print("Connection List:", d.get_server_list())
    print("Instance List:", d.get_instance_list())
    time.sleep(5)
    print("Log output:")
    print(d.get_logs(ident, stream=True))
    print(d.get_status(ident))
    stream = d.subscribe()
    th = threading.Thread(target=health_watch,args=(stream,))
    th.start()
    input("Waiting for ENTER to shut down...")
    try:
        d.shutdown_server(ident)
    except:
        # We don't care that much tbf
        pass
    d.shutdown()
    th.join()

if __name__ == "__main__":
    main()
