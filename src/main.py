from database.listener import start_notification_listener_in_thread
from initialization import initialize_bot
from utils.scheduler import start_scheduler

from handlers import *


def main():
    start_scheduler()
    start_notification_listener_in_thread('commendations_mod_changes')
    initialize_bot()


if __name__ == '__main__':
    main()
