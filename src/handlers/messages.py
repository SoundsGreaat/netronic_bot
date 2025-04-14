from telebot import types
from src.database import DatabaseConnection
from src.utils.message_deletion import delete_messages
from src.utils.form_filling import send_question_form
from src.services.notification import send_mass_message
from src.services.employee_management import proceed_add_employee_data
from src.services.form_management import callback as form_callback

def handle_text_message(message):
    bot.send_message(message.chat.id, "You sent a text message.")

def handle_photo_message(message):
    bot.send_message(message.chat.id, "You sent a photo.")

def handle_video_message(message):
    bot.send_message(message.chat.id, "You sent a video.")

def handle_document_message(message):
    bot.send_message(message.chat.id, "You sent a document.")
