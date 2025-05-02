import datetime

from telebot import types

from config import bot
from database import DatabaseConnection
from handlers.authorization import authorized_only
from handlers.main_menu import send_birthdays


@bot.callback_query_handler(func=lambda call: call.data.startswith('birthdays_'))
@authorized_only(user_type='users')
def send_birthdays_month(call):
    month = int(call.data.split('_')[1])
    today = datetime.datetime.now().date()
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, date_of_birth '
                       'FROM employees '
                       'WHERE EXTRACT(MONTH FROM date_of_birth) = %s '
                       'ORDER BY date_of_birth', (month,))
        birthdays = cursor.fetchall()
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_birthdays')
    markup.add(back_btn)
    birthdays_sorted = sorted(birthdays, key=lambda x: x[1].day)
    if birthdays:
        birthday_messages = []
        for name, date in birthdays_sorted:
            if date.day == today.day and date.month == today.month:
                birthday_messages.append(f'🎂 <b>{name} - {date.strftime("%d/%m")}</b>')
            else:
                birthday_messages.append(f'🎂 {name} - {date.strftime("%d/%m")}')
        bot.edit_message_text('\n\n'.join(birthday_messages), call.message.chat.id,
                              call.message.message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.edit_message_text('У цьому місяці немає днів народження.', call.message.chat.id,
                              call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_birthdays')
def back_to_birthdays(call):
    send_birthdays(call.message, edit_message=True)
