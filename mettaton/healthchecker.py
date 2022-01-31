"""
Health Checker Mechanism
Module containing logic to check the state of a docker container
"""

import docker   # engine
import logging  # logging library
import time     # To check check cycle duration
# Errors from docker's library
from docker.errors import DockerException, APIError, NotFound
from docker.types.services import EndpointSpec
from docker.types import ServiceMode, Placement

from .utils import *    # Various utilities
from .errors import *   # All of our error types
from .persistence import save_state, load_state, discard_state

from threading import Thread, Lock
from queue import Queue, Empty

class HealthChecker(Thread):
    """
    The Health Checker is the thread that runs alongside a Mettaton object
    in order to verify
    """
    def __init__(self, connections: list[docker.DockerClient]):
        """
        Initialization of a `HealthChecker` object requires nothing more than
        a list of initial `DockerClient` objects.
        """
        Thread.__init__(self)
        self.o_queue = Queue()
        self.clients = connections.copy()
        self.clients_lock = Lock()
        self.watch_for_list = []
        self.watch_for_lock = Lock()
        self.running = False
        self.last_known = {}
        self.logger = logging.getLogger("mettaton.nurse")
        self.logger.info("Built nurse healthchecker")

    def shutdown(self):
        """
        Shut the health checker down, and send the final
        notification message (i.e. "None")
        """
        # Final shutdown message
        self.o_queue.put(None)

    def get_event_queue(self) -> Queue:
        """
        Return the event queue to which the Health Checker posts.
        """
        return self.o_queue

    def add_connection(self, endpoint: str, client: docker.DockerClient):
        """
        Add a connection to a Docker daemon, given the provided `endpoint` (str)
        and `DockerClient` client object.
        """
        self.clients_lock.acquire()
        self.clients[endpoint] = client
        self.clients_lock.release()
        self.logger.info("Added connection to %s", endpoint)

    def disconnect(self, endpoint: str):
        """
        Disconnect from the provided endpoint.
        """
        self.clients_lock.acquire()
        try:
            del self.clients[endpoint]
        except KeyError:
            self.logger.warning("HealthChecker did not have a connection to %s", endpoint)
        self.clients_lock.release()
        self.logger.info("Disconnected from %s", endpoint)

    def watch_for(self, endpoint: str, ident: str) -> bool:
        """
        Add references to a container at `endpoint` with ID `ident` which state
        needs to be watched.
        Returns True if all went well.
        """
        self.watch_for_lock.acquire()
        if not (endpoint, ident) in self.watch_for_list:
            self.logger.info("Now watching for %s / %s", endpoint, ident)
            self.watch_for_list.append((endpoint, ident))
        self.watch_for_lock.release()
        return True

    def unwatch_for(self, endpoint: str, ident: str) -> bool:
        """
        Tells the Health Checker to stop watching for the container `ident` at endpoint `endpoint`.
        Returns True if all went well, False if the specified container was not being watched.
        """
        self.watch_for_lock.acquire()
        if not (endpoint, ident) in self.watch_for_list:
            return False
        self.logger.info("No longer watching for %s / %s", endpoint, ident)
        self.watch_for_list.remove((endpoint, ident))
        self.watch_for_lock.release()
        return True

    def start(self):
        """
        Start the Health Checker thread.
        """
        Thread.start(self)
        self.running = True

    def stop(self):
        """
        Stop the Health Checker thread.
        """
        self.running = False

    def check_container(self, endpoint: str, ident: str):
        """
        Internal method used by the Health Checker to check for the health of a specific
        container at `endpoint` with identifier `ident`. The health status is obtained from
        the attributes of the retrieved container object, which contains a key
        ['State']['Health']['Status'].

        The values can be "starting", "healthy", "unhealthy", and so on. "UNKNOWN" is another state
        that can be returned when the health checker loses an endpoint. "NOT_FOUND" is a similar state
        that does not exist within docker but is returned when the health checker still has the
        associated endpoint for a container, but cannot find it there anymore.

        Updates are only sent when the state of a container changes.

        The status retrieved here is shoved into the event queue as the second element of a tuple
        which first element is the combination `(endpoint, ident)` describing the container.
        """
        container = None
        self.clients_lock.acquire()
        conn = self.clients.get(endpoint)
        watch = (endpoint, ident)
        if conn is None and self.last_known[watch]:
            self.last_known[watch] = "UNKNOWN"
            self.o_queue.put((watch, "UNKNOWN"))
            self.clients_lock.release()
            return

        # With the connection we have, try and
        # Get the container
        try:
            container = conn.containers.get(ident)
        except NotFound:
            container = None

        # Potentially raise an alert
        if container is None:
            if self.last_known.get(ident, "UNKNOWN") != "NOT_FOUND":
                self.last_known[ident] = "NOT_FOUND"
                self.o_queue.put((ident, "NOT_FOUND"))
            self.clients_lock.release()
            return

        status = container.attrs['State']['Health']['Status']
        if self.last_known.get(ident, "UNKNOWN") != status:
            self.last_known[ident] = status
            self.o_queue.put((ident, status))
        self.clients_lock.release()

    def run(self):
        """
        Mail loop.

        Handles triggering the check for every watched container.
        If the check cycle takes longer than a full second, do not wait.
        Otherwise, wait until a full second has elapsed since the loop began.
        """
        self.logger.info("Health check loop begins")
        while self.running:
            now = time.time()
            self.watch_for_lock.acquire()
            for (endpoint, ident) in self.watch_for_list:
                self.check_container(endpoint, ident)
            self.watch_for_lock.release()
            cycle = time.time() - now
            time.sleep(0 if cycle > 1 else 1 - cycle)
        self.shutdown()
