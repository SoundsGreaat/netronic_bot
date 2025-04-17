from src.config import process_in_progress, bot, user_data
from src.handlers.authorization import authorized_only
from src.utils.main_menu_buttons import button_names


@bot.message_handler(
    func=lambda message: message.text not in button_names and process_in_progress.get(
        message.chat.id) == 'question_form')
@authorized_only(user_type='users')
def callback_ans(message):
    user_data['forms_ans'][message.chat.id] = message.text
    user_data['form_messages_to_delete'][message.chat.id].append(message.id)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_form_filling')
@authorized_only(user_type='users')
def cancel_form_filling(call):
    if process_in_progress.get(call.message.chat.id) == 'question_form':
        del process_in_progress[call.message.chat.id]
