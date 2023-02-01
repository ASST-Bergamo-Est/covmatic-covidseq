import logging

__version__ = "0.0.1"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s,%(msecs)03d %(name)-12s %(levelname)-8s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)