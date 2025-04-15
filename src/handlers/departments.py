from rapidfuzz import process
from telebot import types, apihelper

from src.config import bot, process_in_progress, user_data, add_director_data, authorized_ids, add_employee_data, \
    add_sub_department_data
from src.database import DatabaseConnection, find_contact_by_name
from src.handlers import authorized_only
from src.utils import button_names, delete_messages


@bot.callback_query_handler(func=lambda call: call.data == 'departments')
@authorized_only(user_type='users')
def send_departments(call):
    buttons = []
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT id, name, additional_instance FROM departments ORDER BY name')
        departments = cursor.fetchall()

    for department in departments:
        department_id = department[0]
        department_name = department[1]
        additional_instance = department[2]

        if additional_instance:
            call_data = f'additional_{int(additional_instance)}_{department_id}'
        else:
            call_data = f'dep_{int(additional_instance)}_{department_id}'

        btn = types.InlineKeyboardButton(text=f'🏢 {department_name}', callback_data=call_data)
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text('Оберіть департамент:', call.message.chat.id, call.message.message_id,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('additional_'))
@authorized_only(user_type='users')
def send_inter_department_contacts(call):
    additional_instance, department_id = map(int, call.data.split('_')[1:])
    buttons = []

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''SELECT id, name, is_chief_department FROM intermediate_departments WHERE department_id = %s
                            ORDER BY is_chief_department DESC, name''',
                       (department_id,))
        intermediate_departments = cursor.fetchall()

    for intermediate_department in intermediate_departments:
        intermediate_department_id = intermediate_department[0]
        intermediate_department_name = intermediate_department[1]
        intermediate_department_is_chief = intermediate_department[2]
        emoji = '👔' if intermediate_department_is_chief else '🗄️'
        btn = types.InlineKeyboardButton(text=f'{emoji} {intermediate_department_name}',
                                         callback_data=f'dep_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}')
        buttons.append(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_'))
@authorized_only(user_type='users')
def send_department_contacts(call):
    if process_in_progress.get(call.message.chat.id) == 'add_director':
        del process_in_progress[call.message.chat.id]
        del add_director_data[call.message.chat.id]
    additional_instance, department_id = map(int, call.data.split('_')[1:3])
    buttons = []
    if additional_instance:
        intermediate_department_id = int(call.data.split('_')[3])
        db_column = 'intermediate_department_id'
        instance_id = intermediate_department_id
    else:
        intermediate_department_id = 0
        db_column = 'department_id'
        instance_id = department_id

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(f'''SELECT id, name, is_chief_department FROM sub_departments WHERE {db_column} = %s
                                ORDER BY is_chief_department DESC, name''',
                       (instance_id,))
        sub_departments = cursor.fetchall()

    add_director = True

    for sub_department in sub_departments:
        sub_department_id = sub_department[0]
        sub_department_name = sub_department[1]
        sub_department_is_chief = sub_department[2]
        if sub_department_is_chief:
            add_director = False

        emoji = '👔' if sub_department_is_chief else '🗄️'
        btn = types.InlineKeyboardButton(text=f'{emoji} {sub_department_name}',
                                         callback_data=f'sub_dep_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}_{sub_department_id}')
        buttons.append(btn)
    if additional_instance:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                              callback_data=f'additional_{additional_instance}_{department_id}')
    else:
        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='departments')

    if add_director:
        add_director_btn = types.InlineKeyboardButton(text='➕ Додати керівника департаменту',
                                                      callback_data=f'add_dir_{additional_instance}_{department_id}_'
                                                                    f'{intermediate_department_id}')
    else:
        add_director_btn = types.InlineKeyboardButton(text='🗑️ Видалити керівника департаменту',
                                                      callback_data=f'del_dir_{additional_instance}_{department_id}_'
                                                                    f'{intermediate_department_id}')

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(*buttons)
    if call.message.chat.id in authorized_ids['admins']:
        markup.row(add_director_btn)
    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть відділ:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_dir_'))
@authorized_only(user_type='admins')
def add_director(call):
    additional_instance, department_id, intermediate_department_id = map(int, call.data.split('_')[2:])
    process_in_progress[call.message.chat.id] = 'add_director'
    add_director_data[call.message.chat.id]['department_id'] = department_id
    add_director_data[call.message.chat.id]['additional_instance'] = additional_instance
    add_director_data[call.message.chat.id]['intermediate_department_id'] = intermediate_department_id
    cancel_btn = types.InlineKeyboardButton(text='❌ Скасувати',
                                            callback_data=f'dep_{additional_instance}_{department_id}_'
                                                          f'{intermediate_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, '👤 Введіть назву посади керівника'
                                                          '\n Наприклад: <i>Виконавчий директор</i>',
                                    reply_markup=markup, parse_mode='HTML')
    add_director_data[call.message.chat.id]['saved_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_director')
@authorized_only(user_type='admins')
def proceed_add_director(message):
    department_id = add_director_data[message.chat.id]['department_id']
    additional_instance = add_director_data[message.chat.id]['additional_instance']
    intermediate_department_id = add_director_data[message.chat.id]['intermediate_department_id']
    sent_message = add_director_data[message.chat.id]['saved_message']
    if not additional_instance:
        intermediate_department_id = None
    director_position = message.text
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''INSERT INTO sub_departments (name, is_chief_department, department_id,
                           intermediate_department_id)
                           VALUES (%s, %s, %s, %s) RETURNING id''',
                       (director_position, True, department_id, intermediate_department_id))
        conn.commit()
    del process_in_progress[message.chat.id]
    del add_director_data[message.chat.id]
    back_btn = types.InlineKeyboardButton(text='🔙 Назад',
                                          callback_data=f'dep_{additional_instance}_{department_id}_'
                                                        f'{intermediate_department_id}')
    markup = types.InlineKeyboardMarkup()
    markup.add(back_btn)
    bot.delete_message(message.chat.id, sent_message.message_id)
    bot.send_message(message.chat.id, f'✅ Керівника департаменту успішно додано.', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_dep_'))
@authorized_only(user_type='users')
def send_sub_departments_contacts(call):
    additional_instance, department_id, intermediate_department_id, sub_department_id = map(int,
                                                                                            call.data.split('_')[2:])
    markup = types.InlineKeyboardMarkup(row_width=1)

    with DatabaseConnection() as (conn, cursor):
        query = '''
            SELECT DISTINCT e.id, e.name
            FROM employees e
            LEFT JOIN additional_sub_departments ad ON e.sub_department_id = ad.sub_department_id
            WHERE e.sub_department_id = %s
    
            UNION
    
            SELECT DISTINCT e.id, e.name
            FROM employees e
            INNER JOIN additional_sub_departments ad ON e.id = ad.employee_id
            WHERE ad.sub_department_id = %s
            
            ORDER BY name
        '''
        cursor.execute(query, (sub_department_id, sub_department_id))
        employees = cursor.fetchall()

    for employee in employees:
        employee_id = employee[0]
        employee_name = employee[1]

        btn = types.InlineKeyboardButton(text=f'👨‍💻 {employee_name}',
                                         callback_data=f'profile_{additional_instance}_{department_id}_'
                                                       f'{intermediate_department_id}_{sub_department_id}_'
                                                       f'{employee_id}')
        markup.add(btn)

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'dep_{additional_instance}_{department_id}_'
                                                                        f'{intermediate_department_id}')

    if call.from_user.id in authorized_ids['admins']:
        add_employee_btn = types.InlineKeyboardButton(text='➕ Додати співробітника',
                                                      callback_data=f'add_employee_{additional_instance}_'
                                                                    f'{department_id}_{intermediate_department_id}_'
                                                                    f'{sub_department_id}')
        markup.row(add_employee_btn)

    markup.row(back_btn)

    bot.edit_message_text(f'Оберіть співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)

    if process_in_progress.get(call.message.chat.id) == 'add_employee':
        del process_in_progress[call.message.chat.id]
    if add_employee_data.get(call.message.chat.id):
        del add_employee_data[call.message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data == 'search')
@authorized_only(user_type='users')
def send_search_form(call):
    process_in_progress[call.message.chat.id] = 'search'

    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(back_btn)

    bot.edit_message_text('Введіть ім\'я, прізвище або посаду співробітника:', call.message.chat.id,
                          call.message.message_id, reply_markup=markup)

    user_data['messages_to_delete'][call.message.chat.id] = call.message.message_id


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

            formatted_name = employee_name.split()
            formatted_name = f'{formatted_name[0]} {formatted_name[1]}'
            btn = types.InlineKeyboardButton(text=f'👨‍💻 {formatted_name} - {employee_position}',
                                             callback_data=f'profile_s_{message.text}_{employee_id}')
            markup.add(btn)

        back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data='back_to_send_contacts')
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('bck_srch_'))
@authorized_only(user_type='users')
def back_to_search_results(call):
    call.message.text = '_'.join(call.data.split('_')[2:])
    proceed_contact_search(call.message, edit_message=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_add_'))
@authorized_only(user_type='admins')
def manage_additional_departments(call):
    employee_id, edit_message = call.data.split('_')[2:]
    employee_id = int(employee_id)
    edit_message = True if edit_message == 'True' else False

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT sub_departments.name, additional_sub_departments.id '
                       'FROM additional_sub_departments '
                       'JOIN sub_departments ON additional_sub_departments.sub_department_id = sub_departments.id '
                       'WHERE additional_sub_departments.employee_id = %s', (employee_id,))
        additional_sub_departments = cursor.fetchall()

    markup = types.InlineKeyboardMarkup(row_width=1)
    if additional_sub_departments:
        for sub_department_name, add_sub_department_id in additional_sub_departments:
            show_sub_department_btn = types.InlineKeyboardButton(text=f'🗄️ {sub_department_name}',
                                                                 callback_data=f'manage_subdep_{employee_id}_'
                                                                               f'{add_sub_department_id}')
            markup.add(show_sub_department_btn)

        message_text = 'Додаткові відділи:'
    else:
        message_text = 'Додаткові відділи відсутні.'
    add_sub_department_btn = types.InlineKeyboardButton(text='➕ Додати відділ',
                                                        callback_data=f'add_subdep_{employee_id}')
    markup.add(add_sub_department_btn)
    if edit_message:
        bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
        print(1)
    else:
        bot.send_message(call.message.chat.id, message_text, reply_markup=markup)
        print(2)


