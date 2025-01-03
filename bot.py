import math
import os
import re
import threading
import asyncio
import time
import datetime

import gforms

from collections import defaultdict
from time import sleep

from telebot import TeleBot, types, apihelper
from openai import OpenAI
from rapidfuzz import process

from src.crm_api_functions import get_employee_pass_from_crm, add_employee_to_crm, delete_employee_from_crm, \
    update_employee_in_crm
from src.google_forms_filler import FormFiller
from src.database import DatabaseConnection, test_connection, update_authorized_users, find_contact_by_name
from src.telethon_functions import proceed_find_user_id, send_photo, decrypt_session, remove_user_from_chat
from src.make_card import make_card

authorized_ids = {
    'users': set(),
    'admins': set(),
    'moderators': set(),
    'temp_users': set(),
}

user_data = {
    'edit_link_mode': {},
    'messages_to_delete': {},
    'form_messages_to_delete': {},
    'forms_ans': {},
    'forms_timer': {},
}

edit_employee_data = defaultdict(dict)

add_keyword_data = defaultdict(dict)

edit_link_data = {
    'saved_message': {},
    'column': {},
    'show_back_btn': {},
}

add_link_data = defaultdict(dict)

add_employee_data = defaultdict(dict)

openai_data = defaultdict(dict)

make_card_data = defaultdict(dict)

process_in_progress = {}

COMMENDATIONS_PER_PAGE = 10


def authorized_only(user_type):
    def decorator(func):
        def wrapper(data, *args, **kwargs):
            try:
                chat_id = data.chat.id
            except AttributeError:
                chat_id = data.from_user.id

            if (chat_id in authorized_ids[user_type] or chat_id in authorized_ids['temp_users'] and user_type == 'users'
                    or chat_id in authorized_ids['admins']):
                func(data, *args, **kwargs)
                print(f'User @{data.from_user.username} accessed {func.__name__}')
            else:
                with DatabaseConnection() as (conn, cursor):
                    cursor.execute('''SELECT employees.telegram_username
                                FROM admins
                                JOIN employees ON admins.employee_id = employees.id
                            ''')
                    admin_list = [username[0] for username in cursor.fetchall()]
                markup = types.ReplyKeyboardRemove()
                print(
                    f'Unauthorized user @{data.from_user.username} (chat id: {data.chat.id}) tried to access {func.__name__}')
                bot.send_message(chat_id, f'Ви не авторизовані для використання цієї функції.'
                                          f'\nЯкщо ви вважаєте, що це помилка, зверніться до адміністратора.'
                                          f'\n\nСписок адміністраторів: {", ".join(admin_list)}',
                                 reply_markup=markup)

        return wrapper

    return decorator


def callback(element, page_index, element_index, message):
    if element.name == 'Ваш ПІБ':
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT name FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
            employee_name = cursor.fetchone()
            return employee_name[0]

    sent_message = bot.send_message(message.chat.id, f'{element.name}:')
    try:
        user_data['form_messages_to_delete'][message.chat.id].append(sent_message.message_id)
    except KeyError:
        pass
    process_in_progress[message.chat.id] = 'question_form'
    user_data['forms_timer'][message.chat.id] = time.time()

    while True:
        if (process_in_progress.get(message.chat.id) != 'question_form' or
                time.time() - user_data['forms_timer'][message.chat.id] > 3600):
            delete_messages(message.chat.id, 'form_messages_to_delete')
            try:
                del user_data['forms_timer'][message.chat.id]
            except KeyError:
                pass
            break
        if user_data['forms_ans'].get(message.chat.id):
            ans = user_data['forms_ans'][message.chat.id]
            del process_in_progress[message.chat.id]
            del user_data['forms_timer'][message.chat.id]
            del user_data['forms_ans'][message.chat.id]
            return ans
        sleep(0.5)


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


client = OpenAI()
assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
bot = TeleBot(os.getenv('NETRONIC_BOT_TOKEN'))

fernet_key = os.environ.get('FERNET_KEY')
decrypt_session(fernet_key, input_file='src/userbot_session_encrypted', output_file='userbot_session.session')

main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)

knowledge_base_button = types.KeyboardButton('🎓 Навчання')
business_processes_button = types.KeyboardButton('💼 Бізнес-процеси')
news_feed_button = types.KeyboardButton('🔗 Стрічка новин')
contacts_button = types.KeyboardButton('📞 Контакти')
make_card_button = types.KeyboardButton('📜 Меню подяк')
support_button = types.KeyboardButton('💭 Зауваження по роботі боту')

main_menu.row(knowledge_base_button, business_processes_button)
main_menu.row(news_feed_button, contacts_button)
main_menu.row(make_card_button, support_button)

button_names = [btn['text'] for row in main_menu.keyboard for btn in row]

old_button_names = ['🎓 База знань', '🎅 Таємний Санта']


@bot.message_handler(commands=['start', 'menu', 'help'])
@authorized_only(user_type='users')
def send_main_menu(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
        employee_name = cursor.fetchone()
        user_first_name = f' {employee_name[0].split()[1]}' if employee_name and len(
            employee_name[0].split()) >= 2 else ''
    with open('./assets/netronic_logo.png', 'rb') as photo:
        bot.send_photo(message.chat.id, photo,
                       caption=f'👋 Привіт<b>{user_first_name}</b>! Я твій особистий бот-помічник в компанії '
                               f'<b>Netronic</b>.'
                               f'\nЩо тебе цікавить?',
                       reply_markup=main_menu, parse_mode='HTML')

    if message.chat.id in authorized_ids['admins']:
        bot.send_message(message.chat.id, '🔐 Ви авторизовані як адміністратор.'
                                          '\nВам доступні додаткові команди:'
                                          '\n\n/update_authorized_users - оновити список авторизованих користувачів'
                                          '\n/edit_link_mode - увімкнути/вимкнути режим редагування посилань'
                                          '\n/temp_authorize - тимчасово авторизувати користувача')


@bot.message_handler(commands=['update_authorized_users'])
@authorized_only(user_type='admins')
def proceed_authorize_users(message):
    update_authorized_users(authorized_ids)
    bot.send_message(message.chat.id, '✔️ Список авторизованих користувачів оновлено.')


@bot.message_handler(commands=['edit_link_mode'])
@authorized_only(user_type='admins')
def toggle_admin_mode(message):
    if user_data['edit_link_mode'].get(message.chat.id):
        del user_data['edit_link_mode'][message.chat.id]
        bot.send_message(message.chat.id, '🔓 Режим редагування посилань вимкнено.')
    else:
        bot.send_message(message.chat.id, '🔐 Режим редагування посилань увімкнено.')
        user_data['edit_link_mode'][message.chat.id] = True


@bot.message_handler(commands=['temp_authorize'])
@authorized_only(user_type='admins')
def temp_authorize_user(message):
    process_in_progress[message.chat.id] = 'temp_authorization'
    bot.send_message(message.chat.id, 'Надішліть контакт користувача, якого ви хочете авторизувати.')


@bot.message_handler(commands=['mass_message'])
@authorized_only(user_type='admins')
def send_mass_message(message):
    process_in_progress[message.chat.id] = 'mass_message'
    bot.send_message(message.chat.id, 'Надішліть повідомлення, яке ви хочете розіслати.')


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'mass_message')
@authorized_only(user_type='admins')
def proceed_mass_message(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees')
        employees = cursor.fetchall()
    for employee in employees:
        try:
            bot.send_message(employee[0], message.text)
        except Exception as e:
            print(e)
    bot.send_message(message.chat.id, '✔️ Повідомлення розіслано.')
    del process_in_progress[message.chat.id]


@bot.message_handler(content_types=['new_chat_members'])
def new_member_handler(message):
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('INSERT INTO telegram_chats (chat_id, chat_name) VALUES (%s, %s) ',
                               (message.chat.id, message.chat.title))
                conn.commit()


@bot.message_handler(func=lambda message: message.text in old_button_names)
@authorized_only(user_type='users')
def old_button_handler(message):
    bot.send_message(message.chat.id, 'Ця кнопка була видалена або замінена.'
                                      '\nБудь ласка, скористайтесь меню нижче.',
                     reply_markup=main_menu)


@bot.message_handler(func=lambda message: message.text == '🎓 Навчання')
@authorized_only(user_type='users')
def send_knowledge_base(message, edit_message=False):
    send_links(message, 'knowledge_base', edit_message)


@bot.message_handler(func=lambda message: message.text == '💼 Бізнес-процеси')
@authorized_only(user_type='users')
def send_business_processes(message, edit_message=False):
    personnel_management_btn = types.InlineKeyboardButton(text='📁 Кадрове діловодство',
                                                          callback_data='b_process_personnel_management')
    recruitment_btn = types.InlineKeyboardButton(text='🕵️ Recruitment', callback_data='b_process_recruitment')
    office_equipment_btn = types.InlineKeyboardButton(text='💻 Забезпечення офісу',
                                                      callback_data='b_process_office_equipment')
    hr_btn = types.InlineKeyboardButton(text='👨‍💼 HR', callback_data='b_process_hr')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(personnel_management_btn, recruitment_btn, office_equipment_btn, hr_btn)
    if edit_message:
        bot.edit_message_text('🔍 Оберіть бізнес-процес для перегляду:', message.chat.id, message.message_id,
                              reply_markup=markup)
    else:
        bot.send_message(message.chat.id, '🔍 Оберіть бізнес-процес для перегляду:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('b_process_'))
@authorized_only(user_type='users')
def send_business_process(call):
    split_data = call.data.split('_', 2)
    process_name = '_'.join(split_data[2:])
    send_links(call.message, process_name, edit_message=True, show_back_btn=True)


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
        if link.startswith('https://docs.google.com/forms') or user_data['edit_link_mode'].get(message.chat.id):
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


@bot.callback_query_handler(func=lambda call: call.data == 'business_processes')
@authorized_only(user_type='users')
def send_business_processes_menu(call):
    send_business_processes(call.message, edit_message=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_link_'))
@authorized_only(user_type='admins')
def add_link(call):
    link_type_id, show_back_btn = map(int, call.data.split('_')[2:])
    process_in_progress[call.message.chat.id] = 'add_link'
    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'back_to_send_links_{link_type_id}_{show_back_btn}')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id,
                                    '📝 Введіть назву нового посилання (бажано на початку додати емодзі):',
                                    reply_markup=markup)
    add_link_data[call.message.chat.id]['saved_message'] = sent_message
    add_link_data[call.message.chat.id]['link_type_id'] = link_type_id
    add_link_data[call.message.chat.id]['show_back_btn'] = show_back_btn


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(message.chat.id) == 'add_link')
@authorized_only(user_type='admins')
def proceed_add_link_data(message):
    finish_function = False
    link_type_id = add_link_data[message.chat.id]['link_type_id']
    show_back_btn = add_link_data[message.chat.id]['show_back_btn']
    if not add_link_data[message.chat.id].get('name'):
        add_link_data[message.chat.id]['name'] = message.text
        message_text = '🔗 Введіть посилання:'
    else:
        if not re.match(r'^https?://.*', message.text):
            message_text = ('🚫 Посилання введено невірно.'
                            '\nВведіть посилання в форматі <b>http://</b> або <b>https://:</b>')
        else:
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('INSERT INTO links (name, link, link_type_id) VALUES (%s, %s, %s) RETURNING id',
                               (add_link_data[message.chat.id]['name'], message.text, link_type_id))
                link_id = cursor.fetchone()[0]
                conn.commit()
            message_text = f'✅ Посилання <b>{add_link_data[message.chat.id]["name"]}</b> успішно додано.'
            log_text = f'Link {link_id} added by @{message.from_user.username}.'
            print(log_text)
            finish_function = True

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'back_to_send_links_{link_type_id}_{show_back_btn}')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn) if not finish_function else None
    saved_message = add_link_data[message.chat.id]['saved_message']
    bot.delete_message(message.chat.id, saved_message.message_id)
    bot.delete_message(message.chat.id, message.message_id)
    sent_message = bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode='HTML')
    add_link_data[message.chat.id]['saved_message'] = sent_message
    if finish_function:
        del add_link_data[message.chat.id]
        del process_in_progress[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('open_link_'))
