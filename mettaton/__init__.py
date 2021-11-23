__version__ = "0.0.0"

# Mechanism to initialize the logger
from .logger import init_logger
init_logger()

# Expose the class
from .mettaton import Mettaton