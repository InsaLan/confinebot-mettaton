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

from .utils import *   # Various utilities
from .persistence import save_state, load_state, discard_state

class Mettaton:
    """Mettaton, the friendly(?) server deployment manager"""
    def __init__(self, cluster_config = {}, nfp = 5000, storage_path="/tmp/mettaton.state"):
        """Initialize a Mettaton client.
        This will not perform the connection to the local docker
        client automatically. This is your own responsability to
        do with Mettaton.connect
        """
        # Is the manager connected?
        self.connected = False

        # Client object to Docker Daemon
        self.client = None

        # Node identifier returned when creating/connecting
        # To the swarm
        self.raw_object = None

        # A list of gaps in the list of ports available
        self.available_ports = []

        # The next known free port after which none are taken
        self.next_free_port = nfp

        # List of currently deployed servers
        self.servers = {}

        # Worker token to add servers to the swarm
        self.worker_token = None

        # The logger
        self.logger = logging.getLogger("mettaton")
        self.logger.info("Built Mettaton")

        # The configuration for the cluster
        self.config = cluster_config

        # Path to persistent state storage
        self.storage_path = storage_path

    def is_connected(self):
        """Is the manager connected?"""
        return self.connected

    def connect(self):
        """Connect mettaton to the local environment docker client"""
        try:
            self.client = docker.from_env()
        except DockerException as e:
            # TODO: Change this to have explicit errors
            raise produce_appropriate_exception(e)
        else:
            self.logger.info("Connected to Docker Daemon")
            self.connected = True
        # TODO: This could fail, figure out all the ways it could
        # and report them

    def start_new_cluster(self):
        """Start the Mettaton cluster, yielding the key that lets you connected to it"""
        self.logger.debug("Initializing cluster...")
        try:
            self.client.swarm.init(**self.config)
        except APIError as e:
            raise produce_appropriate_exception(e)

        self._update_post_join_info()
        self.logger.info("Initialized cluster successfully: %s", self.raw_object.get('ID'))
        self.save_state()

    def save_state(self):
        """Save current state to persistent storage"""
        self.logger.info("Saving state to storage...")
        try:
            save_state(self.storage_path, self)
        except Exception as e:
            self.logger.error("%s", e)
        else:
            self.logger.info("Success")

    def load_state(self):
        """Load a previous state from persistent storage"""
        self.logger.info("Reloading older state from persistent storage")
        try:
            load_state(self.storage_path, self)
        except RuntimeError as error:
            self.logger.error("Could not load state: %s", error)
        except FileNotFoundError as error:
            self.logger.error("No previous state found. Saving.")
            self.save_state()
        else:
            self.logger.info("Successfully reloaded state")

    def regain_cluster(self):
        """Regain control over an existing cluster"""
        self.logger.info("Reloading cluster information...")
        try:
            self.client.swarm.reload()
        except APIError as error:
            raise produce_appropriate_exception(error)
        self._update_post_join_info()
        self.logger.info("Regained cluster successfully (swam id %s)", self.raw_object.get('ID'))
        self.load_state()

    def _update_post_join_info(self):
        """Update and display vital information after successfully
        connecting to/creating a swarm"""
        self.raw_object = self.client.swarm.attrs
        self.worker_token = self.raw_object.get("JoinTokens", {}).get("Worker")
        self.logger.info("Worker join token is " + str(self.worker_token))

    def shutdown(self, force=False):
        if not self.connected:
            raise RuntimeError("Not running")
        if not self.raw_object:
            raise RuntimeError("Cluster Not Started")
        ret_status = self.client.swarm.leave(force=force)
        if ret_status:
            self.logger.info("Successfully left the cluster")
        else:
            self.logger.error("Failure to leave the cluster")

        # Destroy on-disk state
        try:
            discard_state(self.storage_path)
        except IOError:
            self.logger.error("I/O error during state removal")
        except FileNotFoundError:
            pass
        else:
            self.logger.info("Successfully destroyed stale state")
        return ret_status

    def get_worker_token(self):
        """Return the worker token needed by servers to join the cluster"""
        return self.worker_token

    def _find_next_free_port(self):
        """Obtain the next free port in our range"""
        if len(self.available_ports) == 0:
            self.next_free_port += 1
            return self.next_free_port
        port = self.available_ports.pop(0)
        return port

    def launch_server(self, image, exposition_port = 80,
            server = None, port = None,
            **kwargs):
        """Deploy a server somewhere in the cluster"""
        # TODO: Check validity of arguments
        identifier = generate_identifier()
        # The collision probability is very small
        while self.servers.get(identifier):
            identifier = generate_identifier()

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
            port = self._find_next_free_port()
        else:
            # Just in case someone wants to be a trickster and sends us
            # a port that is not a string but parses as an int
            port = int(port)
            # No, I will not catch the resulting exception. If someone
            # does garbage with this module they might as well own up
            # to it
            if port in self.available_ports:
                self.available_ports.remove(port)
            elif port == self.next_free_port:
                self.next_free_port += 1
        port_dict = {}
        port_dict[port] = int(exposition_port)
        epspec = EndpointSpec(ports = port_dict)
        # Create its endpoint specifications
        kwargs["maxreplicas"] = 1

        kwargs["name"] = "server-" + str(identifier)
        self.logger.info("Launching image '%s' called %s (ports=%s, constraints=%s)", image, kwargs["name"], port_dict, constraint)

        try:
            self.servers[identifier] = self.client.services.create(image,
                    constraints = constraint,
                    endpoint_spec = epspec,
                    **kwargs).id
        except APIError as error:
            raise produce_appropriate_exception(error)

        self.save_state()
