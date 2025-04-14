from telebot import types
from src.database import DatabaseConnection
from src.utils.message_deletion import delete_messages
from src.utils.form_filling import send_question_form
from src.services.notification import send_mass_message
from src.services.employee_management import proceed_add_employee_data
from src.services.form_management import callback as form_callback

def handle_start_command(message):
    bot.send_message(message.chat.id, "Welcome to the bot! Use /help to see available commands.")

def handle_help_command(message):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/delete_messages - Delete messages\n"
        "/send_question_form - Send question form\n"
        "/send_mass_message - Send mass message\n"
        "/proceed_add_employee_data - Add employee data\n"
    )
    bot.send_message(message.chat.id, help_text)

def handle_delete_messages_command(message):
    delete_messages(message.chat.id, message.message_id)

def handle_send_question_form_command(message):
    send_question_form(message.chat.id)

def handle_send_mass_message_command(message):
    send_mass_message(message.chat.id, message.text)

def handle_proceed_add_employee_data_command(message):
    proceed_add_employee_data(message.chat.id, message.text)
