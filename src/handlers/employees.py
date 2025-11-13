import asyncio
import datetime
import re

from rapidfuzz import process
from telebot import types

from config import bot, process_in_progress, edit_employee_data, authorized_ids, add_employee_data, add_keyword_data
from database import DatabaseConnection, update_authorized_users
from handlers import authorized_only
from integrations.crm_api_functions import add_employee_to_crm, delete_employee_from_crm, update_employee_in_crm
from integrations.telethon_functions import proceed_find_user_id, remove_user_from_chat
from utils.main_menu_buttons import button_names


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
    sub_department_id = None
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

    if not sub_department_id:
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('''SELECT emp.name,
                                     departments.name     AS department,
                                     sub_departments.name AS sub_department,
                                     emp.position,
                                     emp.phone,
                                     emp.telegram_username,
                                     intermediate_departments.name,
                                     emp.email,
                                     emp.date_of_birth,
                                     emp.work_phone
                              FROM employees as emp
                                       JOIN sub_departments ON emp.sub_department_id = sub_departments.id
                                       JOIN departments ON sub_departments.department_id = departments.id
                                       LEFT JOIN intermediate_departments ON
                                  sub_departments.intermediate_department_id = intermediate_departments.id
                              WHERE emp.id = %s
                           ''', (employee_id,))
            employee_info = cursor.fetchone()

    else:
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('''
                           SELECT emp.name,
                                  CASE
                                      WHEN ad.sub_department_id IS NOT NULL THEN d2.name
                                      ELSE d1.name
                                      END AS department,

                                  CASE
                                      WHEN ad.sub_department_id IS NOT NULL THEN sd2.name
                                      ELSE sd1.name
                                      END AS sub_department,

                                  CASE
                                      WHEN ad.sub_department_id IS NOT NULL THEN ad.position
                                      ELSE emp.position
                                      END AS position,

                                  emp.phone,
                                  emp.telegram_username,
                                  intermediate_departments.name,
                                  emp.email,
                                  emp.date_of_birth,
                                  emp.work_phone
                           FROM employees AS emp
                                    LEFT JOIN sub_departments AS sd1 ON emp.sub_department_id = sd1.id
                                    LEFT JOIN departments AS d1 ON sd1.department_id = d1.id

                                    LEFT JOIN additional_sub_departments AS ad ON emp.id = ad.employee_id
                                    LEFT JOIN sub_departments AS sd2 ON ad.sub_department_id = sd2.id
                                    LEFT JOIN departments AS d2 ON sd2.department_id = d2.id

                                    LEFT JOIN intermediate_departments
                                              ON sd1.intermediate_department_id = intermediate_departments.id

                           WHERE emp.id = %s
                             AND (emp.sub_department_id = %s OR ad.sub_department_id = %s)
                           ''', (employee_id, sub_department_id, sub_department_id))
            employee_info = cursor.fetchone()

    employee_name = employee_info[0]
    employee_department = employee_info[1]
    employee_sub_department = employee_info[2]
    employee_position = employee_info[3]
    employee_phone = employee_info[4]
    employee_username = employee_info[5]
    employee_intermediate_department = employee_info[6]
    employee_email = employee_info[7]
    employee_date_of_birth = employee_info[8].strftime('%d/%m') if employee_info[8] else None
    employee_work_phone = employee_info[9]

    office_string = f'\n<b>🏢 Офіс/служба</b>: {employee_intermediate_department}' if employee_intermediate_department \
        else ''

    sub_department_string = f'\n<b>🗄️ Відділ</b>: {employee_sub_department}' if (
            employee_sub_department != 'Відобразити співробітників') else ''

    phone_string = f'\n<b>📞 Особистий телефон</b>: {employee_phone}' if employee_phone else \
        f'\n<b>📞 Особистий телефон</b>: Не вказано'
    work_phone_string = f'\n<b>📞 Робочий телефон</b>: {employee_work_phone}' if employee_work_phone else \
        f'\n<b>📞 Робочий телефон</b>: Не вказано'

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
                    f'{work_phone_string}'
                    f'{username_string}'
                    f'{email_string}'
                    f'{date_of_birth_string}')
    if call_data:
        bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.edit_message_text(message_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_emp'))
@authorized_only(user_type='admins')
def edit_employee(call):
    if call.data.startswith('edit_emp_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[3:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)

        edit_name_btn_callback = f'e_name_s_{search_query}_{employee_id}'
        edit_phone_btn_callback = f'phone_s_{search_query}_{employee_id}'
        edit_position_btn_callback = f'e_pos_s_{search_query}_{employee_id}'
        edit_username_btn_callback = f'e_uname_s_{search_query}_{employee_id}'
        edit_email_btn_callback = f'e_email_s_{search_query}_{employee_id}'
        edit_date_of_birth_btn_callback = f'e_dob_s_{search_query}_{employee_id}'
        edit_department_btn_callback = f'e_depart_s_{search_query}_{employee_id}'
        edit_sub_department_btn_callback = f'e_subdep_s_{search_query}_{employee_id}'
        show_keywords_btn_callback = f'show_keywords_s_{search_query}_{employee_id}'
        delete_btn_callback = f'delete_s_{search_query}_{employee_id}'
        back_btn_callback = f'profile_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[2:])
        edit_name_btn_callback = (f'e_name_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                  f'{sub_department_id}_{employee_id}')
        edit_phone_btn_callback = (f'phone_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                   f'{sub_department_id}_{employee_id}')
        edit_position_btn_callback = (f'e_pos_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                      f'{sub_department_id}_{employee_id}')
        edit_username_btn_callback = (f'e_uname_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                      f'{sub_department_id}_{employee_id}')
        edit_email_btn_callback = (f'e_email_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                   f'{sub_department_id}_{employee_id}')
        edit_date_of_birth_btn_callback = (f'e_dob_{additional_instance}_{department_id}_{intermediate_department_id}_'
                                           f'{sub_department_id}_{employee_id}')
        edit_department_btn_callback = (f'e_depart_{additional_instance}_{department_id}_'
                                        f'{intermediate_department_id}_{sub_department_id}_{employee_id}')
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

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, employee_id FROM employees '
                       'LEFT JOIN admins ON employees.id = admins.employee_id '
                       'WHERE employees.id = %s', (employee_id,))
        employee_name, employee_admin_id = cursor.fetchone()
    is_admin = True if employee_admin_id else False

    edit_name_btn = types.InlineKeyboardButton(text='✏️ Змінити ім\'я', callback_data=edit_name_btn_callback)
    edit_phone_btn = types.InlineKeyboardButton(text='📞 Змінити телефон', callback_data=edit_phone_btn_callback)
    edit_position_btn = types.InlineKeyboardButton(text='💼 Змінити посаду', callback_data=edit_position_btn_callback)
    edit_username_btn = types.InlineKeyboardButton(text='🆔 Змінити юзернейм', callback_data=edit_username_btn_callback)
    edit_email_btn = types.InlineKeyboardButton(text='📧 Змінити email', callback_data=edit_email_btn_callback)
    edit_date_of_birth_btn = types.InlineKeyboardButton(text='🎂 Змінити дату народження',
                                                        callback_data=edit_date_of_birth_btn_callback)
    edit_department_btn = types.InlineKeyboardButton(text='🏢 Змінити департамент',
                                                     callback_data=edit_department_btn_callback)
    edit_sub_department_btn = types.InlineKeyboardButton(text='🗄️ Змінити відділ',
                                                         callback_data=edit_sub_department_btn_callback)
    manage_additional_departments_btn = types.InlineKeyboardButton(text='🗄️ Керування додатковими відділами',
                                                                   callback_data=f'manage_add_{employee_id}_{False}')
    show_keywords_btn = types.InlineKeyboardButton(text='🔍 Показати ключові слова',
                                                   callback_data=show_keywords_btn_callback)
    make_admin_btn_text = '✅ Зняти статус адміністратора' if is_admin else '⚠️ Призначити адміністратором'
    make_admin_btn = types.InlineKeyboardButton(text=make_admin_btn_text, callback_data=f'make_admin_{employee_id}')
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити контакт', callback_data=delete_btn_callback)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        edit_name_btn, edit_phone_btn, edit_position_btn, edit_username_btn, show_keywords_btn,
        edit_email_btn, edit_date_of_birth_btn, edit_department_btn, edit_sub_department_btn,
        manage_additional_departments_btn
    )
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees WHERE id = %s', (employee_id,))
        employee_telegram_id = cursor.fetchone()[0]
    if employee_telegram_id != call.from_user.id:
        markup.row(make_admin_btn)
        markup.row(delete_btn)
    markup.row(back_btn)

    bot.edit_message_text(f'📝 Редагування контакту <b>{employee_name}</b>:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')

    if process_in_progress.get(call.message.chat.id) == 'edit_employee':
        del process_in_progress[call.message.chat.id]
        del edit_employee_data[call.from_user.id]


@bot.message_handler(content_types=['new_chat_members'])
def new_member_handler(message):
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('INSERT INTO telegram_chats (chat_id, chat_name) VALUES (%s, %s) ',
                               (message.chat.id, message.chat.title))
                conn.commit()


@bot.callback_query_handler(func=lambda call: call.data.startswith('phone_'))
@authorized_only(user_type='admins')
def phone_menu(call):
    if call.data.startswith('phone_s'):
        parts = call.data.split('_')
        search_query = '_'.join(parts[2:-1])
        employee_id = parts[-1]
        employee_id = int(employee_id)
        change_personal_btn_callback = f'e_personal_s_{search_query}_{employee_id}'
        change_work_btn_callback = f'e_work_s_{search_query}_{employee_id}'
        back_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        (additional_instance, department_id, intermediate_department_id, sub_department_id,
         employee_id) = map(int, call.data.split('_')[1:])
        change_personal_btn_callback = (f'e_personal_{additional_instance}_{department_id}_'
                                        f'{intermediate_department_id}_{sub_department_id}_{employee_id}')
        change_work_btn_callback = (f'e_work_{additional_instance}_{department_id}_'
                                    f'{intermediate_department_id}_{sub_department_id}_{employee_id}')
        back_btn_callback = (f'edit_emp_{additional_instance}_{department_id}_{intermediate_department_id}_'
                             f'{sub_department_id}_{employee_id}')

    swap_phone_btn_callback = f'swap_phone_{employee_id}'

    change_personal_btn = types.InlineKeyboardButton(text='📞 Змінити особистий телефон',
                                                     callback_data=change_personal_btn_callback)
    change_work_btn = types.InlineKeyboardButton(text='📞 Змінити робочий телефон',
                                                 callback_data=change_work_btn_callback)
    swap_phone_btn = types.InlineKeyboardButton(text='🔄 Поміняти телефони місцями',
                                                callback_data=swap_phone_btn_callback)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(change_personal_btn, change_work_btn, swap_phone_btn, back_btn)

    bot.edit_message_text('Виберіть дію з телефонами співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('swap_phone_'))
@authorized_only(user_type='admins')
def swap_phone(call):
    employee_id = int(call.data.split('_')[2])

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT phone, work_phone FROM employees WHERE id = %s', (employee_id,))
        phone, work_phone = cursor.fetchone()
        cursor.execute('UPDATE employees SET phone = %s, work_phone = %s WHERE id = %s RETURNING phone, work_phone',
                       (work_phone, phone, employee_id))
        new_phone, new_work_phone = cursor.fetchone()
        conn.commit()

    print(f'Phones swapped for employee {employee_id} by {call.from_user.username}.')

    bot.answer_callback_query(call.id, '✅ Телефони успішно поміняні місцями.\n '
                                       f'Новий особистий телефон: {new_phone if new_phone else "Не вказано"}\n'
                                       f'Новий робочий телефон: {new_work_phone if new_work_phone else "Не вказано"}',
                              show_alert=True)


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
    elif call.data.startswith('e_work'):
        edit_employee_data[call.from_user.id]['column'] = ('work_phone', employee_id)
        message_text = f'📞 Введіть новий робочий телефон для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_personal'):
        edit_employee_data[call.from_user.id]['column'] = ('phone', employee_id)
        message_text = f'📞 Введіть новий особистий телефон для контакту <b>{employee_name}</b>:'
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
    elif call.data.startswith('e_depart'):
        edit_employee_data[call.from_user.id]['column'] = ('department_id', employee_id)
        message_text = f'🏢 Введіть приблизну назву департаменту для контакту <b>{employee_name}</b>:'
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
            result_message_text = f'✅ Особистий номер телефону контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
            log_text = f'Employee {employee_id} phone changed to {new_value} by {message.from_user.username}.'
        else:
            result_message_text = ('🚫 Номер телефону введено невірно.'
                                   '\nВведіть номер телефону в форматі 0XXXXXXXXX:')
            log_text = ''
            finish_function = False

    elif column == 'work_phone':
        clear_number = re.match(r'^3?8?(0\d{9})$', re.sub(r'\D', '', new_value))
        if clear_number:
            new_value = f'+38{clear_number.group(1)}'
            result_message_text = f'✅ Робочий номер телефону контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
            log_text = f'Employee {employee_id} work phone changed to {new_value} by {message.from_user.username}.'
        else:
            result_message_text = ('🚫 Номер телефону введено невірно.'
                                   '\nВведіть номер телефону в форматі 0XXXXXXXXX:')
            log_text = ''
            finish_function = False

    elif column == 'position':
        result_message_text = f'✅ Посаду контакту <b>{employee_name}</b> змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} position changed to {new_value} by {message.from_user.username}.'

    elif column == 'department_id':
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id, name FROM departments')
            departments = cursor.fetchall()
            original_departments = [(department[0], department[1].strip()) for department in departments]
            departments = [(id, name.lower()) for id, name in original_departments]
        query = new_value.lower()
        best_match = process.extractOne(query, [name for id, name in departments])
        original_best_match = next((id, name) for id, name in original_departments if name.lower() == best_match[0])
        new_value = original_best_match[0]
        department_name = original_best_match[1]
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id FROM sub_departments WHERE department_id = %s LIMIT 1', (new_value,))
            sub_department = cursor.fetchone()
        new_value = sub_department[0]
        column = 'sub_department_id'
        result_message_text = (f'✅ Департамент контакту <b>{employee_name}</b> змінено на <b>{department_name}</b>.'
                               f'\nСхожість: {best_match[1]:.1f}%')
        log_text = f'Employee {employee_id} department_id changed to {new_value} by {message.from_user.username}.'

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
        return

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
