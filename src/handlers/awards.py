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


@bot.callback_query_handler(func=lambda call: call.data == 'show_awards')
@authorized_only(user_type='moderators')
def show_awards(call):
    week_awards_button = types.InlineKeyboardButton(text='📅 За тиждень', callback_data='time_awards_week')
    month_awards_button = types.InlineKeyboardButton(text='📅 За місяць', callback_data='time_awards_month')
    year_awards_button = types.InlineKeyboardButton(text='📅 За рік', callback_data='time_awards_year')
    all_awards_button = types.InlineKeyboardButton(text='📅 Всі', callback_data='time_awards_all')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(week_awards_button, month_awards_button, year_awards_button, all_awards_button)
    bot.edit_message_text('🔍 Оберіть період:', call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_awards_'))
@authorized_only(user_type='moderators')
def show_awards_period(call):
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
                'SELECT awards.id, name, awards.position, award_text, award_date '
                'FROM awards '
                'JOIN employees ON employee_to_id = employees.id '
                'WHERE award_date >= %s '
                'ORDER BY award_date DESC', (start_date,)
            )
        else:
            cursor.execute(
                'SELECT awards.id, name, awards.position, award_text, award_date '
                'FROM awards '
                'JOIN employees ON employee_to_id = employees.id '
                'ORDER BY award_date DESC'
            )
        awards = cursor.fetchall()

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='show_awards')
    markup = types.InlineKeyboardMarkup()

    if not awards:
        markup.add(back_btn)
        bot.edit_message_text('🔍 Нагород немає.', call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
        return

    total_pages = math.ceil(len(awards) / COMMENDATIONS_PER_PAGE)
    start_index = (page - 1) * COMMENDATIONS_PER_PAGE
    end_index = start_index + COMMENDATIONS_PER_PAGE
    awards_page = awards[start_index:end_index]

    for award in awards_page:
        award_id, employee_name, employee_position, _, award_date = award
        formatted_date = award_date.strftime('%d.%m.%Y')
        split_name = employee_name.split()
        formatted_name = f'{split_name[0]} {split_name[1][0]}'
        button_text = f'👨‍💻 {formatted_name} | {formatted_date}'
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f'award_{award_id}'))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            types.InlineKeyboardButton(text='⬅️', callback_data=f'time_awards_{period}_{page - 1}'))
    if page < total_pages:
        nav_buttons.append(
            types.InlineKeyboardButton(text='➡️', callback_data=f'time_awards_{period}_{page + 1}'))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(back_btn)
    bot.edit_message_text(f'📜 Нагороди ({page}/{total_pages}):', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('award_'))
@authorized_only(user_type='moderators')
def show_award(call):
    award_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT e_to.name, awards.position, award_text, award_date, e_from.name, e_from.position '
            'FROM awards '
            'JOIN employees e_to ON employee_to_id = e_to.id '
            'JOIN employees e_from ON employee_from_id = e_from.id '
            'WHERE awards.id = %s', (award_id,)
        )
        employee_name, employee_position, award_text, award_date, employee_from_name, \
            employee_from_position = cursor.fetchone()

    formatted_date = award_date.strftime('%d.%m.%Y')

    image = make_card_old(employee_name, employee_position, award_text, 'Нагорода')

    message_text = (f'👨‍💻 <b>{employee_name}</b> | {formatted_date}\n\nВід <b>{employee_from_name}</b>'
                    f'\n\n{award_text}')
    delete_btn = types.InlineKeyboardButton(text='🗑️ Видалити', callback_data=f'delaward_{award_id}')
    hide_btn = types.InlineKeyboardButton(text='❌ Сховати', callback_data='hide_message')
    markup = types.InlineKeyboardMarkup()
    markup.add(delete_btn, hide_btn)
    bot.send_photo(call.message.chat.id, image, caption=message_text, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('delaward_'))
@authorized_only(user_type='admins')
def delete_award(call):
    award_id = int(call.data.split('_')[1])
    confirm_delete_btn = types.InlineKeyboardButton(text='✅ Підтвердити видалення',
                                                    callback_data=f'cdaward_{award_id}')
    back_btn = types.InlineKeyboardButton(text='❌ Скасувати видалення', callback_data='hide_message')
    markup = types.InlineKeyboardMarkup()
    markup.add(confirm_delete_btn, back_btn)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cdaward_'))
@authorized_only(user_type='admins')
def confirm_delete_award(call):
    award_id = int(call.data.split('_')[1])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM awards WHERE id = %s', (award_id,))
        conn.commit()

    # update_commendations_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I',
    #                               'BOT AUTOFILL COMMENDATIONS',
    #                               DatabaseConnection)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    print(f'Award {award_id} deleted by {call.from_user.username}.')
    bot.send_message(call.message.chat.id, '✅ Нагороду видалено.')


@bot.callback_query_handler(func=lambda call: call.data == 'send_award')
@authorized_only(user_type='moderators')
def send_award(call):
    process_in_progress[call.message.chat.id] = 'award_search'

    if make_card_data.get(call.message.chat.id):
        del make_card_data[call.message.chat.id]

    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_award')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    sent_message = bot.edit_message_text('📝 Введіть ім\'я співробітника для пошуку:',
                                         call.message.chat.id, call.message.message_id, reply_markup=markup)
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'award_search')
@authorized_only(user_type='moderators')
def proceed_award_search(message):
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
                                             callback_data=f'giveaward_{employee_id}')
            markup.add(btn)
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_award')
        markup.add(cancel_btn)
        bot.delete_message(message.chat.id, message.message_id)
        sent_message = bot.edit_message_text('🔍 Оберіть співробітника:', message.chat.id, sent_message.message_id,
                                             reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('giveaward_'))
