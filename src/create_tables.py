from src.database import DatabaseConnection

with DatabaseConnection() as (conn, cursor):
    with open('database/create_tables.sql', 'r') as file:
        cursor.execute(file.read())
        conn.commit()
        print('Tables created.')
