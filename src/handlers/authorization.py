from telebot import types
from src.database import DatabaseConnection

def authorized_only(user_type):
    def decorator(func):
        def wrapper(data, *args, **kwargs):
            try:
                chat_id = data.chat.id
            except AttributeError:
                chat_id = data.from_user.id

            if (chat_id in authorized_ids[user_type] or chat_id in authorized_ids['temp_users'] and user_type == 'users'
                    or chat_id in authorized_ids['admins']):
                func(data, *args, **kwargs)
                print(f'User @{data.from_user.username} accessed {func.__name__}')
            else:
                with DatabaseConnection() as (conn, cursor):
                    cursor.execute('''SELECT employees.telegram_username
                                FROM admins
                                JOIN employees ON admins.employee_id = employees.id
                            ''')
                    admin_list = [username[0] for username in cursor.fetchall()]
                markup = types.ReplyKeyboardRemove()
                print(
                    f'Unauthorized user @{data.from_user.username} (chat id: {data.chat.id}) tried to access {func.__name__}')
                bot.send_message(chat_id, f'Ви не авторизовані для використання цієї функції.'
                                          f'\nЯкщо ви вважаєте, що це помилка, зверніться до адміністратора.'
                                          f'\n\nСписок адміністраторів: {", ".join(admin_list)}',
                                 reply_markup=markup)

        return wrapper

    return decorator