@authorized_only(user_type='moderators')
def proceed_send_award(call):
    employee_id = int(call.data.split('_')[1])
    process_in_progress[call.message.chat.id] = 'send_award'
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

    sent_message = bot.edit_message_text(
        '📝 Введіть текст нагороди:',
        call.message.chat.id, call.message.message_id, parse_mode='HTML')
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'send_award')
@authorized_only(user_type='moderators')
def send_award_name(message, position_changed=False):
    data_filled = False

    if not make_card_data[message.chat.id].get('award_text'):
        make_card_data[message.chat.id]['award_text'] = message.text
        sent_message = make_card_data[message.chat.id]['sent_message']
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, sent_message.message_id)
        data_filled = True

    if data_filled or position_changed:
        if data_filled or position_changed:
            with DatabaseConnection() as (conn, cursor):
                cursor.execute('SELECT name, position FROM employees WHERE telegram_user_id = %s',
                               (message.chat.id,))
                employee_from_name, employee_from_position = cursor.fetchone()

        image = make_card_old(
            make_card_data[message.chat.id]['employee_name_basic'],
            make_card_data[message.chat.id]['employee_position'],
            make_card_data[message.chat.id]['award_text'],
            'Нагорода',
        )
        make_card_data[message.chat.id]['image'] = image

        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton(text='✅ Підтвердити', callback_data='confirm_send_award')
        position_change_btn = types.InlineKeyboardButton(text='🔄 Змінити посаду', callback_data='awd_change_position')
        cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_send_award')
        markup.add(confirm_btn, cancel_btn, position_change_btn)

        sent_message = bot.send_photo(message.chat.id, image, caption='📝 Перевірте нагороду:', reply_markup=markup)
        make_card_data[message.chat.id]['sent_message'] = sent_message


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_send_award')
@authorized_only(user_type='moderators')
def confirm_send_award(call):
    sent_message = make_card_data[call.message.chat.id]['sent_message']
    bot.delete_message(call.message.chat.id, sent_message.message_id)
    recipient_id = make_card_data[call.message.chat.id]['employee_telegram_id']
    image = make_card_data[call.message.chat.id]['image']

    employee_id = make_card_data[call.message.chat.id]['employee_id']
    award_text = make_card_data[call.message.chat.id]['award_text']
    employee_position = make_card_data[call.message.chat.id]['employee_position']
    award_date = datetime.datetime.now().date()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id FROM employees WHERE telegram_user_id = %s', (call.message.chat.id,))
        sender_id = cursor.fetchone()[0]

        cursor.execute(
            'INSERT INTO awards ('
            'employee_to_id, employee_from_id, award_text, award_date, position) '
            'VALUES (%s, %s, %s, %s, %s)',
            (employee_id, sender_id, award_text, award_date, employee_position)
        )

        conn.commit()

    # update_commendations_in_sheet('15_V8Z7fW-KP56dwpqbe0osjlJpldm6R5-bnUoBEgM1I',
    #                               'BOT AUTOFILL COMMENDATIONS',
    #                               DatabaseConnection)

    try:
        bot.send_photo(recipient_id, image, caption='📩 Вам було надіслано нагороду.')
    except apihelper.ApiTelegramException as e:
        if e.error_code == 400 and "chat not found" in e.description:
            bot.send_message(call.message.chat.id, '🚫 Користувача не знайдено. Надсилаю нагороду як юзербот.')
            print('Sending image to user failed. Chat not found. Trying to send image as user.')
            try:
                asyncio.run(send_photo(recipient_id, image, caption='📩 Вам надіслано нагороду.'))
            except Exception as e:
                print('Error sending photo via userbot:', e)

    bot.send_photo(call.message.chat.id, image, caption='✅ Нагороду надіслано.')

    del make_card_data[call.message.chat.id]
    if process_in_progress.get(call.message.chat.id):
        del process_in_progress[call.message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'awd_change_position')
@authorized_only(user_type='moderators')
def awd_change_position(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    process_in_progress[call.message.chat.id] = 'awd_change_position'
    sent_message = bot.send_message(call.message.chat.id, '💼 Введіть нову посаду:')
    make_card_data[call.message.chat.id]['sent_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'awd_change_position')
@authorized_only(user_type='moderators')
def awd_change_position_ans(message):
    make_card_data[message.chat.id]['employee_position'] = message.text
    sent_message = make_card_data[message.chat.id]['sent_message']
    bot.delete_message(message.chat.id, message.message_id)
    bot.delete_message(message.chat.id, sent_message.message_id)

    del process_in_progress[message.chat.id]

    send_award_name(message, position_changed=True)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_send_award')
@authorized_only(user_type='moderators')
def cancel_send_award(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, '🚪 Створення нагороди скасовано.')
    del make_card_data[call.message.chat.id]
    del process_in_progress[call.message.chat.id]

