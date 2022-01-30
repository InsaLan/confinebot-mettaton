"""Various error types"""

class SaveStateParseError(RuntimeError):
    """The save state file has is invalid JSON"""
    pass

class ContainerNameAlreadyInuse(RuntimeError):
    """The name for a container we are trying to create is already used by another one"""
    pass

class DockerConnectSSLWrongVersionNumber(RuntimeError):
    """
    Connection to the Docker socket via SSL failed,
    most likely from your client trying to connect
    with SSL when the server doesn't handle it
    """
    pass

class DockerNetworkPortAlreadyAllocated(RuntimeError):
    """
    The network ports being used for forward are already being
    forwarded for another docker container
    """
    pass

class NoHostAvailable(RuntimeError):
    """
    We tried to deploy a container, but we are not connected to any host
    """
    pass
