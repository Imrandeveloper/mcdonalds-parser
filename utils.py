import os

CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))

LOGS_DIR = 'logs'
LOGS_PATH = os.path.join(CURRENT_PATH, LOGS_DIR)


def prepare_logs_dir(logs_path=None):
    """
    Create logs directory if it does not exists
    :param logs_path: path to logs directory
    """
    if not logs_path:
        logs_path = LOGS_PATH

    if not os.path.exists(logs_path):
        os.makedirs(logs_path)
