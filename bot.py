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

user_info = {
    'admin_mode': {},
    'temp_authorization_in_process': {},
    'callback_in_process': {},
    'messages_to_delete': {},
    'search_button_pressed': {},
    'forms_ans': {},
    'forms_name_message_id': {},
    'forms_timer': {},
}

edit_contact_data = {
    'name': {},
    'phone': {},
    'position': {},
    'username': {},
}

# TODO move links to database and add functionality to add, remove and edit them
business_processes_buttons = {
    'Заявка на підбір персоналу':
        'https://docs.google.com/forms/d/e/1FAIpQLSdEkG-eTzL5N43MEbmZ3G1tuQdMds4Q4gAOsz5jJo7u7S9hAg/viewform',
    'Перевірка СБ':
        'https://docs.google.com/spreadsheets/d/114YdmBQ1fq6aBiOpuMpiAmwfwa9A3WdQH97seXHwYhI/edit#gid=92769968',
    'Заявка на відпустку':
        'https://docs.google.com/forms/d/1AAjYSxYyPf6CkPKAUpltqoLwMdbzw8RQXoua0QbjCGc/edit',
    'Заявка на перепрацювання':
        'https://docs.google.com/forms/d/1hbmdEuXw2dGdaN7ZT0QQBv-XJHBRwr5QIrOSSi13Qnw/edit',
    'Заявка на зміну зп':
        'https://docs.google.com/forms/d/1akYtqaWQfmesJrDpATjXsNeNNGFhAmqJgpGgj84ulV0/edit',
    'Заявка на зміну посади':
        'https://docs.google.com/forms/d/1Q5fFjnfjI5DGLN8kRyuOR23eFHPguRqYVrstkvh6JlM/edit',
    'Заявка на сумісництво':
        'https://docs.google.com/forms/d/18G-mS3lW4Lylgoa01KMzkUh9khHaZyhK0PSG-zdSqCQ/edit',
    'Заявка на звільнення':
        'https://docs.google.com/forms/d/12DbR04A1eriuDd3wApIZxh_U1TryuqoNJEVo1pB644k/edit',
    'HelpDesk IT':
        'https://docs.google.com/forms/d/e/1FAIpQLSfPFo_4Pryv8SVB0zhfaMZCF7839LUAAGTI0QazmaZGe861Xw/viewform',
    'HelpDesk АГВ':
        'https://docs.google.com/forms/d/e/1FAIpQLSdyeyTarSfnVUMKNPL1ktxJG390coPh-rVpNELQInSGqzCnpQ/viewform',
    'Замовлення ОС':
        'https://docs.google.com/forms/d/e/1FAIpQLSe92Lnu2aWa6BVbxOQPnObk4Vrs9o1UdkH00Qkbc7OFTv1XrQ/viewform',
}

news_feed_buttons = {
    'Телеграм канал Netronic 🌍 stories': 'example.com',
    'Корпоративний чат Netronic Community': 'example.com',
}


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
        user_first_name = cursor.fetchone()[0].split()[1]
        print(user_first_name)
    with open('netronic_logo.png', 'rb') as photo:
        bot.send_photo(message.chat.id, photo,
                       caption=f'Вітаю {user_first_name}! Я бот-помічник <b>Netronic.</b> Що ви хочете зробити?',
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
    if user_info['admin_mode'].get(message.chat.id):
        del user_info['admin_mode'][message.chat.id]
        bot.send_message(message.chat.id, '🔓 Режим адміністратора вимкнено.')
    else:
        bot.send_message(message.chat.id, '🔐 Режим адміністратора увімкнено.')
        user_info['admin_mode'][message.chat.id] = True


@bot.message_handler(commands=['temp_authorize'])
@authorized_only(user_type='admins')
def temp_authorize_user(message):
    user_info['temp_authorization_in_process'][message.chat.id] = True
    bot.send_message(message.chat.id, 'Надішліть контакт користувача, якого ви хочете авторизувати.')


@bot.message_handler(func=lambda message: message.text == '🎓 База знань')
@authorized_only(user_type='users')
def send_knowledge_base(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text='🎓 База знань', url='https://sites.google.com/skif-tech.com/netronic'
                                                              '-knowledge-base/%D0%B1%D0%B0%D0%B7%D0%B0-%D0%B7%D0%BD'
                                                              '%D0%B0%D0%BD%D1%8C')
    markup.add(btn)
    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '💼 Бізнес-процеси')
