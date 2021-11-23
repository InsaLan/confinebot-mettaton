"""
Mettaton, the simple wrapper around the Python Docker
Library's Swarm Engine for Game Server Cluster Management
"""
import docker   # engine
import logging  # logging library
# Errors from docker's library
from docker.errors import DockerException, APIError
from docker.types.services import EndpointSpec
from docker.types import ServiceMode, Placement

class Mettaton:
    def __init__(self, cluster_config = {}, nfp = 5000):
        """Initialize a Mettaton client.
        This will not perform the connection to the local docker
        client automatically. This is your own responsability to
        do with Mettaton.connect
        """
        # Is the manager connected?
        self.connected = False
        # 
        self.client = None
        self.cluster = None
        self.available_ports = []
        self.next_free_port = nfp
        self.servers = {}
        self.worker_token = None
        self.logger = logging.getLogger("mettaton")
        self.logger.info("Built Mettaton")
        self.config = cluster_config

    def is_connected(self):
        """Is the manager connected?"""
        return self.connected
    
    def connect(self):
        """Connect mettaton to the local environment docker client"""
        try:
            self.client = docker.from_env()
        except DockerException as e:
            raise RuntimeError(str(e))
        else:
            self.logger.info("Connected to Docker Daemon")
            self.connected = True
        # TODO: This could fail, figure out all the ways it could
        # and report them
    
    def start_new_cluster(self):
        """Start the Mettaton cluster, yielding the key that lets you connected to it"""
        self.logger.debug("Initializing cluster...")
        try:
            self.cluster = self.client.swarm.init(**self.config)
        except APIError as e:
            raise RuntimeError("API Error while swarm initialized : " + str(e))
        self.logger.info("Initialized cluster successfully")
        self._update_post_join_info()

    def regain_cluster(self):
        """Regain control over an existing cluster"""
        self.logger.info("Reloading cluster information...")
        self.cluster = self.client.swarm.reload()
        self.logger.info("Regained cluster successfully")
        self._update_post_join_info()

    def _update_post_join_info(self):
        """Update and display vital information after successfully 
        connecting to/creating a swarm"""
        self.cluster = self.client.swarm
        self.worker_token = self.cluster.attrs.get("JoinTokens", {}).get("Worker")
        self.logger.info("Worker join token is " + str(self.worker_token))

    def destroy_cluster(self, force=False):
        if not self.connected:
            raise RuntimeError("Not running")
        if not self.cluster:
            raise RuntimeError("Cluster Not Started")
        ret_status = self.cluster.leave(force=force)
        if ret_status:
            self.logger.info("Successfully left the cluster")
        else:
            self.logger.error("Failure to leave the cluster")
        return ret_status
    
    def get_worker_token(self):
        """Return the worker token needed by servers to join the cluster"""
        return self.worker_token

    def launch_server(self, identifier, image, exposition_port = 80,
            server = None, port = None,
            **kwargs):
        """Deploy a server somewhere in the cluster"""
        # TODO Check validity of arguments
        # TODO Check collision
        # Create a service
        # That service will be one replica
        mode = ServiceMode("replicated", replicas=1)
        # If we are given a host, constraint ourselves to it
        constraint = []
        if server is not None:
            constraint = ["node.ip=={}".format(server)]
        # Published in host mode on a port we either generate
        # or we are given
        if port is None:
            # Assign the next free port by default
            port = self.next_free_port
            if len(self.available_ports) > 0:
                # If a port was made available, take it
                port = self.available_ports.pop(0)
            else:
                # Otherwise, increase the next free port
                self.next_free_port += 1
        port = int(port)
        port_dict = {}
        port_dict[port] = int(exposition_port)
        epspec = EndpointSpec(ports = port_dict)
        # Create its endpoint specifications
        kwargs["maxreplicas"] = 1

        kwargs["name"] = "server-" + str(identifier)
        self.logger.info("Launching image '{}' called {} (ports={}, constraints={})"
                .format(image, kwargs["name"], port_dict, constraint))

        self.servers[identifier] = self.client.services.create(image,
                constraints = constraint,
                endpoint_spec = epspec,
                **kwargs)
