from telebot import types
from src.utils.form_filling import FormFiller

def callback(call):
    form_url = "your_form_url"  # Replace with the actual form URL
    form_filler = FormFiller(form_url)
    form_filler.fill_form(form_filler.callback)
    print('Form filled successfully')