@authorized_only(user_type='users')
def send_business_processes(message):
    markup = types.InlineKeyboardMarkup()

    for button_text, url in business_processes_buttons.items():
        btn = types.InlineKeyboardButton(text=button_text, url=url)
        markup.add(btn)

    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання', reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == '🔗 Стрічка новин')
@authorized_only(user_type='users')
def send_useful_links(message):
    markup = types.InlineKeyboardMarkup()
    for button_text, url in news_feed_buttons.items():
        btn = types.InlineKeyboardButton(text=button_text, url=url)
        markup.add(btn)

    bot.send_message(message.chat.id, 'Натисніть на кнопку щоб відкрити посилання', reply_markup=markup)


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
    cancel_form_filling(call)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(back_btn)
    user_info['search_button_pressed'][call.message.chat.id] = True

    bot.edit_message_text('Введіть ім\'я або прізвище співробітника:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)

    user_info['messages_to_delete'][call.message.chat.id] = call.message.message_id


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
def add_contact(call):
    # TODO add contact adding functionality
    pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('profile_'))
@authorized_only(user_type='users')
def send_profile(call):
    if call.data.startswith('profile_s_'):
        search_query, employee_id = call.data.split('_')[2:]
        employee_id = int(employee_id)
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'bck_srch_{search_query}')
        edit_employee_btn = types.InlineKeyboardButton(text='📝 Редагувати контакт',
                                                       callback_data=f'edit_emp_s_{search_query}_{employee_id}')
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[1:])
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'sub_dep_{department_id}_{sub_department_id}')
        edit_employee_btn = types.InlineKeyboardButton(text='📝 Редагувати контакт',
                                                       callback_data=f'edit_emp_{department_id}_'
                                                                     f'{sub_department_id}_{employee_id}')
    markup = types.InlineKeyboardMarkup(row_width=1)

    if call.from_user.id in authorized_ids['admins']:
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_emp'))
@authorized_only(user_type='admins')
def edit_employee(call):
    if call.data.startswith('edit_emp_s'):
        search_query, employee_id = call.data.split('_')[3:]
        employee_id = int(employee_id)
        delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити контакт',
                                                callback_data=f'delete_s_{search_query}_{employee_id}')
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'profile_s_{search_query}_{employee_id}')
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[2:])
        delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити контакт',
                                                callback_data=f'delete_{department_id}_{sub_department_id}_{employee_id}')
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'profile_{department_id}_{sub_department_id}_'
                                                            f'{employee_id}')

    edit_name_btn = types.InlineKeyboardButton(text='✏️ Змінити ім\'я', callback_data=f'edit_name_{employee_id}')
    edit_phone_btn = types.InlineKeyboardButton(text='📱 Змінити телефон', callback_data=f'edit_phone_{employee_id}')
    edit_position_btn = types.InlineKeyboardButton(text='💼 Змінити посаду',
                                                   callback_data=f'edit_position_{employee_id}')
    edit_username_btn = types.InlineKeyboardButton(text='🆔 Змінити юзернейм',
                                                   callback_data=f'edit_username_{employee_id}')

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(edit_name_btn, edit_phone_btn, edit_position_btn, edit_username_btn)
    markup.row(delete_btn)
    markup.row(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    bot.edit_message_text(f'📝 Редагування контакту <b>{employee_name}</b>:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_name_'))
