import threading

from database import DatabaseListener, DatabaseConnection
from integrations.google_api_functions import update_commendations_mod_in_sheet


def listen_for_notifications(channel, timeout=5):
    sheet_id = '15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I'
    with DatabaseListener(channel) as listener:
        while True:
            notify = listener.wait_for_notification(timeout=timeout)
            if notify:
                update_commendations_mod_in_sheet(
                    sheet_id,
                    'COMMENDATIONS TO BE MODERATED',
                    DatabaseConnection
                )


def start_notification_listener_in_thread(channel, timeout=5):
    thread = threading.Thread(
        target=listen_for_notifications,
        args=(channel, timeout),
        daemon=True
    )
    thread.start()
    return thread
