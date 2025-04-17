import threading
import time
from time import sleep

import gforms
from gforms import Form
from fake_useragent import FakeUserAgent
import requests
import os

from telebot import types

from src.config import bot, user_data, process_in_progress
from src.database import DatabaseConnection
from src.utils.messages import delete_messages


class FormFiller:
    def __init__(self, url):
        self.url = url
        self.sess = requests.session()
        self.ua = FakeUserAgent()
        self.sess.headers['User-Agent'] = self.ua.chrome
        self.form = Form()
        self.form.load(url=self.url, session=self.sess)

    def callback(self, element, page_index, element_index):
        ans = input(f'{element.name}: ')
        return ans

    def fill_form(self, callback=None):
        self.form.fill(callback)
        self.form.submit(emulate_history=True)

    def name(self):
        return self.form.name

    def description(self):
        return self.form.description

    def title(self):
        return self.form.title


def main():
    form_url = os.getenv('FORM_URL')
    form_filler = FormFiller(form_url)
    form_filler.fill_form(form_filler.callback)
    print('Form filled successfully')


def callback(element, page_index, element_index, message):
    if element.name == 'Ваш ПІБ':
        with DatabaseConnection() as (conn, cursor):
            cursor.execute('SELECT name FROM employees WHERE telegram_user_id = %s', (message.chat.id,))
            employee_name = cursor.fetchone()
            return employee_name[0]

    sent_message = bot.send_message(message.chat.id, f'{element.name}:')
    try:
        user_data['form_messages_to_delete'][message.chat.id].append(sent_message.message_id)
    except KeyError:
        pass
    process_in_progress[message.chat.id] = 'question_form'
    user_data['forms_timer'][message.chat.id] = time.time()

    while True:
        if (process_in_progress.get(message.chat.id) != 'question_form' or
                time.time() - user_data['forms_timer'][message.chat.id] > 3600):
            delete_messages(message.chat.id, 'form_messages_to_delete')
            try:
                del user_data['forms_timer'][message.chat.id]
            except KeyError:
                pass
            break
        if user_data['forms_ans'].get(message.chat.id):
            ans = user_data['forms_ans'][message.chat.id]
            del process_in_progress[message.chat.id]
            del user_data['forms_timer'][message.chat.id]
            del user_data['forms_ans'][message.chat.id]
            return ans
        sleep(0.5)


def send_question_form(message, form_url, delete_previous_message=False, disable_fill_form=False):
    if process_in_progress.get(message.chat.id) == 'question_form':
        delete_messages(message.chat.id, 'form_messages_to_delete')
    process_in_progress[message.chat.id] = 'question_form'
    try:
        if disable_fill_form:
            raise gforms.errors.SigninRequired(form_url)
        gform = FormFiller(form_url)
    except gforms.errors.SigninRequired:
        link_btn = types.InlineKeyboardButton(text='🔗 Посилання на форму', url=form_url)
        markup = types.InlineKeyboardMarkup()
        markup.add(link_btn)
        bot.send_message(message.chat.id, 'Натисніть кнопку нижче щоб перейти за посиланням.',
                         reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text='❌ Скасувати', callback_data='cancel_form_filling')
    markup.add(btn)

    sent_message = bot.send_message(message.chat.id,
                                    f'{gform.title()}\n\n{gform.description() if gform.description() else ""}',
                                    reply_markup=markup)
    user_data['form_messages_to_delete'][message.chat.id] = [sent_message.message_id]
    if delete_previous_message:
        user_data['form_messages_to_delete'][message.chat.id].append(message.message_id)

    def get_answer():
        try:
            gform.fill_form(
                lambda element, page_index, element_index: callback(element, page_index, element_index,
                                                                    sent_message)
            )
            bot.edit_message_text(sent_message.text, sent_message.chat.id, sent_message.message_id)
            bot.send_message(sent_message.chat.id,
                             '✅ Дякую за заповнення форми! Ваше питання буде розглянуто найближчим часом.')
            del user_data['form_messages_to_delete'][message.chat.id]
        except ValueError:
            pass

    thread = threading.Thread(target=get_answer)
    thread.start()


if __name__ == "__main__":
    main()
