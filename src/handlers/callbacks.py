from telebot import types
from src.database import DatabaseConnection
from src.utils.message_deletion import delete_messages
from src.utils.form_filling import send_question_form
from src.services.notification import send_mass_message
from src.services.employee_management import proceed_add_employee_data
from src.services.form_management import callback as form_callback

def handle_callback_query(call):
    if call.data == 'delete_messages':
        delete_messages(call.message.chat.id, call.message.message_id)
    elif call.data == 'send_question_form':
        send_question_form(call.message.chat.id)
    elif call.data == 'send_mass_message':
        send_mass_message(call.message.chat.id, call.message.text)
    elif call.data == 'proceed_add_employee_data':
        proceed_add_employee_data(call.message.chat.id, call.message.text)
    else:
        form_callback(call)
