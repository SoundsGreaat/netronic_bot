import psycopg2
import select

from config import DATABASE_URL


class DatabaseConnection:
    def __init__(self):
        self.db_url = DATABASE_URL
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = psycopg2.connect(self.db_url)
        self.cursor = self.conn.cursor()
        return self.conn, self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()


class DatabaseListener:
    def __init__(self, channel):
        self.db_url = DATABASE_URL
        self.channel = channel
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = psycopg2.connect(self.db_url)
        self.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        self.cursor = self.conn.cursor()
        self.cursor.execute(f"LISTEN {self.channel};")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()

    def wait_for_notification(self, timeout=None):
        if select.select([self.conn], [], [], timeout) == ([], [], []):
            return None
        self.conn.poll()
        while self.conn.notifies:
            notify = self.conn.notifies.pop(0)
            return notify
        return None
