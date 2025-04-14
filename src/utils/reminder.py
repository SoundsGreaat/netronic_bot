import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

db_url = os.getenv('SCHEDULE_DATABASE_URL')

jobstores = {
    'default': SQLAlchemyJobStore(url=db_url)
}

scheduler = BackgroundScheduler(jobstores=jobstores, timezone='Europe/Kiev')