@authorized_only(user_type='users')
def send_form(call):
    link_id, show_back_btn = map(int, call.data.split('_')[2:])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, link, link_type_id FROM links WHERE id = %s', (link_id,))
        link = cursor.fetchone()
    if not user_data['edit_link_mode'].get(call.message.chat.id):
        form_link = link[1]
        send_question_form(call.message, form_link, disable_fill_form=True)
    else:
        link_name = link[0]
        link_type_id = link[2]
        edit_link_name_btn = types.InlineKeyboardButton(text='📝 Редагувати назву',
                                                        callback_data=f'edit_link_name_{link_id}_{show_back_btn}')
        edit_link_url_btn = types.InlineKeyboardButton(text='🔗 Редагувати посилання',
                                                       callback_data=f'edit_link_url_{link_id}_{show_back_btn}')
        delete_link_btn = types.InlineKeyboardButton(text='🗑️ Видалити посилання',
                                                     callback_data=f'delete_link_{link_id}_{show_back_btn}')
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'back_to_send_links_{link_type_id}_{show_back_btn}')

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(edit_link_name_btn, edit_link_url_btn, delete_link_btn, back_btn)
        bot.edit_message_text(f'❗ Ви у режимі редагування посилань.'
                              f'\nОберіть дію для посилання <b>{link_name}</b>:',
                              call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'helpdesk_it')
@authorized_only(user_type='users')
def send_helpdesk(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text='🔗 Перейти до Helpdesk IT', url='https://help.netronic.team/'))
    markup.add(types.InlineKeyboardButton(text='🔑 Нагадати пароль', callback_data='helpdesk_show_password'))
    bot.send_message(call.message.chat.id,
                     f'🔗 Оберіть опцію нижче:',
                     reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'helpdesk_show_password')
