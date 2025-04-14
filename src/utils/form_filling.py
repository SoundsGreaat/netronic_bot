from telebot import types
import gforms
from src.database import DatabaseConnection

def send_question_form(chat_id):
    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT form_url FROM forms WHERE form_type = %s', ('question',))
        form_url = cursor.fetchone()[0]

    form = gforms.Form(form_url)
    form.load()

    questions = form.questions
    answers = []

    for question in questions:
        if question.type == 'text':
            answers.append(types.InputTextMessageContent(question.text))
        elif question.type == 'choice':
            answers.append(types.InputTextMessageContent(question.choices[0]))

    form.fill(answers)
    form.submit()

    return 'Form submitted successfully'
