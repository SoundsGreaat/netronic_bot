import asyncio
import datetime
import re

from telebot import types

from src.config import bot, process_in_progress, edit_employee_data, authorized_ids, add_employee_data
from src.database import DatabaseConnection, update_authorized_users
from src.handlers.authorization import authorized_only
from src.integrations.crm_api_functions import add_employee_to_crm
from src.integrations.telethon_functions import proceed_find_user_id


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
                                     emp.date_of_birth
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
                       emp.date_of_birth
                FROM employees AS emp
                LEFT JOIN sub_departments AS sd1 ON emp.sub_department_id = sd1.id
                LEFT JOIN departments AS d1 ON sd1.department_id = d1.id
        
                LEFT JOIN additional_sub_departments AS ad ON emp.id = ad.employee_id
                LEFT JOIN sub_departments AS sd2 ON ad.sub_department_id = sd2.id
                LEFT JOIN departments AS d2 ON sd2.department_id = d2.id
        
                LEFT JOIN intermediate_departments ON sd1.intermediate_department_id = intermediate_departments.id
        
                WHERE emp.id = %s AND (emp.sub_department_id = %s OR ad.sub_department_id = %s)
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
    markup.add(edit_name_btn, edit_phone_btn, edit_position_btn, edit_username_btn, show_keywords_btn,
               edit_email_btn, edit_date_of_birth_btn, edit_sub_department_btn, manage_additional_departments_btn)
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
