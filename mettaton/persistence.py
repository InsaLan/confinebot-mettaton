"""Persistence module"""

import json
import logging
import os

log = logging.getLogger('mettaton.persistence')

def save_state(path: str, meta):
    # TODO: Check filesystem

    if meta.raw_object is None:
        raise RuntimeError("You should not save a dead robot!")

    cluster_id = meta.raw_object.get('ID')
    with open(path, "w") as fptr:
        dct_data = {}
        dct_data['cluster_id'] = cluster_id
        dct_data['registry'] = meta.servers
        dct_data['available_ports'] = meta.available_ports
        dct_data['next_free_port'] = meta.next_free_port
        dct_data['worker_token'] = meta.worker_token
        dct_data['config'] = meta.config

        json.dump(dct_data, fptr)

def load_state(path: str, meta):
    """Load a state for the manager object from a given file path"""
    if meta.raw_object is None:
        raise RuntimeError("You should only restore after regaining the cluster")

    with open(path, "r") as fptr:
        dct_data = json.load(fptr)
    if meta.raw_object.get('ID') != dct_data.get('cluster_id'):
        log.error("Ignoring order to reload state : ID mismatch " +
                "indicates cluster change; not overwriting metatton " +
                "config with file")

    meta.servers = dct_data['registry']
    meta.available_ports = dct_data['available_ports']
    meta.next_free_port = dct_data['next_free_port']
    meta.worker_token = dct_data['worker_token']
    #meta.config = dct_data['config']

def discard_state(path: str):
    os.remove(path)
