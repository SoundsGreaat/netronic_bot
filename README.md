# Netronic Bot / Telegram Bot

[![Static Badge](https://img.shields.io/badge/MIT-Lisence?style=for-the-badge&logo=github&label=Lisense&color=yellow)](https://github.com/SoundsGreaat/netronic_bot?tab=MIT-1-ov-file)

## Description
The project aims to simplify the process of obtaining employee contacts. Users can quickly find the necessary information using a bot in the messenger, which allows them to effectively organize communication in the organization. It is possible to ask AI for help and get answers to work-related questions.
In addition, the project allows administrators to easily edit contact information to always have up-to-date employee data.
The project was implemented strictly to [**Netronic's**](https://netronic.com.ua/lp) order.

Telegram Bot name: [**@netronic_bot**](https://t.me/netronic_bot)

## Features
### User functionality
- 🔒 **Restricted access**: Only users added to the database can access the bot.
- 🔍 **Employee search**: Search for employees by name, position, or Telegram nickname.
- 📝 **Google Forms integration**: Fill out Google Forms directly from the bot menu.
- 🏆 **View commendations**: Users can view commendation cards created by administrators.
- 🔔 **Credentials reminders**: Provide credentials for work accounts upon user request.
- 🎉 **Birthday reminders**: Notifies users about upcoming employee birthdays.
- 🤖 **AI assistance**: Ask AI for help with work-related questions and document analysis.

### Admin functionality
- 💼 **Add employees**: Add new employees to the database with their details.
- 🖋️ **Edit employee data**: Update existing employee information.
- 🗑️ **Delete employees**: Remove employees from the database when necessary.
- 🕒 **Grant temporary access**: Temporarily allow bot access without adding users to the database.
- 🔗 **Link editing mode**: Modify or delete links in the bot's menu.
- ✅ **Validation checks**: Notify administrators of incorrect phone numbers, Telegram nicknames, or links.
- 🖼️ **Create commendation cards**: Generate commendation cards using the `make_card.py` script.
- 🔄 **CRM integration**: Automatically add or remove employees in the CRM system based on database updates.
- 📊 **Google Sheets export**: Automatically export employee data to Google Sheets for convenience.
- 🎂 **Birthday notifications**: Automatically send birthday reminders to administrators or employees.
- 📝 **Programmatic Google Forms filling**: Use the `google_forms_filler.py` script to fill forms programmatically.
- 📤 **Send messages and photos**: Use the `telethon_functions.py` script to send messages and photos to users.

## Technologies
- **Python 3.12**: Main programming language.
- **Telethon**: Library for interacting with the Telegram Bot API.
- **Telegram Bot API**: Used for user interaction.
- **PostgreSQL**: Database for storing employee data.
- **SQLAlchemy**: Library for database ORM and SQL operations.
- **GForms**: Library for Google Forms integration.
- **OpenAI**: Library for AI-powered assistance.
- **Pillow**: Library for image processing.
- **Cryptography**: Library for encrypting and decrypting session files.
- **RapidFuzz**: Library for fuzzy string matching and similarity calculations.
- **APScheduler**: Library for scheduling tasks.

## Project Structure
```yaml
src/database/:             Database models and session management
src/handlers/:             Telegram bot handlers (commands, callbacks, etc.)
src/integrations/:         Integrations with external services (Google Forms, CRM, etc.)
src/utils/:                Utility scripts (CRM, Google Forms, etc.)
src/config.py:             Configuration, constants, and global variables
src/initialization.py:     Initialization of the bot and database
src/main.py:               Bot entry point
assets/:                   Fonts and image templates for commendation cards
sessions/:                 Encrypted and decrypted session files
```

## Getting Started
1. **Clone the repository**: `git clone https://github.com/SoundsGreaat/netronic_bot.git`
2. **Install the required packages**: `pip install -r requirements.txt`
3. **Generate secret keys**: Create a `.env` file in the root of the project and fill it with the following data:
    ```yaml
   BIRTHDAY_NOTIFICATION_USER_IDS: your_user_ids
   CRM_KEY: admins_ua_crm_key
   CRM_URL: admins_ua_crm_url
   DATABASE_URL: your_database_url
   SCHEDULE_DATABASE_URL: your_schedule_database_url
   FERNET_KEY: your_fernet_key
   GOOGLE_API_CREDENTIALS: your_google_api_credentials
   NETRONIC_BOT_TOKEN: your_bot_token
   OPENAI_API_KEY: your_openai_api_key
   OPENAI_ASSISTANT_ID: your_openai_assistant_id
   TELETHON_API_HASH: your_telethon_api_hash
   TELETHON_API_HASH_USERBOT: your_telethon_api_hash_userbot
   TELETHON_API_ID: your_telethon_api_id
   TELETHON_API_ID_USERBOT: your_telethon_api_id_userbot
    ```
4. **Run the bot**: `python src/main.py`

## Example docker-compose.yml
Bot:
```yaml
  netronic-bot:
    image: netronic-bot:latest
    build:
      context: https://github.com/SoundsGreaat/netronic_bot.git
    container_name: netronic-bot
    restart: always
    depends_on:
      - postgresql
    environment:
      BIRTHDAY_NOTIFICATION_USER_IDS: ${BIRTHDAY_NOTIFICATION_USER_IDS}
      CRM_KEY: ${NETRONIC_CRM_KEY}
      CRM_URL: ${NETRONIC_CRM_URL}
      DATABASE_URL: ${NETRONIC_DATABASE_URL}
      SCHEDULE_DATABASE_URL: ${NETRONIC_SCHEDULE_DATABASE_URL}
      FERNET_KEY: ${NETRONIC_FERNET_KEY}
      GOOGLE_API_CREDENTIALS: ${NETRONIC_GOOGLE_API_CREDENTIALS}
      NETRONIC_BOT_TOKEN: ${NETRONIC_BOT_TOKEN}
      OPENAI_API_KEY: ${NETRONIC_OPENAI_API_KEY}
      OPENAI_ASSISTANT_ID: ${NETRONIC_OPENAI_ASSISTANT_ID}
      TELETHON_API_HASH: ${NETRONIC_TELETHON_API_HASH}
      TELETHON_API_HASH_USERBOT: ${NETRONIC_TELETHON_API_HASH_USERBOT}
      TELETHON_API_ID: ${NETRONIC_TELETHON_API_ID}
      TELETHON_API_ID_USERBOT: ${NETRONIC_TELETHON_API_ID_USERBOT}
    env_file:
      - .env
```

Database:
```yaml
  postgresql:
    image: postgres:latest
    container_name: netronic-postgresql
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - ./postgresql_data:/var/lib/postgresql/data
    env_file:
       - .env
```
