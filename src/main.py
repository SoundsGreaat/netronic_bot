from initialization import initialize_bot
from utils.scheduler import start_scheduler

from handlers import *


def main():
    start_scheduler()
    initialize_bot()


if __name__ == '__main__':
    main()