@authorized_only(user_type='users')
def show_helpdesk_password(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT crm_id FROM employees WHERE telegram_user_id = %s', (call.message.chat.id,))
        crm_user_id = cursor.fetchone()[0]
    crm_password = get_employee_pass_from_crm(crm_user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text='🔗 Перейти до Helpdesk IT', url='https://help.netronic.team/'))
    sent_message = bot.edit_message_text(f'🔑 Ваш пароль: <code>{crm_password}</code> (натисніть для копіювання)',
                                         call.message.chat.id, call.message.message_id, reply_markup=markup,
                                         parse_mode='HTML')
    sleep(15)
    markup.add(types.InlineKeyboardButton(text='🔑 Нагадати пароль', callback_data='helpdesk_show_password'))
    bot.edit_message_text(f'🔗 Оберіть опцію нижче:',
                          call.message.chat.id, sent_message.message_id, reply_markup=markup,
                          parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_link_'))
@authorized_only(user_type='admins')
def edit_link(call):
    operation, link_id = call.data.split('_')[2:4]
    show_back_btn = int(call.data.split('_')[4])
    link_id = int(link_id)
    process_in_progress[call.message.chat.id] = 'edit_link'
    user_data['edit_link_mode'][call.message.chat.id] = True
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM links WHERE id = %s', (link_id,))
        link_info = cursor.fetchone()
    link_name = link_info[0]
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data=f'open_link_{link_id}_{show_back_btn}')
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if operation == 'name':
        edit_link_data['column'][call.message.chat.id] = ('name', link_id)
        message_text = f'📝 Введіть нову назву для посилання <b>{link_name}</b> (бажано на початку додати емодзі):'
    else:
        edit_link_data['column'][call.message.chat.id] = ('link', link_id)
        message_text = f'🔗 Введіть нове посилання для <b>{link_name}</b>:'
    sent_message = bot.send_message(call.message.chat.id, message_text, reply_markup=markup, parse_mode='HTML')
    edit_link_data['saved_message'][call.message.chat.id] = sent_message
    edit_link_data['show_back_btn'][call.message.chat.id] = show_back_btn


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(message.chat.id) == 'edit_link')
@authorized_only(user_type='admins')
def proceed_edit_link_data(message):
    column, link_id = edit_link_data['column'][message.chat.id]
    show_back_btn = edit_link_data['show_back_btn'][message.chat.id]

    bot.delete_message(message.chat.id, edit_link_data['saved_message'][message.chat.id].message_id)
    bot.delete_message(message.chat.id, message.message_id)

    if column == 'link':
        if not re.match(r'^https?://.*', message.text):
            message_text = ('🚫 Посилання введено невірно.'
                            '\nВведіть посилання в форматі <b>http://</b> або <b>https://:</b>')
            back_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                                  callback_data=f'open_link_{link_id}_{show_back_btn}')
            markup = types.InlineKeyboardMarkup()
            markup.add(back_btn)
            sent_message = bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode='HTML')
            edit_link_data['saved_message'][message.chat.id] = sent_message
            return
        else:
            message_text = f'✅ Посилання змінено на <b>{message.text}</b>.'
    else:
        message_text = f'✅ Назву посилання змінено на <b>{message.text}</b>.'

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(f'UPDATE links SET {column} = %s WHERE id = %s', (message.text, link_id))
        conn.commit()

    bot.send_message(message.chat.id, message_text, parse_mode='HTML')
    del process_in_progress[message.chat.id]
    del edit_link_data['column'][message.chat.id]
    del edit_link_data['saved_message'][message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_link_'))
@authorized_only(user_type='admins')
def delete_link_confirmation(call):
    link_id, show_back_btn = map(int, call.data.split('_')[2:])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM links WHERE id = %s', (link_id,))
        link_info = cursor.fetchone()
    link_name = link_info[0]
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення',
                                          callback_data=f'open_link_{link_id}_{show_back_btn}')
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                             callback_data=f'confirm_delete_link_{link_id}')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(confirm_btn, back_btn)
    bot.edit_message_text(f'Ви впевнені, що хочете видалити посилання <b>{link_name}</b>?', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_link_'))
@authorized_only(user_type='admins')
def delete_link(call):
    link_id = int(call.data.split('_')[3])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM links WHERE id = %s', (link_id,))
        link_info = cursor.fetchone()
        cursor.execute('DELETE FROM links WHERE id = %s', (link_id,))
        conn.commit()
    link_name = link_info[0]
    bot.edit_message_text(f'✅ Посилання <b>{link_name}</b> успішно видалено.',
                          call.message.chat.id, call.message.message_id, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_send_links_'))
@authorized_only(user_type='admins')
def back_to_send_links(call):
    if process_in_progress.get(call.message.chat.id) == 'add_link':
        del process_in_progress[call.message.chat.id]
        del add_link_data[call.message.chat.id]

    link_type_id, show_back_btn = map(int, call.data.split('_')[4:])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM link_types WHERE id = %s', (link_type_id,))
        link_type_name = cursor.fetchone()[0]
        send_links(call.message, link_type_name, edit_message=True, show_back_btn=bool(show_back_btn))


@bot.message_handler(func=lambda message: message.text == '🔗 Стрічка новин')
@authorized_only(user_type='users')
def send_useful_links(message, edit_message=False):
    send_links(message, 'news_feed', edit_message)


@bot.message_handler(func=lambda message: message.text == '📞 Контакти')
@authorized_only(user_type='users')
def send_contacts_menu(message, edit_message=False):
    search_btn = types.InlineKeyboardButton(text='🔎 Пошук співробітника', callback_data='search')
    departments_btn = types.InlineKeyboardButton(text='🏢 Департаменти', callback_data='departments')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(search_btn, departments_btn)

    if edit_message:
        bot.edit_message_text('Оберіть дію:', message.chat.id, message.message_id, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Оберіть дію:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'search')
@authorized_only(user_type='users')
def send_search_form(call):
    process_in_progress[call.message.chat.id] = 'search'

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(back_btn)

    bot.edit_message_text('Введіть ім\'я, прізвище або посаду співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)

    user_data['messages_to_delete'][call.message.chat.id] = call.message.message_id


@bot.callback_query_handler(func=lambda call: call.data == 'departments')
@authorized_only(user_type='users')
def send_departments(call):
    buttons = []
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name, additional_instance FROM departments ORDER BY name')
        departments = cursor.fetchall()

    for department in departments:
        department_id = department[0]
        department_name = department[1]
        additional_instance = department[2]

        if additional_instance:
            call_data = f'additional_{int(additional_instance)}_{department_id}'
        else:
            call_data = f'dep_{int(additional_instance)}_{department_id}'

        btn = types.InlineKeyboardButton(text=f'🏢 {department_name}', callback_data=call_data)
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text('Оберіть департамент:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('additional_'))
@authorized_only(user_type='users')
def send_department_contacts(call):
    additional_instance, department_id = map(int, call.data.split('_')[1:])
    buttons = []

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''SELECT id, name, is_chief_department FROM intermediate_departments WHERE department_id = %s
                            ORDER BY is_chief_department DESC, name''',
                       (department_id,))
        intermediate_departments = cursor.fetchall()

    for intermediate_department in intermediate_departments:
        intermediate_department_id = intermediate_department[0]
        intermediate_department_name = intermediate_department[1]
        intermediate_department_is_chief = intermediate_department[2]
        emoji = '👔' if intermediate_department_is_chief else '🗄️'
        btn = types.InlineKeyboardButton(text=f'{emoji} {intermediate_department_name}',
                                         callback_data=
                                         f'dep_{additional_instance}_{department_id}_{intermediate_department_id}')
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
@authorized_only(user_type='users')
def send_department_contacts(call):
    additional_instance, department_id = map(int, call.data.split('_')[1:3])
    buttons = []
    if additional_instance:
        intermediate_department_id = int(call.data.split('_')[3])
        db_column = 'intermediate_department_id'
        instance_id = intermediate_department_id
    else:
        intermediate_department_id = 0
        db_column = 'department_id'
        instance_id = department_id

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(f'''SELECT id, name, is_chief_department FROM sub_departments WHERE {db_column} = %s
                                ORDER BY is_chief_department DESC, name''',
                       (instance_id,))
        sub_departments = cursor.fetchall()

    for sub_department in sub_departments:
        sub_department_id = sub_department[0]
        sub_department_name = sub_department[1]
        sub_department_is_chief = sub_department[2]
        emoji = '👔' if sub_department_is_chief else '🗄️'
        btn = types.InlineKeyboardButton(text=f'{emoji} {sub_department_name}',
                                         callback_data=
                                         f'sub_dep_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                         f'{sub_department_id}')
        buttons.append(btn)
    if additional_instance:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'additional_{additional_instance}_{department_id}')
    else:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_dep_'))
@authorized_only(user_type='users')
def send_sub_departments_contacts(call):
    additional_instance, department_id, intermediate_department_id, sub_department_id = map(int,
                                                                                            call.data.split('_')[2:])
    markup = types.InlineKeyboardMarkup(row_width=1)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name FROM employees WHERE sub_department_id = %s ORDER BY name',
                       (sub_department_id,))
        employees = cursor.fetchall()

    for employee in employees:
        employee_id = employee[0]
        employee_name = employee[1]

        btn = types.InlineKeyboardButton(text=f'👨‍💻 {employee_name}',
                                         callback_data=
                                         f'profile_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                         f'{sub_department_id}_{employee_id}')
        markup.add(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'dep_{additional_instance}_{department_id}_'
                                                                        f'{intermediate_department_id}')

    if call.from_user.id in authorized_ids['admins']:
        add_employee_btn = types.InlineKeyboardButton(text='➕ Додати співробітника',
                                                      callback_data=f'add_employee_{additional_instance}_'
                                                                    f'{department_id}_{intermediate_department_id}_'
                                                                    f'{sub_department_id}')
        markup.row(add_employee_btn)

    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)

    if process_in_progress.get(call.message.chat.id) == 'add_employee':
        del process_in_progress[call.message.chat.id]
    if add_employee_data.get(call.message.chat.id):
        del add_employee_data[call.message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_employee_'))
@authorized_only(user_type='admins')
def add_employee(call):
    additional_instance, department_id, intermediate_department_id, sub_department_id = map(int,
                                                                                            call.data.split('_')[2:])
    process_in_progress[call.message.chat.id] = 'add_employee'
    if add_employee_data.get(call.message.chat.id):
        del add_employee_data[call.message.chat.id]
    add_employee_data[call.message.chat.id]['department_id'] = department_id
    add_employee_data[call.message.chat.id]['sub_department_id'] = sub_department_id
    add_employee_data[call.message.chat.id]['additional_instance'] = additional_instance
    add_employee_data[call.message.chat.id]['intermediate_department_id'] = intermediate_department_id
    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'sub_dep_{additional_instance}_{department_id}_'
                                                          f'{intermediate_department_id}_{sub_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_massage = bot.send_message(call.message.chat.id, '👤 Введіть ПІБ нового співробітника:', reply_markup=markup)
    add_employee_data[call.message.chat.id]['saved_message'] = sent_massage


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_employee')
@authorized_only(user_type='admins')
def proceed_add_employee_data(message, delete_user_message=True, skip_phone=False, skip_email=False,
                              skip_username=False, skip_dob=False):
    finish_function = False
    department_id = add_employee_data[message.chat.id]['department_id']
    sub_department_id = add_employee_data[message.chat.id]['sub_department_id']
    additional_instance = add_employee_data[message.chat.id]['additional_instance']
    intermediate_department_id = add_employee_data[message.chat.id]['intermediate_department_id']

    skip_btn = None

    if not add_employee_data[message.chat.id].get('name'):
        if re.match(r'^[А-ЯІЇЄҐа-яіїєґ\'\s]+$', message.text):
            add_employee_data[message.chat.id]['name'] = message.text
            message_text = '📞 Введіть номер телефону нового співробітника:'
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('SELECT name FROM employees WHERE name = %s',
                               (add_employee_data[message.chat.id]['name'],))
                employee_name = cursor.fetchone()
            if employee_name:
                message_text = ('🚫 Співробітник з таким ПІБ вже існує в базі даних.'
                                '\nВведіть унікальне ПІБ нового співробітника:')
                add_employee_data[message.chat.id].pop('name')
        else:
            message_text = '🚫 ПІБ введено невірно.\nВведіть ПІБ українською мовою без цифр та спецсимволів:'
        if add_employee_data[message.chat.id].get('name'):
            skip_btn = types.InlineKeyboardButton(text='⏭️ Пропустити', callback_data='skip_phone')

    elif not add_employee_data[message.chat.id].get('phone'):
        clear_number = re.match(r'^3?8?(0\d{9})$', re.sub(r'\D', '', message.text))
        message_text = '📧 Введіть email нового співробітника:'
        if skip_phone:
            add_employee_data[message.chat.id]['phone'] = 'skip'
        else:
            if clear_number:
                add_employee_data[message.chat.id]['phone'] = f'+38{clear_number.group(1)}'
            else:
                message_text = ('🚫 Номер телефону введено невірно.'
                                '\nВведіть номер телефону в форматі 0XXXXXXXXX:')
        if add_employee_data[message.chat.id].get('phone'):
            skip_btn = types.InlineKeyboardButton(text='⏭️ Пропустити', callback_data='skip_email')

    elif not add_employee_data[message.chat.id].get('email'):
        if skip_email:
            add_employee_data[message.chat.id]['email'] = 'skip'
        else:
            add_employee_data[message.chat.id]['email'] = message.text
        message_text = '💼 Введіть посаду нового співробітника:'

    elif not add_employee_data[message.chat.id].get('position'):
        add_employee_data[message.chat.id]['position'] = message.text
        message_text = '🎂 Введіть дату народження нового співробітника:'
        if add_employee_data[message.chat.id].get('position'):
            skip_btn = types.InlineKeyboardButton(text='⏭️ Пропустити', callback_data='skip_dob')

    elif not add_employee_data[message.chat.id].get('date_of_birth'):
        if skip_dob:
            add_employee_data[message.chat.id]['date_of_birth'] = 'skip'
        else:
            date_formats = ['%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%d %m %Y']
            for date_format in date_formats:
                try:
                    formatted_date = datetime.datetime.strptime(message.text, date_format)
                    break
                except ValueError:
                    continue
            else:
                message_text = ('🚫 Дата народження введена невірно.'
                                '\nВведіть дату народження в форматі <b>ДД.ММ.РРРР</b>:')
                sent_message = bot.send_message(message.chat.id, message_text, parse_mode='HTML')
                add_employee_data[message.chat.id]['saved_message'] = sent_message
                return

            add_employee_data[message.chat.id]['date_of_birth'] = formatted_date
            print(add_employee_data[message.chat.id]['date_of_birth'])
        message_text = '🆔 Введіть юзернейм нового співробітника:'
        if add_employee_data[message.chat.id].get('date_of_birth'):
            skip_btn = types.InlineKeyboardButton(text='⏭️ Пропустити', callback_data='skip_username')

    elif not add_employee_data[message.chat.id].get('telegram_username'):
        if skip_username:
            add_employee_data[message.chat.id]['telegram_username'] = 'skip'
        else:
            if message.text.startswith('@'):
                add_employee_data[message.chat.id]['telegram_username'] = message.text
            else:
                add_employee_data[message.chat.id]['telegram_username'] = f'@{message.text}'

            searching_message = bot.send_message(message.chat.id, '🔄 Пошук користувача в Telegram...')
            add_employee_data[message.chat.id]['telegram_user_id'] = asyncio.run(
                proceed_find_user_id(add_employee_data[message.chat.id]['telegram_username']))
            if add_employee_data[message.chat.id]['telegram_user_id'] is not None:
                bot.delete_message(message.chat.id, searching_message.message_id)
            else:
                sent_message = bot.edit_message_text(
                    '🚫 Користувач не знайдений. Перевірте правильність введеного юзернейму та спробуйте ще раз.',
                    message.chat.id, searching_message.message_id)
                saved_message = add_employee_data[message.chat.id]['saved_message']
                bot.delete_message(message.chat.id, saved_message.message_id)
                bot.delete_message(message.chat.id, message.message_id)
                add_employee_data[message.chat.id]['saved_message'] = sent_message
                return

        if add_employee_data[message.chat.id]['phone'] == 'skip':
            add_employee_data[message.chat.id]['phone'] = None

        if add_employee_data[message.chat.id]['email'] == 'skip':
            add_employee_data[message.chat.id]['email'] = None

        if add_employee_data[message.chat.id]['date_of_birth'] == 'skip':
            add_employee_data[message.chat.id]['date_of_birth'] = None

        if add_employee_data[message.chat.id]['telegram_username'] == 'skip':
            add_employee_data[message.chat.id]['telegram_username'] = None
            add_employee_data[message.chat.id]['telegram_user_id'] = None

        crm_id = add_employee_to_crm(add_employee_data[message.chat.id]['name'],
                                     add_employee_data[message.chat.id]['phone'],
                                     add_employee_data[message.chat.id]['position'],
                                     add_employee_data[message.chat.id]['telegram_user_id'],
                                     add_employee_data[message.chat.id]['telegram_username'],
                                     add_employee_data[message.chat.id]['email'])

        with DatabaseConnection() as (conn, cursor):
            cursor.execute(
                'INSERT INTO employees (name, phone, position, telegram_username, sub_department_id, '
                'telegram_user_id, email, date_of_birth,crm_id) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                (add_employee_data[message.chat.id]['name'],
                 add_employee_data[message.chat.id]['phone'],
                 add_employee_data[message.chat.id]['position'],
                 add_employee_data[message.chat.id]['telegram_username'],
                 int(add_employee_data[message.chat.id]['sub_department_id']),
                 add_employee_data[message.chat.id]['telegram_user_id'],
                 add_employee_data[message.chat.id]['email'],
                 add_employee_data[message.chat.id]['date_of_birth'],
                 crm_id))
            employee_id = cursor.fetchone()[0]
            conn.commit()
        message_text = f'✅ Співробітник <b>{add_employee_data[message.chat.id]["name"]}</b> доданий до бази даних та CRM системи.'
        update_authorized_users(authorized_ids)
        finish_function = True
        log_text = f'Employee {employee_id} added by @{message.from_user.username}.'
        print(log_text)

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'sub_dep_{additional_instance}_{department_id}_'
                                                          f'{intermediate_department_id}_{sub_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(skip_btn) if skip_btn else None
    markup.add(cancel_btn) if not finish_function else None
    saved_message = add_employee_data[message.chat.id]['saved_message']
    bot.delete_message(message.chat.id, saved_message.message_id)
    if delete_user_message:
        bot.delete_message(message.chat.id, message.message_id)
    sent_message = bot.send_message(message.chat.id, message_text, reply_markup=markup, parse_mode='HTML')
    add_employee_data[message.chat.id]['saved_message'] = sent_message
    if finish_function:
        del add_employee_data[message.chat.id]
        del process_in_progress[message.chat.id]
        send_profile(message,
                     call_data=f'profile_{additional_instance}_{department_id}_{intermediate_department_id}_'
                               f'{sub_department_id}_{employee_id}')


@bot.callback_query_handler(func=lambda call: call.data == 'skip_phone')
@authorized_only(user_type='admins')
def skip_phone(call):
    proceed_add_employee_data(call.message, delete_user_message=False, skip_phone=True)


@bot.callback_query_handler(func=lambda call: call.data == 'skip_email')
@authorized_only(user_type='admins')
def skip_email(call):
    proceed_add_employee_data(call.message, delete_user_message=False, skip_email=True)


@bot.callback_query_handler(func=lambda call: call.data == 'skip_username')
@authorized_only(user_type='admins')
def skip_username(call):
    proceed_add_employee_data(call.message, delete_user_message=False, skip_username=True)


@bot.callback_query_handler(func=lambda call: call.data == 'skip_dob')
@authorized_only(user_type='admins')
def skip_dob(call):
    proceed_add_employee_data(call.message, delete_user_message=False, skip_dob=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('profile_'))
@authorized_only(user_type='users')
def send_profile(call, call_data=None):
    if call_data:
        chat_id = call.chat.id
        call.data = call_data
    else:
        chat_id = call.message.chat.id

    if call.data.startswith('profile_s_'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[2:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)
        back_btn_callback = f'bck_srch_{search_query}'
        edit_employee_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[1:])
        back_btn_callback = (f'sub_dep_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}')
        edit_employee_btn_callback = (f'edit_emp_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                      f'{sub_department_id}_{employee_id}')

    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)

    if chat_id in authorized_ids['admins']:
        edit_employee_btn = types.InlineKeyboardButton(text='📝 Редагувати контакт',
                                                       callback_data=edit_employee_btn_callback)
        markup.row(edit_employee_btn)

    markup.row(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''SELECT emp.name,
                                 departments.name     AS department,
                                 sub_departments.name AS sub_department,
                                 emp.position,
                                 emp.phone,
                                 emp.telegram_username,
                                 intermediate_departments.name,
                                 emp.email,
                                 emp.date_of_birth
                        FROM employees as emp
                        JOIN sub_departments ON emp.sub_department_id = sub_departments.id
                        JOIN departments ON sub_departments.department_id = departments.id
                        LEFT JOIN intermediate_departments ON 
                                                sub_departments.intermediate_department_id = intermediate_departments.id
                        WHERE emp.id = %s
                ''', (employee_id,))
        employee_info = cursor.fetchone()

    employee_name = employee_info[0]
    employee_department = employee_info[1]
    employee_sub_department = employee_info[2]
    employee_position = employee_info[3]
    employee_phone = employee_info[4]
    employee_username = employee_info[5]
    employee_intermediate_department = employee_info[6]
    employee_email = employee_info[7]
    employee_date_of_birth = employee_info[8].strftime('%d/%m/%Y') if employee_info[8] else None

    office_string = f'\n<b>🏢 Офіс/служба</b>: {employee_intermediate_department}' if employee_intermediate_department \
        else ''
    sub_department_string = f'\n<b>🗄️ Відділ</b>: {employee_sub_department}' if (
            employee_sub_department != 'Відобразити співробітників') else ''
    phone_string = f'\n<b>📞 Телефон</b>: {employee_phone}' if employee_phone else f'\n<b>📞 Телефон</b>: Не вказано'
    username_string = f'\n<b>🆔 Юзернейм</b>: {employee_username}' \
        if employee_username else f'\n<b>🆔 Юзернейм</b>: Не вказано'
    email_string = f'\n<b>📧 Email</b>: {employee_email}' if employee_email else f'\n<b>📧 Email</b>: Не вказано'
    date_of_birth_string = f'\n<b>🎂 Дата народження</b>: {employee_date_of_birth}' \
        if employee_date_of_birth else f'\n<b>🎂 Дата народження</b>: Не вказано'

    message_text = (f'👨‍💻 <b>{employee_name}</b>'
                    f'\n\n<b>🏢 Департамент</b>: {employee_department}'
                    f'{office_string}'
                    f'{sub_department_string}'
                    f'\n<b>💼 Посада</b>: {employee_position}'
                    f'{phone_string}'
                    f'{username_string}'
                    f'{email_string}'
                    f'{date_of_birth_string}')
    if call_data:
        bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.edit_message_text(message_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('bck_srch_'))
@authorized_only(user_type='users')
def back_to_search_results(call):
    call.message.text = '_'.join(call.data.split('_')[2:])
    proceed_contact_search(call.message, edit_message=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_emp'))
@authorized_only(user_type='admins')
def edit_employee(call):
    if call.data.startswith('edit_emp_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)

        edit_name_btn_callback = f'e_name_s_{search_query}_{employee_id}'
        edit_phone_btn_callback = f'e_phone_s_{search_query}_{employee_id}'
        edit_position_btn_callback = f'e_pos_s_{search_query}_{employee_id}'
        edit_username_btn_callback = f'e_uname_s_{search_query}_{employee_id}'
        edit_email_btn_callback = f'e_email_s_{search_query}_{employee_id}'
        edit_date_of_birth_btn_callback = f'e_dob_s_{search_query}_{employee_id}'
        edit_sub_department_btn_callback = f'e_subdep_s_{search_query}_{employee_id}'
        show_keywords_btn_callback = f'show_keywords_s_{search_query}_{employee_id}'
        delete_btn_callback = f'delete_s_{search_query}_{employee_id}'
        back_btn_callback = f'profile_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])
        edit_name_btn_callback = (f'e_name_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                  f'{sub_department_id}_{employee_id}')
        edit_phone_btn_callback = (f'e_phone_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                   f'{sub_department_id}_{employee_id}')
        edit_position_btn_callback = (f'e_pos_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                      f'{sub_department_id}_{employee_id}')
        edit_username_btn_callback = (f'e_uname_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                      f'{sub_department_id}_{employee_id}')
        edit_email_btn_callback = (f'e_email_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                   f'{sub_department_id}_{employee_id}')
        edit_date_of_birth_btn_callback = (f'e_dob_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                           f'{sub_department_id}_{employee_id}')
        edit_sub_department_btn_callback = (
            f'e_subdep_{additional_instance}_{department_id}_{intermediate_department_id}_'
            f'{sub_department_id}_{employee_id}')
        show_keywords_btn_callback = (
            f'show_keywords_{additional_instance}_{department_id}_{intermediate_department_id}_'
            f'{sub_department_id}_{employee_id}')
        delete_btn_callback = (f'delete_{additional_instance}_{department_id}_{intermediate_department_id}_'
                               f'{sub_department_id}_{employee_id}')
        back_btn_callback = (f'profile_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}_{employee_id}')

    edit_name_btn = types.InlineKeyboardButton(text='✏️ Змінити ім\'я', callback_data=edit_name_btn_callback)
    edit_phone_btn = types.InlineKeyboardButton(text='📞 Змінити телефон', callback_data=edit_phone_btn_callback)
    edit_position_btn = types.InlineKeyboardButton(text='💼 Змінити посаду', callback_data=edit_position_btn_callback)
    edit_username_btn = types.InlineKeyboardButton(text='🆔 Змінити юзернейм', callback_data=edit_username_btn_callback)
    edit_email_btn = types.InlineKeyboardButton(text='📧 Змінити email', callback_data=edit_email_btn_callback)
    edit_date_of_birth_btn = types.InlineKeyboardButton(text='🎂 Змінити дату народження',
                                                        callback_data=edit_date_of_birth_btn_callback)
    edit_sub_department_btn = types.InlineKeyboardButton(text='🗄️ Змінити відділ',
                                                         callback_data=edit_sub_department_btn_callback)
    show_keywords_btn = types.InlineKeyboardButton(text='🔍 Показати ключові слова',
                                                   callback_data=show_keywords_btn_callback)
    make_admin_btn = types.InlineKeyboardButton(text='⚠️ Переключити статус адміністратора',
                                                callback_data=f'make_admin_{employee_id}')
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити контакт', callback_data=delete_btn_callback)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(edit_name_btn, edit_phone_btn, edit_position_btn, edit_username_btn, show_keywords_btn,
               edit_email_btn, edit_date_of_birth_btn, edit_sub_department_btn)
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees WHERE id = %s', (employee_id,))
        employee_telegram_id = cursor.fetchone()[0]
    if employee_telegram_id != call.from_user.id:
        markup.row(make_admin_btn)
        markup.row(delete_btn)
    markup.row(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    bot.edit_message_text(f'📝 Редагування контакту <b>{employee_name}</b>:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')

    if process_in_progress.get(call.message.chat.id) == 'edit_employee':
        del process_in_progress[call.message.chat.id]
        del edit_employee_data[call.from_user.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('show_keywords_'))
@authorized_only(user_type='admins')
def show_keywords(call):
    if call.data.startswith('show_keywords_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)
        keyword_btn_callback = f'd_kwd_s_{search_query}_{employee_id}'
        add_keyword_btn_callback = f'a_kwd_s_{search_query}_{employee_id}'
        back_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])
        keyword_btn_callback = (f'd_kwd_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                f'{sub_department_id}_{employee_id}')
        add_keyword_btn_callback = (f'a_kwd_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                    f'{sub_department_id}_{employee_id}')
        back_btn_callback = f'edit_emp_{additional_instance}_{department_id}_{intermediate_department_id}_' \
                            f'{sub_department_id}_{employee_id}'

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, keyword FROM keywords WHERE employee_id = %s ORDER BY keyword', (employee_id,))
        keywords = cursor.fetchall()
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    markup = types.InlineKeyboardMarkup(row_width=1)
    for keyword_id, keyword in keywords:
        keyword_btn = types.InlineKeyboardButton(text=f'🔍 {keyword}',
                                                 callback_data=f'{keyword_btn_callback}_{keyword_id}')
        markup.add(keyword_btn)

    add_keyword_btn = types.InlineKeyboardButton(text='➕ Додати ключове слово', callback_data=add_keyword_btn_callback)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup.add(add_keyword_btn, back_btn)

    bot.edit_message_text(f'Ключові слова для контакту <b>{employee_name}</b>:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('a_kwd_'))
@authorized_only(user_type='admins')
def add_keyword(call):
    if call.data.startswith('a_kwd_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)
        back_btn_callback = f'show_keywords_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])
        back_btn_callback = f'show_keywords_{additional_instance}_{department_id}_{intermediate_department_id}_' \
                            f'{sub_department_id}_{employee_id}'

    process_in_progress[call.message.chat.id] = 'add_keyword'
    add_keyword_data[call.message.chat.id]['employee_id'] = employee_id
    add_keyword_data[call.message.chat.id]['back_btn_callback'] = back_btn_callback

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, '🔍 Введіть ключові слова через кому.\n'
                                                          'Приклад: <i>програміст, розробник, IT-спеціаліст</i>',
                                    reply_markup=markup, parse_mode='HTML')
    add_keyword_data[call.message.chat.id]['saved_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_keyword')
@authorized_only(user_type='admins')
def proceed_add_keyword_data(message):
    employee_id = add_keyword_data[message.chat.id]['employee_id']
    back_btn_callback = add_keyword_data[message.chat.id]['back_btn_callback']
    split_message = message.text.split(',')

    with DatabaseConnection() as (conn, cursor):
        for keyword in split_message:
            cursor.execute('INSERT INTO keywords (employee_id, keyword) VALUES (%s, %s)',
                           (employee_id, keyword.strip()))
        conn.commit()

    print(f'Keywords "{message.text}" added to employee {employee_id} by {message.from_user.username}.')

    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup.add(back_btn)

    bot.delete_message(message.chat.id, add_keyword_data[message.chat.id]['saved_message'].message_id)
    bot.send_message(message.chat.id, '✅ Ключові слова успішно додані.', reply_markup=markup)

    del process_in_progress[message.chat.id]
    del add_keyword_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('d_kwd_'))
@authorized_only(user_type='admins')
def delete_keyword(call):
    if call.data.startswith('d_kwd_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-2])
        employee_id = int(parts[-2])
        keyword_id = int(parts[-1])
        confirm_delete_keyword_callback = f'cd_kwd_s_{search_query}_{employee_id}_{keyword_id}'
        back_btn_callback = f'show_keywords_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id, keyword_id) = map(int, call.data.split('_')[2:])
        confirm_delete_keyword_callback = (f'cd_kwd_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                           f'{sub_department_id}_{employee_id}_{keyword_id}')
        back_btn_callback = (f'show_keywords_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}_{employee_id}')

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT keyword FROM keywords WHERE id = %s', (keyword_id,))
        keyword = cursor.fetchone()[0]

    message_text = f'Підтвердіть видалення ключового слова <b>{keyword}</b>:'
    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data=back_btn_callback)
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                             callback_data=confirm_delete_keyword_callback)
    markup.add(confirm_btn, back_btn)

    bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, reply_markup=markup,
                          parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('cd_kwd_'))
@authorized_only(user_type='admins')
def confirm_delete_keyword(call):
    if call.data.startswith('cd_kwd_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-2])
        employee_id = int(parts[-2])
        keyword_id = int(parts[-1])
        back_btn_callback = f'show_keywords_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id, keyword_id) = map(int, call.data.split('_')[2:])
        back_btn_callback = (f'show_keywords_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}_{employee_id}')

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM keywords WHERE id = %s RETURNING keyword', (keyword_id,))
        keyword = cursor.fetchone()[0]
        conn.commit()

    print(f'Keyword "{keyword}" deleted from employee {employee_id} by {call.from_user.username}.')

    message_text = f'✅ Ключове слово <b>{keyword}</b> видалено.'
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup.add(back_btn)

    bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, reply_markup=markup,
                          parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('make_admin_'))
@authorized_only(user_type='admins')
def make_admin(call):
    employee_id = int(call.data.split('_')[2])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM admins WHERE employee_id = %s', (employee_id,))
        is_admin = cursor.fetchone()
        if is_admin:
            cursor.execute('DELETE FROM admins WHERE employee_id = %s', (employee_id,))
            message_text = f'✅ Користувач {employee_id} більше не є адміністратором.'
            log_text = f'Employee {employee_id} removed from admins by {call.from_user.username}.'
        else:
            cursor.execute('INSERT INTO admins (employee_id) VALUES (%s)', (employee_id,))
            message_text = f'✅ Користувач {employee_id} тепер є адміністратором.'
            log_text = f'Employee {employee_id} added to admins by {call.from_user.username}.'
        conn.commit()
    print(log_text)
    update_authorized_users(authorized_ids)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, message_text)
    bot.send_message(call.message.chat.id, call.message.text, reply_markup=call.message.reply_markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('e_'))
@authorized_only(user_type='admins')
def proceed_edit_employee(call):
    process_in_progress[call.message.chat.id] = 'edit_employee'
    edit_employee_data[call.from_user.id]['saved_message'] = call.message

    additional_button = None

    if call.data.split('_')[2] == 's':
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)

        back_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])

        back_btn_callback = (f'edit_emp_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}_{employee_id}')

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    if call.data.startswith('e_name'):
        edit_employee_data[call.from_user.id]['column'] = ('name', employee_id)
        message_text = f'✏️ Введіть нове ім\'я для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_phone'):
        edit_employee_data[call.from_user.id]['column'] = ('phone', employee_id)
        message_text = f'📞 Введіть новий телефон для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_pos'):
        edit_employee_data[call.from_user.id]['column'] = ('position', employee_id)
        message_text = f'💼 Введіть нову посаду для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_uname'):
        edit_employee_data[call.from_user.id]['column'] = ('telegram_username', employee_id)
        message_text = f'🆔 Введіть новий юзернейм для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_email'):
        edit_employee_data[call.from_user.id]['column'] = ('email', employee_id)
        message_text = f'📧 Введіть новий email для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_dob'):
        edit_employee_data[call.from_user.id]['column'] = ('date_of_birth', employee_id)
        message_text = f'🎂 Введіть нову дату народження для контакту <b>{employee_name}</b>:'
        delete_date_of_birth_btn = types.InlineKeyboardButton(text='🗑️ Видалити дату народження',
                                                              callback_data=f'del_dob_{employee_id}')
        additional_button = delete_date_of_birth_btn
    elif call.data.startswith('e_subdep'):
        edit_employee_data[call.from_user.id]['column'] = ('sub_department_id', employee_id)
        message_text = f'🗄️ Введіть приблизну назву відділу для контакту <b>{employee_name}</b>:'

    back_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)
    if additional_button:
        markup.add(additional_button)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, message_text, reply_markup=markup, parse_mode='HTML')
    edit_employee_data[call.from_user.id]['saved_markup'] = markup
    edit_employee_data[call.from_user.id]['saved_message'].message_id = sent_message.message_id


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'edit_employee')
@authorized_only(user_type='admins')
def edit_employee_data_ans(message):
    finish_function = True
    telegram_user_id = None
    column, employee_id = edit_employee_data[message.chat.id]['column']
    new_value = message.text
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(f'SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_data = cursor.fetchone()
    employee_name = employee_data[0]

    if column == 'name':
        result_message_text = f'✅ Ім\'я контакту змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} name changed to {new_value} by {message.from_user.username}.'

    elif column == 'phone':
        clear_number = re.match(r'^3?8?(0\d{9})$', re.sub(r'\D', '', new_value))
        if clear_number:
            new_value = f'+38{clear_number.group(1)}'
            result_message_text = f'✅ Номер телефону контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
            log_text = f'Employee {employee_id} phone changed to {new_value} by {message.from_user.username}.'
        else:
            result_message_text = ('🚫 Номер телефону введено невірно.'
                                   '\nВведіть номер телефону в форматі 0XXXXXXXXX:')
            log_text = ''
            finish_function = False

    elif column == 'position':
        result_message_text = f'✅ Посаду контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} position changed to {new_value} by {message.from_user.username}.'

    elif column == 'sub_department_id':
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id, name FROM sub_departments')
            sub_departments = cursor.fetchall()
            original_sub_departments = [(sub_department[0], sub_department[1].strip()) for sub_department in
                                        sub_departments]
            sub_departments = [(id, name.lower()) for id, name in original_sub_departments]
        query = new_value.lower()
        best_match = process.extractOne(query, [name for id, name in sub_departments])
        original_best_match = next((id, name) for id, name in original_sub_departments if name.lower() == best_match[0])
        new_value = original_best_match[0]
        sub_department_name = original_best_match[1]
        result_message_text = (f'✅ Відділ контакту <b>{employee_name}</b> змінено на <b>{sub_department_name}</b>.'
                               f'\nСхожість: {best_match[1]:.1f}%')
        log_text = f'Employee {employee_id} sub_department_id changed to {new_value} by {message.from_user.username}.'

    elif column == 'telegram_username':
        searching_message = bot.send_message(message.chat.id, '🔄 Пошук користувача в Telegram...')
        telegram_user_id = asyncio.run(proceed_find_user_id(new_value))
        bot.delete_message(message.chat.id, searching_message.message_id)
        if telegram_user_id is not None:
            if not new_value.startswith('@'):
                new_value = f'@{new_value}'
            update_authorized_users(authorized_ids)
            result_message_text = f'✅ Юзернейм контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
            log_text = f'Employee {employee_id} username changed to {new_value} by {message.from_user.username}.'
        else:
            result_message_text = (
                '🚫 Користувач не знайдений. Перевірте правильність введеного юзернейму та спробуйте ще раз.')
            log_text = ''
            finish_function = False
    elif column == 'email':
        result_message_text = f'✅ Email контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} email changed to {new_value} by {message.from_user.username}.'
    elif column == 'date_of_birth':
        date_formats = ['%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%d %m %Y']
        for date_format in date_formats:
            try:
                new_value = datetime.datetime.strptime(new_value, date_format)
                result_message_text = f'✅ Дату народження контакту <b>{employee_name}</b> змінено на <b>{new_value.strftime("%d/%m/%Y")}</b>.'
                log_text = f'Employee {employee_id} date of birth changed to {new_value} by {message.from_user.username}.'
                break
            except ValueError:
                continue
        else:
            result_message_text = ('🚫 Дату народження введено невірно.'
                                   '\nВведіть дату народження в форматі ДД.ММ.РРРР:')
            log_text = ''
            finish_function = False
    else:
        return  # This should never happen

    saved_message = edit_employee_data[message.chat.id]['saved_message']
    bot.delete_message(message.chat.id, message.message_id)
    if edit_employee_data[message.chat.id].get('error_message'):
        error_message = edit_employee_data[message.chat.id]['error_message']
        bot.delete_message(message.chat.id, error_message.message_id)
        del edit_employee_data[message.chat.id]['error_message']
    else:
        bot.delete_message(message.chat.id, saved_message.message_id)

    if not finish_function:
        markup = edit_employee_data[message.chat.id]['saved_markup']
        error_message = bot.send_message(message.chat.id, result_message_text, reply_markup=markup, parse_mode='HTML')
        edit_employee_data[message.chat.id]['error_message'] = error_message
    else:
        with DatabaseConnection() as (conn, cursor):
            cursor.execute(f'UPDATE employees SET {column} = %s WHERE id = %s '
                           f'RETURNING crm_id, name, phone, position, telegram_user_id, telegram_username, email',
                           (new_value, employee_id))
            crm_id, name, phone, position, telegram_user_id, telegram_username, email = cursor.fetchone()
            if telegram_user_id is not None:
                cursor.execute('UPDATE employees SET telegram_user_id = %s WHERE id = %s',
                               (telegram_user_id, employee_id))
            conn.commit()

        update_employee_in_crm(crm_id, name, phone, position, telegram_user_id, telegram_username, email)

        bot.send_message(message.chat.id, result_message_text, parse_mode='HTML')
        bot.send_message(message.chat.id, text=saved_message.text, reply_markup=saved_message.reply_markup,
                         parse_mode='HTML')

        del process_in_progress[message.chat.id]
        del edit_employee_data[message.chat.id]
        print(log_text)


@bot.callback_query_handler(func=lambda call: call.data.startswith('del_dob_'))
@authorized_only(user_type='admins')
def delete_date_of_birth(call):
    employee_id = int(call.data.split('_')[2])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('UPDATE employees SET date_of_birth = NULL WHERE id = %s RETURNING name', (employee_id,))
        employee_name = cursor.fetchone()[0]
        conn.commit()
    markup = call.message.reply_markup

    new_markup = types.InlineKeyboardMarkup()
    back_button = markup.keyboard[0][0]
    back_button.text = '🔙 Назад'

    new_markup.add(back_button)
    bot.edit_message_text(f'✅ Дату народження контакту <b>{employee_name}</b> видалено.', call.message.chat.id,
                          call.message.message_id, parse_mode='HTML', reply_markup=new_markup)
    print(f'Employee {employee_id} date of birth deleted by {call.from_user.username}.')
    del process_in_progress[call.message.chat.id]
    del edit_employee_data[call.from_user.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
@authorized_only(user_type='admins')
def delete_employee(call):
    if call.data.startswith('delete_s'):
        search_query, employee_id = call.data.split('_')[2:]
        employee_id = int(employee_id)

        cancel_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
        confirm_btn_callback = f'confirm_delete_s_{employee_id}'

    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[1:])

        cancel_btn_callback = (f'edit_emp_{additional_instance}_{department_id}_{intermediate_department_id}_'
                               f'{sub_department_id}_{employee_id}')
        confirm_btn_callback = (f'confirm_delete_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                f'{sub_department_id}_{employee_id}')

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data=cancel_btn_callback)
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення', callback_data=confirm_btn_callback)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(confirm_btn, cancel_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    bot.edit_message_text(f'Ви впевнені, що хочете видалити контакт <b>{employee_name}</b>?', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
@authorized_only(user_type='admins')
def confirm_delete_employee(call):
    if call.data.startswith('confirm_delete_s'):
        employee_id = int(call.data.split('_')[3])

        back_btn_callback = 'back_to_send_contacts'

    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])

        back_btn_callback = (f'sub_dep_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}')

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, telegram_user_id FROM employees WHERE id = %s', (employee_id,))
        employee_name, telegram_user_id = cursor.fetchone()
        cursor.execute('DELETE FROM employees WHERE id = %s RETURNING crm_id', (employee_id,))
        crm_id = cursor.fetchone()[0]
        conn.commit()
        cursor.execute('SELECT chat_id, chat_name from telegram_chats')
        chats = cursor.fetchall()

    delete_employee_from_crm(crm_id)

    print(f'Employee {employee_name} deleted by {call.from_user.username}.')
    update_authorized_users(authorized_ids)

    successful_chats = []

    for chat_id, chat_name in chats:
        try:
            remove_user_from_chat(bot, chat_id, telegram_user_id)
        except Exception as e:
            print(f'Error while removing user from chat: {e}')
            continue
        successful_chats.append(chat_name)

    message = f'✅ Контакт <b>{employee_name}</b> видалено.'

    if successful_chats:
        chat_list = ', '.join(successful_chats)
        message += f'\n\nКонтакт також було видалено з чатів: <b>{chat_list}</b>.'

    bot.edit_message_text(message, call.message.chat.id,
                          call.message.message_id, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_send_contacts')
@authorized_only(user_type='users')
def back_to_send_contacts_menu(call):
    send_contacts_menu(call.message, edit_message=True)
    if process_in_progress.get(call.message.chat.id) == 'search':
        del process_in_progress[call.message.chat.id]


@bot.message_handler(func=lambda message: message.text == '📜 Меню подяк')
@authorized_only(user_type='users')
def thanks_menu(message):
    markup = types.InlineKeyboardMarkup()
    show_my_thanks_button = types.InlineKeyboardButton(text='🔍 Мої подяки', callback_data='show_my_thanks')
    markup.add(show_my_thanks_button)

    if message.chat.id in authorized_ids['moderators'] or message.chat.id in authorized_ids['admins']:
        show_thanks_button = types.InlineKeyboardButton(text='🔍 Передивитись подяки', callback_data='show_thanks')
        send_thanks_button = types.InlineKeyboardButton(text='📜 Надіслати подяку', callback_data='send_thanks')
        markup.add(show_thanks_button, send_thanks_button, row_width=1)

    sent_message = bot.send_message(message.chat.id, '🔽 Оберіть дію:',
                                    reply_markup=markup)
    make_card_data[message.chat.id]['sent_message'] = sent_message


@bot.callback_query_handler(func=lambda call: call.data == 'show_thanks')
@authorized_only(user_type='moderators')
def show_thanks(call):
    week_thanks_button = types.InlineKeyboardButton(text='📅 За тиждень', callback_data='time_thanks_week')
    month_thanks_button = types.InlineKeyboardButton(text='📅 За місяць', callback_data='time_thanks_month')
    year_thanks_button = types.InlineKeyboardButton(text='📅 За рік', callback_data='time_thanks_year')
    all_thanks_button = types.InlineKeyboardButton(text='📅 Всі', callback_data='time_thanks_all')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(week_thanks_button, month_thanks_button, year_thanks_button, all_thanks_button)
    bot.edit_message_text('🔍 Оберіть період:', call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'show_my_thanks')
@authorized_only(user_type='users')
def show_my_thanks(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM employees WHERE telegram_user_id = %s', (call.from_user.id,))
        employee_id = cursor.fetchone()[0]
        cursor.execute('SELECT name, position FROM employees WHERE id = %s', (employee_id,))
        employee_name, employee_position = cursor.fetchone()
        cursor.execute('SELECT id, commendation_text, commendation_date FROM commendations WHERE employee_to_id = %s',
                       (employee_id,))
        commendations = cursor.fetchall()

    if not commendations:
        bot.edit_message_text('🔍 У вас немає подяк.', call.message.chat.id, call.message.message_id)
        return

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='thanks_menu')
    markup = types.InlineKeyboardMarkup()
    for commendation_id, commendation_text, commendation_date in commendations:
        formatted_date = commendation_date.strftime('%d.%m.%Y')
        message_text = f'👨‍💻 {employee_name} | {formatted_date}\n\n{commendation_text}'
        markup.add(types.InlineKeyboardButton(text=message_text, callback_data=f'commendation_{commendation_id}'))

    markup.add(back_btn)
    bot.edit_message_text(f'📜 Ваші подяки:', call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_thanks_'))
@authorized_only(user_type='moderators')
def show_thanks_period(call):
    data = call.data.split('_')
    period = data[2]
    page = int(data[3]) if len(data) > 3 else 1
    today = datetime.date.today()

    if period == 'week':
        start_date = today - datetime.timedelta(days=7)
    elif period == 'month':
        start_date = today.replace(day=1)
    elif period == 'year':
        start_date = today.replace(day=1, month=1)
    else:
        start_date = None

    with DatabaseConnection() as (conn, cursor):
        if start_date:
            cursor.execute(
                'SELECT commendations.id, name, commendations.position, commendation_text, commendation_date '
                'FROM commendations '
                'JOIN employees ON employee_to_id = employees.id '
                'WHERE commendation_date >= %s', (start_date,)
            )
        else:
            cursor.execute(
                'SELECT commendations.id, name, commendations.position, commendation_text, commendation_date '
                'FROM commendations '
                'JOIN employees ON employee_to_id = employees.id'
            )
        commendations = cursor.fetchall()

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='show_thanks')
    markup = types.InlineKeyboardMarkup()

    if not commendations:
        markup.add(back_btn)
        bot.edit_message_text('🔍 Подяк немає.', call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
        return

    total_pages = math.ceil(len(commendations) / COMMENDATIONS_PER_PAGE)
    start_index = (page - 1) * COMMENDATIONS_PER_PAGE
    end_index = start_index + COMMENDATIONS_PER_PAGE
    commendations_page = commendations[start_index:end_index]

    for commendation in commendations_page:
        commendation_id, employee_name, employee_position, _, commendation_date = commendation
        formatted_date = commendation_date.strftime('%d.%m.%Y')
        split_name = employee_name.split()
        formatted_name = f'{split_name[0]} {split_name[1][0]}'
        button_text = f'👨‍💻 {formatted_name} | {formatted_date}'
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f'commendation_{commendation_id}'))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            types.InlineKeyboardButton(text='⬅️', callback_data=f'time_thanks_{period}_{page - 1}'))
    if page < total_pages:
        nav_buttons.append(
            types.InlineKeyboardButton(text='➡️', callback_data=f'time_thanks_{period}_{page + 1}'))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(back_btn)
    bot.edit_message_text(f'📜 Подяки ({page}/{total_pages}):', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('commendation_'))
