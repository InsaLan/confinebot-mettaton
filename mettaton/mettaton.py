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
from requests.exceptions import SSLError

from .utils import *    # Various utilities
from .errors import *   # All of our error types
from .persistence import save_state, load_state, discard_state
from .healthchecker import HealthChecker

import urllib3
# I understand the risks
urllib3.disable_warnings()

import random
from threading import Thread
from queue import Queue

class Mettaton:
    """Mettaton, the friendly(?) server deployment manager"""
    def __init__(self, servers_ips, tls_params={}, storage_path="/tmp/mettaton.state"):
        """Initialize a Mettaton client.
        This will not perform the connection to the local docker
        client automatically. This is your own responsability to
        do with Mettaton.connect
        """
        # Valid state?
        self.valid = True

        # The logger
        self.logger = logging.getLogger("mettaton")

        # Path to persistent state storage
        self.storage_path = storage_path

        # TLS certificate parameters
        self.tls_params = None
        if tls_params is not None and tls_params.get("ca_cert") and tls_params.get("client_cert"):
            self.tls_params = docker.tls.TLSConfig(
                ca_cert=tls_params.get("ca_cert"),
                client_cert=tls_params.get("client_cert")
            )

        # Docker container instances
        self.instances = {}
        # Docker connections
        self.clients = {}

        # Nurse/Health Watch daemon
        self.nurse = HealthChecker(self.clients)
        self.event_queue = self.nurse.get_event_queue()
        self.nurse.start()
        self.logger.info("Built Mettaton")

        # Attempt to load previous state
        self.load_state()

        # Build any additional connection that's provided to us
        self.build_connections(servers_ips)

    def __del__(self):
        if self.valid:
            self.shutdown()

    def disconnect_from_endpoint(self, endpoint: str) -> bool:
        if endpoint in self.clients:
            self.clients[endpoint].close()
            del self.clients[endpoint]
            self.nurse.disconnect(endpoint)

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

    def build_connections(self, endpoint_list):
        """Build the dictionary of known connections from the given IP list"""
        for endpoint in endpoint_list:
            if endpoint in self.clients:
                self.logger.info("Not renewing connection to endpoint %s", endpoint)
                continue
            try:
                client = docker.DockerClient(
                        base_url=format(endpoint),
                        tls=self.tls_params
                )
            except DockerException as error:
                self.logger.fatal("Fatal error when initializing Docker daemon connection to %s : %s", endpoint, error)
                raise produce_appropriate_exception(error) from None
            self.logger.info("Successful initial connection to %s", endpoint)
            self.clients[endpoint] = client
            self.nurse.add_connection(endpoint, client)

    def start_server(self, image, name, environment={}, port_config={}, host=None):
        """Start a game server somewhere in one of our managed connections"""
        # If a host is provided, use it
        if host is not None:
            if not host in self.clients:
                raise RuntimeError("Attempting connection to unknown client {}".format(host)) from None
        else:
            if len(self.clients.keys()) == 0:
                raise NoHostAvailable("No host available to deploy right now")
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
            raise appropriate_error from None

        # Save the container
        self.instances[container.id] = (host, container)
        self.logger.info("Successful creation of docker %s named %s (image %s)", container.id, name, image)

        self.save_state()
        # Tell the nurse to check on them
        self.nurse.watch_for(host, container.id)

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

    def subscribe(self):
        """
        Subscribe to a Queue of events that will come from the watcher
        daemon
        """
        return self.event_queue

    def shutdown(self):
        """Shut mettaton down"""
        # Destroy the healthwatcher
        self.nurse.stop()
        self.nurse.join()
        # Destroy the connections
        old_clients = self.clients.copy()
        for endpoint in old_clients:
            self.disconnect_from_endpoint(endpoint)
        self.clients.clear()
        self.logger.info("Destroyed mettaton. Bye bye.")
        self.valid = False

    def shutdown_server(self, instance_id):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        self.nurse.unwatch_for(host, instance_id)
        container.stop()
        self.logger.info("Stopped container %s on %s", instance_id, host)
        container.remove()
        del self.instances[instance_id]
        self.logger.info("Removed container %s on %s", instance_id, host)
        self.save_state()
