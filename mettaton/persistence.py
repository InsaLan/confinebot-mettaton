"""Persistence module"""

import json
import logging
import os

from docker.errors import NotFound

from .errors import SaveStateParseError

log = logging.getLogger('mettaton.persistence')

def save_state(path: str, meta: "Mettaton"):
    """
    Save the state of the provided `Mettaton` object to a file
    which path is provided as first argument.
    """
    # TODO: Check filesystem

    with open(path, "w") as fptr:
        dct_data = {}
        dct_data['servers'] = list(meta.clients.keys())
        dct_data['instances'] = {k: h for (k, (h, _)) in meta.instances.items()}
        json.dump(dct_data, fptr)

def load_state(path: str, meta: "Mettaton") -> bool:
    """
    Load a state for the manager object from a given file path
    """

    with open(path, "r") as fptr:
        try:
            dct_data = json.load(fptr)
        except json.decoder.JSONDecodeError:
            raise SaveStateParseError()
    return dct_data

    meta.build_connections(dct_data['servers'])
    meta.instances_lock.acquire()
    for key, host in dct_data['instances'].items():
        if not host in meta.clients:
            log.error("Host %s for instance %s is not connected. Instance is lost.", host, key)
            continue
        conn = meta.clients[host]
        container = None
        try:
            container = conn.containers.get(key)
        except NotFound as error:
            log.error("ERROR: Server %s in persistence no longer found in docker daemon", key)
        if container is not None:
            meta.instances[key] = (host, container)
        # TODO don't fail silently

    meta.instances_lock.release()
    return True

def discard_state(path: str):
    """
    Discard a save state at location `path`.
    Essentially a glorified alias for `os.remove`.remove
    """
    os.remove(path)
