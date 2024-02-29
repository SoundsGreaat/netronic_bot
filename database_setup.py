import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')


class DatabaseConnection:
    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = None
        self.cursor = None

    def __enter__(self):
        print('Connecting to the PostgreSQL database...')
        self.conn = psycopg2.connect(self.db_url)
        self.cursor = self.conn.cursor()
        return self.conn, self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor is not None:
            self.cursor.close()
        if self.conn is not None:
            self.conn.close()
            print('Database connection closed.')


def create_orders_table():
    with DatabaseConnection(DATABASE_URL) as (conn, cursor):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS orders
        (
            order_id      SERIAL PRIMARY KEY,
            user_id       INT  NOT NULL,
            products      VARCHAR NOT NULL,
            contact_name  VARCHAR NOT NULL,
            contact_phone VARCHAR NOT NULL
        );
        """
        cursor.execute(create_table_query)
        conn.commit()


def main():
    with DatabaseConnection(DATABASE_URL) as (conn, cursor):
        pass  # You can perform operations here if needed


if __name__ == '__main__':
    main()
