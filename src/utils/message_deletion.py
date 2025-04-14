from telebot import types

def delete_messages(bot, chat_id, message_ids):
    for message_id in message_ids:
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Failed to delete message {message_id}: {e}")
