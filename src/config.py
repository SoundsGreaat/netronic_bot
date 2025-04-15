import os

from collections import defaultdict
from openai import OpenAI
from telebot import TeleBot


COMMENDATIONS_PER_PAGE = 10

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

month_dict = {
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

client = OpenAI()
assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
bot = TeleBot(os.getenv('NETRONIC_BOT_TOKEN'))
fernet_key = os.environ.get('FERNET_KEY')
