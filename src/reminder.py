import asyncio
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from telebot import apihelper

from src.telethon_functions import send_message


def secret_santa_notification(bot, DatabaseConnection):
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
                    asyncio.run(
                        send_message(employee[0],
                                     '🎅 Привіт, не забудь заповнити анкету для участі в таємному Санті!'
                                     'Це можна зробити через бота @netronic_bot')
                    )
            print(f'Notification sent to {employee[0]}')
        except Exception as e:
            print(f'Error: {e}')


db_url = os.getenv('SCHEDULE_DATABASE_URL')

jobstores = {
    'default': SQLAlchemyJobStore(url=db_url)
}

scheduler = BackgroundScheduler(jobstores=jobstores, timezone='Europe/Kiev')
