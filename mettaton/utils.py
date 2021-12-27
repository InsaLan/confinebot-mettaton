"""Utilities module"""

from os import urandom
from hashlib import sha256
from .errors import *

def produce_appropriate_exception(exc):
    string_representation = str(exc)
    if "Permission denied" in string_representation:
        return RuntimeError("Permission denied to access docker daemon")
    if "This node is not a swarm manager" in string_representation:
        return RuntimeError("Server is not manager of any node")
    if "name must be valid as a DNS name component" in string_representation:
        return RuntimeError("Generated ID somehow invalid domain name")
    if "to be able to reuse that name." in string_representation:
        return ContainerNameAlreadyInuse(exc)
    else:
        return RuntimeError(string_representation)

def generate_identifier():
    """Generate a random identifier for servers"""
    return sha256(urandom(18)).hexdigest()[:16]
