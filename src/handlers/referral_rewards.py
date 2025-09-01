import asyncio
import datetime
import math

from telebot import types, apihelper

from config import bot, COMMENDATIONS_PER_PAGE, process_in_progress, make_card_data
from database import DatabaseConnection, find_contact_by_name
from handlers import authorized_only
from integrations.telethon_functions import send_photo
from utils.make_card import make_card_old
from utils.main_menu_buttons import button_names


@bot.callback_query_handler(func=lambda call: call.data == 'show_refs')
@authorized_only(user_type='moderators')
def show_refs(call):
    week_refs_button = types.InlineKeyboardButton(text='📅 За тиждень', callback_data='time_refs_week')
    month_refs_button = types.InlineKeyboardButton(text='📅 За місяць', callback_data='time_refs_month')
    year_refs_button = types.InlineKeyboardButton(text='📅 За рік', callback_data='time_refs_year')
    all_refs_button = types.InlineKeyboardButton(text='📅 Всі', callback_data='time_refs_all')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(week_refs_button, month_refs_button, year_refs_button, all_refs_button)
    bot.edit_message_text('🔍 Оберіть період:', call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_refs_'))
@authorized_only(user_type='moderators')
def show_refs_period(call):
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
                'SELECT referrals.id, name, referrals.position, referral_date '
                'FROM referrals '
                'JOIN employees ON employee_to_id = employees.id '
                'WHERE referral_date >= %s '
                'ORDER BY referral_date DESC', (start_date,)
            )
        else:
            cursor.execute(
                'SELECT referrals.id, name, referrals.position, referral_date '
                'FROM referrals '
                'JOIN employees ON employee_to_id = employees.id '
                'ORDER BY referral_date DESC'
            )
        refs = cursor.fetchall()

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='show_refs')
    markup = types.InlineKeyboardMarkup()

    if not refs:
        markup.add(back_btn)
        bot.edit_message_text('🔍 Подяк немає.', call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
        return

    total_pages = math.ceil(len(refs) / COMMENDATIONS_PER_PAGE)
    start_index = (page - 1) * COMMENDATIONS_PER_PAGE
    end_index = start_index + COMMENDATIONS_PER_PAGE
    refs_page = refs[start_index:end_index]

    for ref in refs_page:
        ref_id, employee_name, employee_position, ref_date = ref
        formatted_date = ref_date.strftime('%d.%m.%Y')
        split_name = employee_name.split()
        formatted_name = f'{split_name[0]} {split_name[1][0]}'
        button_text = f'👨‍💻 {formatted_name} | {formatted_date}'
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f'ref_{ref_id}'))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            types.InlineKeyboardButton(text='⬅️', callback_data=f'time_refs_{period}_{page - 1}'))
    if page < total_pages:
        nav_buttons.append(
            types.InlineKeyboardButton(text='➡️', callback_data=f'time_refs_{period}_{page + 1}'))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(back_btn)
    bot.edit_message_text(f'📜 Подяки ({page}/{total_pages}):', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_'))
@authorized_only(user_type='moderators')
def show_ref(call):
    ref_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT e_to.name, referrals.position, referral_date, e_from.name, e_from.position '
            'FROM referrals '
            'JOIN employees e_to ON employee_to_id = e_to.id '
            'JOIN employees e_from ON employee_from_id = e_from.id '
            'WHERE referrals.id = %s', (ref_id,)
        )
        employee_name, employee_position, ref_date, employee_from_name, employee_from_position = cursor.fetchone()

    formatted_date = ref_date.strftime('%d.%m.%Y')

    image = make_card_old(employee_name, employee_position,
                          'Дякуємо, що додали нового потужного гравця до нашої команди!',
                          'Бонус за реферальною програмою')

    message_text = f'👨‍💻 <b>{employee_name}</b> | {formatted_date}\n\nВід <b>{employee_from_name}</b>'
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити', callback_data=f'delref_{ref_id}')
    hide_btn = types.InlineKeyboardButton(text='❌ Сховати', callback_data='hide_message')
    markup = types.InlineKeyboardMarkup()
    markup.add(delete_btn, hide_btn)
    bot.send_photo(call.message.chat.id, image, caption=message_text, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('delref_'))
@authorized_only(user_type='admins')
def delete_ref(call):
    ref_id = int(call.data.split('_')[1])
    confirm_delete_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                                    callback_data=f'cdref_{ref_id}')
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data='hide_message')
    markup = types.InlineKeyboardMarkup()
    markup.add(confirm_delete_btn, back_btn)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cdref_'))
@authorized_only(user_type='admins')
def confirm_delete_ref(call):
    ref_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM referrals WHERE id = %s', (ref_id,))
        conn.commit()

    # update_commendations_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I',
    #                               'BOT AUTOFILL COMMENDATIONS',
    #                               DatabaseConnection)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    print(f'Referral record {ref_id} deleted by {call.from_user.username}.')
    bot.send_message(call.message.chat.id, '✅ Запис про реферал видалено.')


