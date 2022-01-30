"""
Health Checker Mechanism
Module containing logic to check the state of a docker container
"""

import docker   # engine
import logging  # logging library
import time
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
    def __init__(self, connections):
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
        # Final shutdown message
        self.o_queue.put(None)

    def get_event_queue(self) -> Queue:
        return self.o_queue

    def add_connection(self, endpoint, client):
        self.clients_lock.acquire()
        self.clients[endpoint] = client
        self.clients_lock.release()
        self.logger.info("Added connection to %s", endpoint)

    def disconnect(self, endpoint):
        self.clients_lock.acquire()
        try:
            del self.clients[endpoint]
        except KeyError:
            self.logger.warning("HealthChecker did not have a connection to %s", endpoint)
        self.clients_lock.release()
        self.logger.info("Disconnected from %s", endpoint)

    def watch_for(self, endpoint: str, ident: str) -> bool:
        self.watch_for_lock.acquire()
        if not (endpoint, ident) in self.watch_for_list:
            self.logger.info("Now watching for %s / %s", endpoint, ident)
            self.watch_for_list.append((endpoint, ident))
        self.watch_for_lock.release()
        return True

    def unwatch_for(self, endpoint: str, ident: str) -> bool:
        self.watch_for_lock.acquire()
        if not (endpoint, ident) in self.watch_for_list:
            return False
        self.logger.info("No longer watching for %s / %s", endpoint, ident)
        self.watch_for_list.remove((endpoint, ident))
        self.watch_for_lock.release()
        return True

    def start(self):
        Thread.start(self)
        self.running = True

    def stop(self):
        self.running = False

    def check_container(self, endpoint, ident):
        container = None
        self.clients_lock.acquire()
        conn = self.clients.get(endpoint)
        watch = (endpoint, ident)
        if conn is None and self.last_known[()]:
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
