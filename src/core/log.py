import sys
import logging

logger = logging.getLogger("ai-status")
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(_handler)
logger.setLevel(logging.WARNING)
