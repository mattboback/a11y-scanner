import logging
import sys


def setup_logging(level=logging.INFO):
    """Configure logging with a consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
