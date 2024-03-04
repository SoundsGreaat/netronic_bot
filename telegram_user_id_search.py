import os

import telethon
from telethon.sync import TelegramClient

api_id = int(os.environ.get('TELETHON_API_ID'))
api_hash = os.environ.get('TELETHON_API_HASH')


async def proceed_find_user_id(username):
    client = TelegramClient('find_user_id', api_id, api_hash)
    try:
        async with client:
            user = await client.get_entity(username)
            user_id = user.id
            return user_id
    except (ValueError, telethon.errors.rpcerrorlist.UsernameInvalidError):
        return None
    finally:
        await client.disconnect()