@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_subdep_'))
@authorized_only(user_type='admins')
def manage_sub_department(call):
    employee_id, add_sub_department_id = map(int, call.data.split('_')[2:])

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT sub_departments.name, additional_sub_departments.position, employees.name '
                       'FROM additional_sub_departments '
                       'JOIN sub_departments ON additional_sub_departments.sub_department_id = sub_departments.id '
                       'JOIN employees ON additional_sub_departments.employee_id = employees.id '
                       'WHERE additional_sub_departments.id = %s AND additional_sub_departments.employee_id = %s',
                       (add_sub_department_id, employee_id))
        sub_department_name, position, employee_name = cursor.fetchone()

    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton(text='🔙 Назад', callback_data=f'manage_add_{employee_id}_{True}')
    delete_sub_department_btn = types.InlineKeyboardButton(text='🗑️ Видалити відділ',
                                                           callback_data=f'del_subdep_{employee_id}_'
                                                                         f'{add_sub_department_id}')
    markup.add(delete_sub_department_btn, back_btn)
    bot.edit_message_text(f'🗄️ {sub_department_name} ({position}) для контакту <b>{employee_name}</b>',
                          call.message.chat.id,
                          call.message.message_id, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_subdep_'))
@authorized_only(user_type='admins')
def add_sub_department(call):
    employee_id = int(call.data.split('_')[2])

    process_in_progress[call.message.chat.id] = 'add_sub_department'
    if add_sub_department_data.get(call.message.chat.id):
        del add_sub_department_data[call.message.chat.id]

    add_sub_department_data[call.message.chat.id]['employee_id'] = employee_id
    bot.delete_message(call.message.chat.id, call.message.message_id)
    sent_message = bot.send_message(call.message.chat.id, '🗄️ Введіть приблизну назву відділу:')
    add_sub_department_data[call.message.chat.id]['saved_message'] = sent_message


@bot.message_handler(func=lambda message: message.text not in button_names and process_in_progress.get(
    message.chat.id) == 'add_sub_department')
@authorized_only(user_type='admins')
def add_sub_department_ans(message):
    employee_id = add_sub_department_data[message.chat.id]['employee_id']
    bot.delete_message(message.chat.id, message.message_id)
    bot.delete_message(message.chat.id, add_sub_department_data[message.chat.id]['saved_message'].message_id)

    if not add_sub_department_data[message.chat.id].get('sub_department_id'):
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT id, name FROM sub_departments')
            sub_departments = cursor.fetchall()
            original_sub_departments = [(sub_department[0], sub_department[1].strip()) for sub_department in
                                        sub_departments]
            sub_departments = [(id, name.lower()) for id, name in original_sub_departments]

        query = message.text.lower()
        best_match = process.extractOne(query, [name for id, name in sub_departments])
        original_best_match = next((id, name) for id, name in original_sub_departments if name.lower() == best_match[0])

        sub_department_id = original_best_match[0]
        sub_department_name = original_best_match[1]
        add_sub_department_data[message.chat.id]['sub_department_id'] = sub_department_id

        sent_message = bot.send_message(message.chat.id,
                                        f'Обрано відділ <b>{sub_department_name}</b> ({best_match[1]:.1f}%)'
                                        f'\nВведіть посаду для відділу:',
                                        parse_mode='HTML')
        add_sub_department_data[message.chat.id]['saved_message'] = sent_message

    elif not add_sub_department_data[message.chat.id].get('position'):
        position = message.text
        sub_department_id = add_sub_department_data[message.chat.id]['sub_department_id']
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('''
            INSERT INTO additional_sub_departments (employee_id, sub_department_id, position)
            VALUES (%s, %s, %s) 
            
            RETURNING (
            SELECT name 
            FROM sub_departments
            WHERE sub_departments.id = additional_sub_departments.sub_department_id)
            ''',
                           (employee_id, sub_department_id, position))
            conn.commit()
            sub_department_name = cursor.fetchone()[0]

        bot.send_message(message.chat.id, f'✅ Відділ <b>{sub_department_name}</b> ({position}) додано.',
                         parse_mode='HTML')
        del process_in_progress[message.chat.id]
        del add_sub_department_data[message.chat.id]


@bot.callback_query_handler(func=lambda call: call.data.startswith('del_subdep_'))
@authorized_only(user_type='admins')
def delete_sub_department(call):
    employee_id, add_sub_department_id = map(int, call.data.split('_')[2:])
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('DELETE FROM additional_sub_departments WHERE id = %s', (add_sub_department_id,))
        conn.commit()
    call.data = f'manage_add_{employee_id}_{True}'
    manage_additional_departments(call)
    print(f'Employee {call.from_user.username} deleted additional sub_department {add_sub_department_id}.')
