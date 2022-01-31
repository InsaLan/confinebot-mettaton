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
from threading import Thread, Lock
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
        self.valid_lock = Lock()
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
        self.instances_lock = Lock()
        self.instances = {}
        # Docker connections
        self.clients_lock = Lock()
        self.clients = {}

        # Nurse/Health Watch daemon
        with self.clients_lock:
            self.nurse = HealthChecker(self.clients)
        self.event_queue = self.nurse.get_event_queue()
        self.nurse.start()
        self.logger.info("Built Mettaton")

        # Attempt to load previous state
        self.load_state()

        # Build any additional connection that's provided to us
        self.build_connections(servers_ips)

    def __del__(self):
        self.valid_lock.acquire()
        if self.valid:
            self.valid_lock.release()
            self.shutdown()
            self.valid_lock.acquire()
        self.valid_lock.release()

    def disconnect_from_endpoint(self, endpoint: str) -> bool:
        self.clients_lock.acquire()
        if endpoint in self.clients:
            self.instances_lock.acquire()
            for instance_id in self.instances:
                host, container = self.instances[instance_id]
                if host == endpoint:
                    self.instances_lock.release()
                    self.shutdown_server(instance_id)
                    self.instances_lock.acquire()
            self.instances_lock.release()
            self.clients[endpoint].close()
            del self.clients[endpoint]
            self.nurse.disconnect(endpoint)
        self.clients_lock.release()

    def save_state(self):
        """Save current state to persistent storage"""
        self.logger.info("Saving state to storage...")
        try:
            self.clients_lock.acquire()
            self.instances_lock.acquire()
            save_state(self.storage_path, self)
            self.instances_lock.release()
            self.clients_lock.release()
        except Exception as e:
            self.logger.error("%s", e)
        else:
            self.logger.info("Success")

    def load_state(self):
        """Load a previous state from persistent storage"""
        self.logger.info("Reloading older state from persistent storage")
        try:
            # No locks because they're acquired by the methods that
            # Need them and are called internally by `load_state`
            cur_state_res = load_state(self.storage_path, self)
            return cur_state_res
        except SaveStateParseError:
            self.logger.error("Unable to parse saved state")
        except RuntimeError as error:
            self.logger.error("Could not load state: %s", error)
        except FileNotFoundError as error:
            self.logger.error("No previous state found. Saving.")
            self.clients_lock.acquire()
            self.instances_lock.acquire()
            self.save_state()
            self.clients_lock.release()
            self.instances_lock.release()
        else:
            self.logger.info("Successfully reloaded state")

    def build_connections(self, endpoint_list):
        """Build the dictionary of known connections from the given IP list"""
        self.clients_lock.acquire()
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
                self.clients_lock.release()
                raise produce_appropriate_exception(error) from None
            self.logger.info("Successful initial connection to %s", endpoint)
            self.clients[endpoint] = client
            self.nurse.add_connection(endpoint, client)
        self.clients_lock.release()

    def start_server(self, image, name, environment={}, port_config={}, host=None):
        """Start a game server somewhere in one of our managed connections"""
        # If a host is provided, use it
        self.clients_lock.acquire()
        if host is not None:
            if not host in self.clients:
                self.clients_lock.release()
                raise RuntimeError("Attempting connection to unknown client {}".format(host)) from None
        else:
            if len(self.clients.keys()) == 0:
                self.clients_lock.release()
                raise NoHostAvailable("No host available to deploy right now")
            host = random.choice(list(self.clients.keys()))

        client = self.clients[host]
        self.clients_lock.release()

        self.instances_lock.acquire()
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
            self.instances_lock.release()
            raise appropriate_error from None

        # Save the container
        self.instances[container.id] = (host, container)
        self.logger.info("Successful creation of docker %s named %s (image %s)", container.id, name, image)
        self.instances_lock.release()

        self.save_state()
        # Tell the nurse to check on them
        self.nurse.watch_for(host, container.id)

        return host, container.id

    def get_server_list(self):
        # Return a list of the servers we are connected to
        with self.clients_lock:
            return list(self.clients.keys())

    def get_instance_list(self):
        # Return a list of instances we have launched
        with self.instances_lock:
            return list(self.instances.keys())
    
    def get_logs(self, instance_id, **kwargs):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        self.instances_lock.acquire()
        host, container = self.instances[instance_id]
        self.instances_lock.release()
        return container.logs(**kwargs)

    def get_log_stream(self, instance_id, **kwargs):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        self.instances_lock.acquire()
        host, container = self.instances[instance_id]
        self.instances_lock.release()
        return container.logs(stream=True, **kwargs)

    def get_status(self, instance_id):
        if not instance_id in self.instances:
            raise RuntimeError("No such instance known")

        self.instances_lock.acquire()
        host, container = self.instances[instance_id]
        container.update()
        self.instances_lock.release()
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
        self.clients_lock.acquire()
        old_clients = self.clients.copy()
        self.clients_lock.release()
        for endpoint in old_clients:
            self.disconnect_from_endpoint(endpoint)
        self.logger.info("Destroyed mettaton. Bye bye.")
        self.valid_lock.acquire()
        self.valid = False
        self.valid_lock.release()

    def shutdown_server(self, instance_id):
        self.instances_lock.acquire()
        instances_exist = instance_id in self.instances
        if not instances_exist:
            self.instances_lock.release()
            raise RuntimeError("No such instance known")

        host, container = self.instances[instance_id]
        self.nurse.unwatch_for(host, instance_id)
        container.stop()
        self.logger.info("Stopped container %s on %s", instance_id, host)
        container.remove()
        del self.instances[instance_id]
        self.logger.info("Removed container %s on %s", instance_id, host)
        self.instances_lock.release()
        self.save_state()
