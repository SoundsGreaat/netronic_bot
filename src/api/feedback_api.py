from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os
from telebot import types

from config import bot

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

    try:
        bot.send_message(
            chat_id=payload.user_id,
            text=message,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

    return {"status": "ok"}
