import os
from io import BytesIO
from pathlib import Path

import telethon
import tempfile
from cryptography.fernet import Fernet
from telethon.sync import TelegramClient

api_id = int(os.environ.get('TELETHON_API_ID'))
api_hash = os.environ.get('TELETHON_API_HASH')
api_id_userbot = int(os.environ.get('TELETHON_API_ID_USERBOT'))
api_hash_userbot = os.environ.get('TELETHON_API_HASH_USERBOT')
token = os.environ.get('NETRONIC_BOT_TOKEN')
fernet_key = os.environ.get('FERNET_KEY')


def encrypt_session(key):
    fernet = Fernet(key)
    with open('send_message.session', 'rb') as file:
        session = file.read()
    encrypted_session = fernet.encrypt(session)
    with open('send_message_session_encrypted', 'wb') as file:
        file.write(encrypted_session)


def decrypt_session(key):
    fernet = Fernet(key)
    with open('send_message_session_encrypted', 'rb') as file:
        encrypted_session = file.read()
    session = fernet.decrypt(encrypted_session)
    with open('send_message.session', 'wb') as file:
        file.write(session)


async def proceed_find_user_id(username):
    client = TelegramClient('find_user_id', api_id, api_hash)
    await client.start(bot_token=token)
    print(await client.get_me())
    try:
        async with client:
            user = await client.get_entity(username)
            user_id = user.id
            return user_id
    except (ValueError, telethon.errors.rpcerrorlist.UsernameInvalidError):
        return None
    finally:
        await client.disconnect()


async def send_message(user_id, message):
    client = TelegramClient('send_message', api_id_userbot, api_hash_userbot)
    await client.start()
    try:
        async with client:
            await client.send_message(user_id, message)
    except telethon.errors.rpcerrorlist.UserIsBlockedError:
        return False
    finally:
        await client.disconnect()


async def send_photo(user_id, image, caption):
    client = TelegramClient('send_message', api_id_userbot, api_hash_userbot)
    await client.start()

    root_dir = Path(__file__).parent

    with tempfile.NamedTemporaryFile(dir=root_dir, suffix='.png', delete=False) as temp:
        image_bytes = BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes = image_bytes.getvalue()

        temp.write(image_bytes)
        temp.seek(0)
        image_path = temp.name
        print(f'Temp file saved as {image_path}')

    try:
        async with client:
            await client.send_file(user_id, image_path, caption=caption)
    except telethon.errors.rpcerrorlist.UserIsBlockedError:
        return False
    finally:
        await client.disconnect()
        os.remove(image_path)
