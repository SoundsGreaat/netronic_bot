from telebot import types
from src.database import DatabaseConnection

def send_birthday_notification():
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''SELECT employees.name, employees.telegram_user_id, employees.date_of_birth
                          FROM employees
                          WHERE EXTRACT(MONTH FROM employees.date_of_birth) = EXTRACT(MONTH FROM CURRENT_DATE)
                          AND EXTRACT(DAY FROM employees.date_of_birth) = EXTRACT(DAY FROM CURRENT_DATE)''')
        employees_with_birthday = cursor.fetchall()

        for employee in employees_with_birthday:
            name, telegram_user_id, date_of_birth = employee
            bot.send_message(telegram_user_id, f'Happy Birthday, {name}! 🎉')
