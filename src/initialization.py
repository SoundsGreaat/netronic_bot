from src.config import bot, FERNET_KEY, SESSION_ENCRYPTED_PATH, SESSION_DECRYPTED_PATH, authorized_ids
from src.database import test_connection, update_authorized_users
from src.integrations import decrypt_session


def initialize_bot():
    if test_connection():
        decrypt_session(FERNET_KEY, input_file=SESSION_ENCRYPTED_PATH,
                        output_file=SESSION_DECRYPTED_PATH)
    update_authorized_users(authorized_ids)
    bot.infinity_polling()
