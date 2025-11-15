import datetime
import random

from telebot import types, apihelper

from config import bot, authorized_ids, process_in_progress, secret_santa_data
from database import DatabaseConnection
from handlers import authorized_only
from utils.main_menu_buttons import button_names
from utils.scheduler import run_update_secret_santa_sheet, scheduler
from utils.secret_santa_reminder import secret_santa_notification_wrapper


@bot.message_handler(func=lambda message: message.text == '🎅 Таємний Санта')
@authorized_only(user_type='users')
def secret_santa_menu(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 1')
        is_phase_1_started = cursor.fetchone()[0]
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 2')
        is_phase_2_started = cursor.fetchone()[0]

    markup = types.InlineKeyboardMarkup()
    if message.chat.id in authorized_ids['admins']:
        if not is_phase_1_started and not is_phase_2_started:
            start_phase_1_btn = types.InlineKeyboardButton(text='🎁 Почати першу фазу', callback_data='start_phase_1')
            markup.add(start_phase_1_btn)
            start_phase_2_btn = types.InlineKeyboardButton(text='🎁 Почати другу фазу', callback_data='start_phase_2')
            markup.add(start_phase_2_btn)
        elif is_phase_1_started:
            finish_phase_1_btn = types.InlineKeyboardButton(text='🎁 Завершити першу фазу',
                                                            callback_data='finish_phase_1')
            markup.add(finish_phase_1_btn)
            remind_btn = types.InlineKeyboardButton(text='🔔 Надіслати нагадування', callback_data='santa_notify_users')
            markup.add(remind_btn)
        elif is_phase_2_started:
            finish_phase_2_btn = types.InlineKeyboardButton(text='🎁 Завершити другу фазу',
                                                            callback_data='finish_phase_2')
            markup.add(finish_phase_2_btn)

    if is_phase_1_started:
        fill_info_btn = types.InlineKeyboardButton(text='📝 Заповнити анкету для Санти',
                                                   callback_data='secret_santa_fill_info')
        markup.row(fill_info_btn)
    if is_phase_1_started or is_phase_2_started:
        show_profile_btn = types.InlineKeyboardButton(text='👤 Моя анкета',
                                                      callback_data='secret_santa_show_profile')
        markup.row(show_profile_btn)

    if is_phase_2_started:
        show_recipient_btn = types.InlineKeyboardButton(text='🎅 Чий я Санта?',
                                                        callback_data='secret_santa_show_recipient')
        markup.row(show_recipient_btn)

    bot.send_message(message.chat.id, '🎅 Оберіть дію:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'start_phase_1')
@authorized_only(user_type='admins')
def start_phase_1(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 1')
        is_started = cursor.fetchone()[0]
        if is_started:
            bot.edit_message_text('🎁 Перша фаза вже розпочата.', call.message.chat.id, call.message.message_id)
            return
        cursor.execute('UPDATE secret_santa_phases SET is_started = TRUE WHERE phase_number = 1')
        conn.commit()

    notify_users_btn = types.InlineKeyboardButton(text='📢 Повідомити всіх користувачів', callback_data='notify_users')
    markup = types.InlineKeyboardMarkup()
    markup.add(notify_users_btn)
    bot.edit_message_text('🎁 Перша фаза розпочата.'
                          '\n Бажаєте повідомити всіх користувачів?', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'finish_phase_1')
@authorized_only(user_type='admins')
def finish_phase_1(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 1')
        is_started = cursor.fetchone()[0]
        if not is_started:
            bot.edit_message_text('🎁 Перша фаза ще не розпочата.', call.message.chat.id, call.message.message_id)
            return
        cursor.execute('UPDATE secret_santa_phases SET is_started = FALSE WHERE phase_number = 1')
        conn.commit()
        cursor.execute('SELECT employee_id FROM secret_santa_info')
        participants = [row[0] for row in cursor.fetchall()]
        random.shuffle(participants)
        for i, participant_id in enumerate(participants):
            secret_santa_id = participants[(i + 1) % len(participants)]
            cursor.execute('UPDATE secret_santa_info SET secret_santa_id = %s WHERE employee_id = %s',
                           (secret_santa_id, participant_id))
        conn.commit()

    bot.edit_message_text('🎁 Перша фаза завершена. Учасники отримали своїх Таємних Сант.',
                          call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'start_phase_2')
@authorized_only(user_type='admins')
def start_phase_2(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT is_started FROM secret_santa_phases WHERE phase_number = 2')
        is_started = cursor.fetchone()[0]
        if is_started:
            bot.edit_message_text('🎁 Друга фаза вже розпочата.', call.message.chat.id, call.message.message_id)
            return
        cursor.execute('UPDATE secret_santa_phases SET is_started = TRUE WHERE phase_number = 2')
        conn.commit()
    run_update_secret_santa_sheet()
    sent_message = bot.edit_message_text('🎁 Друга фаза розпочата. Розсилаю повідомлення...',
                                         call.message.chat.id, call.message.message_id)
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT employee_id, secret_santa_id FROM secret_santa_info')
        participants = cursor.fetchall()

        for recipient_id, secret_santa_id in participants:
            try:
                cursor.execute('SELECT telegram_user_id FROM employees WHERE id = %s', (secret_santa_id,))
                secret_santa_telegram_id = cursor.fetchone()[0]
                cursor.execute('SELECT emp.name, santa.address, santa.request, santa.aversions, santa.phone '
                               'FROM employees emp '
                               'JOIN secret_santa_info santa ON emp.id = santa.employee_id '
                               'WHERE emp.id = %s', (recipient_id,))
                recipient_name, address, requests, aversions, phone = cursor.fetchone()
                bot.send_message(secret_santa_telegram_id, f'🎅 Привіт!'
                                                           f'\nТи Таємний Санта для <b>{recipient_name}!</b>'
                                                           f'\nНе забудь підготувати подарунок та відправити його.'
                                                           f'\nТа не забудь про інтригу! Не розкривай свою особу!'
                                                           f'\n\n\n🏠 Адреса отримання: <b>{address}</b>'
                                                           f'\n\n🎁 Побажання: <b>{requests}</b>'
                                                           f'\n\n🚫 Небажане: <b>{aversions}</b>'
                                                           f'\n\n📞 Телефон: <b>{phone}</b>',
                                 parse_mode='HTML')
            except Exception as e:
                print(f'Error while sending message to {secret_santa_telegram_id}: {e}')
        bot.delete_message(call.message.chat.id, sent_message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'secret_santa_show_recipient')
@authorized_only(user_type='users')
def secret_santa_show_recipient(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT recipient.name, santa.address, santa.request, santa.aversions, santa.phone '
                       'FROM employees emp '
                       'JOIN secret_santa_info santa ON emp.id = santa.secret_santa_id '
                       'JOIN employees recipient ON recipient.id = santa.employee_id '
                       'WHERE emp.telegram_user_id = %s', (call.message.chat.id,))
        recipient_name, address, requests, aversions, phone = cursor.fetchone()

    markup = types.InlineKeyboardMarkup()
    anonymous_message_button = types.InlineKeyboardButton(text='📩 Анонімне повідомлення',
                                                          callback_data='secret_santa_anonymous_message')
    markup.add(anonymous_message_button)

    bot.send_message(call.message.chat.id, f'🎅 Ти Таємний Санта для <b>{recipient_name}!</b>'
                                           f'\n\n🏠 Адреса отримання: <b>{address}</b>'
                                           f'\n\n🎁 Побажання: <b>{requests}</b>'
                                           f'\n\n🚫 Небажане: <b>{aversions}</b>'
                                           f'\n\n📞 Телефон: <b>{phone}</b>',
                     parse_mode='HTML',
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'secret_santa_anonymous_message')
@authorized_only(user_type='users')
def secret_santa_anonymous_message(call):
    process_in_progress[call.message.chat.id] = 'secret_santa_anonymous_message'
    sent_message = bot.send_message(call.message.chat.id, '📝 Введіть текст повідомлення для отримувача:',
                                    reply_markup=types.ForceReply())
    secret_santa_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'secret_santa_anonymous_message')
@authorized_only(user_type='users')
def secret_santa_anonymous_message_ans(message):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT recipient.telegram_user_id FROM employees emp '
                       'JOIN secret_santa_info santa ON emp.id = santa.secret_santa_id '
                       'JOIN employees recipient ON recipient.id = santa.employee_id '
                       'WHERE emp.telegram_user_id = %s', (message.chat.id,))
        recipient_telegram_id = cursor.fetchone()[0]

    bot.send_message(recipient_telegram_id, f'🎅 Таємний Санта пише:'
                                            f'\n\n{message.text}')
    bot.send_message(message.chat.id, '✅ Повідомлення надіслано.')
    del process_in_progress[message.chat.id]
    del secret_santa_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'notify_users')
@authorized_only(user_type='admins')
def notify_users(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees WHERE telegram_user_id IS NOT NULL')
        users = cursor.fetchall()

    for user in users:
        try:
            bot.send_message(user[0], '🎅 Привіт!'
                                      '\nМи розпочинаємо довгоочікувану гру - Таємний Санта!'
                                      '\nТи готовий?'
                                      '\nНатисни 👉 /start і приймай участь у грі!')
        except apihelper.ApiTelegramException:
            print(f'Error while sending message to {user[0]}.')

    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'secret_santa_fill_info')
@authorized_only(user_type='users')
def secret_santa_fill_info(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT emp.id FROM secret_santa_info '
                       'JOIN employees emp ON employee_id = emp.id '
                       'WHERE emp.telegram_user_id = %s', (call.message.chat.id,))
        if cursor.fetchone():
            bot.send_message(call.message.chat.id, '🎅 Ви вже заповнили інформацію для Таємного Санти.')
            return

    process_in_progress[call.message.chat.id] = 'secret_santa_fill_info'
    if secret_santa_data.get(call.message.chat.id):
        del secret_santa_data[call.message.chat.id]
    sent_message = bot.edit_message_text(
        '🎅 Введіть назву міста та номер відділення/поштомату (тільки НП):', call.message.chat.id,
        call.message.message_id)
    secret_santa_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(
        message.chat.id) == 'secret_santa_fill_info')
@authorized_only(user_type='users')
def secret_santa_fill_info_ans(message, skip_phone=False, delete_message=True):
    if not secret_santa_data[message.chat.id].get('address'):
        secret_santa_data[message.chat.id]['address'] = message.text
        sent_message = secret_santa_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT phone FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
            employee_phone = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup()
        confirm_btn = types.InlineKeyboardButton(text='✅ Це мій особистий номер',
                                                 callback_data='secret_santa_confirm_phone')
        markup.add(confirm_btn)

        if employee_phone:
            message_text = f'🎅 Санта вже знає твій номер телефону, '
            f'якщо {employee_phone} це твій особистий номер, натисни кнопку нижче.'
            f'\nЯкщо це не твій особистий номер, введи його:'
            reply_markup = markup

        else:
            message_text = '🎅 Введи, будь ласка, свій номер телефону для зв\'язку'
            reply_markup = None

        sent_message = bot.edit_message_text(
            message_text,
            message.chat.id,
            sent_message.message_id,
            reply_markup=reply_markup
        )
        secret_santa_data[message.chat.id]['sent_message'] = sent_message

    elif not secret_santa_data[message.chat.id].get('phone'):
        if skip_phone:
            secret_santa_data[message.chat.id]['phone'] = 'skip'
        else:
            secret_santa_data[message.chat.id]['phone'] = message.text
        sent_message = secret_santa_data[message.chat.id]['sent_message']
        if delete_message:
            bot.delete_message(message.chat.id, message.message_id)
        sent_message = bot.edit_message_text('🎅 Введіть ваші побажання, що би ви хотіли отримати?'
                                             '\nПостарайтеся бути якомога конкретнішими:', message.chat.id,
                                             sent_message.message_id)
        secret_santa_data[message.chat.id]['sent_message'] = sent_message

    elif not secret_santa_data[message.chat.id].get('requests'):
        secret_santa_data[message.chat.id]['requests'] = message.text
        sent_message = secret_santa_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        sent_message = bot.edit_message_text('🎅 Супер! А що би ви НЕ хотіли отримати?'
                                             '\nПостарайтеся бути якомога конкретнішими:', message.chat.id,
                                             sent_message.message_id)
        secret_santa_data[message.chat.id]['sent_message'] = sent_message

    elif not secret_santa_data[message.chat.id].get('aversions'):
        secret_santa_data[message.chat.id]['aversions'] = message.text

        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id, phone FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
            employee_id, employee_phone = cursor.fetchone()
            if secret_santa_data[message.chat.id]['phone'] == 'skip':
                secret_santa_data[message.chat.id]['phone'] = employee_phone
            cursor.execute(
                'INSERT INTO secret_santa_info (employee_id, address, request, aversions, phone) VALUES (%s, %s, '
                '%s, %s, %s)',
                (
                    employee_id,
                    secret_santa_data[message.chat.id]['address'],
                    secret_santa_data[message.chat.id]['requests'],
                    secret_santa_data[message.chat.id]['aversions'],
                    secret_santa_data[message.chat.id]['phone']
                ))
            conn.commit()
        scheduler.add_job(run_update_secret_santa_sheet, trigger='date', run_date=datetime.datetime.now())

        sent_message = secret_santa_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, sent_message.message_id)
        bot.send_message(message.chat.id, '🎅 Дякую за твою відповіді!'
                                          '\nТепер почекаємо поки всі збираються для гри!')
        del process_in_progress[message.chat.id]
        del secret_santa_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'secret_santa_confirm_phone')
