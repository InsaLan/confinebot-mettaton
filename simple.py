"""A really simple test script"""
from mettaton import Mettaton
import time

def main():
    d = Mettaton({
        "advertise_addr": "10.8.2.135",
    })
    d.connect()
    try:
        d.start_new_cluster()
    except RuntimeError:
        d.regain_cluster()

    # Start a simple http server
    d.launch_server(str(int(time.time())%86400), "nginx")

    #d.destroy_cluster(force=True)

if __name__ == "__main__":
    main()
