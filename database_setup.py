import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')


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


def test_connection():
    try:
        with DatabaseConnection():
            print('Database connection established.')
        print('Connection test complete.')
        return True

    except Exception as e:
        print(f'Error: {e}')
        return False


if __name__ == "__main__":
    test_connection()
