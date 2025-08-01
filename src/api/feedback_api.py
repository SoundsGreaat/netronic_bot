from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os
from telebot import types

from config import bot
from database import DatabaseConnection
from handlers import authorized_only
from integrations.crm_api_functions import send_rating_to_crm

app = FastAPI()

BOT_API_KEY = os.getenv("BOT_API_KEY")


class RateRequest(BaseModel):
    user_id: int
    task_name: str
    task_id: str


@app.post("/send-feedback-request")
async def send_feedback(
        payload: RateRequest,
        authorization: str = Header(None)
):
    if authorization != f"Bearer {BOT_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    message = (
        f"👋 Привіт! Задачу *{payload.task_name}* (ID: `{payload.task_id}`) було закрито.\n\n"
        f"Будь ласка, оцініть якість наданих послуг:\n"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton(text="⭐️ 1", callback_data=f"rate:1:{payload.task_id}"),
        types.InlineKeyboardButton(text="⭐️ 2", callback_data=f"rate:2:{payload.task_id}"),
        types.InlineKeyboardButton(text="⭐️ 3", callback_data=f"rate:3:{payload.task_id}"),
        types.InlineKeyboardButton(text="⭐️ 4", callback_data=f"rate:4:{payload.task_id}"),
        types.InlineKeyboardButton(text="⭐️ 5", callback_data=f"rate:5:{payload.task_id}")
    ]

    markup.add(*buttons)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('SELECT telegram_user_id FROM employees WHERE crm_id = %s', (payload.user_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found in the database")
        telegram_user_id = result[0]

    try:
        bot.send_message(
            chat_id=telegram_user_id,
            text=message,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

    return {"status": "ok"}


@bot.callback_query_handler(func=lambda call: call.data.startswith('rate:'))
@authorized_only(user_type='users')
def handle_rating(call):
    _, rating, task_id = call.data.split(':')
    rating = int(rating)
    task_id = int(task_id)
    if send_rating_to_crm(task_id, rating):
        bot.answer_callback_query(call.id, text="Дякуємо за вашу оцінку!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, text="Помилка при відправці оцінки.", show_alert=True)
    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.id)
