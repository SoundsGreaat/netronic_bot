import math
import threading
import asyncio
import time
import datetime

from time import sleep
from telebot import types, apihelper
from src.config import authorized_ids, openai_data, make_card_data, \
    process_in_progress, COMMENDATIONS_PER_PAGE, MONTH_DICT, client, bot, \
    BIRTHDAY_NOTIFICATIONS_USER_IDS, OPENAI_ASSISTANT_ID, FERNET_KEY
from src.handlers import *
from src.integrations import *
from src.database import *
from src.utils import *


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
        assistant_id=OPENAI_ASSISTANT_ID,
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
    user_ids = BIRTHDAY_NOTIFICATIONS_USER_IDS.split(',')
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
        message = (f'🎂 Дні народження робітників на {MONTH_DICT[month]}:\n\n'
                   + '\n'.join(birthdays))

    for user_id in user_ids:
        bot.send_message(user_id, message)


def main():
    scheduler.add_job(send_birthday_notification, 'cron', day=25, hour=17, minute=0, id='monthly_job',
                      replace_existing=True)
    scheduler.start()

    if test_connection():
        decrypt_session(FERNET_KEY, input_file='../sessions/userbot_session_encrypted',
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
