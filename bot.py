import os
import threading
import time

from time import sleep
from telebot import TeleBot, types, apihelper

from google_forms_filler import FormFiller
from database import DatabaseConnection, test_connection, update_authorized_users, find_contact_by_name

authorized_ids = {
    'users': set(),
    'admins': set(),
    'temp_users': set(),
}

user_data = {
    'admin_mode': {},
    'messages_to_delete': {},
    'form_messages_to_delete': {},
    'forms_ans': {},
    'forms_timer': {},
}

edit_employee_data = {
    'saved_message': {},
    'column': {},
}

add_employee_data = {
    'column': {},
}

process_in_progress = {}


def authorized_only(user_type):
    def decorator(func):
        def wrapper(data, *args, **kwargs):
            try:
                chat_id = data.chat.id
            except AttributeError:
                chat_id = data.from_user.id

            if chat_id in authorized_ids[user_type] or chat_id in authorized_ids['temp_users'] and user_type == 'users':
                func(data, *args, **kwargs)
            else:
                with DatabaseConnection() as (conn, cursor):
                    cursor.execute('''SELECT employees.telegram_username
                                FROM admins
                                JOIN employees ON admins.employee_id = employees.id
                            ''')
                    admin_list = [username[0] for username in cursor.fetchall()]
                markup = types.ReplyKeyboardRemove()
                print(f'Unauthorized user @{data.from_user.username} tried to access {func.__name__}\n')
                bot.send_message(chat_id, f'Ви не авторизовані для використання цієї функції.'
                                          f'\nЯкщо ви вважаєте, що це помилка, зверніться до адміністратора.'
                                          f'\n\nСписок адміністраторів: {", ".join(admin_list)}',
                                 reply_markup=markup)

        return wrapper

    return decorator


def callback(element, page_index, element_index, message):
    sent_message = bot.send_message(message.chat.id, f'{element.name}')
    user_data['form_messages_to_delete'][message.chat.id].append(sent_message.message_id)
    process_in_progress[message.chat.id] = 'question_form'
    user_data['forms_timer'][message.chat.id] = time.time()

    while True:
        if (process_in_progress.get(message.chat.id) != 'question_form' or
                time.time() - user_data['forms_timer'][message.chat.id] > 3600):
            delete_messages(message.chat.id, 'form_messages_to_delete')
            del user_data['forms_timer'][message.chat.id]
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
            for message_id in user_data[dict_key][chat_id]:
                bot.delete_message(chat_id, message_id)
        else:
            bot.delete_message(chat_id, user_data[dict_key][chat_id])
        del user_data[dict_key][chat_id]


bot = TeleBot(os.getenv('NETRONIC_BOT_TOKEN'))

main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)

knowledge_base_button = types.KeyboardButton('🎓 База знань')
business_processes_button = types.KeyboardButton('💼 Бізнес-процеси')
news_feed_button = types.KeyboardButton('🔗 Стрічка новин')
contacts_button = types.KeyboardButton('📞 Контакти')
support_button = types.KeyboardButton('💭 Маєш питання?')

main_menu.row(knowledge_base_button, business_processes_button)
main_menu.row(news_feed_button, contacts_button)
main_menu.row(support_button)

button_names = [btn['text'] for row in main_menu.keyboard for btn in row]


