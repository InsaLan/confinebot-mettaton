"""Persistence module"""

import json
import logging
import os

from docker.errors import NotFound

from .errors import SaveStateParseError

log = logging.getLogger('mettaton.persistence')

def save_state(path: str, meta):
    # TODO: Check filesystem

    with open(path, "w") as fptr:
        dct_data = {}
        dct_data['servers'] = list(meta.clients.keys())
        dct_data['instances'] = {k: h for (k, (h, _)) in meta.instances.items()}
        json.dump(dct_data, fptr)

def load_state(path: str, meta):
    """Load a state for the manager object from a given file path"""

    with open(path, "r") as fptr:
        try:
            dct_data = json.load(fptr)
        except json.decoder.JSONDecodeError:
            raise SaveStateParseError()

    meta.build_connections(dct_data['servers'])
    for key, host in dct_data['instances'].items():
        conn = meta.clients[host]
        container = None
        try:
            container = conn.containers.get(key)
        except NotFound as error:
            log.error("ERROR: Server %s in persistence no longer found in docker daemon", key)
        if container is not None:
            meta.instances[key] = (host, container)
        # TODO don't fail silently
    #meta.config = dct_data['config']
    return True

def discard_state(path: str):
    os.remove(path)
