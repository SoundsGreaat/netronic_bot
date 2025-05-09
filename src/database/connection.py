import psycopg2

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
