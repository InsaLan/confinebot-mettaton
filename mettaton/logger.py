"""Logging utility"""

# External import
import logging

def init_logger():
    """Initialize the general logger."""
    # Configure the logger
    logger = logging.getLogger("mettaton")

    # Creates a handler for proper formatting
    # it takes any message that arrives to the main Astatine logger
    # and formats them
    globalfilehandler = logging.FileHandler("/tmp/mettaton.log")
    globalstreamhandler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s][%(name)-10s][%(levelname)-8s]"
        +"(%(filename)s::%(funcName)s::%(lineno)s) %(message)s")
    globalstreamhandler.setFormatter(formatter)
    globalfilehandler.setFormatter(formatter)
    logger.addHandler(globalfilehandler)
    logger.addHandler(globalstreamhandler)
    logger = logging.getLogger("mettaton")
    logger.setLevel(logging.INFO)

    logger.debug("Initialized logger")