@bot.message_handler(commands=['start', 'menu', 'help'])
@authorized_only(user_type='users')
def send_main_menu(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
        employee_name = cursor.fetchone()
        user_first_name = f' {employee_name[0].split()[1]}' if employee_name and len(
            employee_name[0].split()) == 3 else ''
    with open('netronic_logo.png', 'rb') as photo:
        bot.send_photo(message.chat.id, photo,
                       caption=f'Вітаю{user_first_name}! Я бот-помічник <b>Netronic.</b> Що ви хочете зробити?',
                       reply_markup=main_menu, parse_mode='HTML')

    if message.chat.id in authorized_ids['admins']:
        bot.send_message(message.chat.id, 'Ви авторизовані як адміністратор.'
                                          '\nВам доступні додаткові команди:'
                                          '\n\n/update_authorized_users - оновити список авторизованих користувачів'
                                          '\n/admin_mode - увімкнути/вимкнути режим адміністратора'
                                          '\n/temp_authorize - тимчасово авторизувати користувача')


@bot.message_handler(commands=['update_authorized_users'])
@authorized_only(user_type='admins')
def proceed_authorize_users(message):
    update_authorized_users(authorized_ids)
    bot.send_message(message.chat.id, '✔️ Список авторизованих користувачів оновлено.')


@bot.message_handler(commands=['admin_mode'])
@authorized_only(user_type='admins')
def toggle_admin_mode(message):
    if user_data['admin_mode'].get(message.chat.id):
        del user_data['admin_mode'][message.chat.id]
        bot.send_message(message.chat.id, '🔓 Режим адміністратора вимкнено.')
    else:
        bot.send_message(message.chat.id, '🔐 Режим адміністратора увімкнено.')
        user_data['admin_mode'][message.chat.id] = True


@bot.message_handler(commands=['temp_authorize'])
@authorized_only(user_type='admins')
def temp_authorize_user(message):
    process_in_progress[message.chat.id] = 'temp_authorization'
    bot.send_message(message.chat.id, 'Надішліть контакт користувача, якого ви хочете авторизувати.')


@bot.message_handler(func=lambda message: message.text == '🎓 База знань')
@authorized_only(user_type='users')
def send_knowledge_base(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, link FROM knowledge_base_links ORDER BY id')
        knowledge_base_links = cursor.fetchall()
    markup = types.InlineKeyboardMarkup()
    for name, link in knowledge_base_links:
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)
    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання:', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '💼 Бізнес-процеси')
@authorized_only(user_type='users')
def send_business_processes(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, link FROM business_process_links ORDER BY id')
        business_process_links = cursor.fetchall()

    markup = types.InlineKeyboardMarkup()
    for name, link in business_process_links:
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)

    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання:', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '🔗 Стрічка новин')
@authorized_only(user_type='users')
def send_useful_links(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, link FROM news_feed_links ORDER BY id')
        news_feed_links = cursor.fetchall()
    markup = types.InlineKeyboardMarkup()
    for name, link in news_feed_links:
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)

    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання:', reply_markup=markup)


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

    bot.edit_message_text('Введіть ім\'я або прізвище співробітника:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)

    user_data['messages_to_delete'][call.message.chat.id] = call.message.message_id


@bot.callback_query_handler(func=lambda call: call.data == 'departments')
@authorized_only(user_type='users')
def send_departments(call):
    buttons = []
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name FROM departments')
        departments = cursor.fetchall()

    for department in departments:
        department_id = department[0]
        department_name = department[1]
        btn = types.InlineKeyboardButton(text=f'🏢 {department_name}', callback_data=f'dep_{department_id}')
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text('Оберіть департамент:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
@authorized_only(user_type='users')
def send_department_contacts(call):
    department_id = int(call.data.split('_')[1])
    buttons = []

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name FROM sub_departments WHERE department_id = %s', (department_id,))
        sub_departments = cursor.fetchall()

    for sub_department in sub_departments:
        sub_department_id = sub_department[0]
        sub_department_name = sub_department[1]
        btn = types.InlineKeyboardButton(text=f'🗄️ {sub_department_name}',
                                         callback_data=f'sub_dep_{department_id}_{sub_department_id}')
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_dep_'))
@authorized_only(user_type='users')
def send_sub_departments_contacts(call):
    department_id, sub_department_id = map(int, call.data.split('_')[2:])
    markup = types.InlineKeyboardMarkup(row_width=1)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name, gender FROM employees WHERE sub_department_id = %s', (sub_department_id,))
        employees = cursor.fetchall()

    for employee in employees:
        employee_id = employee[0]
        employee_name = employee[1]
        employee_gender = employee[2]

        emoji = '👨‍💼' if employee_gender == 'M' else '👩‍💼'
        btn = types.InlineKeyboardButton(text=f'{emoji} {employee_name}',
                                         callback_data=f'profile_{department_id}_{sub_department_id}_{employee_id}')
        markup.add(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'dep_{department_id}')

    if call.from_user.id in authorized_ids['admins']:
        add_contact_btn = types.InlineKeyboardButton(text='📝 Додати співробітника',
                                                     callback_data=f'add_contact_{sub_department_id}')
        markup.row(back_btn, add_contact_btn)
    else:
        markup.row(back_btn)

    bot.edit_message_text(f'Оберіть співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'add_contact_')
@authorized_only(user_type='admins')
def add_employee(call):
    process_in_progress[call.message.chat.id] = 'add_employee'
    # TODO finish this function


@bot.callback_query_handler(func=lambda call: call.data.startswith('profile_'))
@authorized_only(user_type='users')
def send_profile(call):
    if call.data.startswith('profile_s_'):
        search_query, employee_id = call.data.split('_')[2:]
        employee_id = int(employee_id)
        back_btn_callback = f'bck_srch_{search_query}'
        edit_employee_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[1:])
        back_btn_callback = f'sub_dep_{department_id}_{sub_department_id}'
        edit_employee_btn_callback = f'edit_emp_{department_id}_{sub_department_id}_{employee_id}'

    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)

    if call.from_user.id in authorized_ids['admins']:
        edit_employee_btn = types.InlineKeyboardButton(text='📝 Редагувати контакт',
                                                       callback_data=edit_employee_btn_callback)
        markup.row(back_btn, edit_employee_btn)
    else:
        markup.row(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, phone, position, telegram_username, gender FROM employees WHERE id = %s',
                       (employee_id,))
        employee_info = cursor.fetchone()

    employee_name = employee_info[0]
    employee_phone = employee_info[1]
    employee_position = employee_info[2]
    employee_username = employee_info[3]
    employee_gender = employee_info[4]
    emoji = '👨‍💼' if employee_gender == 'M' else '👩‍💼'
    bot.edit_message_text(f'{emoji} {employee_name} - {employee_position}:\n{employee_username} ({employee_phone})',
                          call.message.chat.id,
                          call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('bck_srch_'))
@authorized_only(user_type='users')
def back_to_search_results(call):
    call.message.text = call.data.split('_')[2]
    proceed_contact_search(call.message, edit_message=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_emp'))
@authorized_only(user_type='admins')
def edit_employee(call):
    if call.data.startswith('edit_emp_s'):
        search_query, employee_id = call.data.split('_')[3:]
        employee_id = int(employee_id)

        edit_name_btn_callback = f'e_name_s_{search_query}_{employee_id}'
        edit_phone_btn_callback = f'e_phone_s_{search_query}_{employee_id}'
        edit_position_btn_callback = f'e_pos_s_{search_query}_{employee_id}'
        edit_username_btn_callback = f'e_uname_s_{search_query}_{employee_id}'
        delete_btn_callback = f'delete_s_{search_query}_{employee_id}'
        back_btn_callback = f'profile_s_{search_query}_{employee_id}'
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[2:])
        edit_name_btn_callback = f'e_name_{department_id}_{sub_department_id}_{employee_id}'
        edit_phone_btn_callback = f'e_phone_{department_id}_{sub_department_id}_{employee_id}'
        edit_position_btn_callback = f'e_pos_{department_id}_{sub_department_id}_{employee_id}'
        edit_username_btn_callback = f'e_uname_{department_id}_{sub_department_id}_{employee_id}'
        delete_btn_callback = f'delete_{department_id}_{sub_department_id}_{employee_id}'
        back_btn_callback = f'profile_{department_id}_{sub_department_id}_{employee_id}'

    edit_name_btn = types.InlineKeyboardButton(text='✏️ Змінити ім\'я', callback_data=edit_name_btn_callback)
    edit_phone_btn = types.InlineKeyboardButton(text='📱 Змінити телефон', callback_data=edit_phone_btn_callback)
    edit_position_btn = types.InlineKeyboardButton(text='💼 Змінити посаду', callback_data=edit_position_btn_callback)
    edit_username_btn = types.InlineKeyboardButton(text='🆔 Змінити юзернейм', callback_data=edit_username_btn_callback)
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити контакт', callback_data=delete_btn_callback)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(edit_name_btn, edit_phone_btn, edit_position_btn, edit_username_btn)
    markup.row(delete_btn)
    markup.row(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    bot.edit_message_text(f'📝 Редагування контакту <b>{employee_name}</b>:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')

    if process_in_progress.get(call.message.chat.id) == 'edit_employee':
        del user_data['messages_to_delete'][call.message.chat.id]
        del process_in_progress[call.message.chat.id]
        del edit_employee_data['saved_message'][call.from_user.id]
        del edit_employee_data['column'][call.from_user.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('e_'))
@authorized_only(user_type='admins')
def proceed_edit_employee(call):
    process_in_progress[call.message.chat.id] = 'edit_employee'
    edit_employee_data['saved_message'][call.from_user.id] = call.message
    if call.data.split('_')[2] == 's':
        search_query, employee_id = call.data.split('_')[3:]
        employee_id = int(employee_id)

        back_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[2:])

        back_btn_callback = f'edit_emp_{department_id}_{sub_department_id}_{employee_id}'

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    if call.data.startswith('e_name'):
        edit_employee_data['column'][call.from_user.id] = ('name', employee_id)
        message_text = f'✏️ Введіть нове ім\'я для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_phone'):
        edit_employee_data['column'][call.from_user.id] = ('phone', employee_id)
        message_text = f'📱 Введіть новий телефон для контакту <b>{employee_name}</b>:'
    elif call.data.startswith('e_pos'):
        edit_employee_data['column'][call.from_user.id] = ('position', employee_id)
        message_text = f'💼 Введіть нову посаду для контакту <b>{employee_name}</b>:'
    else:
        edit_employee_data['column'][call.from_user.id] = ('telegram_username', employee_id)
        message_text = f'🆔 Введіть новий юзернейм для контакту <b>{employee_name}</b>:'

    back_btn = types.InlineKeyboardButton(text='❌ Відмінити', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)

    sent_message = bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id,
                                         reply_markup=markup, parse_mode='HTML')
    user_data['messages_to_delete'][call.message.chat.id] = sent_message.message_id


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'edit_employee')
@authorized_only(user_type='admins')
def edit_employee_data_ans(message):
    column, employee_id = edit_employee_data['column'][message.chat.id]
    new_value = message.text
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(f'UPDATE employees SET {column} = %s WHERE id = %s', (new_value, employee_id))
        conn.commit()
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    if column == 'name':
        message_text = f'✅ Ім\'я контакту змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} name changed to {new_value} by {message.from_user.username}.\n'

    elif column == 'phone':
        message_text = f'✅ Номер телефону контакту змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} phone changed to {new_value} by {message.from_user.username}.\n'

    elif column == 'position':
        message_text = f'✅ Посаду контакту змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} position changed to {new_value} by {message.from_user.username}.\n'

    else:
        message_text = f'✅ Юзернейм контакту змінено на <b>{new_value}</b>.'
        log_text = f'Employee {employee_id} username changed to {new_value} by {message.from_user.username}.\n'

        print(f'Employee {employee_id} username changed to {new_value} by {message.from_user.username}.\n')

    print(log_text)

    saved_message = edit_employee_data['saved_message'][message.chat.id]
    bot.delete_message(message.chat.id, saved_message.message_id)
    bot.send_message(message.chat.id, message_text, parse_mode='HTML')
    bot.send_message(saved_message.chat.id, f'📝 Редагування контакту <b>{employee_name}</b>:',
                     parse_mode='HTML', reply_markup=saved_message.reply_markup)

    del process_in_progress[message.chat.id]
    del edit_employee_data['column'][message.chat.id]
    del edit_employee_data['saved_message'][message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
@authorized_only(user_type='admins')
def delete_employee(call):
    if call.data.startswith('delete_s'):
        search_query, employee_id = call.data.split('_')[2:]
        employee_id = int(employee_id)

        cancel_btn_callback = f'edit_emp_s_{search_query}_{employee_id}'
        confirm_btn_callback = f'confirm_delete_s_{employee_id}'

    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[1:])

        cancel_btn_callback = f'edit_emp_{department_id}_{sub_department_id}_{employee_id}'
        confirm_btn_callback = f'confirm_delete_{department_id}_{sub_department_id}_{employee_id}'

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data=cancel_btn_callback)
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення', callback_data=confirm_btn_callback)
    markup = types.InlineKeyboardMarkup()
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
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[2:])

        back_btn_callback = f'sub_dep_{department_id}_{sub_department_id}'

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=back_btn_callback)
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]
        cursor.execute('DELETE FROM employees WHERE id = %s', (employee_id,))
        conn.commit()

    print(f'Employee {employee_name} deleted by {call.from_user.username}.\n')
    update_authorized_users(authorized_ids)

    bot.edit_message_text(f'✅ Контакт <b>{employee_name}</b> видалено.', call.message.chat.id,
                          call.message.message_id, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_send_contacts')
@authorized_only(user_type='users')
def back_to_send_contacts_menu(call):
    send_contacts_menu(call.message, edit_message=True)
    if process_in_progress.get(call.message.chat.id) == 'search':
        del process_in_progress[call.message.chat.id]


@bot.message_handler(func=lambda message: message.text == '💭 Маєш питання?')
@authorized_only(user_type='users')
def send_question_form(message):
    process_in_progress[message.chat.id] = 'question_form'

    form_url = 'https://docs.google.com/forms/d/e/1FAIpQLSfzamHCZtyBu2FDI3dYlV8PZw46ON2qzhTGrIRqA9eFAiI86Q/viewform'
    gform = FormFiller(form_url)

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text='❌ Відмінити', callback_data='cancel_form_filling')
    markup.add(btn)

    sent_message = bot.send_message(message.chat.id,
                                    f'{gform.name()}\n\n{gform.description() if gform.description() else ""}',
                                    reply_markup=markup)
    user_data['form_messages_to_delete'][message.chat.id] = [message.id, sent_message.message_id]

    def get_answer():
        try:
            gform.fill_form(
                lambda element, page_index, element_index: callback(element, page_index, element_index,
                                                                    sent_message)
            )
            bot.edit_message_text(sent_message.text, sent_message.chat.id, sent_message.message_id)
            bot.send_message(sent_message.chat.id,
                             'Дякую за заповнення форми! Ваше питання буде розглянуто найближчим часом.')
            del user_data['form_messages_to_delete'][message.chat.id]
        except ValueError:
            pass

    thread = threading.Thread(target=get_answer)
    thread.start()


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_form_filling')
@authorized_only(user_type='users')
def cancel_form_filling_(call):
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
                        f'\nTemporarily authorized users: {authorized_ids["temp_users"]}\n')
        except apihelper.ApiTelegramException:
            log_text = (
                f'User {new_user_id} temporarily authorized by @{message.from_user.username} without notification.'
                f'\nTemporarily authorized users: {authorized_ids["temp_users"]}\n')

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
    user_data['messages_to_delete'][message.chat.id].append(message.id)


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
            employee_gender = employee_info[3]

            emoji = '👨‍💼' if employee_gender == 'M' else '👩‍💼'
            btn = types.InlineKeyboardButton(text=f'{emoji} {employee_name} - {employee_position}',
                                             callback_data=f'profile_s_{message.text}_{employee_id}')
            markup.add(btn)

        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='search')
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
