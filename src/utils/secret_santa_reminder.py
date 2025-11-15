from telebot import apihelper

from config import bot
from database import DatabaseConnection


def secret_santa_notification():
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT telegram_user_id FROM employees '
            'LEFT JOIN secret_santa_info ON employees.id = secret_santa_info.employee_id '
            'WHERE secret_santa_info.employee_id IS NULL '
        )
        employees = cursor.fetchall()
    for employee in employees:
        try:
            if employee[0] is None:
                continue
            try:
                bot.send_message(employee[0], '🎅 Привіт, не забудь заповнити анкету для участі в таємному Санті!')
            except apihelper.ApiTelegramException as e:
                if e.error_code == 400 and "chat not found" in e.description:
                    print(f'Cannot send message to {employee[0]}: chat not found.')
            print(f'Notification sent to {employee[0]}')
        except Exception as e:
            print(f'Error: {e}')


def secret_santa_notification_wrapper():
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 1')
        is_phase_1_started = cursor.fetchone()[0]

    if is_phase_1_started:
        secret_santa_notification()
