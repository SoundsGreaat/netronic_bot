import time
from time import sleep

from telebot import types

from src.config import bot, process_in_progress, openai_data, client, OPENAI_ASSISTANT_ID
from src.database import DatabaseConnection
from src.handlers import authorized_only
from src.utils.main_menu_buttons import button_names


@bot.message_handler(func=lambda message: message.text == '💭 Маєш питання?')
@authorized_only(user_type='users')
def ai_question(message):
    openai_data[message.chat.id]['thread'] = client.beta.threads.create()
    process_in_progress[message.chat.id] = 'ai_question'
    cancel_btn = types.InlineKeyboardButton(text='🚪 Завершити сесію', callback_data='cancel_ai_question')
    markup = types.InlineKeyboardMarkup()
    markup.add(cancel_btn)
    sent_message = bot.send_message(message.chat.id, '🤖 Сесію зі штучним інтелектом розпочато. Задайте своє питання.',
                                    reply_markup=markup)
    openai_data[message.chat.id]['sent_message'] = sent_message


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
