from src.database import DatabaseConnection
from src.google_api_functions import update_employees_in_sheet

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

        update_employees_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I', 'BOT AUTOFILL', DatabaseConnection)

        authorized_ids['moderators'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        print(f'List of authorized users updated.'
              f'\nAuthorized users: {authorized_ids["users"]}'
              f'\nAuthorized admins: {authorized_ids["admins"]}')
