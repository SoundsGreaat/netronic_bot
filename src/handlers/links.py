import re
from time import sleep

from telebot import types

from src.config import bot, process_in_progress, add_link_data, user_data, edit_link_data
from src.database import DatabaseConnection
from src.handlers.authorization import authorized_only
from src.handlers.main_menu import send_business_processes
from src.integrations.crm_api_functions import get_employee_pass_from_crm
from src.integrations.google_forms_filler import send_question_form
from src.utils import button_names
from src.utils.messages import send_links


@bot.callback_query_handler(func=lambda call: call.data.startswith('b_process_'))
@authorized_only(user_type='users')
def send_business_process(call):
    split_data = call.data.split('_', 2)
    process_name = '_'.join(split_data[2:])
    send_links(call.message, process_name, edit_message=True, show_back_btn=True)


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