@authorized_only(user_type='moderators')
def show_commendation(call):
    commendation_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT e_to.name, commendations.position, commendation_text, commendation_date, e_from.name '
            'FROM commendations '
            'JOIN employees e_to ON employee_to_id = e_to.id '
            'JOIN employees e_from ON employee_from_id = e_from.id '
            'WHERE commendations.id = %s', (commendation_id,)
        )
        employee_name, employee_position, commendation_text, commendation_date, employee_from_name = cursor.fetchone()

    formatted_date = commendation_date.strftime('%d.%m.%Y')
    image = make_card(employee_name, employee_position, commendation_text)
    message_text = (f'👨‍💻 <b>{employee_name}</b> | {formatted_date}\n\nВід <b>{employee_from_name}</b>'
                    f'\n{commendation_text}')
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити', callback_data=f'delcommendation_{commendation_id}')
    hide_btn = types.InlineKeyboardButton(text='❌ Сховати', callback_data='hide_message')
    markup = types.InlineKeyboardMarkup()
    markup.add(delete_btn, hide_btn)
    bot.send_photo(call.message.chat.id, image, caption=message_text, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('delcommendation_'))
@authorized_only(user_type='admins')
def delete_commendation(call):
    commendation_id = int(call.data.split('_')[1])
    confirm_delete_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                                    callback_data=f'cdcommendation_{commendation_id}')
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data=f'commendation_{commendation_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(confirm_delete_btn, back_btn)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cdcommendation_'))
@authorized_only(user_type='admins')
def confirm_delete_commendation(call):
    commendation_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM commendations WHERE id = %s', (commendation_id,))
        conn.commit()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    print(f'Commendation {commendation_id} deleted by {call.from_user.username}.')
    bot.send_message(call.message.chat.id, '✅ Подяку видалено.')