@authorized_only(user_type='admins')
def edit_employee_name(call):
    # TODO add name editing functionality
    pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_phone_'))
@authorized_only(user_type='admins')
def edit_employee_phone(call):
    # TODO add phone editing functionality
    pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_position_'))
@authorized_only(user_type='admins')
def edit_employee_position(call):
    # TODO add position editing functionality
    pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_username_'))
@authorized_only(user_type='admins')
def edit_employee_username(call):
    # TODO add username editing functionality
    pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
@authorized_only(user_type='admins')
def delete_employee(call):
    if call.data.startswith('delete_s'):
        search_query, employee_id = call.data.split('_')[2:]
        employee_id = int(employee_id)

        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення',
                                                callback_data=f'edit_emp_s_{search_query}_{employee_id}')
        confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                                 callback_data=f'confirm_delete_s_{employee_id}')
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[1:])
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення',
                                                callback_data=f'edit_emp_{department_id}_{sub_department_id}_{employee_id}')
        confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                                 callback_data=f'confirm_delete_{department_id}_{sub_department_id}_'
                                                               f'{employee_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(confirm_btn, cancel_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]

    bot.edit_message_text(f'Ви впевнені, що хочете видалити контакт <b>{employee_name}</b>?', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('bck_srch_'))
@authorized_only(user_type='users')
def back_to_search_results(call):
    call.message.text = call.data.split('_')[2]
    proceed_contact_search(call.message, edit_message=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
@authorized_only(user_type='admins')
def confirm_delete_employee(call):
    if call.data.startswith('confirm_delete_s'):
        employee_id = int(call.data.split('_')[3])
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
    else:
        department_id, sub_department_id, employee_id = map(int, call.data.split('_')[2:])
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'sub_dep_{department_id}_{sub_department_id}')

    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name FROM employees WHERE id = %s', (employee_id,))
        employee_name = cursor.fetchone()[0]
        cursor.execute('DELETE FROM employees WHERE id = %s', (employee_id,))
        conn.commit()

    print(f'Employee {employee_name} deleted by {call.from_user.username}.\n')

    bot.edit_message_text(f'✅ Контакт <b>{employee_name}</b> видалено.', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_send_contacts')
@authorized_only(user_type='users')
def back_to_send_contacts_menu(call):
    if user_info['search_button_pressed'].get(call.message.chat.id):
        del user_info['search_button_pressed'][call.message.chat.id]

    send_contacts_menu(call.message, edit_message=True)


@bot.message_handler(func=lambda message: message.text == '💭 Маєш питання?')
@authorized_only(user_type='users')
def send_question_form(message):
    cancel_form_filling(message)
    if not user_info['callback_in_process'].get(message.chat.id):
        if user_info['forms_ans'].get(message.chat.id):
            del user_info['forms_ans'][message.chat.id]

        user_info['messages_to_delete'][message.chat.id] = [message.id]

        form_url = 'https://docs.google.com/forms/d/e/1FAIpQLSfzamHCZtyBu2FDI3dYlV8PZw46ON2qzhTGrIRqA9eFAiI86Q/viewform'
        gform = FormFiller(form_url)

        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text='❌ Відмінити відправку форми', callback_data='cancel_form_filling')
        markup.add(btn)

        sent_message = bot.send_message(message.chat.id,
                                        f'{gform.name()}\n\n{gform.description() if gform.description() else ""}',
                                        reply_markup=markup)
        user_info['messages_to_delete'][sent_message.chat.id].append(sent_message.message_id)

        def get_answer():
            try:
                gform.fill_form(
                    lambda element, page_index, element_index: callback(element, page_index, element_index,
                                                                        sent_message)
                )
                bot.edit_message_text(sent_message.text, sent_message.chat.id, sent_message.message_id)
                bot.send_message(sent_message.chat.id,
                                 'Дякую за заповнення форми! Ваше питання буде розглянуто найближчим часом.')
                del user_info['messages_to_delete'][message.chat.id]
                del user_info['forms_timer'][message.chat.id]
            except ValueError:
                pass

        thread = threading.Thread(target=get_answer)
        thread.start()


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_form_filling')
@authorized_only(user_type='users')
def cancel_form_filling(message):
    if user_info['callback_in_process'].get(message.from_user.id):
        del user_info['callback_in_process'][message.from_user.id]
        del user_info['forms_timer'][message.from_user.id]

        for message_id in user_info['messages_to_delete'][message.from_user.id]:
            bot.delete_message(message.from_user.id, message_id)
        if user_info['messages_to_delete'].get(message.from_user.id):
            del user_info['messages_to_delete'][message.from_user.id]


