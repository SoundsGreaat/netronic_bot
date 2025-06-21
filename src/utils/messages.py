from telebot import apihelper, types

from config import user_data, bot
from database import DatabaseConnection


def delete_messages(chat_id, dict_key='messages_to_delete'):
    if user_data[dict_key].get(chat_id):
        if isinstance(user_data[dict_key][chat_id], list):
            try:
                for message_id in user_data[dict_key][chat_id]:
                    bot.delete_message(chat_id, message_id)
            except apihelper.ApiException:
                pass
        else:
            bot.delete_message(chat_id, user_data[dict_key][chat_id])
        try:
            del user_data[dict_key][chat_id]
        except KeyError:
            pass


def send_links(message, link_type, edit_message=False, show_back_btn=False):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''SELECT links.id, links.name, links.link FROM link_types
                            JOIN links ON link_types.id = links.link_type_id
                            WHERE link_types.name = %s
                            ORDER BY LEFT(links.name, 1), links.name''', (link_type,))
        links = cursor.fetchall()
        cursor.execute('SELECT id FROM link_types WHERE name = %s', (link_type,))
        link_type_id = cursor.fetchone()[0]
    markup = types.InlineKeyboardMarkup()
    for link_id, link_name, link in links:
        if link_name == '📋 Каса взаємодопомоги':
            btn = types.InlineKeyboardButton(text=link_name, callback_data='mutual_assistance')
        elif link.startswith('https://docs.google.com/forms') or user_data['edit_link_mode'].get(message.chat.id):
            btn = types.InlineKeyboardButton(text=link_name, callback_data=f'open_link_{link_id}_{int(show_back_btn)}')
        elif link == 'https://help.netronic.team/':
            btn = types.InlineKeyboardButton(text=link_name, callback_data='helpdesk_it')
        else:
            btn = types.InlineKeyboardButton(text=link_name, url=link)
        markup.add(btn)
    if user_data['edit_link_mode'].get(message.chat.id):
        add_link_btn = types.InlineKeyboardButton(text='➕ Додати посилання',
                                                  callback_data=f'add_link_{link_type_id}_{int(show_back_btn)}')
        markup.add(add_link_btn)
        message_text = '📝 Оберіть посилання для редагування:'
    else:
        message_text = '🔍 Оберіть посилання для перегляду:'
    if show_back_btn:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='business_processes')
        markup.add(back_btn)
    if edit_message:
        bot.edit_message_text(message_text, message.chat.id, message.message_id,
                              reply_markup=markup)
    else:
        bot.send_message(message.chat.id, message_text, reply_markup=markup)
