import datetime
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from config import BIRTHDAY_NOTIFICATIONS_USER_IDS, MONTH_DICT, bot
from database import DatabaseConnection
from integrations.google_api_functions import update_employees_in_sheet, update_bot_users_in_sheet
from integrations.log_exporter import update_google_stats

db_url = os.getenv('SCHEDULE_DATABASE_URL')

jobstores = {
    'default': SQLAlchemyJobStore(url=db_url)
}

scheduler = BackgroundScheduler(jobstores=jobstores, timezone='Europe/Kiev')


def send_birthday_notification():
    user_ids = BIRTHDAY_NOTIFICATIONS_USER_IDS.split(',')
    month = (datetime.date.today().month % 12) + 1
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, date_of_birth '
                       'FROM employees '
                       'WHERE EXTRACT(MONTH FROM date_of_birth) = %s '
                       'ORDER BY EXTRACT(DAY FROM date_of_birth)', (month,))
        employees = cursor.fetchall()
    birthdays = []
    for name, date_of_birth in employees:
        formatted_date = date_of_birth.strftime('%d/%m')
        birthdays.append(f'🎉 {name} - {formatted_date}')
        message = (f'🎂 Дні народження робітників на {MONTH_DICT[month]}:\n\n'
                   + '\n'.join(birthdays))

    for user_id in user_ids:
        bot.send_message(user_id, message)


def update_google_sheets():
    update_employees_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I', 'BOT AUTOFILL', DatabaseConnection)


def run_update_bot_users_in_sheet():
    update_bot_users_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I', 'LIST OF NOT BOT USERS',
                              DatabaseConnection)


def run_update_google_stats():
    update_google_stats('1Z0hSaiuBJEE-nv0bIch95243BdE6tQwEodTWix5krto')


def start_scheduler():
    scheduler.add_job(send_birthday_notification, 'cron', day=25, hour=17, minute=0,
                      id='birthday_notification_job', replace_existing=True)
    scheduler.add_job(update_google_sheets, 'interval', minutes=5,
                      id='update_google_sheets_job', replace_existing=True)
    scheduler.add_job(run_update_bot_users_in_sheet, 'interval', days=7,
                      id='update_bot_users_in_sheet_job', replace_existing=True)
    scheduler.add_job(run_update_google_stats, 'cron', hour=23, minute=0,
                      id='update_google_stats_job', replace_existing=True)
    scheduler.start()
