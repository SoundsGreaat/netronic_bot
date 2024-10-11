import os
from io import BytesIO
from pathlib import Path

import telethon
import tempfile
from cryptography.fernet import Fernet
from telethon import functions
from telethon.sync import TelegramClient

api_id = int(os.environ.get('TELETHON_API_ID'))
api_hash = os.environ.get('TELETHON_API_HASH')
api_id_userbot = int(os.environ.get('TELETHON_API_ID_USERBOT'))
api_hash_userbot = os.environ.get('TELETHON_API_HASH_USERBOT')
token = os.environ.get('NETRONIC_BOT_TOKEN')
fernet_key = os.environ.get('FERNET_KEY')


def decrypt_session(key, input_file, output_file):
    fernet = Fernet(key)
    with open(input_file, 'rb') as file:
        encrypted_session = file.read()
    session = fernet.decrypt(encrypted_session)
    with open(output_file, 'wb') as file:
        file.write(session)


async def proceed_find_user_id(username):
    client = TelegramClient('bot_session', api_id, api_hash)
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
    client = TelegramClient('userbot_session', api_id_userbot, api_hash_userbot)
    await client.start()
    try:
        async with client:
            await client.send_message(user_id, message)
    except telethon.errors.rpcerrorlist.UserIsBlockedError:
        return False
    finally:
        await client.disconnect()


async def send_photo(user_id, image, caption):
    client = TelegramClient('userbot_session', api_id_userbot, api_hash_userbot)
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


async def add_user_to_supergroup(group_id, user_ids):
    client = TelegramClient('userbot_session', api_id_userbot, api_hash_userbot)
    await client.start()
    async with client:
        for user_id in user_ids:
            await client(functions.channels.InviteToChannelRequest(group_id, [user_id]))
        await client.disconnect()


def remove_user_from_chat(bot, chat_id, user_id):
    bot.kick_chat_member(chat_id, user_id)
    bot.unban_chat_member(chat_id, user_id)