@bot.callback_query_handler(func=lambda call: call.data == 'hide_message')
@authorized_only(user_type='users')
def hide_message(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'send_thanks')
@authorized_only(user_type='moderators')
def send_thanks(call):
    process_in_progress[call.message.chat.id] = 'thanks_search'

    if make_card_data.get(call.message.chat.id):
        del make_card_data[call.message.chat.id]

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_thanks')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    sent_message = bot.edit_message_text('📝 Введіть ім\'я співробітника для пошуку:',
                                         call.message.chat.id, call.message.message_id, reply_markup=markup)
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'thanks_search')
@authorized_only(user_type='moderators')
def proceed_thanks_search(message):
    search_query = message.text
    found_contacts = find_contact_by_name(search_query)
    sent_message = make_card_data[message.chat.id]['sent_message']
    if found_contacts:
        markup = types.InlineKeyboardMarkup(row_width=1)

        for employee_info in found_contacts:
            employee_id = employee_info[0]
            employee_name = employee_info[1]
            employee_position = employee_info[2]

            formatted_name = employee_name.split()
            formatted_name = f'{formatted_name[0]} {formatted_name[1]}'
            btn = types.InlineKeyboardButton(text=f'👨‍💻 {formatted_name} - {employee_position}',
                                             callback_data=f'thanks_{employee_id}')
            markup.add(btn)
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_thanks')
        markup.add(cancel_btn)
        bot.delete_message(message.chat.id, message.message_id)
        sent_message = bot.edit_message_text('🔍 Оберіть співробітника:', message.chat.id, sent_message.message_id,
                                             reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('thanks_'))
