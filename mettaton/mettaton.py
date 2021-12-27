"""
Mettaton, the simple wrapper around the Python Docker
Library's Engine for Game Server Cluster Management
"""
import docker   # engine
import logging  # logging library
# Errors from docker's library
from docker.errors import DockerException, APIError
from docker.types.services import EndpointSpec
from docker.types import ServiceMode, Placement

from .utils import *    # Various utilities
from .errors import *   # All of our error types
from .persistence import save_state, load_state, discard_state

import urllib3
# I understand the risks
urllib3.disable_warnings()

import random

class Mettaton:
    """Mettaton, the friendly(?) server deployment manager"""
    def __init__(self, servers_ips, tls_params={}, storage_path="/tmp/mettaton.state"):
        """Initialize a Mettaton client.
        This will not perform the connection to the local docker
        client automatically. This is your own responsability to
        do with Mettaton.connect
        """
        # The logger
        self.logger = logging.getLogger("mettaton")
        self.logger.info("Built Mettaton")

        # Path to persistent state storage
        self.storage_path = storage_path

        # TLS certificate parameters
        self.tls_params = docker.tls.TLSConfig(
                ca_cert=tls_params["ca_cert"],
                client_cert=tls_params["client_cert"]
        )

        # Docker container instances
        self.instances = {}

        # Attempt to load previous state
        if self.load_state():
            return # no need to go further

        # If that didn't work, build connections
        # Client connections to the given server ips
        self.build_connections(servers_ips)

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
            return load_state(self.storage_path, self)
        except SaveStateParseError:
            self.logger.error("Unable to parse saved state")
        except RuntimeError as error:
            self.logger.error("Could not load state: %s", error)
        except FileNotFoundError as error:
            self.logger.error("No previous state found. Saving.")
            self.save_state()
        else:
            self.logger.info("Successfully reloaded state")

    def build_connections(self, ip_list):
        """Build the dictionary of known connections from the given IP list"""
        self.clients = {}
        for ip_addr in ip_list:
            client = docker.DockerClient(base_url="tcp://{}".format(ip_addr), tls=self.tls_params)
            self.logger.info("Successful initial connection to %s", ip_addr)
            self.clients[ip_addr] = client

    def start_server(self, image, name, environment={}, port_config={}, host=None):
        """Start a game server somewhere in one of our managed connections"""
        # If a host is provided, use it
        if host is not None:
            if not host in self.clients:
                raise RuntimeError("Attempting connection to unknown client {}".format(host))
        else:
            # TODO: could be empty
            host = random.choice(list(self.clients.keys()))

        client = self.clients[host]

        try:
            container = client.containers.run(
                    image,
                    detach = True,
                    name = name,
                    restart_policy = { "Name": "always" },
                    network_mode = "bridge",
                    ports = port_config,
                    environment = environment)
        except APIError as e:
            appropriate_error = produce_appropriate_exception(e)
            self.logger.error("%s", appropriate_error)
            raise appropriate_error

        # Save the container
        self.instances[container.id] = (host, container)
        self.logger.info("Successful creation of docker %s named %s (image %s)", container.id, name, image)

        self.save_state()

        return host, container.id

    def get_server_list(self):
        # Return a list of the servers we are connected to
        return list(self.clients.keys())

    def get_instance_list(self):
        # Return a list of instances we have launched
        return list(self.instances.keys())
    
    def get_logs(self, instance_id, **kwargs):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        return container.logs(**kwargs)

    def get_log_stream(self, instance_id, **kwargs):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        return container.logs(stream=True, **kwargs)


    def get_status(self, instance_id):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        container.update()
        return container.status

    def shutdown_server(self, instance_id):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        container.stop()
        self.logger.info("Stopped container %s on %s", instance_id, host)
        container.remove()
        self.logger.info("Removed container %s on %s", instance_id, host)
        self.save_state()
