from .database_setup import DatabaseConnection


def test_connection():
    try:
        with DatabaseConnection():
            print('Database connection established.')
        print('Connection test complete.')
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

        cursor.execute('''SELECT employees.telegram_user_id, employees.name
            FROM moderators
            JOIN employees ON moderators.employee_id = employees.id
        ''')
        cursor_result = cursor.fetchall()
        authorized_ids['moderators'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        print(f'List of authorized users updated.'
              f'\nAuthorized users: {authorized_ids["users"]}'
              f'\nAuthorized admins: {authorized_ids["admins"]}')


def find_contact_by_name(query):
    words = query.split()
    with DatabaseConnection() as (conn, cursor):
        for word in words:
            cursor.execute(
                '''
                SELECT emp.id, emp.name, emp.position, string_agg(key.keyword, ', ') as keywords
                FROM employees emp
                LEFT JOIN keywords key ON emp.id = key.employee_id
                WHERE emp.name ILIKE %s OR emp.position ILIKE %s OR key.keyword ILIKE %s OR emp.telegram_username = %s
                GROUP BY emp.id, emp.name, emp.position
                ORDER BY emp.name;
                ''',
                (f'%{word}%', f'%{word}%', f'%{word}%', word))
            found_contacts = cursor.fetchall()
            return found_contacts
