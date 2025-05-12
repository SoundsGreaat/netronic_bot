from time import sleep

from telebot import types
from telebot.types import InlineKeyboardMarkup
from utils.main_menu_buttons import main_menu, button_names, old_button_names
from config import bot, authorized_ids, user_data, process_in_progress
from database import DatabaseConnection, update_authorized_users
from handlers.authorization import authorized_only
from integrations.google_api_functions import read_credentials_from_sheet, update_commendations_mod_in_sheet, \
    approve_and_parse_to_database


@bot.message_handler(commands=['start', 'menu', 'help'])
@authorized_only(user_type='users')
def send_main_menu(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''
                       SELECT name, CASE WHEN admins.employee_id IS NOT NULL THEN TRUE ELSE FALSE END
                       FROM employees
                                LEFT JOIN admins ON employees.id = admins.employee_id
                       WHERE telegram_user_id = %s
                       ''', (message.chat.id,))
        employee_name, is_admin = cursor.fetchone()
        user_first_name = f' {employee_name[0].split()[1]}' if employee_name and len(
            employee_name[0].split()) >= 2 else ''

    with open('../assets/images/netronic_logo.png', 'rb') as photo:
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


@bot.message_handler(commands=['remind_password'])
@authorized_only(user_type='users')
def remind_password(message):
    spreadsheet_id = '1hG7Fsf8Uk9CDZ-OOP4OKUvcAr4URF0ZMPvyhgImRMV0'
    sheet_name = 'Main'
    telegram_username = f'@{message.from_user.username}'

    sent_message = bot.send_message(message.chat.id, '🔍 Пошук вашого пароля...')

    user_data = read_credentials_from_sheet(spreadsheet_id, sheet_name, telegram_username)
    if user_data:
        message_text = ''
        for i, (key, value) in enumerate(user_data.items()):
            message_text += f'{key}: <code>{value}</code>\n'
            if i % 2 == 1:
                message_text += '\n'
    else:
        message_text = 'Ваші дані не знайдено.'

    sent_message = bot.edit_message_text(message_text, message.chat.id, sent_message.message_id, parse_mode='HTML')
    sleep(30)
    bot.delete_message(message.chat.id, sent_message.id)


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


@bot.message_handler(func=lambda message: message.text in old_button_names)
@authorized_only(user_type='users')
def old_button_handler(message):
    bot.send_message(message.chat.id, 'Ця кнопка була видалена або замінена.'
                                      '\nБудь ласка, скористайтесь меню нижче.',
                     reply_markup=main_menu)


@bot.message_handler(commands=['approve_commendations'])
@authorized_only(user_type='moderators')
def approve_commendations_handler(message):
    markup = InlineKeyboardMarkup()
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити', callback_data='confirmmod_approve')
    cancel_btn = types.InlineKeyboardButton(text='❌ Відмінити', callback_data='cancelmod_approve')
    markup.add(confirm_btn, cancel_btn)
    bot.send_message(
        message.chat.id,
        'Ви впевнені, що хочете підтвердити відправку подяк?'
        '\nВсі затверджені подяки будуть надіслані в базу даних.'
        '\nВсі незатверджені подяки будуть безповоротно видалені.',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == 'confirmmod_approve')
@authorized_only(user_type='moderators')
def confirm_approve_commendations_handler(call):
    sheet_id = '15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I'
    approve_and_parse_to_database(sheet_id, 'COMMENDATIONS TO BE MODERATED',
                                  DatabaseConnection)
    bot.edit_message_text('✔️ Подяки успішно підтверджені та надіслані в базу даних.',
                          call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'cancelmod_approve')
@authorized_only(user_type='moderators')
def cancel_approve_commendations_handler(call):
    bot.edit_message_text('❌ Підтвердження подяк скасовано.', call.message.chat.id, call.message.message_id)
