import threading
import time

from database import DatabaseListener, DatabaseConnection
from integrations.google_api_functions import update_commendations_mod_in_sheet
from utils.logger import logger


def listen_for_notifications(channel, timeout=5, reconnect_delay=5):
    last_ping_time = time.time()
    sheet_id = '15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I'
    while True:
        try:
            with DatabaseListener(channel) as listener:
                while True:
                    notify = listener.wait_for_notification(timeout=timeout)
                    if notify:
                        update_commendations_mod_in_sheet(
                            sheet_id,
                            'COMMENDATIONS TO BE MODERATED',
                            DatabaseConnection
                        )
                    if time.time() - last_ping_time > 60:
                        listener.ping()
                        last_ping_time = time.time()
        except Exception as e:
            logger.error(f"Listener error: {e}. Reconnecting in {reconnect_delay} seconds...")
            time.sleep(reconnect_delay)


def start_notification_listener_in_thread(channel, timeout=5):
    thread = threading.Thread(
        target=listen_for_notifications,
        args=(channel, timeout),
        daemon=True
    )
    thread.start()
    return thread