@authorized_only(user_type='moderators')
def proceed_send_thanks(call):
    employee_id = int(call.data.split('_')[1])
    process_in_progress[call.message.chat.id] = 'send_thanks'
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, position, telegram_user_id FROM employees WHERE id = %s', (employee_id,))
        employee_data = cursor.fetchone()
    employee_name = employee_data[0]
    employee_position = employee_data[1]
    employee_telegram_id = employee_data[2]
    make_card_data[call.message.chat.id]['employee_id'] = employee_id
    make_card_data[call.message.chat.id]['employee_position'] = employee_position
    make_card_data[call.message.chat.id]['employee_telegram_id'] = employee_telegram_id
    sent_message = bot.edit_message_text(
        f'📝 Введіть ім\'я для співробітника <b>{employee_name}</b> у давальному відмінку:',
        call.message.chat.id, call.message.message_id, parse_mode='HTML')
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'send_thanks')
@authorized_only(user_type='moderators')
def send_thanks_name(message, position_changed=False):
    data_filled = False

    if not make_card_data[message.chat.id].get('employee_name'):
        make_card_data[message.chat.id]['employee_name'] = message.text
        sent_message = make_card_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        bot.edit_message_text('📝 Введіть текст подяки:', message.chat.id, sent_message.message_id)

    elif not make_card_data[message.chat.id].get('thanks_text'):
        make_card_data[message.chat.id]['thanks_text'] = message.text
        sent_message = make_card_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, sent_message.message_id)
        data_filled = True

    if data_filled or position_changed:
        image = make_card(make_card_data[message.chat.id]['employee_name'],
                          make_card_data[message.chat.id]['employee_position'],
                          make_card_data[message.chat.id]['thanks_text'])
        make_card_data[message.chat.id]['image'] = image

        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити', callback_data='confirm_send_thanks')
        position_change_btn = types.InlineKeyboardButton(text='🔄 Змінити посаду', callback_data='com_change_position')
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_thanks')
        markup.add(confirm_btn, cancel_btn, position_change_btn)

        sent_message = bot.send_photo(message.chat.id, image, caption='📝 Перевірте подяку:', reply_markup=markup)
        make_card_data[message.chat.id]['sent_message'] = sent_message


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_send_thanks')
@authorized_only(user_type='moderators')
def confirm_send_thanks(call):
    sent_message = make_card_data[call.message.chat.id]['sent_message']
    bot.delete_message(call.message.chat.id, sent_message.message_id)
    recipient_id = make_card_data[call.message.chat.id]['employee_telegram_id']
    image = make_card_data[call.message.chat.id]['image']

    employee_id = make_card_data[call.message.chat.id]['employee_id']
    commendation_text = make_card_data[call.message.chat.id]['thanks_text']
    employee_position = make_card_data[call.message.chat.id]['employee_position']
    commendation_date = datetime.datetime.now().date()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM employees WHERE telegram_user_id = %s', (call.message.chat.id,))
        sender_id = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO commendations (employee_to_id, employee_from_id, commendation_text, commendation_date, position) '
            'VALUES (%s, %s, %s, %s, %s)',
            (employee_id, sender_id, commendation_text, commendation_date, employee_position)
        )
        conn.commit()

    try:
        bot.send_photo(recipient_id, image, caption='📩 Вам було надіслано подяку.')
    except apihelper.ApiTelegramException as e:
        if e.error_code == 400 and "chat not found" in e.description:
            bot.send_message(call.message.chat.id, '🚫 Користувач не знайдений. Надслисаю подяку як юзербот.')
            print('Sending image to user failed. Chat not found. Trying to send image as user.')
            asyncio.run(send_photo(recipient_id, image, caption='📩 Вам надіслано подяку.'))

    bot.send_photo(call.message.chat.id, image, caption='✅ Подяку надіслано.')

    del make_card_data[call.message.chat.id]
    if process_in_progress.get(call.message.chat.id):
        del process_in_progress[call.message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'com_change_position')
