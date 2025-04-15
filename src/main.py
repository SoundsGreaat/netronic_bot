import math
import os
import re
import threading
import asyncio
import time
import datetime

from time import sleep
from telebot import types, apihelper
from rapidfuzz import process
from src.config import authorized_ids, user_data, edit_employee_data, add_keyword_data, add_director_data, \
    add_employee_data, openai_data, make_card_data, add_sub_department_data, \
    process_in_progress, COMMENDATIONS_PER_PAGE, month_dict, client, assistant_id, bot, fernet_key
from src.handlers import *
from src.integrations import *
from src.database import *
from src.utils import *


@bot.message_handler(content_types=['new_chat_members'])
def new_member_handler(message):
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('INSERT INTO telegram_chats (chat_id, chat_name) VALUES (%s, %s) ',
                               (message.chat.id, message.chat.title))
                conn.commit()


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


@bot.callback_query_handler(func=lambda call: call.data.startswith('additional_'))
@authorized_only(user_type='users')
def send_inter_department_contacts(call):
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
                                         callback_data=f'dep_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}')
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
    if process_in_progress.get(call.message.chat.id) == 'add_director':
        del process_in_progress[call.message.chat.id]
        del add_director_data[call.message.chat.id]
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

    add_director = True

    for sub_department in sub_departments:
        sub_department_id = sub_department[0]
        sub_department_name = sub_department[1]
        sub_department_is_chief = sub_department[2]
        if sub_department_is_chief:
            add_director = False

        emoji = '👔' if sub_department_is_chief else '🗄️'
        btn = types.InlineKeyboardButton(text=f'{emoji} {sub_department_name}',
                                         callback_data=f'sub_dep_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}_{sub_department_id}')
        buttons.append(btn)
    if additional_instance:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'additional_{additional_instance}_{department_id}')
    else:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    if add_director:
        add_director_btn = types.InlineKeyboardButton(text='➕ Додати керівника департаменту',
                                                      callback_data=f'add_dir_{additional_instance}_{department_id}_'
                                                                    f'{intermediate_department_id}')
    else:
        add_director_btn = types.InlineKeyboardButton(text='🗑️ Видалити керівника департаменту',
                                                      callback_data=f'del_dir_{additional_instance}_{department_id}_'
                                                                    f'{intermediate_department_id}')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    if call.message.chat.id in authorized_ids['admins']:
        markup.row(add_director_btn)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_dir_'))
@authorized_only(user_type='admins')
def add_director(call):
    additional_instance, department_id, intermediate_department_id = map(int, call.data.split('_')[2:])
    process_in_progress[call.message.chat.id] = 'add_director'
    add_director_data[call.message.chat.id]['department_id'] = department_id
    add_director_data[call.message.chat.id]['additional_instance'] = additional_instance
    add_director_data[call.message.chat.id]['intermediate_department_id'] = intermediate_department_id
    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'dep_{additional_instance}_{department_id}_'
                                                          f'{intermediate_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, '👤 Введіть назву посади керівника'
                                                          '\n Наприклад: <i>Виконавчий директор</i>',
                                    reply_markup=markup, parse_mode='HTML')
    add_director_data[call.message.chat.id]['saved_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_director')
