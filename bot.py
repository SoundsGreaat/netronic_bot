import os
import threading
import time
from time import sleep
from telebot import TeleBot, types, apihelper
from google_forms_filler import FormFiller
from database_setup import DatabaseConnection, test_connection

authorized_ids = {
    'users': set(),
    'admins': set(),
    'temp_users': set(),
}

user_info = {
    'temp_authorization_in_process': {},
    'last_message': {},
    'callback_in_process': {},
    'messages_to_delete': {},
    'forms_name_message_id': {},
    'forms_timer': {},
    'search_button_pressed': {},
}

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

departments_contacts = {
    'Адміністративний департамент': {
        'ED': [['Іванов Іван Іванович', '+380123456789'], ['Петров Петро Петрович', '+380987654321']],
        'PMD': [['Сидоров Сидір Сидорович', '+380123456789'], ['Кузьмін Кузьма Кузьмич', '+380987654321']],
        'RDD': [['Микита Микитович Микитенко', '+380123456789'], ['Іваненко Іван Іванович', '+380987654321']],
    },
    'Департамент персоналу': {
        'HR': [['Іванов Іван Іванович', '+380123456789'], ['Петров Петро Петрович', '+380987654321']],
        'Recruitment': [['Сидоров Сидір Сидорович', '+380123456789'], ['Кузьмін Кузьма Кузьмич', '+380987654321']],
    },
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
                    admins_list = [username[0] for username in cursor.fetchall()]
                markup = types.ReplyKeyboardRemove()
                print(f'Unauthorized user @{data.from_user.username} tried to access {func.__name__}\n')
                bot.send_message(chat_id, f'Ви не авторизовані для використання цієї функції.'
                                          f'\nЯкщо ви вважаєте, що це помилка, зверніться до адміністратора.'
                                          f'\n\nСписок адміністраторів: {", ".join(admins_list)}',
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
    with open('netronic_logo.png', 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption='Вітаю! Я бот-помічник <b>Netronic.</b> Що ви хочете зробити?',
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
    authorize_ids()
    bot.send_message(message.chat.id, 'Список авторизованих користувачів оновлено.')


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
def send_contacts(message, edit_message=False):
    markup = types.InlineKeyboardMarkup(row_width=1)
    search_button = types.InlineKeyboardButton(text='🔍 Пошук співробітника', callback_data='search')
    departments_button = types.InlineKeyboardButton(text='🏢 Департаменти', callback_data='departments')
    markup.add(search_button, departments_button)

    if edit_message:
        bot.edit_message_text('Оберіть дію:', message.chat.id, message.message_id, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Оберіть дію:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'search')
@authorized_only(user_type='users')
def send_search_form(call):
    cancel_form_filling(call)
    markup = types.InlineKeyboardMarkup(row_width=1)
    back_button = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
    markup.add(back_button)
    user_info['search_button_pressed'][call.message.chat.id] = True

    bot.edit_message_text('Введіть ім\'я або прізвище співробітника:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)

    user_info['messages_to_delete'][call.message.chat.id] = call.message.message_id


@bot.callback_query_handler(func=lambda call: call.data == 'departments')
@authorized_only(user_type='users')
def send_departments(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for index, department in enumerate(departments_contacts.keys()):
        btn = types.InlineKeyboardButton(text=f'🏢 {department}', callback_data=f'dep_{index}')
        buttons.append(btn)

    back_button = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')

    markup.add(*buttons)
    markup.row(back_button)

    bot.edit_message_text('Оберіть департамент:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
@authorized_only(user_type='users')
def send_department_contacts(call):
    department_index = int(call.data.split('_')[1])
    department = list(departments_contacts.keys())[department_index]
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []

    for index, (section_name, contact_list) in enumerate(departments_contacts[department].items()):
        btn = types.InlineKeyboardButton(text=f'🗄️ {section_name}', callback_data=f'sec_{department_index}_{index}')
        buttons.append(btn)
    back_button = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    markup.add(*buttons)
    markup.row(back_button)

    bot.edit_message_text(f'Оберіть відділ у департаменті <i><b>{department}:</b></i>', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('sec_'))
@authorized_only(user_type='users')
def send_section_contacts(call):
    department_index, section_index = map(int, call.data.split('_')[1:])
    department = list(departments_contacts.keys())[department_index]
    section = list(departments_contacts[department].keys())[section_index]
    markup = types.InlineKeyboardMarkup(row_width=1)

    for index, contact_info in enumerate(departments_contacts[department][section]):
        btn = types.InlineKeyboardButton(text=f'👨‍💼 {contact_info[0]}',
                                         callback_data=f'cont_{department_index}_{section_index}_{index}')
        markup.add(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'dep_{department_index}')

    if call.from_user.id in authorized_ids['admins']:
        add_contact_btn = types.InlineKeyboardButton(text='📝 Додати співробітника', callback_data='add_contact')
        markup.row(back_btn, add_contact_btn)
    else:
        markup.row(back_btn)

    bot.edit_message_text(f'Оберіть співробітника у відділі <i><b>{section}:</b></i>', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


# TODO add contact adding functionality


@bot.callback_query_handler(func=lambda call: call.data.startswith('cont_'))
@authorized_only(user_type='users')
def send_contact_info(call):
    department_index, section_index, contact_index = map(int, call.data.split('_')[1:])
    department = list(departments_contacts.keys())[department_index]
    section = list(departments_contacts[department].keys())[section_index]
    contact_info = departments_contacts[department][section][contact_index]
    contact_name = contact_info[0]
    contact_phone = contact_info[1]

    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'sec_{department_index}_{section_index}')

    if call.from_user.id in authorized_ids['admins']:
        edit_contact_btn = types.InlineKeyboardButton(text='📝 Редагувати контакт',
                                                      callback_data=f'edit_{department_index}_{section_index}_{contact_index}')
        markup.row(back_btn, edit_contact_btn)
    else:
        markup.row(back_btn)

    bot.edit_message_text(f'{contact_name} - {section}:\n{contact_phone}', call.message.chat.id,
                          call.message.message_id,
                          reply_markup=markup)


# TODO add contact editing functionality


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_send_contacts')
@authorized_only(user_type='users')
def back_to_send_contacts_menu(call):
    if user_info['search_button_pressed'].get(call.message.chat.id):
        del user_info['search_button_pressed'][call.message.chat.id]

    send_contacts(call.message, edit_message=True)


@bot.message_handler(func=lambda message: message.text == '💭 Маєш питання?')
@authorized_only(user_type='users')
def send_question_form(message):
    cancel_form_filling(message)
    if not user_info['callback_in_process'].get(message.chat.id):
        if user_info['last_message'].get(message.chat.id):
            del user_info['last_message'][message.chat.id]

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
def temp_authorize_user_by_contact(message):
    del user_info['temp_authorization_in_process'][message.chat.id]
    new_user_id = message.contact.user_id
    authorized_ids['users'].add(new_user_id)

    try:
        bot.send_message(new_user_id, f'Вас тимчасово авторизовано адміністратором @{message.from_user.username}.')
        print(f'User {new_user_id} authorized by @{message.from_user.username} with notification.'
              f'\nAuthorized users: {authorized_ids["users"]}\n')
    except apihelper.ApiTelegramException:
        print(f'User {new_user_id} authorized by @{message.from_user.username} without notification.'
              f'\nAuthorized users: {authorized_ids["users"]}\n')

    bot.send_message(message.chat.id, f'Користувача <b>{message.contact.first_name}</b> авторизовано.',
                     parse_mode='HTML')


@bot.message_handler(
    func=lambda message: message.text not in button_names and user_info['callback_in_process'].get(message.chat.id))
@authorized_only(user_type='users')
def callback_ans(message):
    if user_info['search_button_pressed'].get(message.chat.id):
        del user_info['search_button_pressed'][message.chat.id]

    user_info['last_message'][message.chat.id] = message.text
    user_info['messages_to_delete'][message.chat.id].append(message.id)


@bot.message_handler(
    func=lambda message: message.text not in button_names and user_info['search_button_pressed'].get(message.chat.id))
@authorized_only(user_type='users')
def proceed_contact_search(message):
    del user_info['search_button_pressed'][message.chat.id]
    found_contacts = find_contact_by_name(message.text)
    if found_contacts:
        for department, department_name, contact_info in found_contacts:
            bot.send_message(message.chat.id, f'{department} - {department_name}:\n'
                                              f'{contact_info[0]}  ({contact_info[1]})')
    else:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
        repeat_btn = types.InlineKeyboardButton(text='🔍 Повторити спробу', callback_data='search')
        markup.add(back_btn, repeat_btn)

        bot.send_message(message.chat.id, 'Співробітник не знайдений', reply_markup=markup)
        bot.delete_message(message.chat.id, user_info['messages_to_delete'][message.chat.id])

        del user_info['messages_to_delete'][message.chat.id]


def find_contact_by_name(name):
    found_contacts = []
    for department, contacts in departments_contacts.items():
        for department_name, contact_list in contacts.items():
            for contact_info in contact_list:
                if name.lower() in contact_info[0].lower():
                    found_contacts.append((department, department_name, contact_info))
    return found_contacts


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
        if user_info['last_message'].get(message.chat.id):
            ans = user_info['last_message'][message.chat.id]
            del user_info['callback_in_process'][message.chat.id]
            del user_info['last_message'][message.chat.id]
            return ans
        sleep(0.5)


def authorize_ids():
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees')
        cursor_result = cursor.fetchall()
        authorized_ids['users'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        cursor.execute('''SELECT employees.telegram_user_id, employees.name
            FROM admins
            JOIN employees ON admins.employee_id = employees.id
        ''')
        cursor_result = cursor.fetchall()
        authorized_ids['admins'] = {telegram_user_id[0] for telegram_user_id in cursor_result}

        print(f'List of authorized users updated.'
              f'\nAuthorized users: {authorized_ids["users"]}'
              f'\nAuthorized admins: {authorized_ids["admins"]}\n')


if test_connection():
    authorize_ids()
    bot.infinity_polling()