@authorized_only(user_type='moderators')
def com_change_position(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    process_in_progress[call.message.chat.id] = 'com_change_position'
    sent_message = bot.send_message(call.message.chat.id, '💼 Введіть нову посаду:')
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'com_change_position')
@authorized_only(user_type='moderators')
def com_change_position_ans(message):
    make_card_data[message.chat.id]['employee_position'] = message.text
    sent_message = make_card_data[message.chat.id]['sent_message']
    bot.delete_message(message.chat.id, message.message_id)
    bot.delete_message(message.chat.id, sent_message.message_id)

    del process_in_progress[message.chat.id]

    send_thanks_name(message, position_changed=True)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_send_thanks')
@authorized_only(user_type='moderators')
def cancel_send_thanks(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, '🚪 Створення подяки скасовано.')
    del make_card_data[call.message.chat.id]
    del process_in_progress[call.message.chat.id]


@bot.message_handler(func=lambda message: message.text == '💭 Зауваження по роботі боту')
@authorized_only(user_type='users')
def send_form(message):
    form_url = ('https://docs.google.com/forms/d/e/1FAIpQLSfcoy2DMzrZRtLzf8wzfDEZnk-4yIsL9uUBK5kOFBs0Q8N0dA/'
                'viewform?usp=sf_link')
    send_question_form(message, form_url)


