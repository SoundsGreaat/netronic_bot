import os

from collections import defaultdict
from openai import OpenAI
from telebot import TeleBot

FONT_ARIAL = '../assets/fonts/ARIAL.TTF'
FONT_ARIAL_BOLD = '../assets/fonts/ARIALBD.TTF'
COMMENDATION_TEMPLATE = '../assets/images/commendation_template.png'

SESSION_ENCRYPTED_PATH = '../sessions/userbot_session_encrypted'
SESSION_DECRYPTED_PATH = '../sessions/userbot_session.session'

BIRTHDAY_NOTIFICATIONS_USER_IDS = os.getenv('BIRTHDAY_NOTIFICATION_USER_IDS')

DATABASE_URL = os.environ.get('DATABASE_URL')

BOT_TOKEN = os.environ.get('NETRONIC_BOT_TOKEN')

OPENAI_ASSISTANT_ID = os.environ.get('OPENAI_ASSISTANT_ID')

FERNET_KEY = os.environ.get('FERNET_KEY')

COMMENDATIONS_PER_PAGE = 10

MONTH_DICT = {
    1: 'Січень 🌨️',
    2: 'Лютий ❄️',
    3: 'Березень 🌸',
    4: 'Квітень 🌷',
    5: 'Травень 🌼',
    6: 'Червень 🌞',
    7: 'Липень 🌴',
    8: 'Серпень 🏖️',
    9: 'Вересень 🍂',
    10: 'Жовтень 🎃',
    11: 'Листопад 🍁',
    12: 'Грудень 🎄'
}

authorized_ids = {
    'users': set(),
    'admins': set(),
    'moderators': set(),
    'temp_users': set(),
}

user_data = {
    'edit_link_mode': {},
    'messages_to_delete': {},
    'form_messages_to_delete': {},
    'forms_ans': {},
    'forms_timer': {},
}

edit_link_data = {
    'saved_message': {},
    'column': {},
    'show_back_btn': {},
}

edit_employee_data = defaultdict(dict)

add_keyword_data = defaultdict(dict)

add_director_data = defaultdict(dict)

add_link_data = defaultdict(dict)

add_employee_data = defaultdict(dict)

openai_data = defaultdict(dict)

make_card_data = defaultdict(dict)

add_sub_department_data = defaultdict(dict)

process_in_progress = {}

client = OpenAI()
bot = TeleBot(BOT_TOKEN)
