import datetime
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from config import BIRTHDAY_NOTIFICATIONS_USER_IDS, MONTH_DICT, bot
from database import DatabaseConnection

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


def start_scheduler():
    scheduler.add_job(send_birthday_notification, 'cron', day=25, hour=17, minute=0, id='monthly_job',
                      replace_existing=True)
    scheduler.start()
