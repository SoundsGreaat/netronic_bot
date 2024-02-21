import os
from telebot import TeleBot, types

bot = TeleBot(os.getenv('NETRONIC_BOT_TOKEN'))

main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
support_button = types.KeyboardButton('💭 Маєш питання?')

main_menu.row(support_button)


@bot.message_handler(commands=['start'])
def send_main_menu(message):
    bot.send_message(message.chat.id, 'Вітаю! Я бот-помічник Netronic. Що ви хочете зробити?',
                     reply_markup=main_menu)


bot.infinity_polling()
