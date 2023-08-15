import sys
from loguru import logger


def init_logging():
    logger.remove()
    sep = "<r>|</r>"
    time = "<g>{time:hh:mm:ss}</g>"
    level = "<level>{level}</level>"
    traceback = "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
    message = "<level>{message}</level>"
    logger.add(sys.stdout, format = f"{time} {sep} {level} {sep} {traceback} {sep} {message}")


if __name__ == '__main__':
    init_logging()
    logger.error("oh noes")
    logger.success("oh noes")
