from telebot import TeleBot, types
from src.database import DatabaseConnection

def send_mass_message(bot: TeleBot, message: str):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees')
        user_ids = cursor.fetchall()

    for user_id in user_ids:
        bot.send_message(user_id[0], message)