@authorized_only(user_type='users')
def secret_santa_confirm_phone(call):
    secret_santa_fill_info_ans(call.message, skip_phone=True, delete_message=False)


@bot.callback_query_handler(func=lambda call: call.data == 'secret_santa_show_profile')
@authorized_only(user_type='users')
def secret_santa_show_profile(call):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT address, request, aversions, emp.name, secret_santa_info.phone FROM secret_santa_info '
                       'JOIN employees emp ON employee_id = emp.id '
                       'WHERE emp.telegram_user_id = %s', (call.message.chat.id,))
        if not cursor.rowcount:
            bot.send_message(call.message.chat.id, '🎅 Ви ще не заповнили інформацію для Таємного Санти.')
            return
        address, request, aversions, name, phone = cursor.fetchone()

    change_address_btn = types.InlineKeyboardButton(text='🏠 Змінити адресу', callback_data='santa_change_address')
    change_request_btn = types.InlineKeyboardButton(text='🎁 Змінити побажання', callback_data='santa_change_request')
    change_aversion_btn = types.InlineKeyboardButton(text='🚫 Змінити небажане', callback_data='santa_change_aversions')
    change_phone_btn = types.InlineKeyboardButton(text='📞 Змінити телефон', callback_data='santa_change_phone')

    markup = types.InlineKeyboardMarkup()
    markup.add(change_address_btn, change_request_btn, change_aversion_btn, change_phone_btn, row_width=1)

    bot.edit_message_text(f'🎅 Ваші дані для Таємного Санти:'
                          f'\n\n👤 Ім\'я: {name}'
                          f'\n📞 Телефон: {phone}'
                          f'\n🏠 Адреса: {address}'
                          f'\n🎁 Побажання: {request}'
                          f'\n🚫 Небажане: {aversions}',
                          call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('santa_change_'))