@authorized_only(user_type='admins')
def proceed_add_director(message):
    department_id = add_director_data[message.chat.id]['department_id']
    additional_instance = add_director_data[message.chat.id]['additional_instance']
    intermediate_department_id = add_director_data[message.chat.id]['intermediate_department_id']
    sent_message = add_director_data[message.chat.id]['saved_message']
    if not additional_instance:
        intermediate_department_id = None
    director_position = message.text
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''INSERT INTO sub_departments (name, is_chief_department, department_id,
                           intermediate_department_id)
                           VALUES (%s, %s, %s, %s) RETURNING id''',
                       (director_position, True, department_id, intermediate_department_id))
        conn.commit()
    del process_in_progress[message.chat.id]
    del add_director_data[message.chat.id]
    back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                          callback_data=f'dep_{additional_instance}_{department_id}_'
                                                        f'{intermediate_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)
    bot.delete_message(message.chat.id, sent_message.message_id)
    bot.send_message(message.chat.id, f'✅ Керівника департаменту успішно додано.', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_dep_'))
@authorized_only(user_type='users')
def send_sub_departments_contacts(call):
    additional_instance, department_id, intermediate_department_id, sub_department_id = map(int,
                                                                                            call.data.split('_')[2:])
    markup = types.InlineKeyboardMarkup(row_width=1)

    with DatabaseConnection() as (conn, cursor):
        query = '''
            SELECT DISTINCT e.id, e.name
            FROM employees e
            LEFT JOIN additional_sub_departments ad ON e.sub_department_id = ad.sub_department_id
            WHERE e.sub_department_id = %s
    
            UNION
    
            SELECT DISTINCT e.id, e.name
            FROM employees e
            INNER JOIN additional_sub_departments ad ON e.id = ad.employee_id
            WHERE ad.sub_department_id = %s
            
            ORDER BY name
        '''
        cursor.execute(query, (sub_department_id, sub_department_id))
        employees = cursor.fetchall()

    for employee in employees:
        employee_id = employee[0]
        employee_name = employee[1]

        btn = types.InlineKeyboardButton(text=f'👨‍💻 {employee_name}',
                                         callback_data=f'profile_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}_{sub_department_id}_'
                                                       f'{employee_id}')
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('bck_srch_'))
@authorized_only(user_type='users')
def back_to_search_results(call):
    call.message.text = '_'.join(call.data.split('_')[2:])
    proceed_contact_search(call.message, edit_message=True)


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
    else:
        return

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
                result_message_text = (f'✅ Дату народження контакту <b>{employee_name}</b> змінено на '
                                       f'<b>{new_value.strftime("%d/%m/%Y")}</b>.')
                log_text = (f'Employee {employee_id} date of birth changed to {new_value} by '
                            f'{message.from_user.username}.')
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
            crm_id, name, phone, position, telegram_user_id_crm, telegram_username, email = cursor.fetchone()
            if column == 'telegram_username':
                cursor.execute('UPDATE employees SET telegram_user_id = %s WHERE id = %s',
                               (telegram_user_id, employee_id))
                print(f'Employee {employee_id} telegram_user_id changed to {telegram_user_id} by '
                      f'{message.from_user.username}.')
                telegram_user_id_crm = telegram_user_id
            conn.commit()

            if column == 'telegram_username':
                update_authorized_users(authorized_ids)

        update_employee_in_crm(crm_id, name, phone, position, telegram_user_id_crm, telegram_username, email)

        bot.send_message(message.chat.id, result_message_text, parse_mode='HTML')
        bot.send_message(message.chat.id, text=saved_message.text, reply_markup=saved_message.reply_markup,
                         parse_mode='HTML')

        del process_in_progress[message.chat.id]
        del edit_employee_data[message.chat.id]
        print(log_text)


@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_add_'))
@authorized_only(user_type='admins')
def manage_additional_departments(call):
    employee_id, edit_message = call.data.split('_')[2:]
    employee_id = int(employee_id)
    edit_message = True if edit_message == 'True' else False

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT sub_departments.name, additional_sub_departments.id '
                       'FROM additional_sub_departments '
                       'JOIN sub_departments ON additional_sub_departments.sub_department_id = sub_departments.id '
                       'WHERE additional_sub_departments.employee_id = %s', (employee_id,))
        additional_sub_departments = cursor.fetchall()

    markup = types.InlineKeyboardMarkup(row_width=1)
    if additional_sub_departments:
        for sub_department_name, add_sub_department_id in additional_sub_departments:
            show_sub_department_btn = types.InlineKeyboardButton(text=f'🗄️ {sub_department_name}',
                                                                 callback_data=f'manage_subdep_{employee_id}_'
                                                                               f'{add_sub_department_id}')
            markup.add(show_sub_department_btn)

        message_text = 'Додаткові відділи:'
    else:
        message_text = 'Додаткові відділи відсутні.'
    add_sub_department_btn = types.InlineKeyboardButton(text='➕ Додати відділ',
                                                        callback_data=f'add_subdep_{employee_id}')
    markup.add(add_sub_department_btn)
    if edit_message:
        bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
        print(1)
    else:
        bot.send_message(call.message.chat.id, message_text, reply_markup=markup)
        print(2)


@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_subdep_'))
@authorized_only(user_type='admins')
def manage_sub_department(call):
    employee_id, add_sub_department_id = map(int, call.data.split('_')[2:])

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT sub_departments.name, additional_sub_departments.position, employees.name '
                       'FROM additional_sub_departments '
                       'JOIN sub_departments ON additional_sub_departments.sub_department_id = sub_departments.id '
                       'JOIN employees ON additional_sub_departments.employee_id = employees.id '
                       'WHERE additional_sub_departments.id = %s AND additional_sub_departments.employee_id = %s',
                       (add_sub_department_id, employee_id))
        sub_department_name, position, employee_name = cursor.fetchone()

    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'manage_add_{employee_id}_{True}')
    delete_sub_department_btn = types.InlineKeyboardButton(text='🗑️ Видалити відділ',
                                                           callback_data=f'del_subdep_{employee_id}_'
                                                                         f'{add_sub_department_id}')
    markup.add(delete_sub_department_btn, back_btn)
    bot.edit_message_text(f'🗄️ {sub_department_name} ({position}) для контакту <b>{employee_name}</b>',
                          call.message.chat.id,
                          call.message.message_id, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_subdep_'))
@authorized_only(user_type='admins')
def add_sub_department(call):
    employee_id = int(call.data.split('_')[2])

    process_in_progress[call.message.chat.id] = 'add_sub_department'
    if add_sub_department_data.get(call.message.chat.id):
        del add_sub_department_data[call.message.chat.id]

    add_sub_department_data[call.message.chat.id]['employee_id'] = employee_id
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, '🗄️ Введіть приблизну назву відділу:')
    add_sub_department_data[call.message.chat.id]['saved_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_sub_department')
@authorized_only(user_type='admins')
def add_sub_department_ans(message):
    employee_id = add_sub_department_data[message.chat.id]['employee_id']
    bot.delete_message(message.chat.id, message.message_id)
    bot.delete_message(message.chat.id, add_sub_department_data[message.chat.id]['saved_message'].message_id)

    if not add_sub_department_data[message.chat.id].get('sub_department_id'):
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id, name FROM sub_departments')
            sub_departments = cursor.fetchall()
            original_sub_departments = [(sub_department[0], sub_department[1].strip()) for sub_department in
                                        sub_departments]
            sub_departments = [(id, name.lower()) for id, name in original_sub_departments]

        query = message.text.lower()
        best_match = process.extractOne(query, [name for id, name in sub_departments])
        original_best_match = next((id, name) for id, name in original_sub_departments if name.lower() == best_match[0])

        sub_department_id = original_best_match[0]
        sub_department_name = original_best_match[1]
        add_sub_department_data[message.chat.id]['sub_department_id'] = sub_department_id

        sent_message = bot.send_message(message.chat.id,
                                        f'Обрано відділ <b>{sub_department_name}</b> ({best_match[1]:.1f}%)'
                                        f'\nВведіть посаду для відділу:',
                                        parse_mode='HTML')
        add_sub_department_data[message.chat.id]['saved_message'] = sent_message

    elif not add_sub_department_data[message.chat.id].get('position'):
        position = message.text
        sub_department_id = add_sub_department_data[message.chat.id]['sub_department_id']
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('''
            INSERT INTO additional_sub_departments (employee_id, sub_department_id, position)
            VALUES (%s, %s, %s) 
            
            RETURNING (
            SELECT name 
            FROM sub_departments
            WHERE sub_departments.id = additional_sub_departments.sub_department_id)
            ''',
                           (employee_id, sub_department_id, position))
            conn.commit()
            sub_department_name = cursor.fetchone()[0]

        bot.send_message(message.chat.id, f'✅ Відділ <b>{sub_department_name}</b> ({position}) додано.',
                         parse_mode='HTML')
        del process_in_progress[message.chat.id]
        del add_sub_department_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('del_subdep_'))
@authorized_only(user_type='admins')
def delete_sub_department(call):
    employee_id, add_sub_department_id = map(int, call.data.split('_')[2:])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM additional_sub_departments WHERE id = %s', (add_sub_department_id,))
        conn.commit()
    call.data = f'manage_add_{employee_id}_{True}'
    manage_additional_departments(call)
    print(f'Employee {call.from_user.username} deleted additional sub_department {add_sub_department_id}.')


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
        cursor.execute('SELECT id, commendation_text, commendation_date FROM commendations WHERE employee_to_id = %s '
                       'ORDER BY commendation_date DESC', (employee_id,))
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
                'WHERE commendation_date >= %s '
                'ORDER BY commendation_date DESC', (start_date,)
            )
        else:
            cursor.execute(
                'SELECT commendations.id, name, commendations.position, commendation_text, commendation_date '
                'FROM commendations '
                'JOIN employees ON employee_to_id = employees.id '
                'ORDER BY commendation_date DESC'
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
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data='hide_message')
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
            'INSERT INTO commendations ('
            'employee_to_id, employee_from_id, commendation_text, commendation_date, position'
            ') '
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





def send_birthday_notification():
    user_ids = os.getenv('BIRTHDAY_NOTIFICATION_USER_IDS').split(',')
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
        message = (f'🎂 Дні народження робітників на {month_dict[month]}:\n\n'
                   + '\n'.join(birthdays))

    for user_id in user_ids:
        bot.send_message(user_id, message)


def main():
    scheduler.add_job(send_birthday_notification, 'cron', day=25, hour=17, minute=0, id='monthly_job',
                      replace_existing=True)
    scheduler.start()

    if test_connection():
        decrypt_session(fernet_key, input_file='../sessions/userbot_session_encrypted',
                        output_file='../sessions/userbot_session.session')
        update_authorized_users(authorized_ids)
        threading.Thread(target=bot.infinity_polling, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == '__main__':
    main()
