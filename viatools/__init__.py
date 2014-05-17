from .version import __version__
import os

# Load configuration
import ConfigParser
config = ConfigParser.ConfigParser()
config.readfp(open(os.path.join(os.path.dirname(__file__), "conf/via.conf")))

# Logging
import logging.config
logging.config.fileConfig(os.path.join(os.path.dirname(__file__),'conf/logging.conf'))
