import logging


def get_logger(name):
    """
    Return a logger with the given name as prefix
    :param name: Name of the logging component
    :return: The logger object
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(ch)

    return logger
