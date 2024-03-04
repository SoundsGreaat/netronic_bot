from .database_setup import DatabaseConnection


def test_connection():
    try:
        with DatabaseConnection():
            print('Database connection established.')
        print('Connection test complete.\n')
        return True

    except Exception as e:
        print(f'Error: {e}')
        return False


def update_authorized_users(authorized_ids: dict):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees')
        cursor_result = cursor.fetchall()
        authorized_ids['users'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        cursor.execute('''SELECT employees.telegram_user_id, employees.name
            FROM admins
            JOIN employees ON admins.employee_id = employees.id
        ''')
        cursor_result = cursor.fetchall()
        authorized_ids['admins'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        print(f'List of authorized users updated.'
              f'\nAuthorized users: {authorized_ids["users"]}'
              f'\nAuthorized admins: {authorized_ids["admins"]}\n')


def find_contact_by_name(query):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT id, name, position FROM employees WHERE name ILIKE'
            '%s OR position ILIKE %s OR telegram_username = %s',
            (f'%{query}%', f'%{query}%', query))
        found_contacts = cursor.fetchall()
        return found_contacts
