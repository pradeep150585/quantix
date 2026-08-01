import sys
from pathlib import Path
from loguru import logger
from config import get

def setup_logger():
    logger.remove()
    logger.add(sys.stderr, level=get("logging.level", "INFO"),
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>")
    log_path = Path(get("logging.path", "logs/app.log"))
    log_path.parent.mkdir(exist_ok=True)
    logger.add(str(log_path), rotation=get("logging.rotation", "10 MB"),
               retention=get("logging.retention", "7 days"),
               level=get("logging.level", "INFO"), compression="zip")
    return logger