# Temporary disabled
# @bot.message_handler(func=lambda message: message.text == '💭 Маєш питання?')
# @authorized_only(user_type='users')
# def ai_question(message):
#     openai_data[message.chat.id]['thread'] = client.beta.threads.create()
#     process_in_progress[message.chat.id] = 'ai_question'
#     cancel_btn = types.InlineKeyboardButton(text='🚪 Завершити сесію', callback_data='cancel_ai_question')
#     markup = types.InlineKeyboardMarkup()
#     markup.add(cancel_btn)
#     sent_message = bot.send_message(message.chat.id, '🤖 Сесію зі штучним інтелектом розпочато. Задайте своє питання.',
#                                     reply_markup=markup)
#     openai_data[message.chat.id]['sent_message'] = sent_message


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(message.chat.id) == 'ai_question')
@authorized_only(user_type='users')
def proceed_ai_question(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE telegram_user_id = %s', (message.from_user.id,))
        employee_name = cursor.fetchone()[0]
    employee_name = employee_name.split()[1]
    thread = openai_data[message.chat.id]['thread']
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role='user',
        content=message.text
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions=f'Please address the user as {employee_name} and call him by his name.',
    )
    bot.edit_message_reply_markup(message.chat.id, openai_data[message.chat.id]['sent_message'].message_id)
    sent_message = bot.send_message(message.chat.id, '🔄 Генерація відповіді...')
    openai_data[message.chat.id]['sent_message'] = sent_message
    ai_timer = time.time()

    cancel_btn = types.InlineKeyboardButton(text='🚪 Завершити сесію', callback_data='cancel_ai_question')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)

    while client.beta.threads.runs.retrieve(run_id=run.id, thread_id=thread.id).status != 'completed':
        if time.time() - ai_timer > 30:
            bot.edit_message_text('⚠️ Відповідь не знайдена. Спробуйте ще раз.', message.chat.id,
                                  sent_message.message_id, reply_markup=markup)
            return
        sleep(1)

    response = client.beta.threads.messages.list(
        thread_id=thread.id,
        limit=1
    )
    bot.edit_message_text(response.data[0].content[0].text.value, message.chat.id, sent_message.message_id,
                          reply_markup=markup, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_ai_question')
@authorized_only(user_type='users')
def cancel_ai_question(call):
    thread = openai_data[call.message.chat.id]['thread']
    client.beta.threads.delete(thread_id=thread.id)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, '🚪 Сесію зі штучним інтелектом завершено.')
    del process_in_progress[call.message.chat.id]
    del openai_data[call.message.chat.id]


def send_question_form(message, form_url, delete_previous_message=False, disable_fill_form=False):
    if process_in_progress.get(message.chat.id) == 'question_form':
        delete_messages(message.chat.id, 'form_messages_to_delete')
    process_in_progress[message.chat.id] = 'question_form'
    # Temporary disabled
    try:
        if disable_fill_form:
            raise gforms.errors.SigninRequired(form_url)
        gform = FormFiller(form_url)
    except gforms.errors.SigninRequired:
        link_btn = types.InlineKeyboardButton(text='🔗 Посилання на форму', url=form_url)
        markup = types.InlineKeyboardMarkup()
        markup.add(link_btn)
        bot.send_message(message.chat.id, 'Натисніть кнопку нижче щоб перейти за посиланням.',
                         reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_form_filling')
    markup.add(btn)

    sent_message = bot.send_message(message.chat.id,
                                    f'{gform.title()}\n\n{gform.description() if gform.description() else ""}',
                                    reply_markup=markup)
    user_data['form_messages_to_delete'][message.chat.id] = [sent_message.message_id]
    if delete_previous_message:
        user_data['form_messages_to_delete'][message.chat.id].append(message.message_id)

    def get_answer():
        try:
            gform.fill_form(
                lambda element, page_index, element_index: callback(element, page_index, element_index,
                                                                    sent_message)
            )
            bot.edit_message_text(sent_message.text, sent_message.chat.id, sent_message.message_id)
            bot.send_message(sent_message.chat.id,
                             '✅ Дякую за заповнення форми! Ваше питання буде розглянуто найближчим часом.')
            del user_data['form_messages_to_delete'][message.chat.id]
        except ValueError:
            pass

    thread = threading.Thread(target=get_answer)
    thread.start()


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_form_filling')
@authorized_only(user_type='users')
def cancel_form_filling(call):
    if process_in_progress.get(call.message.chat.id) == 'question_form':
        del process_in_progress[call.message.chat.id]


@bot.message_handler(func=lambda message: process_in_progress.get(message.chat.id) == 'temp_authorization',
                     content_types=['contact'])
@authorized_only(user_type='admins')
def temp_authorize_user_by_contact(message):
    new_user_id = message.contact.user_id
    if new_user_id not in authorized_ids['users'] and new_user_id not in authorized_ids['temp_users']:
        authorized_ids['temp_users'].add(new_user_id)

        try:
            bot.send_message(new_user_id, f'Вас тимчасово авторизовано адміністратором @{message.from_user.username}.')

            log_text = (f'User {new_user_id} temporarily authorized by @{message.from_user.username} with notification.'
                        f'\nTemporarily authorized users: {authorized_ids["temp_users"]}')
        except apihelper.ApiTelegramException:
            log_text = (
                f'User {new_user_id} temporarily authorized by @{message.from_user.username} without notification.'
                f'\nTemporarily authorized users: {authorized_ids["temp_users"]}')

        print(log_text)

        bot.send_message(message.chat.id, f'✅ Користувача <b>{message.contact.first_name}</b> авторизовано.',
                         parse_mode='HTML')

    else:
        bot.send_message(message.chat.id, f'🚫 Помилка авторизації:'
                                          f'\nКористувач <b>{message.contact.first_name}</b> вже авторизований.',
                         parse_mode='HTML')
    del process_in_progress[message.chat.id]


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(
        message.chat.id) == 'question_form')
@authorized_only(user_type='users')
def callback_ans(message):
    user_data['forms_ans'][message.chat.id] = message.text
    user_data['form_messages_to_delete'][message.chat.id].append(message.id)


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(message.chat.id) == 'search')
@authorized_only(user_type='users')
def proceed_contact_search(message, edit_message=False):
    if not edit_message:
        delete_messages(message.chat.id)

    found_contacts = find_contact_by_name(message.text)

    if found_contacts:
        markup = types.InlineKeyboardMarkup()

        for employee_info in found_contacts:
            employee_id = employee_info[0]
            employee_name = employee_info[1]
            employee_position = employee_info[2]

            formatted_name = employee_name.split()
            formatted_name = f'{formatted_name[0]} {formatted_name[1]}'
            btn = types.InlineKeyboardButton(text=f'👨‍💻 {formatted_name} - {employee_position}',
                                             callback_data=f'profile_s_{message.text}_{employee_id}')
            markup.add(btn)

        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
        markup.row(back_btn)

        if edit_message:
            bot.edit_message_text('🔎 Знайдені співробітники:', message.chat.id, message.message_id,
                                  reply_markup=markup)
        else:
            try:
                bot.send_message(message.chat.id, '🔎 Знайдені співробітники:', reply_markup=markup)
            except apihelper.ApiTelegramException:
                back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='search')
                markup = types.InlineKeyboardMarkup()
                markup.add(back_btn)
                sent_message = bot.send_message(message.chat.id, '🚫 Повідомлення занадто довге для відправки.'
                                                                 '\nСпробуйте виконати пошук знову.',
                                                reply_markup=markup)
                user_data['messages_to_delete'][message.chat.id] = sent_message.message_id

    else:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
        markup = types.InlineKeyboardMarkup()
        markup.add(back_btn)

        sent_message = bot.send_message(message.chat.id, '🚫 Співробітник не знайдений', reply_markup=markup)
        user_data['messages_to_delete'][message.chat.id] = sent_message.message_id


def main():
    if test_connection():
        update_authorized_users(authorized_ids)
        bot.infinity_polling()


if __name__ == '__main__':
    main()
