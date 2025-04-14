import os
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from src.database import DatabaseConnection
from src.handlers.authorization import authorized_only
from src.handlers.callbacks import handle_callback_query
from src.handlers.commands import (
    handle_start_command,
    handle_help_command,
    handle_delete_messages_command,
    handle_send_question_form_command,
    handle_send_mass_message_command,
    handle_proceed_add_employee_data_command
)
from src.handlers.messages import (
    handle_text_message,
    handle_photo_message,
    handle_video_message,
    handle_document_message
)
from src.utils.reminder import send_birthday_notification

# Initialize the bot
bot_token = os.getenv('NETRONIC_BOT_TOKEN')
bot = TeleBot(bot_token)

# Set up the main menu
def set_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Start'), types.KeyboardButton('Help'))
    return markup

# Register handlers
bot.message_handler(commands=['start'])(handle_start_command)
bot.message_handler(commands=['help'])(handle_help_command)
bot.message_handler(commands=['delete_messages'])(handle_delete_messages_command)
bot.message_handler(commands=['send_question_form'])(handle_send_question_form_command)
bot.message_handler(commands=['send_mass_message'])(handle_send_mass_message_command)
bot.message_handler(commands=['proceed_add_employee_data'])(handle_proceed_add_employee_data_command)

bot.message_handler(content_types=['text'])(handle_text_message)
bot.message_handler(content_types=['photo'])(handle_photo_message)
bot.message_handler(content_types=['video'])(handle_video_message)
bot.message_handler(content_types=['document'])(handle_document_message)

bot.callback_query_handler(func=lambda call: True)(handle_callback_query)

# Start the bot and scheduler
if __name__ == '__main__':
    bot.polling(none_stop=True)
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_birthday_notification, 'interval', days=1)
    scheduler.start()