@bot.callback_query_handler(func=lambda call: call.data == 'send_ref')
@authorized_only(user_type='moderators')
def send_ref(call):
    process_in_progress[call.message.chat.id] = 'ref_search'

    if make_card_data.get(call.message.chat.id):
        del make_card_data[call.message.chat.id]

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_ref')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    sent_message = bot.edit_message_text('📝 Введіть ім\'я співробітника для пошуку:',
                                         call.message.chat.id, call.message.message_id, reply_markup=markup)
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'ref_search')
@authorized_only(user_type='moderators')
def proceed_ref_search(message):
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
                                             callback_data=f'giveref_{employee_id}')
            markup.add(btn)
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_ref')
        markup.add(cancel_btn)
        bot.delete_message(message.chat.id, message.message_id)
        sent_message = bot.edit_message_text('🔍 Оберіть співробітника:', message.chat.id, sent_message.message_id,
                                             reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('giveref_'))
@authorized_only(user_type='moderators')
def proceed_send_ref(call):
    employee_id = int(call.data.split('_')[1])
    process_in_progress[call.message.chat.id] = 'send_ref'
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, position, telegram_user_id FROM employees WHERE id = %s', (employee_id,))
        employee_data = cursor.fetchone()
    employee_name = employee_data[0]
    employee_position = employee_data[1]
    employee_telegram_id = employee_data[2]

    employee_name_basic = employee_name
    make_card_data[call.message.chat.id]['employee_id'] = employee_id
    make_card_data[call.message.chat.id]['employee_name_basic'] = employee_name_basic
    make_card_data[call.message.chat.id]['employee_position'] = employee_position
    make_card_data[call.message.chat.id]['employee_telegram_id'] = employee_telegram_id

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT name, position FROM employees WHERE telegram_user_id = %s',
                       (call.message.chat.id,))
        employee_from_name, employee_from_position = cursor.fetchone()

    image = make_card_old(
        make_card_data[call.message.chat.id]['employee_name_basic'],
        make_card_data[call.message.chat.id]['employee_position'],
        'Дякуємо, що додали нового потужного гравця до нашої команди!',
        'Бонус за реферальною програмою',
    )
    make_card_data[call.message.chat.id]['image'] = image

    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити', callback_data='confirm_send_ref')
    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_ref')
    markup.add(confirm_btn, cancel_btn)

    sent_message = bot.send_photo(call.message.chat.id, image, caption='📝 Перевірте подяку:', reply_markup=markup)
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_send_ref')
@authorized_only(user_type='moderators')
def confirm_send_ref(call):
    sent_message = make_card_data[call.message.chat.id]['sent_message']
    bot.delete_message(call.message.chat.id, sent_message.message_id)
    recipient_id = make_card_data[call.message.chat.id]['employee_telegram_id']
    image = make_card_data[call.message.chat.id]['image']

    employee_id = make_card_data[call.message.chat.id]['employee_id']
    ref_text = 'Дякуємо, що додали нового потужного гравця до нашої команди!'
    employee_position = make_card_data[call.message.chat.id]['employee_position']
    ref_date = datetime.datetime.now().date()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM employees WHERE telegram_user_id = %s', (call.message.chat.id,))
        sender_id = cursor.fetchone()[0]

        cursor.execute(
            'INSERT INTO referrals ('
            'employee_to_id, employee_from_id, referral_date, position) '
            'VALUES (%s, %s, %s, %s)',
            (employee_id, sender_id, ref_date, employee_position)
        )

        conn.commit()

    # update_commendations_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I',
    #                               'BOT AUTOFILL COMMENDATIONS',
    #                               DatabaseConnection)

    try:
        bot.send_photo(recipient_id, image, caption='📩 Вам було надіслано подяку.')
    except apihelper.ApiTelegramException as e:
        if e.error_code == 400 and "chat not found" in e.description:
            bot.send_message(call.message.chat.id, '🚫 Користувача не знайдено. Надсилаю подяку як юзербот.')
            print('Sending image to user failed. Chat not found. Trying to send image as user.')
            try:
                asyncio.run(send_photo(recipient_id, image, caption='📩 Вам надіслано подяку.'))
            except Exception as e:
                print('Error sending photo via userbot:', e)

    bot.send_photo(call.message.chat.id, image, caption='✅ Подяку надіслано.')

    del make_card_data[call.message.chat.id]
    if process_in_progress.get(call.message.chat.id):
        del process_in_progress[call.message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_send_ref')
@authorized_only(user_type='moderators')
def cancel_send_ref(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, '🚪 Створення подяки скасовано.')
    del make_card_data[call.message.chat.id]
    del process_in_progress[call.message.chat.id]