@bot.message_handler(func=lambda message: user_info['temp_authorization_in_process'].get(message.chat.id),
                     content_types=['contact'])
@authorized_only(user_type='admins')
def temp_authorize_user_by_contact(message):
    del user_info['temp_authorization_in_process'][message.chat.id]
    new_user_id = message.contact.user_id
    authorized_ids['temp_users'].add(new_user_id)

    try:
        bot.send_message(new_user_id, f'Вас тимчасово авторизовано адміністратором @{message.from_user.username}.')

        print(f'User {new_user_id} temporarily authorized by @{message.from_user.username} with notification.'
              f'\nTemporarily authorized users: {authorized_ids["temp_users"]}\n')
    except apihelper.ApiTelegramException:
        print(f'User {new_user_id} temporarily authorized by @{message.from_user.username} without notification.'
              f'\nTemporarily authorized users: {authorized_ids["temp_users"]}\n')

    bot.send_message(message.chat.id, f'Користувача <b>{message.contact.first_name}</b> авторизовано.',
                     parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.text not in button_names and user_info['callback_in_process'].get(message.chat.id))
@authorized_only(user_type='users')
def callback_ans(message):
    if user_info['search_button_pressed'].get(message.chat.id):
        del user_info['search_button_pressed'][message.chat.id]

    user_info['forms_ans'][message.chat.id] = message.text
    user_info['messages_to_delete'][message.chat.id].append(message.id)


@bot.message_handler(
    func=lambda message: message.text not in button_names and user_info['search_button_pressed'].get(message.chat.id))
@authorized_only(user_type='users')
def proceed_contact_search(message, edit_message=False):
    if user_info['messages_to_delete'].get(message.chat.id):
        bot.delete_message(message.chat.id, user_info['messages_to_delete'][message.chat.id])
        del user_info['messages_to_delete'][message.chat.id]

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
                user_info['messages_to_delete'][message.chat.id] = sent_message.message_id

    else:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
        markup = types.InlineKeyboardMarkup()
        markup.add(back_btn)

        sent_message = bot.send_message(message.chat.id, '🚫 Співробітник не знайдений', reply_markup=markup)
        user_info['messages_to_delete'][message.chat.id] = sent_message.message_id


def callback(element, page_index, element_index, message):
    sent_message = bot.send_message(message.chat.id, f'{element.name}')
    user_info['messages_to_delete'][message.chat.id].append(sent_message.message_id)
    user_info['callback_in_process'][message.chat.id] = True
    user_info['forms_timer'][message.chat.id] = time.time()

    while True:
        if not user_info['callback_in_process'].get(message.chat.id):
            break
        if time.time() - user_info['forms_timer'][message.chat.id] > 3600:
            cancel_form_filling(message)
            break
        if user_info['forms_ans'].get(message.chat.id):
            ans = user_info['forms_ans'][message.chat.id]
            del user_info['callback_in_process'][message.chat.id]
            del user_info['forms_ans'][message.chat.id]
            return ans
        sleep(0.5)


def main():
    if test_connection():
        update_authorized_users(authorized_ids)
        bot.infinity_polling()


if __name__ == '__main__':
    main()