@authorized_only(user_type='users')
def secret_santa_change_info(call):
    change_type = call.data.split('_')[2]
    if change_type == 'address':
        process_in_progress[call.message.chat.id] = 'santa_change_address'
        sent_message = bot.send_message(call.message.chat.id, '🏠 Введіть нову адресу:')
    elif change_type == 'request':
        process_in_progress[call.message.chat.id] = 'santa_change_request'
        sent_message = bot.send_message(call.message.chat.id, '🎁 Введіть нові побажання:')
    elif change_type == 'aversions':
        process_in_progress[call.message.chat.id] = 'santa_change_aversions'
        sent_message = bot.send_message(call.message.chat.id, '🚫 Введіть нові небажані подарунки:')
    elif change_type == 'phone':
        process_in_progress[call.message.chat.id] = 'santa_change_phone'
        sent_message = bot.send_message(call.message.chat.id, '📞 Введіть новий номер телефону:')
    else:
        return

    secret_santa_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(
        message.chat.id) in ['santa_change_address', 'santa_change_request',
                             'santa_change_aversions', 'santa_change_phone'])
@authorized_only(user_type='users')
def secret_santa_change_info_ans(message):
    change_type = process_in_progress[message.chat.id].split('_')[2]
    new_info = message.text

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
        employee_id = cursor.fetchone()[0]
        cursor.execute(f'UPDATE secret_santa_info SET {change_type} = %s WHERE employee_id = %s',
                       (new_info, employee_id))
        conn.commit()

    sent_message = secret_santa_data[message.chat.id]['sent_message']
    bot.delete_message(message.chat.id, message.message_id)
    bot.delete_message(message.chat.id, sent_message.message_id)
    bot.send_message(message.chat.id, '🎅 Інформацію успішно змінено.')
    run_update_secret_santa_sheet()
    del process_in_progress[message.chat.id]
    del secret_santa_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'santa_notify_users')
@authorized_only(user_type='admins')
def santa_notify_users(call):
    bot.send_message(call.message.chat.id, '🔔 Надсилання нагадування...')
    secret_santa_notification_wrapper()
    bot.send_message(call.message.chat.id, '🔔 Нагадування надіслано.')
